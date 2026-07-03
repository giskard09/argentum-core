# transition-sufficiency-ref-v1

Gives a verifier a recomputable set-inclusion check —
`Required(τ) ⊆ Supported(τ)` — for whether a decision record actually has
the support it needs, instead of accepting an assertion that it does.

## Problem

`governance-block-join-ref-v1` recomputes a digest and confirms a terminal
record names it. That answers "does this record derive from the evidence it
claims." It does not answer a related but distinct question: given a
decision record and a verifier profile, is the set of support items the
decision *actually has* a superset of the set it *needs*? Two asserted
hashes — one for what's required, one for what's supported — do not answer
that question; they only confirm someone computed each set once. A verifier
that stops at "both hashes are well-formed" has not checked inclusion, it
has checked that two lists exist.

## Fields

**decision_record_id** — identifies the decision record this sufficiency
check is evaluated against. Opaque reference; the verifier resolves it to
retrieve `required_support_items` and `supported_support_items` from the
decision's own evidence surface, not from this record's assertion of them.

**verifier_profile_id** — the profile under which required/supported items
are compared. Different profiles may have different notions of what an
item is (see "inclusion_operator" below); a check computed under one
profile is not portable to another without recomputation.

**required_support_items** — the set of items `Required(τ)`: content-
addressed identifiers (e.g. hashes of support artifacts) that the decision
record needs present to be considered adequately supported.

**supported_support_items** — the set of items `Supported(τ)`: content-
addressed identifiers actually attached to the decision record.

**missing_support_items** — `Required(τ) \ Supported(τ)`, recomputed as a
set difference, not asserted independently. Non-empty exactly when
`inclusion_result` is `INSUFFICIENT`.

**inclusion_operator** — names the comparison used (e.g. `set_subset`).
Present because "inclusion" is not always plain set containment — a profile
may define equivalence classes over items (e.g. two hashes that resolve to
the same superseded/superseding profile pair, per
`profile_registry.py`'s `SUPERSEDED` map, count as the same item). The
operator is what the verifier must implement to recompute inclusion
correctly; it is not just documentation.

**inclusion_recomputed** — boolean. True only if the verifier independently
recomputed `missing_support_items` from `required_support_items` and
`supported_support_items` under `inclusion_operator`, rather than trusting
the value another party asserted.

**inclusion_result** — `SUFFICIENT` if `missing_support_items` is empty
after recomputation, `INSUFFICIENT` otherwise.

## JCS preimage shape

```json
{
  "decision_record_id": "<string>",
  "verifier_profile_id": "<string>",
  "required_support_items": ["<sha256-hex>", "..."],
  "supported_support_items": ["<sha256-hex>", "..."],
  "inclusion_operator": "set_subset",
  "ts_ms": <integer>,
  "version": "transition-sufficiency-ref-v1"
}
```

`missing_support_items`, `inclusion_recomputed`, and `inclusion_result` are
not part of the preimage — they are the verifier's *output*, computed from
the fields above. A record that includes them as asserted input fields
rather than recomputed output has not met the invariant below.

## Invariants

1. **recomputability** — `missing_support_items` equals
   `required_support_items` minus `supported_support_items`, evaluated
   under `inclusion_operator`, computed by the verifier itself. A verifier
   that accepts an asserted `missing_support_items` field without
   recomputing it has not checked sufficiency.
2. **asserted-hashes-insufficient** — two well-formed hashes,
   `required_support_hash` and `supported_support_hash` (digests of the two
   sets), do not establish `inclusion_result`. Matching hashes only confirm
   the sets were transmitted intact; they say nothing about whether one is
   a subset of the other. A verifier must have the item-level sets, not
   just their digests, to compute inclusion.
3. **profile-bound comparison** — `inclusion_operator` and
   `verifier_profile_id` travel together. Recomputing inclusion under a
   different operator than the one named is not conformant, even if both
   operators are individually well-defined.

## Failure code taxonomy

| code | condition |
|---|---|
| `SUFFICIENT` | recomputed `missing_support_items` is empty |
| `INSUFFICIENT` | recomputed `missing_support_items` is non-empty |
| `INCLUSION_NOT_RECOMPUTED` | verifier accepted an asserted `inclusion_result` without independently computing set difference from item-level sets |
| `UNSUPPORTED_INCLUSION_OPERATOR` | `inclusion_operator` is present but not implemented by the verifier |
| `UNRESOLVABLE_DECISION_RECORD` | `decision_record_id` does not resolve to a decision record the verifier can retrieve required/supported items from |

## Relationship to existing primitives

- `governance-block-join-ref-v1` — answers "does the terminal record derive
  from the evidence it names"; this spec answers a different question,
  "given the evidence the record derives from, was it actually enough."
  A governance_block can carry `required_support_items` /
  `supported_support_items` as one of its signed facts; this spec does not
  replace that join, it adds a sufficiency check on top of it.
- `profile_registry.py` `SUPERSEDED` map — an `inclusion_operator` that
  treats a superseded profile_id and its superseding replacement as
  equivalent items is one concrete instance of a non-trivial
  `inclusion_operator`; plain `set_subset` treats them as distinct.
- `conformance-maturity-ref-v1` — unrelated axis. That spec grades how a
  conformance *claim* was verified; this spec checks whether a *decision
  record* has the support it needs. Both can apply to the same object
  without interacting.
