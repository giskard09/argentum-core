"""CASO GAP3-GUARDED -- RESUME_AFTER_RESTART, fixed with a durable guard.

Identical scenario to `restart_naive_case.py` -- process A commits the
effect and crashes, process B is the retry after restart -- except the
guard is `durable_idempotency_guard.DurableIdempotencyGuard`, backed by a
SQLite row instead of a `dict`. Process B constructs a *new* guard object
but points it at the same `db_path`, so it reads the PENDING record
process A left behind before dying.

Run: python3 restart_guarded_case.py
"""

from __future__ import annotations

import json
import sys

from durable_idempotency_guard import DurableIdempotencyGuard
from effect_store import EffectStore
from harness import run_single_tool_call
from idempotency_guard import derive_idempotency_ref

LOGICAL_ACTION_ID = "resume-after-restart-001"
AGENT_ID = "crewai-unguarded-retry-worked-example"
DB_PATH = "/tmp/argentum_crewai_restart_guarded_effects.db"
GUARD_DB_PATH = "/tmp/argentum_crewai_restart_guarded_state.db"


def main() -> dict:
    store = EffectStore(DB_PATH)
    idempotency_ref = derive_idempotency_ref(
        LOGICAL_ACTION_ID, action_type="tool.restart_effect_tool", agent_id=AGENT_ID
    )

    # --- Attempt 1: process A. Same crash shape as the naive case -- effect
    # commits, then the process dies before returning. The PENDING record
    # written just before `real_effect_fn()` is called lands in
    # GUARD_DB_PATH, not in memory.
    guard_process_a = DurableIdempotencyGuard(GUARD_DB_PATH, reset=True)

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
    guard_process_a.close()

    # --- Simulated restart: process A is gone, but GUARD_DB_PATH is not --
    # process B constructs a fresh DurableIdempotencyGuard against the same
    # path and reads the PENDING record on its first call.
    guard_process_b = DurableIdempotencyGuard(GUARD_DB_PATH, reset=False)

    def effect_tool_attempt_2(logical_action_id: str) -> str:
        def real_effect_fn():
            return store.apply_effect(logical_action_id, 2)

        effect_id, guard_outcome = guard_process_b.guard(idempotency_ref, 2, real_effect_fn)
        if guard_outcome in ("PENDING_GUARD", "RECONCILED_GUARD"):
            return f"guarded: {guard_outcome} (no duplicate effect applied)"
        return f"committed: {effect_id}"

    attempt_2_result = run_single_tool_call(
        effect_tool_attempt_2, "restart_effect_tool", {"logical_action_id": LOGICAL_ACTION_ID}
    )

    # Provider-confirmed resolution, same evidence rule as the base worked
    # example's reconcile() -- never window_ms, never "the record survived
    # the restart" by itself.
    reconciled_effect_id = guard_process_b.reconcile(idempotency_ref, LOGICAL_ACTION_ID, store)
    guard_process_b.close()

    observed = store.read_independent(LOGICAL_ACTION_ID)
    store.close()

    return {
        "case": "RESUME_AFTER_RESTART_GUARDED",
        "logical_action_id": LOGICAL_ACTION_ID,
        "idempotency_ref": idempotency_ref,
        "attempt_1": attempt_1_result,
        "attempt_1_guard_events": guard_process_a.events,
        "attempt_2": attempt_2_result,
        "attempt_2_guard_events": guard_process_b.events,
        "reconciled_effect_id": reconciled_effect_id,
        "effect_observation": observed,
        "duplicate_prevented": bool(
            observed["readable"] and observed["effect_count"] == 1
        ),
    }


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["duplicate_prevented"] else 1)
