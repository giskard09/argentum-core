# Mycelium Trails — Quickstart

Post-execution accountability layer: tamper-evident audit trail for every agent
action, anchored on-chain. Each trail is immutable once written and independently
verifiable from any Arbitrum node without querying this API.

---

## Prerequisites

| What | Value |
|------|-------|
| Base URL | `https://argentum.rgiskard.xyz` |
| Python | 3.8+ |
| Dependencies | `pip install pynacl requests` |
| X-Admin-Key | Required for `POST /trails/anchor`. Request from the Mycelium team. |
| Marks registration | Required for `POST /agent/trail`. One-time setup — see step 1 below. |

> **Recommended:** Register your agent in Marks before deploying to production.
> Marks provides verified agent identity — trails signed with a Marks keypair are
> independently verifiable by any auditor or counterparty without trusting your
> runtime. Agents without Marks registration can still generate trails, but
> identity verification requires a separate mechanism.

---

## 1. Register your agent (one-time)

Generate an Ed25519 keypair and register the public key. The private key never
leaves your process. Registration is first-write-wins per `agent_id`.

```python
import base64
import json
import requests
from nacl.signing import SigningKey

# Generate keypair — store signing_key_b64 securely (treat as a secret)
sk = SigningKey.generate()
signing_key_b64 = base64.b64encode(bytes(sk)).decode("ascii")
pub_key_b64     = base64.b64encode(bytes(sk.verify_key)).decode("ascii")

AGENT_ID = "my-agent-001"   # choose a stable, unique identifier
BASE_URL = "https://argentum.rgiskard.xyz"
MARKS_URL = "https://marks.rgiskard.xyz"  # or use the local port 8015

resp = requests.post(f"{MARKS_URL}/pubkey/register", json={
    "agent_id": AGENT_ID,
    "pub_key":  pub_key_b64,
})
print(resp.json())
# {"status": "registered", "agent_id": "my-agent-001", "epoch": 1}
```

---

## 2. End-to-end example

```python
import base64, datetime, hashlib, json, re, time, uuid
import requests
from nacl.signing import SigningKey

BASE_URL       = "https://argentum.rgiskard.xyz"
AGENT_ID       = "my-agent-001"
SIGNING_KEY_B64 = "<your signing_key_b64 from step 1>"
X_ADMIN_KEY    = "<your X-Admin-Key>"


def sign_request(agent_id: str, timestamp: int, nonce: str) -> str:
    """Ed25519 signature over canonical JSON payload."""
    sk = SigningKey(base64.b64decode(SIGNING_KEY_B64))
    payload = json.dumps(
        {"agent_id": agent_id, "timestamp": timestamp, "nonce": nonce},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return base64.b64encode(sk.sign(payload).signature).decode("ascii")


def format_timestamp(unix_seconds: int) -> str:
    """Unix seconds -> the one accepted timestamp form: YYYY-MM-DDTHH:MM:SS.mmmZ (UTC)."""
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(unix_seconds))


def compute_action_ref(agent_id: str, action_type: str, scope: str, timestamp: str) -> str:
    """action_ref v1 = SHA-256(JCS({agent_id, action_type, scope, timestamp})), RFC 8785.

    `timestamp` is a STRING in the form format_timestamp() returns. Values outside the
    v1 Domain (docs/spec/action-ref.md) are refused, never hashed: ASCII-only
    agent_id/action_type/scope, non-empty scope, a real calendar instant.
    """
    for name, value in (("agent_id", agent_id), ("action_type", action_type), ("scope", scope)):
        if not value.isascii():
            raise ValueError(f"OUT_OF_PROFILE_DOMAIN: {name}: non-ASCII character in field value")
    if not scope:
        raise ValueError("OUT_OF_PROFILE_DOMAIN: scope: must be a non-empty string")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z", timestamp):
        raise ValueError("OUT_OF_PROFILE_DOMAIN: timestamp: expected YYYY-MM-DDTHH:MM:SS.mmmZ")
    try:
        datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        raise ValueError("OUT_OF_PROFILE_DOMAIN: timestamp: not a real calendar instant")
    # For ASCII string members, sorted keys + compact separators is the RFC 8785 form.
    canonical = json.dumps(
        {"agent_id": agent_id, "action_type": action_type, "scope": scope, "timestamp": timestamp},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── Step A: Record a trail ────────────────────────────────────────────────────
# NOTE: POST /agent/trail is not in the current public API. The action_ref derivation
# above (compute_action_ref) is what POST /nexus/trail recomputes; see that endpoint.

timestamp = int(time.time())
nonce     = str(uuid.uuid4())
action    = "payment:usdc:10"
scope     = "my-service"

resp = requests.post(f"{BASE_URL}/agent/trail", json={
    "agent_id":  AGENT_ID,
    "signature": sign_request(AGENT_ID, timestamp, nonce),
    "timestamp": timestamp,
    "nonce":     nonce,
    "state":     f"agent completed {action}",
})
resp.raise_for_status()
trail = resp.json()
trail_id   = trail["trail_id"]
action_ref = compute_action_ref(AGENT_ID, action, scope, format_timestamp(timestamp))
print(f"Trail recorded: {trail_id}")

# ── Step B: Anchor on-chain (Arbitrum) ───────────────────────────────────────
# NOTE: POST /trails/anchor is not in the current public API.

resp = requests.post(
    f"{BASE_URL}/trails/anchor",
    json={"trail_ids": [trail_id], "chain_id": 42161},
    headers={"X-Admin-Key": X_ADMIN_KEY},
)
resp.raise_for_status()
anchor = resp.json()["anchored"][0]
print(f"Anchored: tx={anchor['tx_hash']}  block={anchor['block']}")

# ── Step C: Verify ───────────────────────────────────────────────────────────

resp = requests.get(f"{BASE_URL}/trails/verify", params={
    "agent_id":   AGENT_ID,
    "action_ref": action_ref,
})
result = resp.json()
print(f"verified={result['verified']}  tx={result.get('tx_hash')}")
# verified=True  tx=<arbitrum tx hash>
```

---

## 3. Fields reference

> `POST /agent/trail` and `POST /trails/anchor` are not in the current public API. The two tables below are kept from an earlier revision and are not verified against the current API.

### POST /agent/trail

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `agent_id` | string | Yes | Your registered agent identifier |
| `signature` | string | Yes | Ed25519 over `{agent_id, timestamp, nonce}` — base64 |
| `timestamp` | integer | Yes | Unix epoch seconds. Must be within 60s of server time. |
| `nonce` | string | Yes | Single-use. Replay with the same nonce returns 401. |
| `state` | string | No | Human-readable description of the action. Stored in claims. |
| `payment_hash` | string | No | Lightning payment hash or on-chain tx if the action involved a payment. |

**What breaks if missing:** `agent_id`, `signature`, `timestamp`, `nonce` are all required — the endpoint returns 400 without them. `signature` must match the registered public key; invalid signature returns 401.

### POST /trails/anchor

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `trail_ids` | list[string] | Yes* | One or more trail_ids to anchor |
| `payment_hashes` | list[string] | Yes* | Alternative to trail_ids — resolves by payment_hash |
| `chain_id` | integer | No | `42161` (Arbitrum One, default) or `8453` (Base) |

\* Provide at least one of `trail_ids` or `payment_hashes`.

**Idempotent:** calling anchor twice on the same trail returns the existing tx_hash without writing a new transaction.

**anchor_status in DB:** `pending` → `anchored` on success, `failed` on error. Failed trails are retried automatically every 5 minutes (up to 5 attempts). Telegram alert fires if a trail reaches dead-letter status.

### GET /trails/verify

| Param | Required | Notes |
|-------|----------|-------|
| `agent_id` | Yes (with action_ref) | |
| `action_ref` | Yes (with agent_id) | action_ref v1: SHA-256 of the RFC 8785 JCS of `{agent_id, action_type, scope, timestamp}`, `timestamp` a string `YYYY-MM-DDTHH:MM:SS.mmmZ` (see [action-ref.md](../spec/action-ref.md)) |
| `payment_hash` | Alternative | Can verify without agent_id if you have the payment_hash |

No authentication required. Public endpoint.

---

## 4. Verify your action_ref derivation

Run the conformance suite from the Verifiability Gate to confirm your
canonicalization is byte-identical to the spec:

```
https://gist.github.com/Liuyanfeng1234/82da951b5b94a019468f4ccaf35164ad
```

```bash
# Clone locally and run
python3 verify.py
# Expected: 14/14 PASS (4 CTEF + 10 APS vectors)
```

The conformance suite checks that your RFC 8785 JCS canonicalization produces the
same SHA-256 digest as the reference implementation. If your `action_ref` passes
14/14, it will match what Mycelium stores and what cross-rail verifiers (APS,
SafeAgent, aeoess) expect.

---

## Boundaries

- On `POST /nexus/trail`, `agent_id` is caller-supplied and no signature is checked: a receipt is accepted when its `action_ref` recomputes from the preimage (see [MYCELIUM_TRAILS_REFERENCE.md](../MYCELIUM_TRAILS_REFERENCE.md)).
- Trails are append-only. No update or delete endpoints exist.
- The trail records **what happened** — it does not decide whether it should have happened.
- `anchor_status` is observable via the anchor response. There is no push notification; poll `GET /trails/verify` if you need confirmation of the on-chain anchor.
