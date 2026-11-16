"""Fail CI when pytest skips something nobody listed.

A green run can hide controls that did not run. Read the output of `pytest -q -rs` on stdin, print every skip with
its reason and count, and exit 1 if a skip reason is not in EXPECTED or happens more often than listed.

    pytest -q -rs | tee pytest.out; python tools/check_skips.py < pytest.out

EXPECTED is the explicit list of known skips. Adding a skip means adding a line here, with its cause, in the same commit.
"""
import re
import sys

EXPECTED = {
    # reason substring: (max skipped tests, why it is skipped)
    "needs crewai": (4, "crewai-unguarded-retry verifiers: crewai is not installed in CI and no job runs them (DEUDA_INTERNA 24/09)"),
    "Foundry cast not installed": (1, "ERC-8274 cross-check with Foundry cast: ci.yml does not install Foundry"),
    "set ERC8274_LIVE=1": (1, "ERC-8274 live receipt on Base mainnet: opt-in, needs network"),
}
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


def main() -> int:
    report, errors = check(sys.stdin.read())
    print("pytest skips (each one is a control that did not run):")
    for line in report or ["  none"]:
        print("  " + line)
    for e in errors:
        print("FAIL", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
