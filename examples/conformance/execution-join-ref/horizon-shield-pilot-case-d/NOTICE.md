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

Scoping context: `ogasurfproject-jpg/horizon-shield#51` (2026-10-18),
which freezes the pilot's inputs and explicitly invites this: *"Any other
project that wants to run its approach on the same workflow is welcome; the
inputs below do not change for that."*

`post_commit_consistency` is this repo's own invariant
(`docs/spec/execution-join-ref-v1.md`, "Post-commit divergence (v1.1)"),
built the same day for a different domain (astrogilda/
`probityai/agent-evidence#26`, file-write approvals) — composed here onto
the pilot's shape as a worked example, not adopted from any external
source.
