"""Fail CI when pytest skips something nobody listed, or when the suite shrank below its floor.

A green run can hide controls that did not run. Read the output of `pytest -q -rs` on stdin, print every skip with
its reason and count, and exit 1 if a skip reason is not in EXPECTED or happens more often than listed.

    pytest -q -rs | tee pytest.out; python tools/check_skips.py < pytest.out

EXPECTED is the explicit list of known skips. Adding a skip means adding a line here, with its cause, in the same commit.

PYTEST_FLOOR is the minimum number of PASSED tests. It lives here, outside tests/, on purpose: a floor inside tests/
is deleted together with them. Measured 2026-11-16: 495 passed locally (with Foundry cast), 490 without cast (the CI
shape). Raise it when tests are added; do not lower it without saying why. Final-line formats seen (pytest 9.1.1, -q):
"495 passed, 5 skipped, 124 warnings, 25 subtests passed in 14.21s", "5 passed in 0.01s", "1 failed, 494 passed, ...";
"N subtests passed" is not counted as passed tests.
"""
import re
import sys

EXPECTED = {
    # reason substring: (max skipped tests, why it is skipped)
    "needs crewai": (4, "crewai-unguarded-retry verifiers: crewai is not installed in CI and no job runs them (DEUDA_INTERNA 24/09)"),
    "Foundry cast not installed": (1, "ERC-8274 cross-check with Foundry cast: ci.yml does not install Foundry"),
    "set ERC8274_LIVE=1": (1, "ERC-8274 live receipt on Base mainnet: opt-in, needs network"),
}
PYTEST_FLOOR = 480
FINAL = re.compile(r"(?:=+ )?(\d+ [a-z]+(?: [a-z]+)?(?:, \d+ [a-z]+(?: [a-z]+)?)*) in [\d.]+s(?: \(\d+:\d{2}:\d{2}\))?(?: =+)?")
PASSED = re.compile(r"(\d+) passed")
LINE = re.compile(r"SKIPPED \[(\d+)\] (\S+?):(\d+): (.*)")   # used with fullmatch (repo rule: no $ anchors)


def check(text: str) -> tuple[list[str], list[str]]:
    report, errors, counts = [], [], {}
    for raw in text.splitlines():
        m = LINE.fullmatch(raw.strip())
        if not m:
            continue
        n, path, _, reason = int(m.group(1)), m.group(2), m.group(3), m.group(4)
        key = next((k for k in EXPECTED if k in reason), None)
        report.append(f"skipped x{n}: {path}: {reason}")
        if key is None:
            errors.append(f"UNLISTED SKIP x{n}: {path}: {reason}")
        else:
            counts[key] = counts.get(key, 0) + n
    for key, n in counts.items():
        if n > EXPECTED[key][0]:
            errors.append(f"TOO MANY SKIPS for {key!r}: {n} > {EXPECTED[key][0]}")
    return report, errors


def passed_count(text: str):
    """Number of passed tests from pytest's LAST non-empty line, or None if that line is not a recognisable summary."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return None
    m = FINAL.fullmatch(lines[-1])
    if not m:
        return None
    for token in m.group(1).split(", "):
        p = PASSED.fullmatch(token)
        if p:
            return int(p.group(1))
    return 0


def check_floor(text: str, floor: int = PYTEST_FLOOR) -> list[str]:
    n = passed_count(text)
    if n is None:
        return ["NO RECOGNISABLE pytest summary line at the end of the output; cannot verify the test floor"]
    if n < floor:
        return [f"TEST FLOOR: {n} passed < floor {floor}; the suite shrank (or tests were not collected)"]
    return []


def main() -> int:
    text = sys.stdin.read()
    report, errors = check(text)
    errors += check_floor(text)
    print("pytest skips (each one is a control that did not run):")
    for line in report or ["  none"]:
        print("  " + line)
    for e in errors:
        print("FAIL", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
