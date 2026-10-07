# delegation-chain-ref · partial-chain-recovery

The second of the two vector classes owed on x402-foundation/x402#2332
(scope agreed in comments 5878267660, 5887938781 and 5890759053; restated
in 5940312632). "Recovery" here means restoring missing chain bytes, not
recovering authority: a valid chain has its `delegation_chain_ref` held
fixed, the middle hop is omitted from `chain_artifact`, and the vectors show
what the reference verifier does as the hop is restored, exactly and
otherwise, and what the replay guard does along the way.

## What it exercises

3-hop chain, narrowing at the leaf hop, `delegation_chain_ref` =
`89b3d386856f9bf5de561f4d6f4eaaa07917d7fd06ef7874df46c802b8763b14`, held
fixed in every vector:

```
agent-a -> agent-b -> agent-c -> agent-d
mycelium:payment -> mycelium:payment -> mycelium:payment:route
```

Vectors MUST be run in order against one replay registry that starts empty;
registry state carries across the file, as in `../replay-vectors.json`.

| # | Vector | `hops` supplied | Expected | Registry after |
|---|--------|-----------------|----------|----------------|
| 1 | `recovery-001-missing-hop` | `[h0, h2]` | FAIL: `delegation_chain_ref mismatch` and `chain_break at hop 0` | empty |
| 2 | `recovery-002-substituted-hop-control` | `[h0, h1', h2]` | FAIL: `delegation_chain_ref mismatch` only, never `chain_break` | empty |
| 3 | `recovery-003-misplaced-hop-control` | `[h0, h2, h1]` | FAIL: `delegation_chain_ref mismatch` and `chain_break at hop 0` (others fire too) | empty |
| 4 | `recovery-004-exact-restoration` | `[h0, h1, h2]` | PASS | 1 chain_id, 3 delegation_refs |
| 5 | `recovery-005-resubmission-after-restoration` | `[h0, h1, h2]` | FAIL: `replay_detected` | unchanged |

`h1'` in vector 2 has the same delegator, delegatee and scope as the missing
hop but a different `delegation_ref` (a re-issued grant with
`policy_version` `2026-10-02`; the artifact is in the vector as
`substitute_delegation_artifact`). Continuity is satisfied again, so the
only failure is the digest: restoration has to be the exact bytes, not a hop
that merely makes the chain continuous. Vector 3 supplies the exact hop in
the wrong position; `hops` order is semantic (`HOPS_REORDERED` in
`delegation-chain-ref.md`), so the digest does not match either.

Vectors 1 to 3 fail and are not recorded, per the reference verifier's
recording-order rule (record only after every other check has passed). That
is why vector 4, the first valid submission, is accepted under the original
reference and only then recorded. Vector 5 is byte-identical to vector 4 and
is rejected by the replay guard alone. The agreed three-step sequence
(FAIL, PASS after exact restoration, replay_detected) is vectors 1, 4 and 5;
vectors 2 and 3 are additional controls on the word "exact".

## What it asserts, and what it does not

It asserts byte restoration under the original commitment, and that failed
attempts do not consume replay state. It does not assert recovery of
authority, automatic retrieval of missing delegation artifacts, renewed
authority after a revocation, or anything about `parent_delegation_ref`
resolution, which the spec describes for backward traversal but does not
define for a missing link; that remains a separate open question (comment
5887938781, point 3).

## Runner

`verify.py` is not a copy of the reference verifier. It loads
`../verify.py`, the reference verifier at the commit being run, and calls its
`evaluate_vector()` in file order against one `SeenRegistry`. Before that it
checks fixture integrity: the fixed reference recomputes from
`original_chain_artifact`; vector 1's hops are the original minus the middle
one; vector 2 differs from the original only in `hops[1].delegation_ref`,
which recomputes from `substitute_delegation_artifact`; vector 3 holds
exactly the original hop objects in another order; vector 4 is byte-identical
to `original_chain_artifact`; vector 5 is byte-identical to vector 4. After
each vector it prints the registry size and compares it with
`expected_registry_after`. Exit status is non-zero if any check fails;
flipping any `expected`, reordering vectors 4 and 5, or claiming a failed
attempt was recorded turns it red.

`build.py` regenerates `vectors.json` byte for byte, deriving every digest
with the reference verifier's own `jcs`, `sha256hex` and
`compute_action_ref`.

## Run

```
pip install -r ../requirements.txt
python3 verify.py
```

Expected: `5/5 passed`.

## Provenance

Authored by TKCollective (Tanilo) for
x402-foundation/x402#2332. The reading of "recovery" as restoration of
missing `chain_artifact` bytes, with the `parent_delegation_ref` path left
open, was agreed with giskard09 (comment 5887938781). `verification_mode`
is `asserted`: the result above was produced by the author with the
reference verifier and has not yet been reproduced by anyone else.
