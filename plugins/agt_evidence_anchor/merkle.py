"""
Batch anchoring: Merkle rollup over existing action_ref digests.

Anchors many trails under one AnchorRegistry.anchor(bytes32) call by
committing to a Merkle root instead of one action_ref per transaction.
anchor(bytes32) is unchanged and generic — a Merkle root is just another
bytes32. No new contract, no new on-chain primitive.

Leaves are existing action_ref digests (docs/spec/action-ref.md,
SHA-256(JCS({agent_id, action_type, scope, timestamp}))) — this module does
not define a new preimage format. It only combines already-computed digests
into a tree.

Domain separation (CT-style, RFC 6962 §2.1): leaf hashes are prefixed with
0x00, internal node hashes with 0x01, so a leaf digest can never collide
with an internal node digest fed back in as a "leaf". Without this, a
verifier could be tricked into accepting an internal node hash as if it
were a genuine leaf inclusion.

Pair ordering: sibling pairs are hashed in sorted (byte-lexicographic) order
at every level. This makes verify_inclusion() order-independent — a caller
does not need left/right direction bits alongside the proof, only the list
of sibling hashes.

Odd node at a level: carried up unhashed to the next level (no duplication).
Duplicating the last node is a known footgun (a level with an odd node
duplicated can let an attacker forge inclusion for a padding node that was
never a real leaf) — carrying it up avoids that class of bug entirely.

What this proves and does not prove: see docs/spec/batch-anchor.md.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

_LEAF_PREFIX = b"\x00"
_NODE_PREFIX = b"\x01"


def _leaf_hash(action_ref_hex: str) -> bytes:
    return hashlib.sha256(_LEAF_PREFIX + bytes.fromhex(action_ref_hex)).digest()


def _node_hash(left: bytes, right: bytes) -> bytes:
    a, b = sorted((left, right))
    return hashlib.sha256(_NODE_PREFIX + a + b).digest()


@dataclass
class MerkleTree:
    """Full set of levels, leaves[0] .. root[-1][0], for proof extraction.

    `action_refs` preserves the original input order so get_proof() can find
    a leaf's position. `levels[0]` is the leaf-hash level (post 0x00-prefix
    hashing, not the raw action_ref bytes); `levels[-1]` is `[root]`.

    The root depends on leaf *position*, not only the leaf set — building
    from the same action_refs in a different order produces a different
    root (standard for this pairwise construction). Sorted-pair hashing
    only removes the need for a direction bit within one sibling pair; it
    does not make the whole tree order-independent.
    """

    action_refs: list[str]
    levels: list[list[bytes]] = field(default_factory=list)

    @property
    def root(self) -> str:
        return self.levels[-1][0].hex()


def build_merkle_tree(action_refs: list[str]) -> MerkleTree:
    """Build a Merkle tree over existing action_ref digests.

    action_refs: non-empty list of v1 action_ref hex strings (64 lowercase
    hex chars each — the same digest already produced by compute_action_ref).
    Order is preserved (get_proof() looks a leaf up by position) and the
    resulting root depends on that order, same as any pairwise Merkle tree.

    Raises ValueError on an empty list or a malformed action_ref (wrong
    length / non-hex) — this function does not silently coerce bad input.
    """
    if not action_refs:
        raise ValueError("build_merkle_tree requires at least one action_ref")
    for ref in action_refs:
        if len(ref) != 64:
            raise ValueError(f"not a v1 action_ref (expected 64 hex chars): {ref!r}")
        try:
            bytes.fromhex(ref)
        except ValueError as exc:
            raise ValueError(f"not valid hex: {ref!r}") from exc

    levels: list[list[bytes]] = [[_leaf_hash(r) for r in action_refs]]
    while len(levels[-1]) > 1:
        current = levels[-1]
        next_level: list[bytes] = []
        i = 0
        while i < len(current):
            if i + 1 < len(current):
                next_level.append(_node_hash(current[i], current[i + 1]))
                i += 2
            else:
                next_level.append(current[i])  # odd one out, carried up unhashed
                i += 1
        levels.append(next_level)

    return MerkleTree(action_refs=list(action_refs), levels=levels)


def get_proof(action_ref: str, tree: MerkleTree) -> list[str]:
    """Return the sibling-hash proof (hex strings, leaf-to-root order) for
    action_ref's inclusion in tree.

    Raises ValueError if action_ref is not one of the tree's original leaves
    — a proof can only be extracted for a leaf that was actually built in.
    """
    try:
        idx = tree.action_refs.index(action_ref)
    except ValueError as exc:
        raise ValueError(f"action_ref not in tree: {action_ref!r}") from exc

    proof: list[str] = []
    for level in tree.levels[:-1]:
        sibling_idx = idx ^ 1
        if sibling_idx < len(level):
            proof.append(level[sibling_idx].hex())
        # else: idx was the carried-up odd node at this level, no sibling to record
        idx //= 2
    return proof


def verify_inclusion(action_ref: str, proof: list[str], root: str) -> bool:
    """Recompute the root from action_ref + proof and compare to `root`.

    Returns True only if the recomputed root matches exactly. This proves
    that action_ref was one of the leaves committed to when `root` was
    built — it does NOT independently verify that `root` itself was ever
    anchored on-chain (that is a separate AnchorRegistry query, same as any
    single-leaf anchor) and it does NOT vouch for the action_ref's own
    legitimacy (see docs/spec/batch-anchor.md, "What this does not prove").
    """
    if len(action_ref) != 64:
        return False
    try:
        current = _leaf_hash(action_ref)
        sibling_bytes = [bytes.fromhex(p) for p in proof]
    except ValueError:
        return False

    for sibling in sibling_bytes:
        current = _node_hash(current, sibling)

    return current.hex() == root
