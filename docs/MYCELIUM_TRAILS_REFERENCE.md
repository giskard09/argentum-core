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

A trail records one action an agent performed; `success` says whether it completed. These are the
fields of a trail record, as returned by `GET /trails/{trail_id}` and inside `trail` in
`GET /trails/verify`:

| Field | Type | Description |
|---|---|---|
| `trail_id` | string | Unique record identifier (a UUID) |
| `agent_id` | string | Agent identifier (caller-supplied) |
| `service` | string | Service name (e.g. `giskard-oasis`) |
| `operation` | string | Operation performed (e.g. `enter_oasis`) |
| `action_ref` | string \| null | SHA-256 hex content-addressed identifier (see below); `null` on older records |
| `timestamp` | integer | Unix seconds when the trail was recorded |
| `karma_at_time` | integer \| null | Karma of the agent when the trail was recorded, if known |
| `success` | boolean | Whether the action completed successfully |
| `signature_ref` | string | SHA-256 hex of the nonce the trail was recorded with (for `POST /nexus/trail` the nonce is the `action_ref`). A reference derived from the nonce, not a signature over the record. |
| `scope` | string \| null | What the agent was authorized to do (optional, v2) |
| `delegation_ref` | string \| null | Opaque reference (optional, v2). For a trail from `POST /nexus/trail`, the receipt's `payment_hash` is stored here. |
| `parent_trail_id` | string \| null | Trail that spawned this one (v3) |
| `root_trail_id` | string \| null | First trail in the chain (v3) |
| `negotiation_ref` | string \| null | SHA-256 hex pointer to the negotiation artifact that preceded this action (optional, v4). Does not enter the `action_ref` preimage. |
| `negotiation_ref_status` | string \| null | How the issuer recorded obtaining that artifact; see [`spec/negotiation-ref.md`](spec/negotiation-ref.md) |
| `origin` | string \| null | Where the trail came from, e.g. `nexus` (via `POST /nexus/trail`) |
| `tx_hash` | string \| null | Hash of the transaction that anchors the trail on-chain, once anchored |
| `anchor_status` | string \| null | Anchoring state, e.g. `anchored` |
| `anchor_block` | integer \| null | Block number of the anchor transaction |
| `anchor_fail_reason` | string \| null | Reason recorded when anchoring failed |

There is no `payment_hash` or `claims` field on the record. A NEXUS receipt's `payment_hash` is kept in
`delegation_ref`, and `GET /trails/verify?payment_hash=<hash>` looks a trail up by it.

### scope and delegation_ref — v2 optional fields

`scope` describes what the agent was authorized to do, not just what it did. Useful for
compliance adapters (e.g. ATP delegation chain) that need to verify the action fell within
the declared authorization boundary.

`delegation_ref` is an opaque pointer to the delegation chain that originated the action.
Format is caller-defined (URL, content hash, UUID). Mycelium stores it verbatim — the caller is
responsible for making the reference resolvable.

Both fields are `null` when not supplied. Backward-compatible: consumers that do not supply
or read these fields are unaffected.

### action_ref — content-addressed identifier

```python
import hashlib, json

def compute_action_ref(agent_id: str, action_type: str, scope: str, timestamp: str) -> str:
    # action_ref v1: SHA-256 of the RFC 8785 (JCS) serialization of the four fields.
    # `timestamp` is a string, YYYY-MM-DDTHH:MM:SS.mmmZ. For ASCII string members,
    # sorted keys + compact separators is the RFC 8785 form.
    canonical = json.dumps(
        {"agent_id": agent_id, "action_type": action_type, "scope": scope, "timestamp": timestamp},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

This snippet shows the derivation only. The Domain rules (ASCII-only `agent_id`, `action_type` and
`scope`; non-empty `scope`; a real calendar instant in the exact timestamp form) are in
[`spec/action-ref.md`](spec/action-ref.md), and a value outside them is refused rather than hashed.
`POST /nexus/trail` recomputes this value and answers 422 when it does not match.

Any party (APS gateway, asqav compliance layer, the agent itself) can
pre-compute this identifier before the trail is written. The trail links
back to it on Base. This is the canonical linking key across all surfaces.

---

## Verify Endpoint

```
GET https://argentum.rgiskard.xyz/trails/verify?agent_id=X&action_ref=Y
GET https://argentum.rgiskard.xyz/trails/verify?payment_hash=Z
```

No authentication required. No API key.

**Response — trail found (HTTP 200):**
```json
{"verified": true, "trail": { "trail_id": "...", "agent_id": "...", "action_ref": "...", "tx_hash": "...", "...": "other record fields, see Trail Record Schema" }}
```

**Response — not found (HTTP 404):**
```json
{"verified": false}
```

With neither `agent_id` + `action_ref` nor `payment_hash`, the endpoint answers HTTP 422
(`{"detail": "provide action_ref+agent_id or payment_hash"}`).

`trail.tx_hash` is the hash of the transaction that anchors the trail on-chain; it can be looked up
with any RPC node of that chain. Anchors are on Arbitrum One or Base: a live trail's `tx_hash` resolves
on Arbitrum One, and the example below is on Base.

---

## Example: post-action anchor on Base

An anchor transaction on Base (chain id 8453): `0x7fd0a8ededd1feb65ab37b3324218a0386dbf124174cf122bffc40717c057b84`
([Base explorer](https://basescan.org/tx/0x7fd0a8ededd1feb65ab37b3324218a0386dbf124174cf122bffc40717c057b84)).

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
   → the permit's payment_hash can be carried in delegation_ref and looked up with
     GET /trails/verify?payment_hash=<hash>
```

---

## Boundaries

- Not a security guarantee
- Not an official integration with Sentinel, x402, AgentKit, or Stripe
- The trail records what happened — it does not decide whether it should have happened
- On `POST /nexus/trail`, agent_id is caller-supplied and no signature is checked: a receipt is accepted when its `action_ref` recomputes from the preimage

---

Source: https://github.com/giskard09/argentum-core

---

## Timestamp representation — what is hashed and what is stored

A trail carries its time in two forms. They are not interchangeable.

| Where | Form | Notes |
|-------|------|-------|
| `timestamp` column of the trails DB and the `timestamp` field of trail responses | Unix epoch seconds, integer | The time the trail was recorded, kept as an integer. It is not a member of the preimage, so `action_ref` does not hash it. |
| `timestamp` member of the action_ref preimage (`anchor_proof.preimage`, `preimage_json`) | RFC 3339 string, UTC, three fractional digits, e.g. `"2026-05-13T10:00:00.123Z"` | The form `action_ref` v1 hashes. |
| `anchored_at` in AnchorReceipt; AGT EvidenceAnchor proposal (PR #2244) | RFC 3339 string, same form | API / crosswalk layer. |

`action_ref` is computed over the preimage with the RFC 3339 string:

```
action_ref = SHA-256( JCS( {agent_id, action_type, scope, timestamp} ) )
```

External callers that pre-generate an `action_ref` must therefore convert a Unix time to the RFC 3339 form
before hashing; hashing the integer, or a different spelling of the same instant, gives a different value.
For a trail that stored its preimage, `GET /trails/{trail_id}` returns it under `anchor_proof.preimage`, with `action_ref_verified`, so a third party can recompute the value.
Trail responses do not carry a `timestamp_ms` field.

`POST /nexus/trail` additionally accepts, for the NEXUS wire format (packet_version 1.0), a Unix
epoch-millisecond value written as a string; it is hashed as given and is not the canonical form.

---

## Trail Graphs — Multi-Agent Chaining (v3)

When an agent delegates to another agent, each step in the chain writes its own trail.
`parent_trail_id` and `root_trail_id` link them into a verifiable DAG.

### New fields in v3

| Field | Type | Description |
|---|---|---|
| `parent_trail_id` | UUID \| null | Trail that spawned this one. `null` if this is the chain root. |
| `root_trail_id` | UUID \| null | First trail in the chain. `null` if this trail is itself the root. |
| `negotiation_ref` | string \| null | SHA-256 hex pointer to the negotiation artifact (agreement, covenant, capability-grant) that preceded this action. Stored verbatim — Mycelium does not parse or validate the referenced document. `null` when not supplied. Does not enter the `action_ref` preimage. |

Both fields are `null` when not supplied. Backward-compatible: v2 consumers are unaffected.

**Relationship to existing fields:**
- `delegation_ref` remains the opaque pointer to the external delegation credential (JWT, hash, URL).
- `parent_trail_id` is the internal Mycelium link — it points to another trail record, not an external credential.
- A trail can have both: `delegation_ref` = the credential that authorized the delegation, `parent_trail_id` = the trail where the delegating agent acted.

### Example — three-agent chain

```
trail_id: A  (root)          agent: orchestrator
  └─ trail_id: B             agent: researcher   parent_trail_id: A, root_trail_id: A
       └─ trail_id: C        agent: writer       parent_trail_id: B, root_trail_id: A
```

### Graph endpoint

```
GET https://argentum-api.rgiskard.xyz/mycelium/trails/{trail_id}/graph
```

Returns the DAG that contains the given trail: it walks up through `parent_trail_id` to the root, then down
through all descendants. HTTP 404 `{"detail": "trail not found"}` when the trail does not exist.

**Response:**
```json
{
  "root": {
    "trail_id": "A",
    "agent_id": "orchestrator",
    "karma_at_time": null,
    "attestation_count": 0,
    "parent_trail_id": null,
    "children": [
      {
        "trail_id": "B",
        "agent_id": "researcher",
        "karma_at_time": null,
        "attestation_count": 0,
        "parent_trail_id": "A",
        "children": []
      }
    ]
  }
}
```

`attestation_count` is a placeholder and is always `0`.

### Chain verification endpoint

```
GET https://argentum-api.rgiskard.xyz/mycelium/trails/{trail_id}/verify_chain
```

Walks from the given trail up through `parent_trail_id` to the root and checks, at each trail:
1. the trail exists;
2. `signature_ref` is present (non-empty). **The endpoint does not verify a cryptographic signature**:
   `signature_ref` is derived from the nonce (see Trail Record Schema), and only its presence is checked;
3. when both `parent_trail_id` and `delegation_ref` are set, `delegation_ref` contains the `parent_trail_id`;
4. the walk does not revisit a trail (cycle).

The first check that fails ends the walk.

**Response — valid chain:**
```json
{"valid": true, "broken_at": null, "reason": null, "negotiation_linkage": "absent", "negotiation_ref_status": null}
```

**Response — broken chain:**
```json
{"valid": false, "broken_at": "<trail_id>", "reason": "missing_signature_ref", "negotiation_linkage": "absent", "negotiation_ref_status": null}
```

`reason` is one of `trail_not_found`, `missing_signature_ref`, `delegation_ref_parent_mismatch`,
`cycle_detected`. `negotiation_linkage` describes the trail named in the request:
`absent`, `present` (a `negotiation_ref` is set; the referenced artifact is not validated), `malformed`
(set but empty), or `null` when that trail could not be read.
