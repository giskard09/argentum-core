"""anchoring-precedence-ref/verify.py canonicalizes with RFC 8785 (repo jcs.py), not json.dumps(sort_keys).

Until 2026-11-26 it used json.dumps(sort_keys=True), which the spec says not to use. These tests pin the
two differences (key order outside the BMP, number forms) and that an out-of-profile integer is a reported
failure rather than a crash. Reverting jcs() to sort_keys fails the first two.
"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "examples" / "conformance" / "anchoring-precedence-ref"


def _load():
    spec = importlib.util.spec_from_file_location("apr_verify_jcs", HERE / "verify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v = _load()


def test_keys_are_ordered_by_utf16_code_unit():
    # U+1F600 is D83D DE00 in UTF-16, U+FFFF is FFFF: the emoji sorts first. By code point it is last.
    assert v.jcs({"￿": 2, "\U0001F600": 1}) == '{"\U0001F600":1,"￿":2}'


def test_numbers_use_ecmascript_forms():
    assert v.jcs({"s": 0.000001, "n": 1.0, "e": 1e21}) == '{"e":1e+21,"n":1,"s":0.000001}'


def test_out_of_profile_integer_is_a_failure_not_a_crash():
    vec = {"envelope": {"trail_id": "t", "anchor_block_time": 9007199254740993, "mechanism": "on-chain",
                        "outcome_ts_ms": 1, "version": "anchoring-precedence-ref-v1"},
           "anchoring_precedence_ref": "0" * 64, "admission_hash": "0" * 64}
    ok, failures = v.verify_vector(vec)
    assert not ok
    assert any(f.startswith("canonical_envelope: envelope cannot be canonicalized") for f in failures)
    assert not any("admission_invariant: admission_hash" in f and "!=" in f for f in failures)
