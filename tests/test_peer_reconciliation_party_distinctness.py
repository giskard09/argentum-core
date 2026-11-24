"""peer-reconciliation-ref-v1.3: party_distinctness is computed, and it gates AGREED.

verify.py also compares the computed result with the vector's declared
`checks.party_distinctness`, so a disabled check can still make a negative
vector "fail" for the wrong reason (declared != computed). These tests assert the
computed result directly, so removing either comparison, or the gate in the
comparator, is caught.
"""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "examples" / "conformance" / "peer-reconciliation-ref"


def _load():
    spec = importlib.util.spec_from_file_location("peer_reconciliation_verify", HERE / "verify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_all(v):
    """Raise AssertionError if `v` (a loaded verify module) mishandles distinctness or strictness."""
    import inspect
    assert inspect.signature(v.compute_comparator_state).parameters["distinct"].default is inspect.Parameter.empty
    vectors = {x["id"]: x for x in json.loads((HERE / "vectors.json").read_text())["vectors"]}
    for vid, x in vectors.items():
        env = x["envelope"]
        sa = v.check_structural_validity(env["party_a"])
        sb = v.check_structural_validity(env["party_b"])
        ba = v.check_signature_binding(env["party_a"])
        bb = v.check_signature_binding(env["party_b"])
        distinct = v.check_party_distinctness(env)
        if vid.startswith("distinct-"):
            # Same party or same key: only the distinctness gate keeps it off AGREED.
            assert (sa, sb, ba, bb) == (True, True, True, True), vid
            assert distinct is False, vid
            assert v.compute_comparator_state(x, sa, sb, ba, bb, False) == "UNRESOLVED", vid
            assert v.compute_comparator_state(x, sa, sb, ba, bb, True) == "AGREED", vid
        elif vid.startswith(("pubkey-", "party-id-")):
            # Same identity written differently: structurally invalid, not "a different party".
            assert (sa, sb) == (True, False), vid
            assert distinct is True, vid
            assert v.compute_comparator_state(x, sa, sb, ba, bb, True) == "UNRESOLVED", vid
        else:
            assert distinct is True, vid  # no pre-v1.3 vector changes
    # Strict key parsing, directly.
    good = "MCowBQYDK2VwAyEAqQm7VZ0X8tGxJm6QwYh3fN4dL9pRk2vC5eA1sT7uHzM="
    assert v.pubkey_bytes(good) is not None and len(v.pubkey_bytes(good)) == 32
    assert v.pubkey_bytes(good[:-1]) is None and v.pubkey_bytes(good + "\n") is None
    assert v.pubkey_bytes(" " + good) is None and v.pubkey_bytes(good + "=") is None
    assert v.pubkey_bytes(good[:-2] + "N=") == v.pubkey_bytes(good)  # trailing bits: same key
    assert v.pubkey_bytes(None) is None and v.pubkey_bytes(5) is None
    assert v.party_id_valid("a-b:c") and not v.party_id_valid("a b") and not v.party_id_valid("")
    assert not v.party_id_valid(None) and not v.party_id_valid("é") and not v.party_id_valid("a\n")


def test_party_distinctness_is_computed_and_gates_agreed():
    check_all(_load())


def test_existing_vectors_keep_their_declared_hashes_under_jcs():
    v = _load()
    for x in json.loads((HERE / "vectors.json").read_text())["vectors"]:
        if x["id"] == "malformed-hash-mismatch-001":
            continue  # declared hash is wrong on purpose
        assert v.sha256hex(v.jcs(x["envelope"])) == x["peer_reconciliation_ref"], x["id"]
