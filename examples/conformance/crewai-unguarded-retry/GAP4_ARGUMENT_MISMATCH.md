# Addendum — gap #4 (ARGUMENT_MISMATCH), nsolland

Confirmed by nsolland directly on our own terrain
([crewAIInc/crewAI#7449](https://github.com/crewAIInc/crewAI/issues/7449),
2026-09-15 08:09 UTC, no `@` used) against the worked example this
directory already holds (PR#86, merged). This addendum does not modify
`PROVENANCE.md` — that document is anchored on-chain against a specific
commit (see `PROVENANCE.md` "On-chain anchor") and stays exactly as
published; this is new material added afterward.

## The gap

`logical_action_id` (fixed by the caller, `idempotency_guard.py`,
invariant 5 of `../../../docs/spec/idempotency-ref.md`) identifies **which**
action a retry belongs to. It says nothing about **what** that retry
actually asks for. nsolland's point: a second attempt that carries the
same `logical_action_id` but different arguments — a model-regenerated
retry with a changed amount, a changed recipient — is not a retry of the
first attempt's authorized intent. It is a materially different action
wearing the same identifier, and the existing guard has no way to see
that. It should require a **new authorization decision** (a new
`decision_binding_ref`, ../../../docs/spec/decision-binding-ref-v1.0.md)
rather than silently reuse the first attempt's permit.

This is distinct from the fixture Heimel already covers (stale-authority /
consumed-permit — a permit that expired or was already spent) and distinct
from `idempotency-ref.md`'s own documented false-negative risk (a
`SHA(args)`-keyed scheme missing a *true* retry whose regenerated
arguments differ only superficially). Gap #4 is the case in between:
arguments that differ **materially**, under a key that was deliberately
designed not to look at arguments at all.

## What was built

- `args_binding_guard.py` — `ArgumentBoundGuard`, wraps
  `IdempotencyGuard` with an args-content digest bound on the first
  attempt for a given `idempotency_ref`. Any later attempt whose
  args-digest differs raises `ArgumentMismatchError` **before** the
  wrapped guard (and therefore the effect, and any `RECONCILED_GUARD`
  reuse) is reached at all.
- `argument_mismatch_naive_case.py` — two real
  `crewai.tools.tool_usage.ToolUsage.use()` calls (unmocked,
  `harness.run_single_tool_call`, a new entry point added to `harness.py`
  alongside the existing outer-retry-loop one — this scenario is a
  model-regenerated retry, not crewAI's own re-dispatch, so it is
  reproduced as two independent calls rather than two iterations of
  `ToolUsage`'s internal loop), same `logical_action_id`, amounts `100`
  then `250`, against the **unmodified** `idempotency_guard.py` from the
  base worked example.
- `argument_mismatch_guarded_case.py` — identical scenario, tool wrapped
  with `ArgumentBoundGuard` instead.
- `verify_argument_mismatch.py` — conformance runner, same convention as
  `verify.py`.

## Result (real run, `crewai==1.15.21`, unmocked)

```
$ python3 verify_argument_mismatch.py
crewai-unguarded-retry / ARGUMENT_MISMATCH conformance -- 2 cases
  [PASS] ARGUMENT_MISMATCH_NAIVE: attempt 2 (amount=250) silently discarded, guard reused attempt 1's permit (guard_events=['COMMITTED', 'RECONCILED_GUARD'])
  [PASS] ARGUMENT_MISMATCH_GUARDED: attempt 2 refused with ARGUMENT_MISMATCH_REQUIRES_NEW_DECISION, no silent reuse, no silent second effect

ALL CHECKS PASS
```

**NAIVE**: attempt 1 (amount=100) commits normally. Attempt 2 (amount=250)
hits the existing `IdempotencyGuard` with a COMMITTED record already on
file for the same `idempotency_ref` — it returns `RECONCILED_GUARD` with
attempt 1's `effect_id`. The tool call reports success. Amount=250 never
produces its own effect (`effect_count == 0`, confirmed by an independent
read from `effect_store.py`, same as every other case in this directory)
— and nothing about the returned outcome distinguishes this from a benign
duplicate retry. The caller's real, different request was silently
discarded.

**GUARDED**: identical scenario, `ArgumentBoundGuard` in front. Attempt 2's
args-digest does not match the one bound on attempt 1 — refused with
`ARGUMENT_MISMATCH_REQUIRES_NEW_DECISION` before the wrapped guard is even
called. Same result on the effect store (amount=250 never commits), but
the outcome is now an explicit, machine-readable refusal instead of a
silent substitution — the caller (or its authorization layer) knows a new
decision is required instead of believing the wrong request succeeded.

## What this does not claim

- This is not a fix proposal against `crewAIInc/crewAI` — crewAI's own
  retry engine is not the mechanism under test here (see `harness.py`'s
  `run_single_tool_call` docstring: this reproduces a model-regenerated
  retry, a layer above `ToolUsage`, not `ToolUsage`'s own re-dispatch).
  It is a gap in the pattern this worked example already publishes
  (`idempotency-ref-v1` + `IdempotencyGuard`), fixed here against that
  pattern's own vocabulary.
- `args_binding_guard.py` binds a plain SHA-256 digest of the presented
  arguments — it is not itself a `decision_binding_ref` (no
  `action_ref`/`decision_id`/`decision_at_ms` preimage, no anchor). It
  demonstrates the invariant nsolland is asking for (mismatch → refusal,
  never reuse); wiring it to a real `decision_binding_ref` issuance is a
  follow-up, not done here.
- Not anchored on-chain. This addendum is new since `PROVENANCE.md`'s
  anchored commit and has not gone through that step.

## Not yet built

Gap #3 (resume-after-restart loses state) — mapped 2026-09-14, still
open, no fixture yet.
