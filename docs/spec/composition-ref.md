# composition-ref-v1 — Specification

**Stable tag:** `composition-ref-v1.0`  
**Status:** stable  
**Canonical fixture:** [`examples/conformance/composition-ref-v1.fixture.json`](../../examples/conformance/composition-ref-v1.fixture.json)

---

## What is composition-ref

`composition_ref` is a SHA-256 hex pointer to a composition artifact — a structured document that records how `delegation_ref`, `revocation_ref`, and the dual-timestamps (`authority_verified_at_ms`, `revocation_check_at_ms`) operate as a single verifiable end-to-end authorization lifecycle for one agent action.

**What it enables:** a Mycelium verifier can, from a single hash, reconstruct and verify the complete authorization chain for an action: who authorized it, when the authorization was confirmed valid, when revocation was last checked before execution, whether a subsequent revocation exists, and the action itself. Without `composition_ref`, these four primitives are independently verifiable but compositionally opaque — a verifier must discover and join them manually.

**What it does not do:** `composition_ref` does not replace `delegation_ref` or `revocation_ref` in the trail envelope. It is an additional pointer carried at the envelope level. The underlying artifacts remain independently verifiable; `composition_ref` is the tamper-evident record that they were composed as a system.

---

## Derivation

`composition_ref` is `SHA-256(JCS(composition_artifact))` where:

- **JCS** is RFC 8785 canonical JSON: `json.dumps(obj, separators=(',',':'), sort_keys=True, ensure_ascii=False)`
- **SHA-256** lowercase hex
- `composition_artifact` must contain at minimum: `action_ref`, `authority_verified_at_ms`, `composition_key`, `delegation_ref`, `revocation_check_at_ms`, `revocation_ref`, `scope`, `version`

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

composition_artifact = {
    "action_ref":               "584bc79bb11ce3af5058b3da84d03f85e4aa464a175bd4f913aeb82a22cef60f",
    "authority_verified_at_ms":  1748087390000,
    "composition_key":           "comp_7a2f9c3b1d4e",
    "delegation_ref":            "69e672d1ba7484e3620d4d4ed9b366c4d4c8b203c4176f60f000e2b793761ffb",
    "revocation_check_at_ms":    1748087395000,
    "revocation_ref":            "50cb4f3d564763cd11dde45950ef8298e92f468070a27f125dfd658d45d5eca5",
    "scope":                     "mycelium:payment",
    "version":                   "composition-ref-v1",
}
composition_ref = hashlib.sha256(jcs(composition_artifact).encode()).hexdigest()
# 234f0664ee1912cf210824112598639aca00edcf734221016cc04bb3da158e2a
```

---

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `action_ref` | SHA-256 hex | The `action_ref` of the trail record being described. Derived from the four preimage fields per [`action-ref.md`](./action-ref.md). |
| `authority_verified_at_ms` | integer (Unix ms) | Timestamp when the emitter confirmed the delegation was valid, before executing the action. Must be ≤ action timestamp. |
| `composition_key` | string | Client-generated unique identifier. Ensures uniqueness of the artifact when the same action is composed multiple times (e.g. with different revocation states). |
| `delegation_ref` | SHA-256 hex | Hash of the delegation artifact that authorized this action. Derived per [`delegation-ref.md`](./delegation-ref.md). |
| `revocation_check_at_ms` | integer (Unix ms) | Timestamp of the most recent successful non-revocation check before execution. Must be ≤ action timestamp. |
| `revocation_ref` | SHA-256 hex or `null` | Hash of the revocation artifact, if the delegation was subsequently revoked. `null` if no revocation has occurred. |
| `scope` | string | Must match the `scope` in both the action preimage and the delegation artifact. |
| `version` | string | Always `"composition-ref-v1"` for this spec version. |
| `key_source` | string (optional) | Resolution method used to obtain the signing key at verification time. One of `"inline"`, `"cache"`, `"resolver"`. Omit if unknown or not applicable. |

---

## The dual-timestamp window

`authority_verified_at_ms` and `revocation_check_at_ms` together define the authorization window:

```
authority_verified_at_ms ≤ revocation_check_at_ms ≤ action_timestamp
```

A verifier who holds the composition artifact can establish:

1. The delegation was confirmed valid no later than `authority_verified_at_ms`.
2. No revocation existed as of `revocation_check_at_ms`.
3. The action executed at the timestamp encoded in `action_ref`'s preimage.
4. If `revocation_ref` is non-null, the delegation was revoked after execution — the action was valid when taken.

This closes the audit gap that exists when each primitive is verified independently.

---

## Invariants

**1. envelope-only — does not enter action_ref preimage**

`composition_ref` is carried in the trail envelope. It never enters the four-field preimage (`action_type`, `agent_id`, `scope`, `timestamp`). Changing or removing `composition_ref` does not change `action_ref`.

**2. composition_ref does not replace its constituents**

The underlying `delegation_ref` and `revocation_ref` remain present in the trail envelope. `composition_ref` is an additional, composing pointer — not a replacement. A verifier who only holds `composition_ref` must still resolve the delegation and revocation artifacts to verify them independently.

**3. revocation_ref may be null at composition time**

A composition artifact may be created before any revocation occurs. In that case `revocation_ref` is the JSON literal `null`. If a revocation occurs later, a new composition artifact is created with `revocation_ref` populated — the original artifact is not mutated.

**4. scope must match across all constituents**

The `scope` in the composition artifact must match: (a) the `scope` in the action preimage, (b) the `scope` in the delegation artifact, and (c) the `scope` in the revocation artifact if present. A mismatch indicates a cross-scope composition error.

**5. composition_key scopes uniqueness**

The `composition_key` is client-generated. Without it, recomposing the same action_ref + delegation_ref with a later `revocation_ref` would not be distinguishable as a distinct composition event.

**6. key_source is part of the signed artifact when present**

`key_source` enters the JCS field set and therefore changes the `composition_ref` hash. A composition artifact with `key_source: "inline"` and one without `key_source` produce different `composition_ref` values — they are distinct artifacts. Verifiers must not strip `key_source` before recomputing the hash.

---

## key_source extension

`key_source` records the resolution method used to obtain the signing key when the composition artifact was verified. It is optional — omit it if the resolution method is unknown or irrelevant.

| Value | Meaning |
|-------|---------|
| `"inline"` | Key was present in the artifact itself (e.g. `did:key`, `did:aps`). No resolver on the hot path. SSRF class eliminated by construction. |
| `"cache"` | Key was retrieved from a local or in-process cache. Resolution occurred before the hot path; a stale-key window exists between cache population and use. |
| `"resolver"` | Key was fetched from a remote resolver at verification time. An allowlist profile is required to constrain the resolver endpoint; `key_source` in the signed artifact makes the resolution method auditable across the record's lifetime. |

When `key_source = "inline"` the self-certifying path holds end-to-end: the verifier needs no network access and the artifact is fully self-describing. For `"cache"` and `"resolver"`, the audit trail produced by `composition_ref` makes the trust posture explicit — the same `action_ref` with a different `key_source` represents a meaningfully different verification claim.

---

## Position in the envelope

```json
{
  "packet_version":            "1.0",
  "action_ref":                "<sha256 hex — derived from preimage>",
  "delegation_ref":            "<sha256 hex — derived from delegation_artifact>",
  "revocation_ref":            "<sha256 hex — derived from revocation_artifact, or null>",
  "composition_ref":           "<sha256 hex — derived from composition_artifact>",
  "hash_algo":                 "sha256",
  "preimage_format":           "jcs-rfc8785-v1",
  "preimage": {
    "action_type": "payment.send",
    "agent_id":    "pioneer-agent-001",
    "scope":       "mycelium:payment",
    "timestamp":   "2026-05-24T10:30:00.000Z"
  }
}
```

---

## Cross-references

- `action_ref` derivation + dual-timestamps: [`docs/spec/action-ref.md`](./action-ref.md)
- `delegation_ref`: [`docs/spec/delegation-ref.md`](./delegation-ref.md)
- `revocation_ref`: [`docs/spec/revocation-ref.md`](./revocation-ref.md)
- `idempotency_ref`: [`docs/spec/idempotency-ref.md`](./idempotency-ref.md)
- `negotiation_ref`: [`docs/spec/negotiation-ref.md`](./negotiation-ref.md)
- TrailRecord schema: [`docs/MYCELIUM_TRAILS_REFERENCE.md`](../MYCELIUM_TRAILS_REFERENCE.md)
