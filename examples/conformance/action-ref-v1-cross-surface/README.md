# action-ref-v1 cross-surface scope-policy check

Institutionalizes the method aeoess (Pidlisnyi) used by hand in
[draft-etcheverry-action-ref#6](https://github.com/giskard09/draft-etcheverry-action-ref/issues/6)
(2026-08-25) to find bug #1 of [PR#62](https://github.com/giskard09/argentum-core/pull/62):
`docs/spec/action-ref.md`'s field table and its "Scope conventions" section
stated contradictory policies on whether `scope` may be `""` — and had for
10 days (commit 66df348, #48, 2026-08-15) before anyone noticed.

## What it checks

`check_scope_policy.py` extracts the `scope` field-table row and the
"Scope conventions" section's opening paragraph from `docs/spec/action-ref.md`
at a set of git refs, classifies each as STRICT (non-empty, no exception) or
PERMISSIVE (`""` allowed), and flags any ref where the two locations disagree
with each other.

```
python3 check_scope_policy.py                    # checks action-ref-v1.0, action-ref-v2.0, HEAD (committed)
python3 check_scope_policy.py --worktree          # HEAD reads the working tree instead of the last commit
python3 check_scope_policy.py <ref1> <ref2> ...   # check specific refs
```

## What it found (2026-08-25)

Running it against the two stable tags surfaced a **second, previously
unknown instance** of the same contradiction: the `action-ref-v1.0` tag
itself (2026-05-23) is internally inconsistent — same bug class as #48,
just older and undetected until this tool existed. That tag is cited
externally (Vauban Pay's `draft-vauban-x402-stark-receipts-01`) and declared
immutable in [RFC 002](../../../docs/rfcs/002-action-ref-v2-domain-separation.md#L100)
("`action-ref-v1.0` the git tag stays exactly as is"), so this is **not** a
code fix — it needs an errata decision (documentation-only, does not touch
the tag), flagged to dept-estrategia rather than resolved here.

`action-ref-v2.0` and current `main` are both internally consistent.

## What it does NOT check

It does not re-execute historical code — the pre-2026-07-29 refs predate
`plugins/agt_evidence_anchor/action_ref.py` entirely, so there is no
reference implementation to run at those points. It checks the spec TEXT's
internal consistency, which is what actually diverged in practice. Runtime
behavior of the *current* implementation is covered separately by the
executable vectors in
[`../action-ref-v1-domain-negative/`](../action-ref-v1-domain-negative/).

`plugins/agt_evidence_anchor/tests/test_action_ref.py::test_spec_scope_policy_self_consistent_on_main`
runs this same check against the working tree on every test run, so a future
edit to only one side of this duplicated statement fails CI immediately
instead of sitting silent for days. That test does not check the historical
tags — a tag failing this check needs a human errata decision, not an
automatic CI failure on an unrelated PR.
