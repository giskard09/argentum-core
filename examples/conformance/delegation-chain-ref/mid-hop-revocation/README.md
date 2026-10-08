# delegation-chain-ref · mid-hop-revocation

A structural differential set, the first of the two vector classes owed on
x402-foundation/x402#2332 (scope agreed in comments 5878267660, 5887938781
and 5890759053; restated in 5940312632). It extends `revoked-ancestor/`
rather than replacing its result: the same chain and leaf bytes are verified
with and without a revocation artifact for the mid-chain hop, and a
broken-continuity control is verified the same two ways.

## What it exercises

3-hop chain, narrowing at the leaf hop:

```
agent-a -> agent-b -> agent-c -> agent-d
mycelium:payment -> mycelium:payment -> mycelium:payment:route
```

The revocation artifact revokes `hops[1]` (agent-b's grant to agent-c) at
`2026-10-03T09:00:00.000Z`, before the leaf action at
`2026-10-05T12:00:00.000Z`. It targets the hop with `revoked_delegation_ref`,
the field merged in [PR #112](https://github.com/giskard09/argentum-core/pull/112)
(commit `c277309b`), and carries no `revoked_action_ref`. That is the
difference from `revoked-ancestor/`, which predates the field and uses
`revoked_action_ref` as a documented stand-in.

| Vector | Revocation artifact | Expected |
|--------|--------------------|----------|
| `mid-hop-revocation-001-baseline` | absent | PASS |
| `mid-hop-revocation-001-with-revocation` | present, for `hops[1]` | PASS |
| `mid-hop-revocation-002-broken-continuity-baseline` | absent | FAIL, `chain_break at hop 1` only |
| `mid-hop-revocation-002-broken-continuity-with-revocation` | present, same artifact | FAIL, `chain_break at hop 1` only |

The control chain keeps `hops[0]` and `hops[1]` byte-identical to chain 001
and has `hops[2]` granted by `agent-x` instead of `agent-c`. Its
`delegation_chain_ref` is recomputed over the broken artifact, so
`chain_break` is the only failure the reference verifier reports, with or
without the revocation artifact.

Every vector runs against a fresh replay registry. The two vectors of a pair
are two independent submissions of the same chain, not a resubmission.

## What it asserts, and what it does not

It asserts one thing: revocation metadata for an ancestor hop neither changes
a passing structural verdict nor masks a failing one. The reference verifier's
checks (`delegation_chain_ref` byte-match, `chain_continuity`,
`root_anchoring`, `leaf_anchoring`, `monotonic_scope_narrowing`,
`hop_signature_valid`, `replay_detected`) are computed from `chain_artifact`
and `leaf_preimage` alone; none reads `revocation_artifact`,
`revocation_ref` or `revoked_delegation_ref`.

It does not assert that the chain still authorizes the leaf after the
revocation (present authority), that descendants of a revoked hop are to be
rejected (cascade), or that future use of the chain is blocked. Those are
policy questions outside the structural verdict; AAE-02 §7.5 and the
enforcement layer giskard09 describes in comment 6028975132 sit there, not
here. `parent_delegation_ref` resolution is not exercised either.

## Runner

`verify.py` is not a copy of the reference verifier. It loads
`../verify.py`, the reference verifier at the commit being run, and calls its
`evaluate_vector()`, so the verdicts printed are the reference verifier's own.
Before that it checks fixture integrity: byte-identical `chain_artifact` and
`leaf_preimage` within each pair, `revocation_ref` recomputing from the
artifact, `revoked_delegation_ref` equal to `hops[1].delegation_ref`, no
`revoked_action_ref` present, `revocation_action_ref` recomputing from its
preimage. After the vectors it prints the differential per pair. Exit status
is non-zero if any of the three stages fails; flipping any `expected` turns
it red.

`build.py` regenerates `vectors.json` byte for byte, deriving every digest
with the reference verifier's own `jcs`, `sha256hex` and
`compute_action_ref`.

## Run

```
pip install -r ../requirements.txt
python3 verify.py
```

Expected: `4/4 passed`, and both lines of the differential check `True`.

## Provenance

Authored by TKCollective (Tanilo) for
x402-foundation/x402#2332. The differential question comes from MoltyCel's
test (comment 5995057822 and earlier); the field this set targets was
proposed by giskard09 (comment 5887938781) and merged in #112 at the
request of TKCollective (comment 5890759053). `verification_mode` is
`asserted`, which classifies the result as structurally decidable (content-addressed,
operator-independent) per `docs/spec/verification-semantics.md`; it does not count
reproductions. Reproductions are listed under `provenance.independently_reproduced_by`
in `vectors.json`.
