# delegation-ref-v1 — Specification

**Stable tag:** `delegation-ref-v1.0`  
**Status:** stable  
**Canonical fixture:** [`examples/conformance/delegation-ref-v1.fixture.json`](../../examples/conformance/delegation-ref-v1.fixture.json)

---

## What is delegation-ref

`delegation_ref` is a SHA-256 hex pointer to a delegation artifact — a structured document that records the authorization chain: who authorized whom, to do what, within what scope, under which policy version, and until when.

**What it enables:** a Mycelium verifier can establish that a delegated action was explicitly authorized before it was admitted. Without `delegation_ref`, a trail record proves only that an agent performed an action — not that it was permitted to do so. With `delegation_ref`, the record carries a tamper-evident pointer to the authorization that preceded it.

**What it does not do:** `delegation_ref` does not prove the delegation artifact is still valid at verification time. For post-authorization invalidation, see [`revocation-ref.md`](./revocation-ref.md). For the timestamps that bound the authority check window, see `authority_verified_at_ms` in [`action-ref.md`](./action-ref.md).

---

## Derivation

`delegation_ref` is `SHA-256(JCS(delegation_artifact))` where:

- **JCS** is RFC 8785 canonical JSON: object keys sorted recursively by UTF-16 code units (§3.2.3), no whitespace, literal UTF-8 — **not** `json.dumps(sort_keys=True)`, which sorts by code point and diverges for keys outside the BMP. Reference implementation: [`jcs.py`](../../jcs.py)
- **SHA-256** lowercase hex
- `delegation_artifact` must contain at minimum: `delegator`, `delegatee`, `capability`, `scope`, `expires_at`, `policy_version`, `version`

```python
import hashlib, json

def jcs(obj):
    # RFC 8785 §3.2.3: object keys sorted recursively by UTF-16 code units.
    # Not json.dumps(sort_keys=True): that sorts by code point and diverges
    # from RFC 8785 for keys outside the BMP. Floats additionally need
    # ECMA-262 Number::toString formatting -- see jcs.py.
    def canon(o):
        if isinstance(o, dict):
            return {k: canon(o[k]) for k in sorted(o, key=lambda k: k.encode("utf-16-be", "surrogatepass"))}
        if isinstance(o, list):
            return [canon(v) for v in o]
        return o
    return json.dumps(canon(obj), separators=(',', ':'), ensure_ascii=False)

delegation_artifact = {
    "capability":     "payment.send",
    "delegatee":      "pioneer-agent-001",
    "delegator":      "giskard-self",
    "expires_at":     "2026-05-27T00:00:00.000Z",
    "policy_version": "2026-05-01",
    "scope":          "mycelium:payment",
    "version":        "delegation-ref-v1",
}
delegation_ref = hashlib.sha256(jcs(delegation_artifact).encode()).hexdigest()
# 69e672d1ba7484e3620d4d4ed9b366c4d4c8b203c4176f60f000e2b793761ffb
```

---

## Invariants

**1. envelope-only — does not enter action_ref preimage**

`delegation_ref` is carried in the trail envelope. It never enters the four-field preimage (`action_type`, `agent_id`, `scope`, `timestamp`). Changing or removing `delegation_ref` does not change `action_ref`.

**2. artifact commits to the full authorization chain**

The delegation artifact should include both `delegator` (the human or agent that granted) and `delegatee` (the agent that received). Multi-hop chains (human → orchestrator → leaf agent) should be represented as separate linked delegation artifacts, each with its own `delegation_ref`.

**3. scope must match**

A conformant implementation SHOULD verify that the `scope` in the delegation artifact matches the `scope` in the action preimage. A mismatch means the delegation was for a different authorization boundary than the action claimed.

**4. expires_at is informational**

The `expires_at` field is part of the artifact and enters the hash. It does not expire the `delegation_ref` itself — it is the integrator's responsibility to check currency. A `delegation_ref` pointing to an expired artifact is not invalid; it is a pointer to an artifact that is no longer in force.

**5. opaque artifact format beyond required fields**

The delegation artifact schema is implementer-defined beyond the required fields. Additional fields (e.g. `conditions`, `max_amount`, `audit_trail_id`) are permitted and enter the hash.

---

## Relationship to other refs

| Ref | What it answers |
|-----|----------------|
| `delegation_ref` | Who authorized this action, under what policy? |
| `revocation_ref` | Has a prior authorization been invalidated? |
| `idempotency_ref` | Is this a duplicate of a prior submission? |
| `negotiation_ref` | Was there a prior agreement (capability-grant, covenant)? |

---

## Position in the envelope

```json
{
  "packet_version":  "1.0",
  "action_ref":      "<sha256 hex — derived from preimage>",
  "delegation_ref":  "<sha256 hex — derived from delegation_artifact>",
  "hash_algo":       "sha256",
  "preimage_format": "jcs-rfc8785-v1",
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

- `action_ref` derivation: [`docs/spec/action-ref.md`](./action-ref.md) — also documents `authority_verified_at_ms` and `revocation_check_at_ms`
- `revocation_ref`: [`docs/spec/revocation-ref.md`](./revocation-ref.md)
- `idempotency_ref`: [`docs/spec/idempotency-ref.md`](./idempotency-ref.md)
- `negotiation_ref`: [`docs/spec/negotiation-ref.md`](./negotiation-ref.md)
- TrailRecord schema: [`docs/MYCELIUM_TRAILS_REFERENCE.md`](../MYCELIUM_TRAILS_REFERENCE.md)
