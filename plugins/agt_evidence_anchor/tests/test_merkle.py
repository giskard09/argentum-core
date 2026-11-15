"""Conformance test: Merkle rollup over existing action_ref digests.

Vectors per docs/spec/batch-anchor.md: positive inclusion, and two negative
cases (leaf never in the tree; tampered proof/root).
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from plugins.agt_evidence_anchor.action_ref import compute_action_ref
from plugins.agt_evidence_anchor.merkle import build_merkle_tree, get_proof, verify_inclusion


def _refs(n):
    return [
        compute_action_ref(f"agent-{i}", "batch.test", "batch-anchor-test", "2026-07-31T00:00:00.000Z")
        for i in range(n)
    ]


# ── Positivo ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 7, 8])
def test_inclusion_valid_for_every_leaf(n):
    refs = _refs(n)
    tree = build_merkle_tree(refs)
    for ref in refs:
        proof = get_proof(ref, tree)
        assert verify_inclusion(ref, proof, tree.root) is True


def test_root_depends_on_leaf_order():
    """Same leaf set, different order -> different root (standard for this
    pairwise construction — sorted-pair hashing only removes the direction
    bit within one sibling pair, it does not make the whole tree
    order-independent). Guards against silently switching to a scheme that
    would collapse distinct batches to the same root."""
    refs = _refs(6)
    tree_a = build_merkle_tree(refs)
    tree_b = build_merkle_tree(list(reversed(refs)))
    assert tree_a.root != tree_b.root


# ── Negativo: leaf nunca estuvo en el árbol ──────────────────────────────

def test_get_proof_raises_for_leaf_not_in_tree():
    refs = _refs(4)
    tree = build_merkle_tree(refs)
    outsider = compute_action_ref("agent-outsider", "batch.test", "batch-anchor-test", "2026-07-31T00:00:00.000Z")
    with pytest.raises(ValueError):
        get_proof(outsider, tree)


# ── Negativo: proof tampered / root equivocado ───────────────────────────

def test_verify_inclusion_false_for_wrong_root():
    refs = _refs(5)
    tree = build_merkle_tree(refs)
    other_refs = [
        compute_action_ref(f"other-agent-{i}", "batch.test", "batch-anchor-test", "2026-07-31T00:00:00.000Z")
        for i in range(5)
    ]
    other_tree = build_merkle_tree(other_refs)
    proof = get_proof(refs[0], tree)
    assert verify_inclusion(refs[0], proof, other_tree.root) is False


def test_verify_inclusion_false_for_flipped_sibling_hash():
    refs = _refs(5)
    tree = build_merkle_tree(refs)
    proof = get_proof(refs[2], tree)
    assert proof, "expected at least one sibling for a 5-leaf tree"
    tampered = list(proof)
    tampered[0] = "00" * 32
    assert verify_inclusion(refs[2], tampered, tree.root) is False


def test_verify_inclusion_false_for_malformed_action_ref():
    tree = build_merkle_tree(_refs(3))
    assert verify_inclusion("not-a-valid-hex-ref", [], tree.root) is False


def test_build_merkle_tree_rejects_empty_list():
    with pytest.raises(ValueError):
        build_merkle_tree([])


def test_build_merkle_tree_rejects_malformed_ref():
    with pytest.raises(ValueError):
        build_merkle_tree(["not-64-hex-chars"])


# ── Solo membresía: ni posición ni tamaño del lote quedan autenticados ──────
# Congela la propiedad declarada en docs/spec/batch-anchor.md ("does NOT
# authenticate the leaf's position or the batch size"). Documenta el
# comportamiento actual; no lo cambia.

def test_verify_inclusion_takes_no_position_or_size():
    """The verifier's only inputs are (action_ref, proof, root)."""
    import inspect
    params = list(inspect.signature(verify_inclusion).parameters)
    assert params == ["action_ref", "proof", "root"]


def test_position_is_not_authenticated():
    """[a, b] and [b, a] give the same root, and the same proof verifies the
    leaf at index 0 or index 1: the proof carries no position."""
    a, b = _refs(2)
    t_ab = build_merkle_tree([a, b])
    t_ba = build_merkle_tree([b, a])
    assert t_ab.root == t_ba.root
    proof_a_at_0 = get_proof(a, t_ab)
    proof_a_at_1 = get_proof(a, t_ba)
    assert proof_a_at_0 == proof_a_at_1
    assert verify_inclusion(a, proof_a_at_0, t_ab.root) is True
    assert verify_inclusion(a, proof_a_at_1, t_ba.root) is True


def test_batch_size_is_not_authenticated_by_proof_length():
    """A one-sibling proof is valid both in a 2-leaf batch and for the last
    leaf of a 5-leaf batch (odd node carried up): proof shape does not reveal
    batch size, and verify_inclusion has no size input to check against."""
    refs2, refs5 = _refs(2), _refs(5)
    t2, t5 = build_merkle_tree(refs2), build_merkle_tree(refs5)
    p2 = get_proof(refs2[0], t2)
    p5 = get_proof(refs5[-1], t5)
    assert len(p2) == len(p5) == 1
    assert verify_inclusion(refs2[0], p2, t2.root) is True
    assert verify_inclusion(refs5[-1], p5, t5.root) is True
    assert t2.root != t5.root


def test_membership_only_rejects_leaf_not_in_batch():
    """Membership is still enforced: a leaf that is not in the batch is
    rejected, even when given another leaf's valid proof."""
    refs = _refs(5)
    tree = build_merkle_tree(refs)
    outsider = compute_action_ref("agent-outsider", "batch.test", "batch-anchor-test",
                                  "2026-07-31T00:00:00.000Z")
    assert outsider not in refs
    for ref in refs:
        assert verify_inclusion(outsider, get_proof(ref, tree), tree.root) is False
    assert verify_inclusion(outsider, [], tree.root) is False
