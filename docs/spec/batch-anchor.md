# Batch anchoring: Merkle rollup over AnchorRegistry

`AnchorRegistry.anchor(bytes32)` (Base/Arbitrum/Ink, CREATE2 address
`0x49fEcA52bC634a9Ab773226D16619deC547794aa`) is permissionless and generic —
it commits any 32-byte value, with no opinion on what that value means. This
document defines a second way to use it: commit a Merkle root over many
`action_ref` digests in one transaction, instead of one `anchor()` call per
`action_ref`.

No contract change. No new on-chain primitive. `anchor(bytes32)` already
accepts a Merkle root the same way it accepts a single `action_ref` — the
value is opaque to the contract either way.

## Motivation

Detected 2026-07-31: StelarDigital (x402-receipts v0.5.1, commit `debc94f`)
shipped a two-layer pattern — per-action anchor immediate + a cheaper batch
rollup on top, with `buildMerkleTree`/`getProof`/`verifyInclusion` in their
own repo. We had only the per-action layer. This document and
`plugins/agt_evidence_anchor/merkle.py` close that gap using our own leaf
digest (`action_ref`, unchanged) — not StelarDigital's preimage format, and
not their code.

## Leaf construction

Each leaf is an existing `action_ref` (docs/spec/action-ref.md):

```
action_ref = SHA-256(JCS({agent_id, action_type, scope, timestamp}))
```

No new preimage format. A batch is simply a list of `action_ref` values that
already exist as individual trail records — batching does not change how any
individual `action_ref` is computed or what it means.

## Tree construction

Implemented in `plugins/agt_evidence_anchor/merkle.py`:

- `build_merkle_tree(action_refs: list[str]) -> MerkleTree`
- `get_proof(action_ref: str, tree: MerkleTree) -> list[str]`
- `verify_inclusion(action_ref: str, proof: list[str], root: str) -> bool`

Construction rules (see module docstring for full rationale):

- **Domain separation** — leaf hashes prefixed `0x00`, internal node hashes
  prefixed `0x01` (RFC 6962 §2.1 style), so a leaf can never be mistaken for
  an internal node in a forged proof.
- **Sorted-pair hashing** — sibling pairs hashed in sorted byte order at
  every level, so `verify_inclusion` needs only the sibling hash list, no
  left/right direction bits.
- **Odd node carried up unhashed** — no duplicate-last-leaf padding, which
  avoids a known class of forged-inclusion bug for the padding node.

## Anchoring the root

Zero new infrastructure. The root is a `bytes32` like any other — it goes
through the same existing flow as a single `action_ref`:

- Python/owner-key or signer-vault path: `arb_pay.anchor_action_ref(root_hex)`
  (GiskardPayments `markUsed`, Arbitrum One).
- Worked-example / AnchorRegistry path: `cast send <AnchorRegistry> "anchor(bytes32)" 0x<root>`
  (see any `*-action-ref-anchor` repo's `scripts/anchor.sh` for the exact
  pattern — same registry, same call, root instead of a single leaf).

No new signing path, no new contract ABI, no new environment variable.

## What a batch root proves

- Every `action_ref` a caller can produce a valid `get_proof()` for was
  included in the leaf set at the time the root was built.
- The root itself, once anchored, is tamper-evident the same way any other
  anchored `bytes32` is (immutable on-chain timestamp + `anchoredBy`).

## What a batch root does NOT prove

- **It does not prove the individual `action_ref` is legitimate.** Inclusion
  in an anchored root proves existence-in-the-rollup, not that the
  underlying action happened, or happened as claimed. Each leaf still needs
  to be independently recomputable by a verifier from its own preimage
  fields (`agent_id`, `action_type`, `scope`, `timestamp`) — exactly as a
  single-leaf `action_ref` requires today. Batching changes nothing about
  that requirement; it only changes how many `anchor()` calls it takes to
  commit many of them.
- **It does not prove the leaf set is complete or honest.** A root only
  commits to whatever list of `action_ref` values was passed to
  `build_merkle_tree`. An operator who omits a leaf from the batch leaves no
  trace in the resulting root — absence of a leaf from one root is not
  evidence the corresponding action never happened, only that it was not
  included in *this* rollup (same non-overclaim discipline as
  `guarantee-model.md`'s trail-status table: a missing signal is a missing
  signal, not a negative result).
- **It does not retroactively date the individual action.** The batch root's
  on-chain timestamp bounds when the rollup was anchored, not when any
  individual leaf's underlying action occurred — that timing claim, if
  made, still rests on the leaf's own `timestamp` field and whatever
  independent trail record backs it.

## Conformance vectors

`plugins/agt_evidence_anchor/tests/test_merkle.py`:

- **Positive** — build a tree from N `action_ref` values, extract a proof for
  one, verify inclusion against the tree's own root: `True`.
- **Negative (leaf not in tree)** — `get_proof` on an `action_ref` never
  passed to `build_merkle_tree` raises `ValueError` (there is nothing to
  prove membership of).
- **Negative (tampered proof)** — a valid proof for leaf A, checked against
  leaf B's expected root, or with one sibling hash flipped, returns `False`
  from `verify_inclusion` — never an exception, never a silent pass.
