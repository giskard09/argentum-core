# Case E: post-commit divergence, composed onto the HORIZON SHIELD pilot

Proposed fourth case for the live pilot scoped in
[`ogasurfproject-jpg/horizon-shield#51`](https://github.com/ogasurfproject-jpg/horizon-shield/issues/51)
(aeoess, ogasurfproject-jpg, babyblueviper1 — one paid audit call, three sets
of receipts). The issue explicitly welcomes this: *"Any other project that
wants to run its approach on the same workflow is welcome; the inputs below
do not change for that."*

Named **Case E**, not Case D: ogasurfproject-jpg's own Case D in this issue
is astrogilda's (the same call contents under a different request
occurrence, frozen at `33c22f5a`) — renamed on their request after they
reviewed the first version of this example (comment, 2026-10-18T15:34:49Z).

**This is a worked example, not a PR to their repos.** It adopts the
`request_occurrence`/`task`/`execution-receipt` object shapes frozen in
`COMPANION_v0.md` / `PILOT_v0.md` at the pinned commit (see `NOTICE.md`), and
composes `execution-join-ref-v1`'s `post_commit_consistency` invariant
(this repo, `docs/spec/execution-join-ref-v1.md`, "Post-commit divergence",
PR#137, 2026-10-18) on top of them. No code or spec of theirs is modified.

## Real data, not stand-ins

The first version of this example used synthetic stand-in values
(`amount` 10 in a made-up unit, a `seen_block` with a zero hash, a
`response_sha256` the endpoint never returned). ogasurfproject-jpg pointed
out that the real, deployed system had already produced exactly this case
on its own, with nobody at fault: the same fixture audited against souba-db
2.2.0 and then again after 2.3.0 corrected six price ranges the same day
gives two different, real response hashes for the same call. This revision
uses those two real audits — see `NOTICE.md` for the exact source pins and
the independent byte/hash verification performed before using them.

## What the pilot's own cases A/B/C cover

All three are about the moment of the chain of receipts itself:

- **A. within** — paid, executed, accepted, all at the call.
- **B. acceptance fails** — a deliberately mismatched deliverable under the
  same occurrence.
- **C. budget exceeded** — a second call takes the running total over the
  issuer's budget.

## The gap case E fills

None of A/B/C answer: what if the JCCDB cost database the estimate was
audited against — or the deliverable itself — changes **after** A already
closed validly? The original payment, execution, and acceptance records are
not wrong; nobody misstated anything when they signed. What's needed is a
**separate, later** record naming the divergence, without collapsing the two
states into one. That is exactly what `post_commit_consistency` /
`POST_COMMIT_DIVERGENCE` was built for earlier the same day, in a different
domain (file-write approvals, for astrogilda/`probityai/agent-evidence#26`) —
the same primitive, reused here as a worked example of its domain-generality,
now against the pilot's own real divergence (souba-db 2.2.0 → 2.3.0).

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

## Known gap: no committed `dataset_sha256` on the settlement side

ogasurfproject-jpg also suggested a `dataset_sha256` field on
`post_commit_observation` naming the dataset an observation was recomputed
against, so a reader can tell "the responder changed behavior on an
unchanged dataset" apart from "the dataset itself moved (expected,
anchored)" without the two looking identical. That field is now part of
`execution-join-ref-v1.2` (additive, optional, informational — see
`docs/spec/execution-join-ref-v1.md`, "Post-commit divergence") and is used
in both vectors below. What the spec does **not** yet define is a matching
field on the *settlement* side (the `execution_receipt`/`result_id` the
observation is compared against) naming which dataset *that* commitment
used — without it, a reader still has to trust the observation's own
`dataset_sha256` rather than compare it against a committed one. Noted here
as a known gap, not promised for any date.

## Reproduce

```
python3 verify.py
```

2/2 vectors pass: `case-a-within-paid-accepted-001` (happy path, real
committed `dcbdc5d2` data, shows the new invariant does not interfere) and
`case-e-jccdb-snapshot-divergence-001` (the real divergence —
`canonical_envelope`, `chain_integrity`, `authority_and_payment`,
`acceptance` all stay `true`; only `post_commit_consistency` fails,
`POST_COMMIT_DIVERGENCE`).

See `NOTICE.md` for the exact source pins of the object shapes and real
data this adopts.
