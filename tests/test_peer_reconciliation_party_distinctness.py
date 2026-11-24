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
    """Raise AssertionError if `v` (a loaded verify module) mishandles distinctness."""
    vectors = {x["id"]: x for x in json.loads((HERE / "vectors.json").read_text())["vectors"]}
    for vid in ("distinct-same-party-id-001", "distinct-same-pubkey-001"):
        x = vectors[vid]
        assert v.check_party_distinctness(x["envelope"]) is False, vid
        # Everything else is ready, so only the distinctness gate can keep this off AGREED.
        env = x["envelope"]
        sa = v.check_structural_validity(env["party_a"])
        sb = v.check_structural_validity(env["party_b"])
        ba = v.check_signature_binding(env["party_a"])
        bb = v.check_signature_binding(env["party_b"])
        assert (sa, sb, ba, bb) == (True, True, True, True), vid
        assert v.compute_comparator_state(x, sa, sb, ba, bb, False) == "UNRESOLVED", vid
        assert v.compute_comparator_state(x, sa, sb, ba, bb, True) == "AGREED", vid  # gate is what blocks it
    for vid, x in vectors.items():
        if not vid.startswith("distinct-"):
            assert v.check_party_distinctness(x["envelope"]) is True, vid


def test_party_distinctness_is_computed_and_gates_agreed():
    check_all(_load())


def test_existing_vectors_keep_their_declared_hashes_under_jcs():
    v = _load()
    for x in json.loads((HERE / "vectors.json").read_text())["vectors"]:
        if x["id"] == "malformed-hash-mismatch-001":
            continue  # declared hash is wrong on purpose
        assert v.sha256hex(v.jcs(x["envelope"])) == x["peer_reconciliation_ref"], x["id"]
