# decision_binding_ref — context_digest extension

Proposed by eriknewton (co-founder, trust-evidence-format) in
[A2A discussion#1734](https://github.com/a2aproject/A2A/discussions/1734#discussioncomment-17896415)
(2026-08-04): add a field to `decision_binding_ref` that binds the *inputs available to
the decision* — the set of memories/documents/artifacts assembled at decision time — not
just the action (`action_ref`) and the fact of the decision (`decision_id` +
`decision_at_ms`).

## What context_digest proves — and what it doesn't

`context_digest = SHA-256(JCS(assembled_context))`. A verifier holding the actual context
set (or its content-addressed refs) can recompute the digest and confirm *these artifacts
were present in the input of this decision*.

It does **not** resolve attribution or steering — it can't tell you which artifact caused
which part of the outcome, or how much weight the decision-maker gave to any one of them.
Only presence, the same restraint `action_ref` already applies to content vs. intent.

## Backward compatibility

Additive, non-breaking extension to
[decision-binding-ref-v1.0](../../docs/spec/decision-binding-ref-v1.0.md). Same absence
rule as the existing `policy_ref` field: omit the key entirely when not applicable, never
`null`. Vector `cd-003` is byte-identical to v1.0's Fixture B, proving a verifier that
doesn't know about `context_digest` computes the same `decision_binding_ref` as before.

## Vectors

| id | what it checks | result |
|----|----------------|--------|
| `cd-001` | `context_digest` present, recomputable from the presented context set | PASS |
| `cd-002` | `policy_ref` + `context_digest` combined — deterministic JCS ordering with both optional fields present | PASS |
| `cd-003` | neither optional field present — backward-compat, identical to v1.0 Fixture B | PASS |
| `cd-004` | one artifact silently dropped from the presented context set — digest diverges, verifier rejects | FAIL (`CONTEXT_SET_MISMATCH`) |

Run `python3 verify.py` — recomputes every digest from the raw JSON in `vectors.json`,
never trusts the stored hash values.

## Status

Independent verification pending. eriknewton offered a worked example from the receipt
side (trust-evidence-format) — notify when this fixture is published, cross-check the same
way [`composed-decision-chain-recompute`](../composed-decision-chain-recompute/) was
cross-checked against babyblueviper1's independent implementation.
