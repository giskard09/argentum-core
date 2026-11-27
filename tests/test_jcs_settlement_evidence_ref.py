"""settlement-evidence-ref/verify.py canonicalizes with RFC 8785 (repo jcs.py), not json.dumps(sort_keys).

Until 2026-11-26 it used json.dumps(sort_keys=True), which the spec says not to use. These tests pin the
two differences (key order outside the BMP, number forms), that an out-of-profile integer is a reported
failure and not a crash, and that a verifier reverted to sort_keys fails the vectors in vectors-jcs.json.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "examples" / "conformance" / "settlement-evidence-ref"


def _load():
    spec = importlib.util.spec_from_file_location("settlement_evidence_ref_verify_jcs", HERE / "verify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v = _load()


def test_keys_are_ordered_by_utf16_code_unit():
    # U+1F600 is D83D DE00 in UTF-16, U+FFFF is FFFF: the emoji sorts first. By code point it is last.
    assert v.jcs({"\uffff": 2, "\U0001F600": 1}) == '{"\U0001F600":1,"\uffff":2}'


def test_numbers_use_ecmascript_forms():
    assert v.jcs({"s": 0.000001, "n": 1.0, "e": 1e21}) == '{"e":1e+21,"n":1,"s":0.000001}'


def test_out_of_profile_integer_is_a_failure_not_a_crash():
    vec = json.loads((HERE / "vectors.json").read_text())["vectors"][0]
    vec["settlement_artifact"]["ext"] = 9007199254740993
    ok, failures = v.verify_vector(vec)
    assert not ok
    assert any("cannot be canonicalized under RFC 8785" in f for f in failures)


def test_new_vectors_are_what_the_builder_writes():
    r = subprocess.run([sys.executable, "-B", "-I", str(HERE / "build_jcs_vectors.py"), "--check"])
    assert r.returncode == 0


def test_a_verifier_that_goes_back_to_sort_keys_fails_the_new_vectors():
    src = (HERE / "verify.py").read_text()
    old = '    return jcs_bytes(obj).decode("utf-8")'
    assert src.count(old) == 1
    ns = {"__file__": str(HERE / "verify.py"), "__name__": "mutant"}
    exec(compile(src.replace(old, '    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)'),
                 "mutant.py", "exec"), ns)
    vectors = json.loads((HERE / "vectors-jcs.json").read_text())["vectors"]
    assert len(vectors) == 2
    for vec in vectors:
        assert not ns["verify_vector"](vec)[0], vec["id"]
        assert v.verify_vector(vec)[0], vec["id"]
