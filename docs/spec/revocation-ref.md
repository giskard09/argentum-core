# revocation-ref-v1 — Specification

**Stable tag:** `revocation-ref-v1.0`  
**Status:** stable  
**Canonical fixture:** [`examples/conformance/revocation-ref-v1.fixture.json`](../../examples/conformance/revocation-ref-v1.fixture.json)

---

## What is revocation-ref

`revocation_ref` is a SHA-256 hex pointer to a revocation artifact — a structured document that records when and why a prior authorization became invalid.

**What it enables:** a Mycelium verifier who holds both a delegation artifact and a revocation artifact can establish the exact window during which an agent held valid authority. A trail record with `revocation_ref` is the tamper-evident record of an invalidation event — it does not delete the prior `delegation_ref`, it appends a new record that asserts the prior one is no longer in force.

**The dual-timestamp connection:** `revocation_check_at_ms` in [`action-ref.md`](./action-ref.md) records the last non-revocation check performed before execution. `revocation_ref` records the revocation event itself. Together they close the audit gap: `revocation_check_at_ms` proves "it was valid when I checked"; `revocation_ref` proves "it became invalid at this specific moment."

**The authority gap:** `revocation_check_at_ms` proves a check happened, not what it was checked against. A receipt can carry a fresh check timestamp while consulting a stale or compromised revocation source — same appearance of compliance, no real guarantee. `revocation_authority_ref` (also in [`action-ref.md`](./action-ref.md#updated-canonical-receipt-envelope--v10-with-optional-rotation-fields)) binds the check to a specific, independently identifiable authority (`permissionless-registry` | `private-endpoint` | `third-party-oracle`). Together with `revocation_check_at_ms`, it answers "checked when, against what" instead of just "checked when."

**What it does not do:** `revocation_ref` does not retroactively invalidate COMMITTED trail records. A COMMITTED record with a prior `delegation_ref` that was later revoked is still a valid historical record of what happened. The revocation applies to future use of that delegation, not to the past action.

---

## Derivation

`revocation_ref` is `SHA-256(JCS(revocation_artifact))` where:

- **JCS** is RFC 8785 canonical JSON: `json.dumps(obj, separators=(',',':'), sort_keys=True, ensure_ascii=False)`
- **SHA-256** lowercase hex
- `revocation_artifact` must contain at minimum: `revoker`, `revoked_action_ref`, `revoked_at`, `reason`, `scope`, `version`

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

revocation_artifact = {
    "reason":             "credential_expired",
    "revocation_key":     "rev_a9f3b1c2d4e5",
    "revoked_action_ref": "584bc79bb11ce3af5058b3da84d03f85e4aa464a175bd4f913aeb82a22cef60f",
    "revoked_at":         "2026-05-24T11:00:00.000Z",
    "revoker":            "giskard-self",
    "scope":              "mycelium:payment",
    "version":            "revocation-ref-v1",
}
revocation_ref = hashlib.sha256(jcs(revocation_artifact).encode()).hexdigest()
# 50cb4f3d564763cd11dde45950ef8298e92f468070a27f125dfd658d45d5eca5
```

---

## Invariants

**1. envelope-only — does not enter action_ref preimage**

`revocation_ref` is carried in the trail envelope of the revocation action. It never enters the four-field preimage. The revocation action itself has its own `action_ref` derived from its own preimage.

**2. revocation is append-only**

Revocation does not mutate the original trail record. It creates a new trail record with `action_type: authorization.revoke` that carries `revocation_ref`. The original record remains intact with its original `delegation_ref`.

**3. revoked_action_ref links back to the delegation**

The `revoked_action_ref` field inside the revocation artifact should reference the `action_ref` of the trail record that used the now-revoked delegation. This creates a verifiable link: verifier can walk delegation → action → revocation without external lookups.

**4. reason is informational, not normative**

The `reason` field is part of the artifact and enters the hash. Its value is implementer-defined. Mycelium does not validate it.

**5. revocation_key scopes uniqueness**

The `revocation_key` is client-generated to ensure uniqueness of the revocation artifact. Without it, two identical revocations (same revoker, same target, same timestamp) would produce the same `revocation_ref`, making it impossible to distinguish independent revocation events.

---

## Trail record for a revocation event

A revocation is itself a trail action:

```json
{
  "packet_version":  "1.0",
  "action_ref":      "<sha256 hex — action_ref of the revocation action>",
  "revocation_ref":  "<sha256 hex — derived from revocation_artifact>",
  "hash_algo":       "sha256",
  "preimage_format": "jcs-rfc8785-v1",
  "preimage": {
    "action_type": "authorization.revoke",
    "agent_id":    "giskard-self",
    "scope":       "mycelium:payment",
    "timestamp":   "2026-05-24T11:00:00.000Z"
  }
}
```

---

## Cross-references

- `action_ref` derivation + `revocation_check_at_ms`: [`docs/spec/action-ref.md`](./action-ref.md)
- `delegation_ref` (what is being revoked): [`docs/spec/delegation-ref.md`](./delegation-ref.md)
- `idempotency_ref`: [`docs/spec/idempotency-ref.md`](./idempotency-ref.md)
- TrailRecord schema: [`docs/MYCELIUM_TRAILS_REFERENCE.md`](../MYCELIUM_TRAILS_REFERENCE.md)
