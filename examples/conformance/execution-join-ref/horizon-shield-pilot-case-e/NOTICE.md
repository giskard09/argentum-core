The object shapes this worked example adopts (`request_occurrence`, `task`,
`execution-receipt`) are defined in, and cited from, the following files of
`ogasurfproject-jpg/horizon-shield`, commit `4d720ace` (MIT License,
Copyright (c) 2026 The HORIZONs Co., Ltd.):

- `workers/hs-ledger/nenrin/musubi-v0/ca2a-companion-v0/COMPANION_v0.md`
  (section 4, "Request occurrence" and `execution-receipt.v0`)
- `workers/hs-ledger/nenrin/musubi-v0/ca2a-companion-v0/PILOT_v0.md`
  (section 3, `task`)

Field names and JCS object shapes (`type`, `caller`, `responder`, `lineage`,
`capability`, `occurrence_id`, `task_sha256`, `service`, `amount`, `unit`,
`nonce`, `request_sha256`, `seen_block`, `outcome`) are reproduced from
those documents, not invented. No code (`.py`) from that repository is
vendored or imported here — this worked example's `verify.py` is written
from scratch against the documented shapes, and intentionally declares
(rather than reimplements) the authority/payment/acceptance checks those
files' own reference verifiers (`companion_v0_1.py`, `pilot_v0.py`) perform.

`post_commit_consistency` is this repo's own invariant
(`docs/spec/execution-join-ref-v1.md`, "Post-commit divergence"), built
2026-10-18 for a different domain (astrogilda/`probityai/agent-evidence#26`,
file-write approvals) — composed here onto the pilot's shape as a worked
example, not adopted from any external source. The optional
`post_commit_observation.dataset_sha256` field (execution-join-ref-v1.2) was
suggested by ogasurfproject-jpg (see below) and added to the spec the same
day.

## Real data, not stand-ins (2026-10-18, after ogasurfproject-jpg's review)

The first version of this example (then named "Case D") used synthetic
stand-in values. ogasurfproject-jpg reviewed it (comment,
2026-10-18T15:34:49Z, after running `verify.py` at commit `9e28cdd`
themselves) and pointed out the real system had already produced this
exact case, asked for the name to change (their own Case D in this issue
is astrogilda's, frozen at `33c22f5a`), and suggested the `dataset_sha256`
field. This revision replaces every stand-in with real, sourced values:

**`task` and `request_occurrence` (both vectors), and Case A's
`execution_receipt` / `post_commit_observation.observed_hash`** are
byte-identical to `ogasurfproject-jpg/horizon-shield` commit `dcbdc5d2`:

- `workers/hs-ledger/nenrin/musubi-v0/ca2a-companion-v0/rehearsal/fixture.json`
- `workers/hs-ledger/nenrin/musubi-v0/ca2a-companion-v0/rehearsal/live_smoke/call.json`
- `workers/hs-ledger/nenrin/musubi-v0/ca2a-companion-v0/rehearsal/live_smoke/receipt.json`

Verified two ways before use: `git hash-object` on the fetched bytes matches
the blob SHA GitHub's own tree API reports for each file at `dcbdc5d2`
(`call.json` → `bbf2cda74…`, `receipt.json` → `4eb98a53f…`, `fixture.json`
→ `f5d4e9911…`), and this repo's own `jcs.py` independently recomputes
`task_sha256` (`218c938f…`), `request_sha256` (`69546501…`), and the audit
object's own hash (`c2920477…`, declared as `response_sha256`) from the
fetched content, matching the digests ogasurfproject-jpg quoted in the
issue thread.

**Case E's `execution_receipt`** (the first, pre-correction call, audited
against souba-db 2.2.0) reuses the same real `request_sha256`/`caller`/
`responder`/`capability`/`lineage` as above — ogasurfproject-jpg's own
words describing the second call were "the same test payer key and signed
test transfer as the first one," i.e. the same request, rerun later against
a newer dataset. Its `outcome.response_sha256`
(`ccfbae3d1fc006b61642da9d240f85c8b380fc10c8694d35d9f5043ca9d45df1`) and
`seen_block.height` (`971954`) are the full, untruncated values
ogasurfproject-jpg posted directly in the issue thread (comment,
2026-10-18T06:50:23Z) — not the truncated hex from the later summary
comment. **`signature` and `seen_block.hash` are deliberately absent, not
invented**: that call "was a smoke test, not a run: it was not logged and
no budget was charged" (ogasurfproject-jpg, same comment), so no file
exists anywhere with those bytes to cite. This worked example's
`verify.py` never reads either field, so the omission changes nothing it
computes.

**Case E's `post_commit_observation`** is the real, committed `dcbdc5d2`
rerun of the same request after souba-db 2.3.0 corrected six price ranges
the same day (comment, 2026-10-18T11:12:38Z) — the same `receipt.json`
cited above, read as a later observation of the earlier call rather than
as its own settlement. `dataset_sha256` names souba-db 2.3.0
(`7b16600e50ed73b844ff5b2718f04a6dd4d9ace0367982fb8d139db509d023fd`), also
quoted directly by ogasurfproject-jpg and matching the `dataset_sha256`
field already present on every line of the real `audit.json` this
`response_sha256` hashes.

Both dataset releases are independently anchored per ogasurfproject-jpg:
souba-db 2.2.0 as JIDEC entry 42 (Bitcoin block 966969), 2.3.0 as JIDEC
entry 114 (stamped the same night, confirmation pending at review time).

Scoping context: `ogasurfproject-jpg/horizon-shield#51` (2026-10-18),
which freezes the pilot's inputs and explicitly invites this: *"Any other
project that wants to run its approach on the same workflow is welcome; the
inputs below do not change for that."*
