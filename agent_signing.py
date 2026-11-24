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
import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from typing import Optional

import httpx
from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from jcs import jcs_bytes

_log = logging.getLogger("agent_signing")

MARKS_URL = "http://localhost:8015"
# A signature may be this old (seconds) and still verify...
SIGNATURE_TTL_SECONDS = 60
# ...but may only be this far in the future. The old rule was symmetric (60 s), which gave a
# future-dated signature a 120 s life. Small skew tolerance only; override per host if needed.
SIGNATURE_FUTURE_TOLERANCE_SECONDS = int(os.environ.get("AGENT_SIGNING_FUTURE_TOLERANCE", "10"))
NONCE_CACHE_MAX = 100_000        # rows kept at once; when full, new signatures are REFUSED, never cleared
NONCE_PER_AGENT_MAX = 1_000      # rows one agent_id may hold, so one key cannot fill the table
MAX_NONCE_LEN = 128
MAX_AGENT_ID_LEN = 256


def build_payload(agent_id: str, timestamp: int, nonce: str) -> bytes:
    """Canonical payload bytes for signing/verification."""
    return jcs_bytes({"agent_id": agent_id, "timestamp": int(timestamp), "nonce": nonce})


def sign_request(signing_key_b64: str, agent_id: str, timestamp: int, nonce: str) -> str:
    """Return base64 signature for the payload. Used by clients."""
    sk = SigningKey(base64.b64decode(signing_key_b64))
    sig = sk.sign(build_payload(agent_id, timestamp, nonce)).signature
    return base64.b64encode(sig).decode("ascii")


# ---- v2 (opt-in, additive): the signature also names WHO it is for and WHAT it asks for ----------
SIG_V2 = 2
# Fields that carry the signature itself; they are not part of the body that gets hashed.
SIGNATURE_FIELDS = ("signature", "timestamp", "nonce", "sig_v")


def body_sha256(body: dict) -> str:
    """SHA-256 (hex) of the JCS of the request's JSON body without the signature fields.
    Client and server both compute it over the JSON object that was sent."""
    stripped = {k: v for k, v in body.items() if k not in SIGNATURE_FIELDS}
    return hashlib.sha256(jcs_bytes(stripped)).hexdigest()


def build_payload_v2(agent_id: str, timestamp: int, nonce: str, aud: str, method: str, path: str,
                     body_sha256_hex: str) -> bytes:
    """Canonical bytes for a v2 signature. `aud` is the service, `path` the URL path (no query)."""
    return jcs_bytes({
        "agent_id": agent_id, "aud": aud, "body_sha256": body_sha256_hex, "method": method.upper(),
        "nonce": nonce, "path": path, "sig_v": SIG_V2, "timestamp": int(timestamp),
    })


def sign_request_v2(signing_key_b64: str, agent_id: str, timestamp: int, nonce: str, aud: str,
                    method: str, path: str, body_sha256_hex: str) -> str:
    sk = SigningKey(base64.b64decode(signing_key_b64))
    sig = sk.sign(build_payload_v2(agent_id, timestamp, nonce, aud, method, path, body_sha256_hex)).signature
    return base64.b64encode(sig).decode("ascii")


def generate_keypair() -> tuple:
    """Return (signing_key_b64, verify_key_b64). Helper for agents bootstrapping."""
    sk = SigningKey.generate()
    return (
        base64.b64encode(bytes(sk)).decode("ascii"),
        base64.b64encode(bytes(sk.verify_key)).decode("ascii"),
    )


def _default_nonce_db_path() -> str:
    """Where the module-level cache lives. Persisting it lets consumed nonces survive a restart
    (the old in-memory cache was empty after one, reopening every signature still in its window).
    AGENT_SIGNING_NONCE_DB overrides it; ':memory:' keeps the old per-process behaviour."""
    env = os.environ.get("AGENT_SIGNING_NONCE_DB")
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), ".agent_signing_nonces.db")


def _nonce_key(agent_id: str, nonce: str) -> str:
    """Unambiguous cache key: ('a', 'b:c') and ('a:b', 'c') must not collide."""
    return json.dumps([agent_id, nonce], separators=(",", ":"), ensure_ascii=True)


class NonceCache:
    """Single-use nonce store on SQLite, with expiry. Thread-safe and safe across processes that
    share the file (the insert is atomic). Default (db_path=None) is in memory, for tests/injection.

    Entries live until the signature they came from can no longer verify (`expires_at`), and are
    purged by time on every call. When full the cache REFUSES (fail closed); it never clears.
    """

    def __init__(self, ttl: int = SIGNATURE_TTL_SECONDS, max_size: int = NONCE_CACHE_MAX,
                 db_path: Optional[str] = None, per_agent_max: int = NONCE_PER_AGENT_MAX):
        self._ttl = ttl
        self._max_size = max_size
        self._per_agent_max = per_agent_max
        self._lock = threading.Lock()
        self._conn = self._open(db_path or ":memory:")

    @staticmethod
    def _open(path: str):
        try:
            conn = sqlite3.connect(path, check_same_thread=False, timeout=5.0, isolation_level=None)
            conn.execute("PRAGMA journal_mode=WAL") if path != ":memory:" else None
            conn.execute("CREATE TABLE IF NOT EXISTS nonces (k TEXT PRIMARY KEY, agent TEXT, expires_at REAL NOT NULL)")
            conn.execute("CREATE INDEX IF NOT EXISTS nonces_exp ON nonces (expires_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS nonces_agent ON nonces (agent)")
            return conn
        except sqlite3.Error as e:
            _log.error("nonce store %r unavailable (%s); falling back to memory for this process", path, e)
            conn = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
            conn.execute("CREATE TABLE nonces (k TEXT PRIMARY KEY, agent TEXT, expires_at REAL NOT NULL)")
            conn.execute("CREATE INDEX nonces_exp ON nonces (expires_at)")
            conn.execute("CREATE INDEX nonces_agent ON nonces (agent)")
            return conn

    def check_and_store(self, key: str, expires_at: Optional[float] = None, agent: Optional[str] = None) -> bool:
        """True if the key was fresh and is now stored. False if already seen (replay), the cache
        is full, the agent is over its quota, or the store failed (fail closed)."""
        now = time.time()
        exp = float(expires_at) if expires_at is not None else now + self._ttl
        k = hashlib.sha256(key.encode("utf-8")).hexdigest()
        with self._lock:
            try:
                c = self._conn
                c.execute("DELETE FROM nonces WHERE expires_at < ?", (now,))
                if c.execute("SELECT COUNT(*) FROM nonces").fetchone()[0] >= self._max_size:
                    return False
                if agent is not None and c.execute(
                        "SELECT COUNT(*) FROM nonces WHERE agent = ?", (agent,)).fetchone()[0] >= self._per_agent_max:
                    return False
                cur = c.execute("INSERT OR IGNORE INTO nonces (k, agent, expires_at) VALUES (?, ?, ?)", (k, agent, exp))
                return cur.rowcount == 1
            except sqlite3.Error as e:
                _log.error("nonce store error (%s); refusing the signature", e)
                return False


_nonce_cache = NonceCache(db_path=_default_nonce_db_path())


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
    *,
    sig_v: Optional[int] = None,
    aud: Optional[str] = None,
    method: Optional[str] = None,
    path: Optional[str] = None,
    body_sha256_hex: Optional[str] = None,
) -> bool:
    """Verify Ed25519 signature, freshness, and single-use nonce.

    Default is the v1 payload {agent_id, timestamp, nonce}. With sig_v=2 the signature must
    cover aud, method, path and body_sha256 as well, and all four must be supplied by the
    caller (the server states what it expects; nothing is taken from the client). v2 never
    falls back to v1.

    The pub_key is resolved at request-time (at_ts=timestamp) so historical
    signatures validate against the key that was active when they were produced,
    not against the currently-active one. pubkey_loader and nonce_cache are
    injectable for tests; production uses marks + module cache.
    """
    if not (agent_id and signature_b64 and nonce):
        return False
    if not isinstance(agent_id, str) or not isinstance(nonce, str):
        return False
    if len(nonce) > MAX_NONCE_LEN or len(agent_id) > MAX_AGENT_ID_LEN:
        return False
    try:
        timestamp = int(timestamp)
    except (TypeError, ValueError):
        return False

    current = int(now if now is not None else time.time())
    age = current - timestamp            # > 0: signed in the past; < 0: dated in the future
    if age > SIGNATURE_TTL_SECONDS or -age > SIGNATURE_FUTURE_TOLERANCE_SECONDS:
        return False

    if pubkey_loader is not None:
        pub_b64 = pubkey_loader(agent_id)
    else:
        pub_b64 = _fetch_pubkey_at(agent_id, timestamp) or _fetch_pubkey(agent_id)
    if not pub_b64:
        return False

    try:
        vk = VerifyKey(base64.b64decode(pub_b64))
        if sig_v == SIG_V2:
            if not (aud and method and path and body_sha256_hex):
                return False
            payload = build_payload_v2(agent_id, timestamp, nonce, aud, method, path, body_sha256_hex)
        elif sig_v in (None, 1):
            payload = build_payload(agent_id, timestamp, nonce)
        else:
            return False
        vk.verify(payload, base64.b64decode(signature_b64))
    except (BadSignatureError, ValueError, TypeError):
        return False

    cache = nonce_cache if nonce_cache is not None else _nonce_cache
    # Keep the nonce until this signature can no longer verify (ts + TTL, plus a margin for the
    # int() truncation of `now`), not for a fixed time after it was first seen.
    return cache.check_and_store(_nonce_key(agent_id, nonce),
                                 expires_at=timestamp + SIGNATURE_TTL_SECONDS + 2, agent=agent_id)
