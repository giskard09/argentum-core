"""tools/check_skips.py must be able to fail: unlisted skips and excess skips turn it red."""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("check_skips", os.path.join(ROOT, "tools", "check_skips.py"))
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)

OK = """SKIPPED [4] tests/test_conformance_verifiers_run.py:49: needs crewai; NOT run in any CI today (DEUDA_INTERNA 24/09)
SKIPPED [1] tests/test_erc8274_profile_anchor.py:64: Foundry cast not installed
SKIPPED [1] tests/test_erc8274_profile_anchor.py:184: set ERC8274_LIVE=1 to read mainnet.base.org
"""


def test_known_skips_pass():
    assert cs.check(OK)[1] == []


def test_no_skips_pass():
    assert cs.check("410 passed in 1s\n") == ([], [])


def test_unlisted_skip_fails():
    errs = cs.check(OK + "SKIPPED [1] tests/test_x.py:3: flaky on CI\n")[1]
    assert any("UNLISTED" in e for e in errs)


def test_too_many_of_a_known_skip_fails():
    errs = cs.check(OK + "SKIPPED [1] tests/test_y.py:9: needs crewai again\n")[1]
    assert any("TOO MANY" in e for e in errs)


def test_main_exit_code(monkeypatch, capsys):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(OK + "SKIPPED [2] t.py:1: new thing\n500 passed, 8 skipped in 1.00s\n"))
    assert cs.main() == 1
    monkeypatch.setattr("sys.stdin", io.StringIO(OK + "500 passed, 6 skipped in 1.00s\n"))
    assert cs.main() == 0


# ---- test floor ---------------------------------------------------------------------------------------------

def test_floor_ok_with_real_final_lines():
    for line, n in [("490 passed, 6 skipped, 124 warnings, 25 subtests passed in 14.08s", 490),
                    ("495 passed in 12.30s", 495),
                    ("1 failed, 494 passed, 5 skipped, 124 warnings, 25 subtests passed in 14.58s", 494),
                    ("= 495 passed, 5 skipped in 14.21s =", 495),
                    ("495 passed in 1210.30s (0:20:10)", 495)]:
        assert cs.passed_count("x\n" + line + "\n") == n, line
        assert cs.check_floor(line, floor=480) == []


def test_below_floor_fails():
    assert any("TEST FLOOR" in e for e in cs.check_floor("136 passed, 2 skipped in 3.00s", floor=480))


def test_no_summary_line_fails():
    assert any("NO RECOGNISABLE" in e for e in cs.check_floor("", floor=1))
    assert any("NO RECOGNISABLE" in e for e in cs.check_floor("collected 5 items\n", floor=1))


def test_passed_inside_other_text_is_not_the_summary():
    text = "999 passed in verifier output\n3 passed in 0.01s extra words\n"
    assert cs.passed_count(text) is None                       # last line is not a pytest summary
    assert cs.passed_count("999 passed, in the middle\n50 passed in 1.00s\n") == 50   # only the LAST line counts


def test_subtests_are_not_passed_tests():
    assert cs.passed_count("0 failed, 25 subtests passed in 1.00s") == 0


def test_no_tests_ran_is_not_a_summary():
    assert cs.passed_count("no tests ran in 0.00s") is None
    assert cs.check_floor("no tests ran in 0.00s", floor=480)


def test_main_fails_below_floor(monkeypatch):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(OK + "10 passed, 6 skipped in 1.00s\n"))
    assert cs.main() == 1
