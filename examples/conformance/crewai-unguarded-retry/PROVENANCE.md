# PROVENANCE — crewai-unguarded-retry

## What this is

A worked reproduction of the `UNGUARDED_RETRY` case socksninja
(building `sable-agent-reliability`, a reliability layer) requested by
exact spec across five separate comments on
[crewAIInc/crewAI#5802](https://github.com/crewAIInc/crewAI/issues/5802) —
our own terrain since May, 9+ comments — without ever using the `@` handle.
The spec he gave: fix a `logical_action_id`, commit a local effect inside a
tool, inject failure *after* the effect commits but *before* crewAI
registers the tool's result, let crewAI's real retry/re-dispatch fire with
the same `logical_action_id`, then read the effect store independently.

This is not a benchmark of SABLE. It is proof of our own terrain — the
generalization of `idempotency-ref-v1` beyond x402-EVM (IDEA C), tracked
against independent convergences from glennquinting, vasilisnasopoulos,
mstevens843, 0xultravioleta and halobartku on the same pattern. The
Nandana/mycelium-labs worked example (2026-07-27, see
`~/Downloads/BITACORA CODIGO 2026-07-27 aiid-provenance-nandana-reconcile-axes-exchange.txt`)
proved the same control-vs-guard pattern against `mycelium-runtime`'s own
crash/reconcile primitives — never against CrewAI's *native* retry engine
itself. That is the piece this worked example adds.

## What was actually built

Everything in this directory is new code, written for this worked example,
run against the real installed `crewai` package (`crewai==1.15.21`, from
PyPI, in an isolated venv — not committed, not vendored):

- `effect_store.py` — an independent SQLite effect store (counter +
  effect row, one transaction per commit). Read back after each run from a
  fresh connection; it has no knowledge of crewAI's retry state.
- `harness.py` — drives `crewai.tools.tool_usage.ToolUsage` directly (the
  installed package's real class, read from
  `crewai/tools/tool_usage.py`), calling `ToolUsage.use()` with a
  `ToolCalling` built the same way crewAI's own agent executor builds one
  after parsing an LLM tool call. No LLM call is made — the retry engine
  under test lives entirely inside `ToolUsage`, downstream of tool-call
  parsing, so exercising it does not require one.
- `idempotency_guard.py` — the `idempotency-ref-v1` guard
  (`../../../docs/spec/idempotency-ref.md`): `derive_idempotency_ref()`
  follows the spec's JCS+SHA-256 derivation exactly, keyed on the
  caller-fixed `logical_action_id` (invariant 5 of the spec — never on
  model-regenerated tool-call arguments). `IdempotencyGuard.guard()`
  implements PENDING → COMMITTED; `IdempotencyGuard.reconcile()`
  implements provider-confirmed resolution of an orphaned PENDING by
  querying `effect_store` independently — the same shape as
  `ArgentumReconciler` polling `GET /trails/verify` against
  `mycelium-runtime` in the Nandana case, here polling the local effect
  store instead.
- `unguarded_case.py` / `guarded_case.py` — the two cases, identical crash
  injection point, identical `logical_action_id`, only the presence of the
  guard differs.
- `receipt.py` — the machine-readable receipt in the exact shape
  socksninja requested.
- `verify.py` — conformance runner (same convention as
  `../settlement-retry-safety/verify.py`).

## What was verified, and how

Both cases run the **real, unmocked** `crewai.tools.tool_usage.ToolUsage`
retry engine — not a simulation of it, not a reimplementation. Confirmed
by direct source read of the installed package (not from memory or
documentation):

```
$ python3 verify.py
crewai-unguarded-retry conformance -- 2 cases
  [PASS] UNGUARDED_RETRY: 6 duplicate effects observed (expected >1)
  [PASS] GUARDED: exactly 1 effect observed with idempotency-ref-v1 guard

ALL CHECKS PASS
```

**A finding beyond the original spec, disclosed honestly rather than
smoothed over:** CrewAI's retry surface has *two* independent retry
vectors, not one. The outer loop (`ToolUsage._run_attempts` /
`_max_parsing_attempts`, default 3) is the one the spec anticipated. But
inside a single outer attempt, `ToolUsage._use`/`_ause` also has its own
`try`/`except` around `tool.invoke()`: it first calls the tool with
schema-filtered arguments, and on **any** exception from that call —
including the exact `RuntimeError` this reproduction injects — it silently
retries `tool.invoke()` a second time with the unfiltered arguments,
inside the same outer attempt
(`crewai/tools/tool_usage.py`, sync path lines 611–627, async path
355–372, `crewai==1.15.21`). Neither retry is gated on whether the first
call's exception came from argument validation (its apparent intent) or
from the tool's own body (what actually happens here). The practical
effect: every outer attempt invokes the tool's Python function **twice**,
not once. With `_max_parsing_attempts=3`, `UNGUARDED_RETRY` produced **6**
real duplicate effects, not 3 — confirmed by `unguarded_case.py`'s
independent read of `effect_store`, not inferred from `run_attempts`.

**Control validity:** `guarded_case.py` runs the identical crash injection
against the identical unmocked retry engine (both retry vectors included —
`guarded_case.py`'s `python_level_invocations` is 2, confirming the inner
double-invoke fires there too) and observes exactly 1 effect. The variable
that flips the outcome is the guard, not a change to crewAI's behavior —
same as the control-vs-reconciler pairing in the Nandana worked example.

**PENDING_GUARD / RECONCILED_GUARD, both observed live** (not left as a
theoretical "if time allows" — the run's `guard_events` show both):
attempt 2 (the inner double-invoke firing inside outer attempt 1) hits
`PENDING_GUARD` because attempt 1 already set the record PENDING before
crashing; the post-run `reconcile()` call — querying `effect_store`
independently, exactly as `idempotency-ref.md`'s "provider-confirmed
resolution" requires, never on `window_ms` alone — finds the one real
effect and transitions the record to `RECONCILED_GUARD` with the true
`effect_id`.

## On-chain anchor

`ref = keccak256("crewai-unguarded-retry-v1:argentum-core@4613c83")` =
`0xf28ee32220242db2d66dee7207a6b0e42869685b5b47f5ef10d3903deb22ac40`

Anchored via `anchor(bytes32)` on AnchorRegistry (Base mainnet,
`0x49fEcA52bC634a9Ab773226D16619deC547794aa`), permissionless — same
contract used across this repo's other worked examples.

- tx: `0xd5ff5b661424f27963643c9ef208b38e04196ff33808974d22e820efaa151733`
- block: `51285043`
- status: `0x1` (confirmed via direct `eth_getTransactionReceipt` against
  `mainnet.base.org`, not read back from the sender's own response)

**What this anchor claims and what it does not:** it timestamps the
existence of this artifact (commit `4613c83`) on Base mainnet at block
51285043 — a public, permissionless proof-of-existence. It is **not** a
public "safe" or "bug confirmed" claim on CrewAI's behalf — that
determination lives in this document's own findings above, not in the
anchor.

## What was not built

- No LLM was called at any point — see harness rationale above. This is a
  deliberate scope choice: it isolates the retry engine (the thing under
  test) from LLM non-determinism (irrelevant to it), the same way
  `settlement-retry-safety`'s `MockFacilitator` isolates the client under
  test from a real facilitator's network behavior. If socksninja or a
  crewAI maintainer wants the same case driven through a full `Agent`/
  `Crew`/live-LLM loop to confirm the retry path is reached the same way
  in production, that is a natural next step, not done here.
- No PR opened against `crewAIInc/crewAI` — this is a worked example in
  our own repo, not a proposed fix. Whether the inner double-invoke
  fallback (see finding above) is itself a bug worth reporting separately
  is a judgment call left to dept-estrategia before any posting.

## Reproducing

```
python3 -m venv venv && venv/bin/pip install crewai
cd examples/conformance/crewai-unguarded-retry
venv/bin/python3 verify.py
venv/bin/python3 receipt.py > receipt.json
```
