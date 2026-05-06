# Mycelium Trails — Post-Execution Accountability Reference

This document describes the Mycelium Trails post-execution layer for builders
who want to close the accountability loop after an agent acts.

Composability pattern:

```
pre-check (Sentinel / AgentShield)
  → payment authorization (x402 / Lightning)
  → agent execution (AgentKit / AutoGen / any framework)
  → post-action trail (Mycelium Trails) ← this document
```

No coupling between layers. Each surface is independently queryable.

---

## Trail Record Schema

A trail is written when an agent successfully completes a paid action.

| Field | Type | Description |
|---|---|---|
| `trail_id` | UUID | Unique record identifier |
| `agent_id` | string | Agent identifier (caller-supplied, not authenticated) |
| `service` | string | Service name (e.g. `giskard-oasis`) |
| `operation` | string | Operation performed (e.g. `enter_oasis`) |
| `action_ref` | string | SHA-256 content-addressed identifier (see below) |
| `payment_hash` | string | Lightning payment hash or on-chain tx hash |
| `timestamp` | integer | Unix timestamp of the action |
| `signature_ref` | string | Ed25519 signature reference over canonical record |
| `claims` | object | Runtime metadata attached at write time (see below) |
| `success` | boolean | Whether the action completed successfully |

### action_ref — content-addressed identifier

```python
import hashlib

def compute_action_ref(agent_id: str, action_type: str, scope: str, timestamp: int) -> str:
    payload = f"{agent_id}:{action_type}:{scope}:{int(timestamp)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

Any party (APS gateway, asqav compliance layer, the agent itself) can
pre-compute this identifier before the trail is written. The trail links
back to it on Base. This is the canonical linking key across all surfaces.

### claims object

```json
{
  "runtime": "lightning",
  "wallet": "phoenixd",
  "contract": null,
  "payment_method": "lightning",
  "mocked": false,
  "impossible_effects": false
}
```

Claims are attached at write time and are not modifiable after the fact.

---

## Verify Endpoint

```
GET https://argentum.rgiskard.xyz/trails/verify?agent_id=X&action_ref=Y
```

No authentication required. No API key.

**Response — trail found:**
```json
{
  "verified": true,
  "trail_id": "ea145ca5-e9ac-4900-b583-a2e1bea61140",
  "tx_hash": "7fd0a8ededd1feb65ab37b3324218a0386dbf124174cf122bffc40717c057b84",
  "timestamp": "2026-04-13T02:47:35+00:00",
  "service": "giskard-oasis",
  "operation": "enter_oasis"
}
```

**Response — not found:**
```json
{"verified": false, "block": null, "tx_hash": null, "timestamp": null}
```

The `tx_hash` is the Base mainnet transaction hash or Lightning payment hash
that anchors the trail. A verifier can replay from any Base RPC node without
querying our API.

---

## Example: post-action anchor on Base

Trail from a real agent payment (pioneer-agent-001, 2026-04-13):

- **agent_id:** `pioneer-agent-001`
- **service:** `giskard-oasis`
- **payment:** 20 sats via Lightning
- **bridge tx:** `0x7fd0a8ededd1feb65ab37b3324218a0386dbf124174cf122bffc40717c057b84`
- **Base explorer:** https://basescan.org/tx/0x7fd0a8ededd1feb65ab37b3324218a0386dbf124174cf122bffc40717c057b84

Live trail viewer: https://argentum.rgiskard.xyz/trails/demo

---

## Full composability pattern with Sentinel + x402

```
1. Agent prepares an onchain action
2. Sentinel evaluates: allow / review / block
   → decision shape: {risk_level, recommended_action, rationale}
3. x402 handles payment authorization
   → permit receipt with action_ref as linking key
4. AgentKit / framework executes the action
5. Mycelium Trails writes the post-action record
   → trail anchored on Base with payment_hash cross-referencing the permit
6. Any verifier replays from Base and recovers the full chain
   → permit (APS-signed) → revocation/re-issue (asqav) → trail (Mycelium)
```

No single point of trust. Each surface is independently verifiable.

---

## Boundaries

- Not a security guarantee
- Not an official integration with Sentinel, x402, AgentKit, or Stripe
- The trail records what happened — it does not decide whether it should have happened
- agent_id is caller-supplied; Mycelium does not authenticate the caller

---

## SDK

```python
# pip install argentum-sdk
from argentum.trails import compute_action_ref, verify_trail

ref = compute_action_ref(
    agent_id="my-agent-001",
    action_type="enter_oasis",
    scope="giskard-oasis",
    timestamp=1746500000
)

result = verify_trail(agent_id="my-agent-001", action_ref=ref)
# {"verified": True/False, "tx_hash": "...", "timestamp": "..."}
```

Source: https://github.com/giskard09/argentum-core
