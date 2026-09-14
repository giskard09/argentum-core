"""Conformance runner, same convention as ../settlement-retry-safety/verify.py.

Runs the real crewAI retry engine both without and with the
idempotency-ref-v1 guard and asserts the expected outcome for each.

Requires crewai installed (pip install crewai). Prints ALL CHECKS PASS
only if both checks hold.

Run: python3 verify.py
"""

from __future__ import annotations

import contextlib
import io
import sys

import guarded_case
import unguarded_case


def main() -> int:
    print("crewai-unguarded-retry conformance -- 2 cases")

    with contextlib.redirect_stdout(io.StringIO()):
        unguarded = unguarded_case.main()
        guarded = guarded_case.main()

    ok = True

    if unguarded["bug_confirmed"] and unguarded["effect_observation"]["effect_count"] > 1:
        print(
            f"  [PASS] UNGUARDED_RETRY: {unguarded['effect_observation']['effect_count']} "
            f"duplicate effects observed (expected >1)"
        )
    else:
        print(f"  [FAIL] UNGUARDED_RETRY: {unguarded}")
        ok = False

    if guarded["duplicate_prevented"] and guarded["effect_observation"]["effect_count"] == 1:
        print("  [PASS] GUARDED: exactly 1 effect observed with idempotency-ref-v1 guard")
    else:
        print(f"  [FAIL] GUARDED: {guarded}")
        ok = False

    print()
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
