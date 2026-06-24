# restraint-receipt-v1 — Conformance Surface

Conformance vectors for `restraint-receipt-v1`. A restraint receipt is the
verifiable record produced when an agent receives a deny or defer verdict.
Silence is not conformant — the accountability layer covers denied and deferred
actions with the same fidelity as executed ones.

## Invariant

**A terminal receipt cannot be interpreted independently from the verifier
surface that made the pre-execution decision.**

This means a conformant restraint receipt must fix not only the verdict and
reason code, but also *which verifier* and *which policy bundle* produced that
decision. A receipt that passes field-level validation but allows the verifier
identity or policy bundle reference to be swapped without changing the receipt
reference is non-conformant — this is the quiet-drift failure mode.

The `audit_checkpoints` field closes this gap: it content-addresses both the
verifier identity and the policy bundle at decision time. Presence alone does
not satisfy the requirement — `audit_checkpoints` must be non-empty and
included in the canonical preimage.

## Vector coverage

### Base vectors (RR-ACCEPT-001, RR-ACCEPT-002, RR-REJECT-001)

Cover the five required preimage fields (`action_ref`, `decision_id`,
`verdict`, `reason_code`, `timestamp_ms`). A receipt missing any field is
non-conformant.

### audit_checkpoints vectors (RR-ACCEPT-003, RR-REJECT-002 and follow-up set)

Cover the content-addressed verifier path. Six cases:

| Vector | Description |
|--------|-------------|
| ACCEPT | Denied receipt with verifier identity and policy bundle reference present, non-empty, and included in the canonical preimage |
| REJECT | Missing `policy_bundle` reference in `audit_checkpoints` |
| REJECT | `audit_checkpoints` present but empty object `{}` — presence without substance is non-conformant |
| REJECT | `audit_checkpoints` present and field-valid, but canonical receipt reference computed without it — quiet-drift |
| REJECT | Verifier identity matches but policy bundle digest does not match the referenced bundle |
| REJECT | Policy bundle digest matches but verifier identity is not the verifier selected in the decision record |

The fourth case (quiet-drift) is the strongest integrity test: it catches
implementations that pass field-level validation while allowing the verifier
surface to be swapped without changing the receipt reference.

## Spec

`docs/spec/restraint-receipt.md`

## Verification

```
python3 verify.py
```

All vectors must pass. Output: `N/N passed`.
