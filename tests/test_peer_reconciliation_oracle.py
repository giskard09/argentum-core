"""peer-reconciliation-ref v1.3.1: a negative vector must be rejected for its own reason.

Covers score() (rejection by disagreeing with the declared checks, or under another failure_mode,
does not count), the mutant list (every mutant is caught), that the earlier vectors file is
untouched, and that vectors-v1.3.1.json is what build_v131.py writes.
"""
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "examples" / "conformance" / "peer-reconciliation-ref"
# sha256 of vectors.json at v1.3: cited by others, must not change.
VECTORS_V13_SHA256 = "233801c7789b513852fb8403f0c425effe80c66f84dcd5251ec3f539a7d7dbbb"


def _load():
    spec = importlib.util.spec_from_file_location("peer_reconciliation_verify_oracle", HERE / "verify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _vectors(name):
    return {v["id"]: v for v in json.loads((HERE / name).read_text())["vectors"]}


def test_earlier_vectors_file_is_untouched():
    assert hashlib.sha256((HERE / "vectors.json").read_bytes()).hexdigest() == VECTORS_V13_SHA256


def test_every_vector_passes_score():
    v = _load()
    for vec in v.load_vectors():
        assert v.score(vec)[0], vec["id"]


def test_rejection_by_disagreeing_with_declared_checks_does_not_count():
    v = _load()
    vec = copy.deepcopy(_vectors("vectors.json")["distinct-same-pubkey-001"])
    assert v.score(vec)[0]
    # Still rejected by the verifier, but not under the rule this vector was written for.
    vec["failure_mode"] = "signature_binding"
    ok, conforms, _f, why = v.score(vec)
    assert not conforms and not ok and "failure_mode" in why


def test_disagreement_line_is_not_a_correct_rejection():
    v = _load()
    vec = copy.deepcopy(_vectors("vectors-v1.3.1.json")["party-id-empty-001"])
    vec["checks"]["structural_validity"] = True   # the vector now claims what the verifier will not compute
    ok, conforms, _f, why = v.score(vec)
    assert not conforms and not ok and "disagree" in why


def test_canonical_envelope_mismatch_is_a_correct_rejection():
    v = _load()
    vec = _vectors("vectors.json")["malformed-hash-mismatch-001"]
    assert v.score(vec)[0]


def test_accepted_negative_vector_fails():
    v = _load()
    vec = copy.deepcopy(_vectors("vectors.json")["agreed-001"])
    vec["expected"], vec["failure_mode"] = "FAIL", "structural_validity"
    ok, conforms, _f, _why = v.score(vec)
    assert conforms and not ok


def test_every_mutant_is_caught():
    r = subprocess.run([sys.executable, "-B", "-I", str(HERE / "mutants.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "29/29 caught" in r.stdout


def test_new_vectors_file_is_what_the_builder_writes():
    r = subprocess.run([sys.executable, "-B", "-I", "-c",
                        "import runpy,sys,json;sys.path.insert(0,%r);g=runpy.run_path(%r);print(json.dumps(g['out'],indent=2,ensure_ascii=True))"
                        % (str(HERE.parent.parent.parent), str(HERE / "build_v131.py"))],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout == (HERE / "vectors-v1.3.1.json").read_text()


def test_every_negative_vector_names_a_failure_mode():
    # score() only enforces failure_mode when the vector has one, so a negative vector without it
    # would pass condition 2 trivially.
    v = _load()
    for vec in v.load_vectors():
        if vec["expected"] == "FAIL":
            assert vec.get("failure_mode"), vec["id"]


def test_missing_vector_file_is_an_error(tmp_path):
    import shutil
    d = tmp_path / "peer-reconciliation-ref"
    d.mkdir()
    shutil.copy(HERE / "verify.py", d)
    shutil.copy(HERE / "vectors.json", d)
    spec = importlib.util.spec_from_file_location("v_missing", d / "verify.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HERE.parent.parent.parent))   # jcs.py, as verify.py does from its own location
    try:
        spec.loader.exec_module(mod)
        try:
            mod.load_vectors()
        except SystemExit as e:
            assert "vectors-v1.3.1.json" in str(e)
        else:
            raise AssertionError("a missing vector file was skipped")
    finally:
        sys.path.remove(str(HERE.parent.parent.parent))
