# Mycelium Trails — Post-Execution Accountability Reference

This document describes the Mycelium Trails post-execution layer for builders
who want to close the accountability loop after an agent acts.

Composability pattern:

```
pre-check (Sentinel Alpha / BeezShield)
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
| `scope` | string \| null | What the agent was authorized to do (optional, v2) |
| `delegation_ref` | string \| null | Opaque reference to the delegation chain that originated this action (optional, v2) |

### scope and delegation_ref — v2 optional fields

`scope` describes what the agent was authorized to do, not just what it did. Useful for
compliance adapters (e.g. ATP delegation chain) that need to verify the action fell within
the declared authorization boundary.

`delegation_ref` is an opaque pointer to the delegation chain that originated the action.
Format is caller-defined (URL, content hash, UUID). Mycelium stores it verbatim and indexes
nothing — the caller is responsible for making the reference resolvable.

Both fields are `null` when not supplied. Backward-compatible: consumers that do not supply
or read these fields are unaffected.

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

---

## Timestamp representation — wire vs. API layers

`action_ref` derivation involves a timestamp field that has three distinct representations depending on the layer. These are not inconsistencies — they are intentional boundaries between the internal wire format and external interoperability specs.

| Layer | Format | Where used |
|-------|--------|-----------|
| **Wire (internal)** | Unix epoch seconds, integer | `timestamp` column in trails DB, `compute_action_ref()` input, `record_trail()` |
| **Cross-rail** | `timestamp_ms = timestamp × 1000`, int64 big-endian | Published in `preimage.timestamp_ms` on each TrailRecord response; used by cross-rail integrations (SafeAgent, APS) |
| **API / crosswalk** | RFC 3339 string, UTC, 3-digit ms — e.g. `"2026-05-13T10:00:00.123Z"` | `anchored_at` field in AnchorReceipt; AGT EvidenceAnchor proposal (PR #2244); aeoess crosswalk YAML |

The `action_ref` hash is always computed over the **wire format** (Unix seconds integer):

```
action_ref = SHA-256("{agent_id}:{action_type}:{scope}:{timestamp_seconds}")
```

External callers that need to pre-generate the same `action_ref` should use the integer seconds value, not milliseconds and not RFC 3339. The `preimage.timestamp_ms` field in the API response is provided for cross-rail linking, not for hash recomputation.

This design keeps the internal hash function simple and stable, while allowing external systems to express the same timestamp in their preferred format without creating hash divergence.
