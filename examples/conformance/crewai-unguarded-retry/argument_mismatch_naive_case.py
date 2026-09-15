"""CASO GAP4-NAIVE -- ARGUMENT_MISMATCH, unguarded against argument content.

Reproduces gap #4 of the five cases nsolland mapped against this worked
example's UNGUARDED_RETRY / GUARDED pair (crewAIInc/crewAI#7449,
2026-09-14/15): a model-regenerated retry that carries the SAME
logical_action_id as the first attempt but DIFFERENT arguments (a changed
amount, standing in for any changed action content). Unlike
unguarded_case.py / guarded_case.py, this is not crewAI's own outer retry
loop re-dispatching an identical ToolCalling -- it is two independent real
ToolUsage.use() calls (harness.run_single_tool_call), the shape a fresh
model-proposed tool call actually takes.

Uses idempotency_guard.IdempotencyGuard exactly as guarded_case.py does --
no argument binding. logical_action_id is fixed and correct per
idempotency-ref-v1 invariant 5; the guard does its job for that dimension.
What it has no way to see: attempt 2 is not a retry of attempt 1's intent,
it is a different request wearing the same logical_action_id.

Run: python3 argument_mismatch_naive_case.py
"""

from __future__ import annotations

import json
import sys

from effect_store import EffectStore
from harness import run_single_tool_call
from idempotency_guard import IdempotencyGuard, derive_idempotency_ref

LOGICAL_ACTION_ID = "argument-mismatch-001"
AGENT_ID = "crewai-unguarded-retry-worked-example"
DB_PATH = "/tmp/argentum_crewai_argmismatch_naive.db"

ATTEMPTS = [
    {"logical_action_id": LOGICAL_ACTION_ID, "amount": 100},
    # model-regenerated retry: same logical_action_id, DIFFERENT amount --
    # not a rewording of the same request, a different one.
    {"logical_action_id": LOGICAL_ACTION_ID, "amount": 250},
]


def main() -> dict:
    store = EffectStore(DB_PATH)
    guard = IdempotencyGuard()
    calls = {"n": 0}

    idempotency_ref = derive_idempotency_ref(
        LOGICAL_ACTION_ID, action_type="tool.payment_effect_tool", agent_id=AGENT_ID
    )

    def payment_effect_tool(logical_action_id: str, amount: int) -> str:
        calls["n"] += 1
        attempt_no = calls["n"]

        def real_effect_fn():
            return store.apply_effect(f"{logical_action_id}:{amount}", attempt_no)

        effect_id, guard_outcome = guard.guard(idempotency_ref, attempt_no, real_effect_fn)
        return json.dumps({"effect_id": effect_id, "guard_outcome": guard_outcome})

    attempt_results = []
    for arguments in ATTEMPTS:
        result = run_single_tool_call(payment_effect_tool, "payment_effect_tool", arguments)
        attempt_results.append({"arguments": arguments, "harness_result": result})

    observed_amount_100 = store.read_independent(f"{LOGICAL_ACTION_ID}:100")
    observed_amount_250 = store.read_independent(f"{LOGICAL_ACTION_ID}:250")
    store.close()

    # gap_confirmed: attempt 2's real, different request (amount=250) never
    # produced its own effect -- the guard silently reused attempt 1's
    # RECONCILED_GUARD/COMMITTED outcome instead, and the tool call
    # returned that as success. Nothing surfaced a refusal or an error.
    gap_confirmed = (
        observed_amount_100["effect_count"] == 1
        and observed_amount_250["effect_count"] == 0
    )

    return {
        "case": "ARGUMENT_MISMATCH_NAIVE",
        "logical_action_id": LOGICAL_ACTION_ID,
        "idempotency_ref": idempotency_ref,
        "guard_events": guard.events,
        "attempts": attempt_results,
        "effect_observation_amount_100": observed_amount_100,
        "effect_observation_amount_250": observed_amount_250,
        "gap_confirmed": gap_confirmed,
    }


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["gap_confirmed"] else 1)
