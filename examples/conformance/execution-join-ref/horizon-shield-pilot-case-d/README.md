# Case D: post-commit divergence, composed onto the HORIZON SHIELD pilot

Proposed fourth case for the live pilot scoped in
[`ogasurfproject-jpg/horizon-shield#51`](https://github.com/ogasurfproject-jpg/horizon-shield/issues/51)
(aeoess, ogasurfproject-jpg, babyblueviper1 — one paid audit call, three sets
of receipts). The issue explicitly welcomes this: *"Any other project that
wants to run its approach on the same workflow is welcome; the inputs below
do not change for that."*

**This is a worked example, not a PR to their repos.** It adopts the
`request_occurrence`/`task`/`execution-receipt` object shapes frozen in
`COMPANION_v0.md` / `PILOT_v0.md` at the pinned commit (see `NOTICE.md`), and
composes `execution-join-ref-v1`'s `post_commit_consistency` invariant
(this repo, `docs/spec/execution-join-ref-v1.md`, "Post-commit divergence
(v1.1)", PR#137, 2026-10-18) on top of them. No code or spec of theirs is
modified.

## What the pilot's own cases A/B/C cover

All three are about the moment of the chain of receipts itself:

- **A. within** — paid, executed, accepted, all at the call.
- **B. acceptance fails** — a deliberately mismatched deliverable under the
  same occurrence.
- **C. budget exceeded** — a second call takes the running total over the
  issuer's budget.

## The gap case D fills

None of A/B/C answer: what if the JCCDB cost database the estimate was
audited against — or the deliverable itself — changes **after** A already
closed validly? The original payment, execution, and acceptance records are
not wrong; nobody misstated anything when they signed. What's needed is a
**separate, later** record naming the divergence, without collapsing the two
states into one. That is exactly what `post_commit_consistency` /
`POST_COMMIT_DIVERGENCE` was built for earlier the same day, in a different
domain (file-write approvals, for astrogilda/`probityai/agent-evidence#26`) —
the same primitive, reused here as a worked example of its domain-generality.

## Explicit scope limit

This worked example computes exactly **one** invariant:
`post_commit_consistency` (does a later, independent observation of the
audited output still match the `response_sha256` the execution-receipt
committed to at settlement?). It does **not** reimplement:

- **Authority and payment** (MUSUBI / APS) — budget, delegation, payment
  rail. Declared `true` in both vectors, not recomputed.
- **Acceptance** (babyblueviper1's work-acceptance-record) — criteria
  committed before the call, checked after, signed by the checker key.
  Declared `true` in both vectors, not recomputed.

This is a fourth, complementary check, additive to the three roles the
pilot's own participants already cover — not a competing implementation of
any of them.

## Reproduce

```
python3 verify.py
```

2/2 vectors pass: `case-a-within-paid-accepted-001` (happy path, shows the
new invariant does not interfere) and
`case-d-jccdb-snapshot-divergence-001` (the new case — `canonical_envelope`,
`chain_integrity`, `authority_and_payment`, `acceptance` all stay `true`;
only `post_commit_consistency` fails, `POST_COMMIT_DIVERGENCE`).

See `NOTICE.md` for the exact source pin of the object shapes this adopts.
