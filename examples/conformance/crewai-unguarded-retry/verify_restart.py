"""Conformance runner for the RESUME_AFTER_RESTART gap (gap #3, nsolland,
crewAIInc/crewAI#7449), same convention as verify.py / verify_argument_mismatch.py.

Runs attempt 1 + a simulated process restart + attempt 2 twice -- once
against the unmodified idempotency-ref-v1 guard (naive, in-memory) and
once against durable_idempotency_guard.DurableIdempotencyGuard (fixed,
SQLite-backed). Prints ALL CHECKS PASS only if both hold.

Requires crewai installed (pip install crewai). Run: python3 verify_restart.py
"""

from __future__ import annotations

import contextlib
import io
import sys

import restart_guarded_case
import restart_naive_case


def main() -> int:
    print("crewai-unguarded-retry / RESUME_AFTER_RESTART conformance -- 2 cases")

    with contextlib.redirect_stdout(io.StringIO()):
        naive = restart_naive_case.main()
        fixed = restart_guarded_case.main()

    ok = True

    if naive["gap_confirmed"]:
        print(
            "  [PASS] RESUME_AFTER_RESTART_NAIVE: process restart lost the "
            "PENDING record, attempt 2 re-ran the effect "
            f"(effect_count={naive['effect_observation']['effect_count']})"
        )
    else:
        print(f"  [FAIL] RESUME_AFTER_RESTART_NAIVE: {naive}")
        ok = False

    if fixed["duplicate_prevented"]:
        print(
            "  [PASS] RESUME_AFTER_RESTART_GUARDED: PENDING record survived "
            "the restart on disk, attempt 2 refused with PENDING_GUARD, "
            "reconciled to COMMITTED against the effect store "
            f"(effect_count={fixed['effect_observation']['effect_count']})"
        )
    else:
        print(f"  [FAIL] RESUME_AFTER_RESTART_GUARDED: {fixed}")
        ok = False

    print()
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
