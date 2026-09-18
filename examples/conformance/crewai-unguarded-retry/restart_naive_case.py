"""CASO GAP3-NAIVE -- RESUME_AFTER_RESTART, in-memory guard loses state.

Reproduces gap #3 of the five cases nsolland mapped against this worked
example's UNGUARDED_RETRY / GUARDED pair (crewAIInc/crewAI#7449,
2026-09-14): "resume tras restart pierde estado". Same fixed
logical_action_id across both attempts (idempotency-ref-v1 invariant 5 is
respected), but the process holding the guard's PENDING record dies
between attempt 1 and attempt 2 -- a crash-and-restart, not a same-process
retry.

Uses `idempotency_guard.IdempotencyGuard` exactly as `guarded_case.py`
does. The bug is not in the PENDING/COMMITTED lifecycle itself -- it is
that the lifecycle lives in a `dict` held by one Python object. A second
process (or the same process after a restart) constructs a *new*
`IdempotencyGuard()`, whose `_records` starts empty regardless of what the
crashed process had written.

Run: python3 restart_naive_case.py
"""

from __future__ import annotations

import json
import sys

from effect_store import EffectStore
from harness import run_single_tool_call
from idempotency_guard import IdempotencyGuard, derive_idempotency_ref

LOGICAL_ACTION_ID = "resume-after-restart-001"
AGENT_ID = "crewai-unguarded-retry-worked-example"
DB_PATH = "/tmp/argentum_crewai_restart_naive.db"


def main() -> dict:
    store = EffectStore(DB_PATH)
    idempotency_ref = derive_idempotency_ref(
        LOGICAL_ACTION_ID, action_type="tool.restart_effect_tool", agent_id=AGENT_ID
    )

    # --- Attempt 1: process A. Effect commits, then the process crashes
    # before the result is ever returned to the caller -- same "commit,
    # then die" shape as guarded_case.py's simulated crash, except here
    # nothing survives the crash except what is in the effect store itself.
    guard_process_a = IdempotencyGuard()

    def effect_tool_attempt_1(logical_action_id: str) -> str:
        def real_effect_fn():
            effect_id = store.apply_effect(logical_action_id, 1)
            raise RuntimeError("simulated crash: process dies right here")

        return json.dumps(
            dict(zip(("effect_id", "guard_outcome"),
                     guard_process_a.guard(idempotency_ref, 1, real_effect_fn)))
        )

    attempt_1_result = run_single_tool_call(
        effect_tool_attempt_1, "restart_effect_tool", {"logical_action_id": LOGICAL_ACTION_ID}
    )

    # --- Simulated restart: process A is gone. A fresh IdempotencyGuard()
    # is exactly what a new process (or a naive restart of the same one)
    # constructs -- empty `_records`, no knowledge that idempotency_ref was
    # ever PENDING.
    guard_process_b = IdempotencyGuard()

    def effect_tool_attempt_2(logical_action_id: str) -> str:
        def real_effect_fn():
            return store.apply_effect(logical_action_id, 2)

        effect_id, guard_outcome = guard_process_b.guard(idempotency_ref, 2, real_effect_fn)
        return json.dumps({"effect_id": effect_id, "guard_outcome": guard_outcome})

    attempt_2_result = run_single_tool_call(
        effect_tool_attempt_2, "restart_effect_tool", {"logical_action_id": LOGICAL_ACTION_ID}
    )

    observed = store.read_independent(LOGICAL_ACTION_ID)
    store.close()

    # gap_confirmed: the process-B guard had no record of attempt 1's
    # PENDING state, so it ran the real effect again -- two effects landed
    # for one logical_action_id, and attempt 2's own guard_outcome
    # ("COMMITTED") gives no indication anything is wrong.
    gap_confirmed = observed["readable"] and observed["effect_count"] == 2

    return {
        "case": "RESUME_AFTER_RESTART_NAIVE",
        "logical_action_id": LOGICAL_ACTION_ID,
        "idempotency_ref": idempotency_ref,
        "attempt_1": attempt_1_result,
        "attempt_1_guard_events": guard_process_a.events,
        "attempt_2": attempt_2_result,
        "attempt_2_guard_events": guard_process_b.events,
        "effect_observation": observed,
        "gap_confirmed": gap_confirmed,
    }


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["gap_confirmed"] else 1)
