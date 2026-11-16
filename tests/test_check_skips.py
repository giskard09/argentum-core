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
    monkeypatch.setattr("sys.stdin", io.StringIO(OK + "SKIPPED [2] t.py:1: new thing\n"))
    assert cs.main() == 1
    monkeypatch.setattr("sys.stdin", io.StringIO(OK))
    assert cs.main() == 0
