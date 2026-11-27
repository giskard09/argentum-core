"""disclosure-scoped-ref/verify.py canonicalizes with RFC 8785 (repo jcs.py), not json.dumps(sort_keys).

Until 2026-11-26 it used json.dumps(sort_keys=True), which the spec says not to use in Python. verify.mjs was
already RFC 8785. The fixture is one record with scripted vectors, so no vector with data where the two
canonicalizations differ was added; the regression is pinned at function level, plus a field digest whose value
carries such data.
"""
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "examples" / "conformance" / "disclosure-scoped-ref"


def _load(src=None):
    path = HERE / "verify.py"
    if src is None:
        spec = importlib.util.spec_from_file_location("dsr_verify_jcs", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    ns = {"__file__": str(path), "__name__": "mutant"}
    exec(compile(src, "mutant.py", "exec"), ns)
    return type("M", (), ns)


v = _load()


def test_keys_are_ordered_by_utf16_code_unit():
    # U+1F600 is D83D DE00 in UTF-16, U+FFFF is FFFF: the emoji sorts first. By code point it is last.
    assert v.jcs({"￿": 2, "\U0001F600": 1}) == '{"\U0001F600":1,"￿":2}'


def test_numbers_use_ecmascript_forms():
    assert v.jcs({"s": 0.000001, "n": 1.0, "e": 1e21}) == '{"e":1e+21,"n":1,"s":0.000001}'


def test_field_digest_of_a_value_with_such_data_matches_a_hand_written_string():
    # {"field","salt","value"} in key order; the value's own keys in UTF-16 order (n 006E < U+1F600 D83D DE00 < U+FFFF), numbers in ECMAScript form.
    canonical = '{"field":"f","salt":"s","value":{"n":1,"\U0001F600":1,"\uffff":2}}'
    value = {"￿": 2, "\U0001F600": 1, "n": 1.0}
    assert v.field_digest("f", value, "s") == hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_out_of_profile_integer_raises_value_error():
    try:
        v.field_digest("f", 9007199254740993, "s")
    except ValueError:
        return
    raise AssertionError("an integer outside +/-(2^53-1) was accepted")


def test_verifier_passes_its_vectors():
    r = subprocess.run([sys.executable, "-B", "-I", str(HERE / "verify.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-800:]


def test_reverting_to_sort_keys_is_detected():
    src = (HERE / "verify.py").read_text()
    old = '    return jcs_bytes(obj).decode("utf-8")'
    assert src.count(old) == 1
    m = _load(src.replace(old, '    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)'))
    value = {"￿": 2, "\U0001F600": 1, "n": 1.0}
    assert m.field_digest("f", value, "s") != v.field_digest("f", value, "s")
