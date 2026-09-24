# Addendum — idempotency-ref v1.1, the four cases through crewAI

`../idempotency-ref-v1.1/` proves the v1.1 decision rule at spec level:
`verify.py` replays the four events against a reference ledger. This
addendum runs the same four events through crewAI's real
`ToolUsage.use()`, with the guard inside the tool and the effects counted
from an independent read of the SQLite effect store. It does not modify
`PROVENANCE.md` (anchored on-chain against a specific commit).

The four-case test is impartshadow's (agent-contracts, crewAI issue 5802,
comment 5790417981), pinned as a regression by stringsofthemind-oss
(once PR 45, 9ca1eb3).

## Cases

| Event | Key | Payload | How it reaches the tool | Expected | Effects |
|---|---|---|---|---|---|
| case 1, first intentional payment | A | $100 → X | `ToolUsage.use()` | EXECUTE | 1 |
| case 2, retry after lost acknowledgement | A | $100 → X | crewAI's own re-dispatch of case 1 (the tool commits, then raises) | DUPLICATE | 1 |
| case 3, second intentional payment | B | $100 → X | separate `ToolUsage.use()` | EXECUTE | 2 |
| case 4, drifted retry | A | $125 → X | separate `ToolUsage.use()` (model re-proposal) | CONFLICT | 2 |

Case 4 is a separate call on purpose: crewAI's re-dispatch always resends
the identical `ToolCalling`, so a retry with different arguments can only
come from above `ToolUsage` (see `harness.run_single_tool_call`).

Keys, payloads and the artifact come from `../idempotency-ref-v1.1/vectors.json`.
The verifier checks that the `idempotency_ref` and `admitted_payload_digest`
computed from the arguments crewAI delivered to the tool are the vector's,
byte for byte. `admitted_payload_digest` stays outside the artifact, as the
spec requires.

## Negatives

The same crewAI path, with each non-conformant guard described by the
vectors' negatives. Each one first diverges exactly where its vector says:

| Negative | Guard mode | First divergence |
|---|---|---|
| content-derived key (Invariant 6) | `content_key` | case 3 → DUPLICATE, 1 effect (payment B never happens) |
| no digest check, v1.0 ledger (Invariant 7) | `no_digest_check` | case 4 → DUPLICATE, 2 effects (drift passes silently) |
| digest inside the ref preimage | `digest_inside` | case 4 → EXECUTE, 3 effects |

## Files

- `logical_identity_guard.py` — v1.1 decision rule (EXECUTE / DUPLICATE /
  CONFLICT) keyed by `idempotency_ref`, admission recorded before the
  effect; plus the three non-conformant modes.
- `logical_identity_case.py` — the four events through crewAI, one mode per run.
- `harness.py` — `run_tool_call_under_real_crewai_retry`: the existing
  re-dispatch driver, for tools with more than `logical_action_id` in their
  arguments.
- `verify_logical_identity.py` — conformance runner, same convention as
  `verify.py` / `verify_argument_mismatch.py` / `verify_restart.py`.

```
$ python3 verify_logical_identity.py
crewai-unguarded-retry / idempotency-ref v1.1 logical identity -- 4 cases + 3 negatives
  [PASS] case-1-first-intentional: EXECUTE, effects=1, ref/digest match vectors
  [PASS] case-2-retry-same-payload: DUPLICATE, effects=1, ref/digest match vectors
  [PASS] case-3-second-intentional-same-payload: EXECUTE, effects=2, ref/digest match vectors
  [PASS] case-4-drifted-retry: CONFLICT, effects=2, ref/digest match vectors
  [PASS] negative-content-derived-key (content_key): diverges at case-3-second-intentional-same-payload -> DUPLICATE, effects=1
  [PASS] negative-no-digest-check (no_digest_check): diverges at case-4-drifted-retry -> DUPLICATE, effects=2
  [PASS] negative-digest-inside-artifact (digest_inside): diverges at case-4-drifted-retry -> EXECUTE, effects=3

ALL CHECKS PASS
```

Requires crewai (tested with crewai==1.15.21).
