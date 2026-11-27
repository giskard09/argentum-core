"""recipient-allocation-ref/verify.py canonicalizes with RFC 8785 (repo jcs.py), not json.dumps(sort_keys).

Until 2026-11-26 it used json.dumps(sort_keys=True), which the spec says not to use. The file is a script that
verifies at import time, so the probes execute only the part of it that defines jcs(). The set has no vector with
data where the two canonicalizations differ (the preimage has a fixed set of fields and the spec defines no
extension field, so none was invented): the regression is pinned at function level.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "examples" / "conformance" / "recipient-allocation-ref"
SRC = (HERE / "verify.py").read_text()
MARK = "vectors_path = Path(__file__).parent"


def _ns(src=SRC):
    ns = {"__file__": str(HERE / "verify.py"), "__name__": "probe"}
    exec(compile(src.split(MARK)[0], "verify_head.py", "exec"), ns)
    return ns


def test_keys_are_ordered_by_utf16_code_unit():
    # U+1F600 is D83D DE00 in UTF-16, U+FFFF is FFFF: the emoji sorts first. By code point it is last.
    assert _ns()["jcs"]({"￿": 2, "\U0001F600": 1}) == '{"\U0001F600":1,"￿":2}'


def test_numbers_use_ecmascript_forms():
    assert _ns()["jcs"]({"s": 0.000001, "n": 1.0, "e": 1e21}) == '{"e":1e+21,"n":1,"s":0.000001}'


def test_out_of_profile_integer_raises_value_error():
    try:
        _ns()["jcs"]({"n": 9007199254740993})
    except ValueError:
        return
    raise AssertionError("an integer outside +/-(2^53-1) was accepted")


def test_verifier_passes_its_vectors():
    r = subprocess.run([sys.executable, "-B", "-I", str(HERE / "verify.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-800:]
    assert "2/2 vectors passed" in r.stdout


def test_reverting_to_sort_keys_is_detected():
    old = '    return jcs_bytes(obj).decode("utf-8")'
    assert SRC.count(old) == 1
    mutated = SRC.replace(old, '    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)')
    assert _ns(mutated)["jcs"]({"￿": 2, "\U0001F600": 1}) != '{"\U0001F600":1,"￿":2}'
    assert _ns(mutated)["jcs"]({"n": 1.0}) != '{"n":1}'
