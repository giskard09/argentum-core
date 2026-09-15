"""Conformance runner for the ARGUMENT_MISMATCH gap (gap #4, nsolland,
crewAIInc/crewAI#7449), same convention as verify.py.

Runs the real crewAI ToolUsage dispatcher twice -- fixed logical_action_id,
changed argument content -- once against the unmodified idempotency-ref-v1
guard (naive) and once against the same guard wrapped with
args_binding_guard.py (fixed). Prints ALL CHECKS PASS only if both hold.

Requires crewai installed (pip install crewai). Run: python3 verify_argument_mismatch.py
"""

from __future__ import annotations

import contextlib
import io
import sys

import argument_mismatch_guarded_case
import argument_mismatch_naive_case


def main() -> int:
    print("crewai-unguarded-retry / ARGUMENT_MISMATCH conformance -- 2 cases")

    with contextlib.redirect_stdout(io.StringIO()):
        naive = argument_mismatch_naive_case.main()
        fixed = argument_mismatch_guarded_case.main()

    ok = True

    if naive["gap_confirmed"]:
        print(
            "  [PASS] ARGUMENT_MISMATCH_NAIVE: attempt 2 (amount=250) silently "
            "discarded, guard reused attempt 1's permit "
            f"(guard_events={[e['guard_outcome'] for e in naive['guard_events']]})"
        )
    else:
        print(f"  [FAIL] ARGUMENT_MISMATCH_NAIVE: {naive}")
        ok = False

    if fixed["fix_confirmed"]:
        print(
            "  [PASS] ARGUMENT_MISMATCH_GUARDED: attempt 2 refused with "
            "ARGUMENT_MISMATCH_REQUIRES_NEW_DECISION, no silent reuse, no "
            "silent second effect"
        )
    else:
        print(f"  [FAIL] ARGUMENT_MISMATCH_GUARDED: {fixed}")
        ok = False

    print()
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
