"""
agent_signing — Ed25519 signatures para cerrar el hueco de agent_id autodeclarado.

Cadena de confianza:
    1. Agente genera keypair Ed25519 localmente.
    2. Registra pub_key en giskard-marks vía POST /pubkey/register (first-write-wins).
    3. Cada request a un servicio con precio firma payload {agent_id, timestamp, nonce}.
    4. Servicio verifica firma contra pub_key registrada y valida freshness + nonce único.

Sin firma o firma inválida → karma_discount devuelve base_price. Opt-in, no rompe clientes viejos.
"""
import base64
import json
import threading
import time
from typing import Optional

import httpx
from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

MARKS_URL = "http://localhost:8015"
SIGNATURE_TTL_SECONDS = 60
NONCE_CACHE_MAX = 10_000


def build_payload(agent_id: str, timestamp: int, nonce: str) -> bytes:
    """Canonical payload bytes for signing/verification."""
    return json.dumps(
        {"agent_id": agent_id, "timestamp": int(timestamp), "nonce": nonce},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sign_request(signing_key_b64: str, agent_id: str, timestamp: int, nonce: str) -> str:
    """Return base64 signature for the payload. Used by clients."""
    sk = SigningKey(base64.b64decode(signing_key_b64))
    sig = sk.sign(build_payload(agent_id, timestamp, nonce)).signature
    return base64.b64encode(sig).decode("ascii")


def generate_keypair() -> tuple:
    """Return (signing_key_b64, verify_key_b64). Helper for agents bootstrapping."""
    sk = SigningKey.generate()
    return (
        base64.b64encode(bytes(sk)).decode("ascii"),
        base64.b64encode(bytes(sk.verify_key)).decode("ascii"),
    )


class NonceCache:
    """In-memory nonce store with TTL. Thread-safe, bounded size."""

    def __init__(self, ttl: int = SIGNATURE_TTL_SECONDS, max_size: int = NONCE_CACHE_MAX):
        self._ttl = ttl
        self._max_size = max_size
        self._store: dict = {}
        self._lock = threading.Lock()

    def _evict_expired(self, now: float) -> None:
        cutoff = now - self._ttl
        stale = [k for k, t in self._store.items() if t < cutoff]
        for k in stale:
            del self._store[k]

    def check_and_store(self, key: str) -> bool:
        """True if key was fresh and stored. False if already seen (replay)."""
        with self._lock:
            now = time.time()
            if len(self._store) > self._max_size:
                self._evict_expired(now)
                if len(self._store) > self._max_size:
                    self._store.clear()
            if key in self._store:
                return False
            self._store[key] = now
            return True


_nonce_cache = NonceCache()


def _fetch_pubkey(agent_id: str) -> Optional[str]:
    """Return the currently active pub_key for agent_id, or None."""
    try:
        r = httpx.get(f"{MARKS_URL}/pubkey/{agent_id}", timeout=2.0)
        if r.status_code == 200:
            return r.json().get("pub_key")
    except Exception:
        pass
    return None


def _fetch_pubkey_at(agent_id: str, at_ts: int) -> Optional[str]:
    """Return the pub_key that was active at the given Unix timestamp, or None.

    This is what lets historical signatures stay verifiable after a rotation:
    a trail signed with epoch=1 still validates after the agent rotates to epoch=2.
    """
    try:
        r = httpx.get(f"{MARKS_URL}/pubkey/{agent_id}",
                      params={"at_ts": int(at_ts)}, timeout=2.0)
        if r.status_code == 200:
            return r.json().get("pub_key")
    except Exception:
        pass
    return None


def verify_request(
    agent_id: str,
    signature_b64: str,
    timestamp: int,
    nonce: str,
    now: Optional[int] = None,
    pubkey_loader=None,
    nonce_cache: Optional[NonceCache] = None,
) -> bool:
    """Verify Ed25519 signature, freshness, and single-use nonce.

    The pub_key is resolved at request-time (at_ts=timestamp) so historical
    signatures validate against the key that was active when they were produced,
    not against the currently-active one. pubkey_loader and nonce_cache are
    injectable for tests; production uses marks + module cache.
    """
    if not (agent_id and signature_b64 and nonce):
        return False
    try:
        timestamp = int(timestamp)
    except (TypeError, ValueError):
        return False

    current = int(now if now is not None else time.time())
    if abs(current - timestamp) > SIGNATURE_TTL_SECONDS:
        return False

    if pubkey_loader is not None:
        pub_b64 = pubkey_loader(agent_id)
    else:
        pub_b64 = _fetch_pubkey_at(agent_id, timestamp) or _fetch_pubkey(agent_id)
    if not pub_b64:
        return False

    try:
        vk = VerifyKey(base64.b64decode(pub_b64))
        vk.verify(build_payload(agent_id, timestamp, nonce), base64.b64decode(signature_b64))
    except (BadSignatureError, ValueError, TypeError):
        return False

    cache = nonce_cache or _nonce_cache
    return cache.check_and_store(f"{agent_id}:{nonce}")
