"""CASO GAP4-GUARDED -- same ARGUMENT_MISMATCH scenario as
argument_mismatch_naive_case.py, tool wrapped with args_binding_guard.py in
addition to idempotency_guard.IdempotencyGuard.

Same two real ToolUsage.use() calls, same fixed logical_action_id, same
changed amount on attempt 2. The only change is ArgumentBoundGuard sitting
in front of the existing PENDING/COMMITTED guard: it binds an args_digest
to the idempotency_ref on the first attempt and, on any later attempt
whose args_digest differs, refuses BEFORE the effect (or the old
RECONCILED_GUARD reuse) is ever reached -- reporting
ARGUMENT_MISMATCH_REQUIRES_NEW_DECISION instead of silently substituting
attempt 1's outcome for attempt 2's different request.

Run: python3 argument_mismatch_guarded_case.py
"""

from __future__ import annotations

import json
import sys

from args_binding_guard import ArgumentBoundGuard, ArgumentMismatchError
from effect_store import EffectStore
from harness import run_single_tool_call
from idempotency_guard import IdempotencyGuard, derive_idempotency_ref

LOGICAL_ACTION_ID = "argument-mismatch-001"
AGENT_ID = "crewai-unguarded-retry-worked-example"
DB_PATH = "/tmp/argentum_crewai_argmismatch_guarded.db"

ATTEMPTS = [
    {"logical_action_id": LOGICAL_ACTION_ID, "amount": 100},
    {"logical_action_id": LOGICAL_ACTION_ID, "amount": 250},
]


def main() -> dict:
    store = EffectStore(DB_PATH)
    arg_guard = ArgumentBoundGuard(IdempotencyGuard())
    calls = {"n": 0}

    idempotency_ref = derive_idempotency_ref(
        LOGICAL_ACTION_ID, action_type="tool.payment_effect_tool", agent_id=AGENT_ID
    )

    def payment_effect_tool(logical_action_id: str, amount: int) -> str:
        calls["n"] += 1
        attempt_no = calls["n"]
        arguments = {"logical_action_id": logical_action_id, "amount": amount}

        def real_effect_fn():
            return store.apply_effect(f"{logical_action_id}:{amount}", attempt_no)

        try:
            effect_id, guard_outcome = arg_guard.guard(
                idempotency_ref, attempt_no, arguments, real_effect_fn
            )
            return json.dumps({"effect_id": effect_id, "guard_outcome": guard_outcome})
        except ArgumentMismatchError as exc:
            return json.dumps(
                {
                    "effect_id": None,
                    "guard_outcome": "ARGUMENT_MISMATCH_REQUIRES_NEW_DECISION",
                    "error": str(exc),
                }
            )

    attempt_results = []
    for arguments in ATTEMPTS:
        result = run_single_tool_call(payment_effect_tool, "payment_effect_tool", arguments)
        attempt_results.append({"arguments": arguments, "harness_result": result})

    observed_amount_100 = store.read_independent(f"{LOGICAL_ACTION_ID}:100")
    observed_amount_250 = store.read_independent(f"{LOGICAL_ACTION_ID}:250")
    store.close()

    attempt_2_outcome = json.loads(attempt_results[1]["harness_result"]["outcome"])
    fix_confirmed = (
        observed_amount_100["effect_count"] == 1
        and observed_amount_250["effect_count"] == 0
        and attempt_2_outcome["guard_outcome"] == "ARGUMENT_MISMATCH_REQUIRES_NEW_DECISION"
    )

    return {
        "case": "ARGUMENT_MISMATCH_GUARDED",
        "logical_action_id": LOGICAL_ACTION_ID,
        "idempotency_ref": idempotency_ref,
        "guard_events": arg_guard._guard.events,
        "attempts": attempt_results,
        "effect_observation_amount_100": observed_amount_100,
        "effect_observation_amount_250": observed_amount_250,
        "attempt_2_explicit_outcome": attempt_2_outcome["guard_outcome"],
        "fix_confirmed": fix_confirmed,
    }


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["fix_confirmed"] else 1)
