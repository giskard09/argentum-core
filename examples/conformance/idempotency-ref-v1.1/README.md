# idempotency-ref-v1.1 — four-case logical-identity vectors

Spec: [`docs/spec/idempotency-ref.md`](../../../docs/spec/idempotency-ref.md), section *Logical identity and admitted payload (v1.1)*, Invariants 6 and 7.

Same payload can be new work; same identity cannot drift.

| Event | key | payload | Expected | Effects |
|---|---|---|---|---|
| `case-1-first-intentional` | A | $100 → merchant_x | EXECUTE | 1 |
| `case-2-retry-same-payload` | A | $100 → merchant_x | DUPLICATE | 1 |
| `case-3-second-intentional-same-payload` | B | $100 → merchant_x | EXECUTE | 2 |
| `case-4-drifted-retry` | A | $125 → merchant_x | CONFLICT | 2 |

Events are replayed in order against one ledger, all within `window_ms`.
`idempotency_ref = SHA-256(JCS(idempotency_artifact))`; `admitted_payload_digest = SHA-256(JCS(admitted_payload))`, carried next to the ref, never inside the artifact.

Negatives — each one fails on a different check:

| Negative | Violates | First divergence |
|---|---|---|
| `negative-content-derived-key` | Invariant 6 | case 3 → DUPLICATE (B never paid) |
| `negative-no-digest-check` | Invariant 7 | case 4 → DUPLICATE (drift passes silently) |
| `negative-digest-inside-artifact` | Derivation | case 4 → EXECUTE (third effect) |

What `verify.py` checks: both hashes of every event, that the digest stays outside the artifact, the decision rule over the four cases, and that each negative diverges exactly where it declares. It does not check provider-side reconciliation or `window_ms` expiry.

```
python3 build.py    # regenerates vectors.json (deterministic)
python3 verify.py   # exit 0 = all checks pass
```

Credits: four-case test by impartshadow/agent-contracts ([crewAIInc/crewAI#5802](https://github.com/crewAIInc/crewAI/issues/5802), comment 5790417981); regression by stringsofthemind-oss ([stringsofthemind-oss/once#45](https://github.com/stringsofthemind-oss/once/pull/45)).
