# Addendum — gap #3 (RESUME_AFTER_RESTART), nsolland

Confirmed by nsolland directly on our own terrain
([crewAIInc/crewAI#7449](https://github.com/crewAIInc/crewAI/issues/7449),
2026-09-14 08:26 UTC, no `@` used) against the worked example this
directory already holds (PR#86, merged): "in-process COMMITTED blocks a
retry, but the guard is a dict in memory -- resume after a real restart
loses the state." This addendum does not modify `PROVENANCE.md` — that
document is anchored on-chain against a specific commit and stays exactly
as published; this is new material added afterward, same pattern as
`GAP4_ARGUMENT_MISMATCH.md`.

## The gap

`idempotency_guard.IdempotencyGuard` implements the PENDING/COMMITTED
lifecycle correctly *within one process's memory*: a second attempt that
finds an existing PENDING record refuses to re-run the effect
(`PENDING_GUARD`); a COMMITTED record short-circuits to the original
outcome (`RECONCILED_GUARD`). Neither rule depends on holding the record
in a `dict` specifically — but that is where it lives (`self._records`,
`idempotency_guard.py:48`), so a process crash between "attempt 1 commits
the effect, then dies before returning" and "attempt 2 arrives" wipes the
record along with the process. The retry's guard is a *new*
`IdempotencyGuard()` with an empty `_records` — it has no way to know the
idempotency_ref was ever touched, so it treats the retry as a first
attempt and runs the effect again.

## What was built

- `durable_idempotency_guard.py` — `DurableIdempotencyGuard`, same
  `guard()`/`reconcile()` lifecycle and the same three `guard_outcome`
  values as `idempotency_guard.IdempotencyGuard`, with the record stored
  as a row in a SQLite table (`db_path`) instead of a `dict`. A second
  `DurableIdempotencyGuard` instance pointed at the same `db_path` reads
  the first one's PENDING record, whether that second instance is a
  different process or the same process after a restart.
- `restart_naive_case.py` — attempt 1 (process A: `IdempotencyGuard()`,
  in-memory) commits the effect and raises, simulating a crash. A
  *fresh* `IdempotencyGuard()` (process B) then runs attempt 2 against
  the unmodified base guard.
- `restart_guarded_case.py` — identical scenario, both attempts go
  through `DurableIdempotencyGuard` pointed at the same on-disk path.
- `verify_restart.py` — conformance runner, same convention as
  `verify.py` / `verify_argument_mismatch.py`.

## Result (real run, `crewai==1.15.21`, unmocked)

```
$ python3 verify_restart.py
crewai-unguarded-retry / RESUME_AFTER_RESTART conformance -- 2 cases
  [PASS] RESUME_AFTER_RESTART_NAIVE: process restart lost the PENDING record, attempt 2 re-ran the effect (effect_count=2)
  [PASS] RESUME_AFTER_RESTART_GUARDED: PENDING record survived the restart on disk, attempt 2 refused with PENDING_GUARD, reconciled to COMMITTED against the effect store (effect_count=1)

ALL CHECKS PASS
```

**NAIVE**: attempt 1 commits the effect (`effect_store` row written) and
raises before returning, standing in for the process dying right there.
Attempt 2 runs against a brand-new `IdempotencyGuard()` — the PENDING
record attempt 1 wrote is gone with the old process. The guard sees no
record at all, runs the real effect a second time, and reports
`COMMITTED` — nothing about that outcome distinguishes it from a benign
first-ever attempt. Two effects land in the store for one
`logical_action_id` (`effect_count == 2`, confirmed by an independent read
from `effect_store.py`, same as every other case in this directory).

**GUARDED**: identical crash. The PENDING record attempt 1 wrote lands in
`GUARD_DB_PATH` before the effect function is even called, so it survives
the process dying. Attempt 2, on a new `DurableIdempotencyGuard` pointed
at the same path, finds that PENDING record and refuses with
`PENDING_GUARD` — no second effect is applied. A subsequent `reconcile()`
call independently reads `effect_store` (never window_ms, never "the
record survived" as its own evidence) and promotes the record to
`COMMITTED` with the real `effect_id`. `effect_count == 1`.

## What this does not claim

- Not a fix proposal against `crewAIInc/crewAI` — the restart happens
  above `ToolUsage` entirely, in whatever process embeds this worked
  example's guard, not in crewAI's own retry/re-dispatch engine.
- `DurableIdempotencyGuard`'s SQLite table is a minimal persistence layer
  to demonstrate the invariant (PENDING must survive a restart); it is
  not itself a production-grade store (no migrations, no concurrent-writer
  locking beyond SQLite's own, no TTL/cleanup policy for abandoned
  PENDING rows). Wiring the same lifecycle to a real durable backend
  (Postgres, the same store `arb_pay.py` or `ArgentumReconciler` already
  use) is a follow-up, not done here.
- Not anchored on-chain. This addendum is new since `PROVENANCE.md`'s
  anchored commit and has not gone through that step.

## Status

Gap #3 (resume-after-restart loses state) — mapped 2026-09-14, closed here
(2026-09-18). All five gaps nsolland identified against this worked
example are now covered: (1)(2) demonstrated in the base worked example,
(3) this addendum, (4) `GAP4_ARGUMENT_MISMATCH.md`, (5) probable by
construction (see nsolland's original mapping, `BITACORA_NSOLLAND.txt`
2026-09-14).
