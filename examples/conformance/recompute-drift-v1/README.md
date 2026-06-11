# action-ref recompute-drift conformance vectors - v1

Conformance vectors for the action-ref-v1 **recomputation property**: a verifier
recomputes `action_ref` from the invocation payload's four-field tuple and MUST
fail closed, before invocation, when the claimed `action_ref` does not match.
The verifier never retries alternative preimages, never coerces field types,
and never normalizes field values to force a match.

**Spec:** [`docs/spec/action-ref.md`](../../docs/spec/action-ref.md)
(`action-ref-v1.0` stable tag)
**Canonicalization:** RFC 8785 (JCS), SHA-256 lowercase hex
**Runner:** [`verify.py`](./verify.py) (stdlib only, deterministic, exit 0 on full pass)

## Files

| File | Vectors | What it holds |
|------|---------|---------------|
| [`recompute-drift-v1-positive.fixture.json`](./recompute-drift-v1-positive.fixture.json) | 5 | Tuples that recompute byte-identical. Each digest was computed by two independent paths (a shipping TypeScript implementation and a stdlib-only SHA-256 over the JCS bytes) and byte-checked equal before inclusion. |
| [`recompute-drift-v1-negative.fixture.json`](./recompute-drift-v1-negative.fixture.json) | 9 | Drifted claims that MUST fail closed. Every `claimed_action_ref` is a real SHA-256 digest of a stated drifted byte form, included in the vector, so the forbidden recovery move is explicit per vector. |

## Positive vectors

| Vector | Covers |
|--------|--------|
| `0001-basic` | Minimal four-field tuple, namespace-prefixed scope |
| `0002-unicode-fields` | Non-ASCII BMP characters in `agent_id` and `scope`, raw UTF-8 per JCS |
| `0003-empty-scope` | `scope: ""`, valid per the spec field table |
| `0004-ms-floor` | Timestamp fractional part `.000`, no trailing-zero suppression |
| `0005-ms-ceiling` | Timestamp fractional part `.999`, no rounding or carry |

## Negative drift families

| Family | Vectors | Drift behind the claim | Forbidden recovery move |
|--------|---------|------------------------|-------------------------|
| `field_order_drift` | `neg-a01`, `neg-a02` | Serialization in received field order, no JCS key sort | Rehashing the drifted byte order (preimage retry) |
| `timestamp_form_drift` | `neg-b01`, `neg-b02`, `neg-b03` | Epoch-ms integer, second-precision RFC 3339, six-digit-microsecond forms of the same instant | Converting between timestamp forms and rehashing (normalization retry) |
| `casing_drift` | `neg-c01`, `neg-c02` | `agent_id` letter casing changed between payload and claim preimage | Case folding before comparison |
| `payload_drift` | `neg-d01`, `neg-d02` | Payload `scope` / `action_type` differs from the tuple behind the claim | Substituting the claim's original tuple for the payload tuple |

Every negative vector carries the invocation payload tuple, the claimed
`action_ref` (byte-derived from the drifted form, not invented), the drifted
serialization or drifted preimage with its bytes, the drift family, and the
expected verdict: verifier failure before invocation with a one-line reason.

`neg-b01` is the one vector where the drifted form sits in the invocation
payload itself: the claim matches the payload bytes verbatim, and only the
timestamp grammar gate rejects it. A verifier that hashes first and checks
grammar never (or coerces the integer to a string) accepts a non-conformant
receipt.

## Run

```
python3 verify.py
```

Exit `0` when every positive recomputes byte-identical and every negative is
grammar-rejected or digest-mismatched with the expected failure stage. Exit `1`
otherwise. The verifier under test (`verify_claim`) has a single code path:
grammar gate, one canonical recomputation, one comparison. The fixture
integrity checks at the end recompute the drifted digests only to check the
fixture data itself; they never feed the verifier verdict.

## Quick verify in Python

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

# 0001-basic
preimage = {
    "action_type": "trail.anchor",
    "agent_id":    "recompute-agent-001",
    "scope":       "argentum:recompute_baseline",
    "timestamp":   "2026-06-11T10:00:00.123Z",
}
assert hashlib.sha256(jcs(preimage).encode()).hexdigest() == \
    "de7d7f40147b9b7f41134b14752aa36e3435bda89c51938ba358a69be04dccf6"
```

## What these fixtures do NOT cover

Recomputation agreement only. Passing this set does not establish:

- **Policy correctness.** Nothing here checks that the action was permitted
  by any policy, or that a policy was evaluated at all.
- **Snapshot application.** Nothing here checks that any policy or state
  snapshot was applied at admission time.
- **Authorization.** A byte-identical recomputation says the claim binds to
  the stated tuple; it says nothing about whether the agent held authority
  to perform the action.
- **Occurrence.** A matching `action_ref` does not establish that the action
  happened, only that the identifier is consistent with the stated preimage.

## Cross-references

- Derivation spec: [`docs/spec/action-ref.md`](../../docs/spec/action-ref.md)
- Baseline positives: [`../action-ref-v1-baseline.fixture.json`](../action-ref-v1-baseline.fixture.json)
- Existing negatives (missing field, tampered hash): [`../negative-v1.fixture.json`](../negative-v1.fixture.json)
- Near-miss boundary: [`../near-miss-v1/`](../near-miss-v1/)
