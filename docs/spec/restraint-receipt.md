# Restraint Receipt — `restraint-receipt-v1`

A restraint receipt is the verifiable record produced when an agent receives a deny or defer verdict. It closes the audit gap: the accountability layer covers denied and deferred actions with the same fidelity as executed ones. Silence is not conformant.

## Motivation

An agent that receives a guardrail denial can either produce a restraint receipt or emit nothing. Without a restraint receipt, the denial exists only in the guardrail's internal log — invisible to external verifiers and cross-system audits. The restraint receipt makes the denial a first-class event in the Mycelium trail.

## Preimage

```
restraint_receipt_ref = SHA-256(JCS({
  action_ref,
  decision_id,
  verdict,
  reason_code,
  timestamp_ms
}))
```

Field definitions:

| Field | Type | Description |
|-------|------|-------------|
| `action_ref` | hex string | The `action_ref` from the pre-execution record — same binding as the three-record trail. Not recomputed; carried forward from the denied action instance. |
| `decision_id` | string | Opaque identifier for the authorization decision that produced the verdict. Issued by the guardrail or policy engine. |
| `verdict` | `"denied"` \| `"deferred"` | `denied`: action was blocked; no execution occurred. `deferred`: action is pending further review; execution is suspended. |
| `reason_code` | string | The canonical reason code from the verifier output (see `verifier_precedence` in `guardrail-provider-v1.fixture.json`). |
| `timestamp_ms` | integer | Unix epoch milliseconds at the moment the restraint receipt is emitted. |

Canonicalization: JCS per RFC 8785 (keys sorted, no insignificant whitespace). All fields are required. A receipt missing any field is non-conformant.

## Required fields

All five fields are required. Implementations MUST NOT omit `decision_id` or `reason_code` to reduce payload size — the computable `restraint_receipt_ref` is the integrity anchor for cross-system verification.

## Relationship to the three-record trail

The restraint receipt does not replace the pre-execution record. It extends the trail with a fourth record type covering the deny/defer path:

```
intent tuple
  → action_ref (correlation key)
  → pre-execution record (before guardrail decision)
  → [denied/deferred verdict]
  → restraint receipt (this spec)
```

For the allow path, the existing three-record trail applies (`pre_execution → decision → receipt`). The restraint receipt is the deny/defer counterpart to the terminal receipt.

## Conformance

Conformance vectors: `examples/conformance/restraint-receipt-v1/vectors.json`

Verification script: `examples/conformance/restraint-receipt-v1/verify.py`

A conformant implementation:
1. Emits a restraint receipt for every denied or deferred action.
2. Carries `action_ref` forward unchanged from the pre-execution record.
3. Includes all five fields in the preimage before hashing.
4. Uses JCS (RFC 8785) canonicalization.
5. Records `restraint_receipt_ref` in the trail alongside the pre-execution record.

## Relationship to other specs

- `docs/spec/action-ref.md` — derivation of `action_ref` from the intent tuple
- `docs/spec/verifier-dispatch-contract.md` — the five-field verifier output contract
- `docs/spec/decision-binding-ref-v1.0.md` — `decision_binding_ref` on the allow path
- `examples/conformance/guardrail-provider-v1.fixture.json` — canonical `reason_code` values and `verifier_precedence`
