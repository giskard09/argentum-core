# governance-block-join-ref-v1

Binds a signed, content-addressed evidence object (the governance block) to
the terminal record of a runtime dispatch, so a verifier checks one authority
path instead of reconciling two independently-generated sources of truth.

## Problem

A runtime that emits governance evidence (signed facts: data version, canon
profile, authority chain, fixture version) and a separate terminal record
(what happened at the dispatch boundary: bucket, policy decision) can let
the two drift. If either object can be generated without reference to the
other, replay analysis has to reconcile two authorities instead of checking
one. A terminal record that merely *coexists* with a governance block is not
the same guarantee as a terminal record that *names* the governance block it
relied on and can be recomputed from it.

## Two layers

**governance_block** — the signed and content-addressed evidence surface.
Carries `data_version_hash`, `canonicalization_profile_id`, `authority_chain`,
`fixture_id`/`schema_version`, and optional support metadata. Portable: does
not carry operational/dispatch state.

**terminal_envelope** — the dispatch-boundary record. Carries `operation_id`,
`proposed_call_digest`, `effective_call_digest`, `evaluated_fixture_id`,
`terminal_bucket`, `policy_decision`, and `governance_block_digest` — the
digest of the governance_block it relied on.

## JCS preimage shapes

```json
// governance_block
{
  "authority_chain": ["<string>"],
  "canonicalization_profile_id": "<string>",
  "data_version_hash": "<sha256-hex>",
  "fixture_id": "<string>",
  "schema_version": "<string>",
  "ts_ms": <integer>,
  "version": "governance-block-join-ref-v1"
}

// terminal_envelope
{
  "effective_call_digest": "<sha256-hex>",
  "evaluated_fixture_id": "<string>",
  "governance_block_digest": "<sha256-hex>",
  "operation_id": "<string>",
  "policy_decision": "allow | deny | warn | escalate | transform",
  "proposed_call_digest": "<sha256-hex>",
  "terminal_bucket": "<string>",
  "ts_ms": <integer>,
  "version": "governance-block-join-ref-v1"
}
```

`governance_block_digest` is `SHA-256(JCS(governance_block))`, computed under
the profile named in `governance_block.canonicalization_profile_id`.

## Invariants

1. **recomputability** — `governance_block_digest` in the terminal_envelope
   equals `SHA-256(JCS(governance_block))` recomputed independently by the
   verifier from the governance_block object itself.
2. **lossless_projection** — `terminal_envelope` is a projection over
   `governance_block` plus the proposed/effective call envelope: the same
   `governance_block_digest` combined with the same
   `(proposed_call_digest, effective_call_digest)` pair must always produce
   the same `terminal_bucket`. Two terminal_envelope records that share both
   inputs but disagree on `terminal_bucket` cannot both be conformant.
3. **single_authority_path** — a verifier checks governance_block →
   recompute digest → confirm terminal_envelope names it → confirm
   lossless_projection. It never accepts a terminal_envelope whose
   governance_block_digest does not resolve to a governance_block the
   verifier can independently recompute.

## Failure code taxonomy

| code | condition |
|---|---|
| `JOINED_AND_CONSISTENT` | governance_block recomputes; terminal_envelope names it; projection is deterministic against any other record sharing the same inputs |
| `GOVERNANCE_BLOCK_DIGEST_MISMATCH` | recomputed digest of governance_block does not equal `governance_block_digest` named in terminal_envelope |
| `SPLIT_AUTHORITY` | two terminal_envelope records share `governance_block_digest` + `(proposed_call_digest, effective_call_digest)` but disagree on `terminal_bucket` |
| `ORPHAN_TERMINAL_ENVELOPE` | terminal_envelope names a `governance_block_digest` for which no governance_block object is available to the verifier |
| `UNSUPPORTED_CANONICAL_PROFILE` | `canonicalization_profile_id` is present but not implemented by the verifier |

## Relationship to existing primitives

- `execution-join-ref-v1` — same dispatch-boundary lineage concern
  (action_ref → decision_id → attempt_id → result_id), narrower scope
  (single guardrail decision, not a general signed evidence object). A
  governance_block can carry an execution-join-ref chain as one of its
  signed facts; this spec does not replace that chain, it generalizes the
  join contract to any signed evidence surface.
- `evidence-mode-disclosure-ref-v2` — covers producer-disclosed vs
  referee-verified evidence mode (hint/anchor vectors). Complementary:
  disclosure-ref answers "is this evidence mode earned or merely claimed";
  this spec answers "does the terminal record actually derive from the
  evidence it names."
- `anchoring-precedence-ref-v1` — optional outer layer once a
  governance_block exists; existence ≠ precedence still applies.
