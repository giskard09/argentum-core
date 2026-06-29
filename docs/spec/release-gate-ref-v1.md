# release-gate-ref-v1

A release gate is the point at which a middleware decides whether a proposed
action crosses the runtime boundary. Four precedence modes determine when the
gate opens:

## Modes

**permit_on_internal_seal** — the internal admission decision is sufficient to
release the action. An external anchor or proof is recorded but does not block
execution.

**block_on_external_confirm** — the middleware holds the proposed action until
an external proof or anchor is confirmed by an independent clock (OTS, on-chain
block, CT log). The action does not cross the runtime boundary until
anchoring_precedence is established.

**deny_on_unverifiable** — if the verifier cannot establish the required
evidence (missing proof, unresolvable key, unreachable anchor), the middleware
denies or defers rather than releasing on partial evidence.

**defer_to_trusted** — when policy lookup cannot produce a deterministic
verdict, a declared trusted evaluator supplies the verdict before the gate
opens. The evaluator identity and the scope of its authority are part of the
release record.

## Join requirement

Each mode requires that the release record join back to the exact `action_ref`
and `decision_id` of the gate decision that authorized the release. A signed
receipt proves that something was decided; the release gate proves that this
signed object governed this exact proposed action before the action crossed the
runtime boundary.

## Critical negative case

Mismatched evidence: the attestation is real, recomputable, and signed, but
binds to a different `action_ref` or `decision_id` than the action the
middleware is about to release. Must fail closed before execution, regardless
of mode.

## Fields

```json
{
  "release_gate": {
    "mode": "permit_on_internal_seal | block_on_external_confirm | deny_on_unverifiable | defer_to_trusted",
    "action_ref": "<SHA-256(JCS(...))>",
    "decision_id": "<gate decision ref>",
    "released": true,
    "anchor_confirmed": true,
    "evaluator_ref": "<identity ref — required for defer_to_trusted>"
  }
}
```

## Relationship to existing primitives

- `authorization_ref` — policy basis for the gate decision; closes `permit_on_internal_seal`
- `anchoring-precedence-ref-v1` — required for `block_on_external_confirm`; block_time strictly less than outcome_ts
- `delegation-chain-ref-v1` — authority chain behind `defer_to_trusted`
