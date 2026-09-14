"""CASO A control — same UNGUARDED_RETRY scenario, tool wrapped with
idempotency-ref-v1 (../../../docs/spec/idempotency-ref.md).

Same crewAI real retry engine, same injected failure point, same fixed
logical_action_id. The only change is a guard at the tool boundary that
derives idempotency_ref once (before any attempt) and enforces the
PENDING/COMMITTED lifecycle -- exactly the same guard/reconciler pattern
already verified against mycelium-runtime in the Nandana/mycelium-labs
worked example (2026-07-27), applied here for the first time against
CrewAI's own retry/re-dispatch instead of a simulated crash.

Run: python3 guarded_case.py
"""

from __future__ import annotations

import json
import sys

from effect_store import EffectStore
from harness import run_tool_under_real_crewai_retry
from idempotency_guard import IdempotencyGuard, derive_idempotency_ref

LOGICAL_ACTION_ID = "unguarded-retry-001"
AGENT_ID = "crewai-unguarded-retry-worked-example"
DB_PATH = "/tmp/argentum_crewai_guarded.db"
MAX_ATTEMPTS = 3


def main() -> dict:
    store = EffectStore(DB_PATH)
    guard = IdempotencyGuard()
    calls = {"n": 0}

    idempotency_ref = derive_idempotency_ref(
        LOGICAL_ACTION_ID, action_type="tool.unguarded_effect_tool", agent_id=AGENT_ID
    )

    def guarded_effect_tool(logical_action_id: str) -> str:
        calls["n"] += 1
        attempt_no = calls["n"]

        def real_effect_fn():
            effect_id = store.apply_effect(logical_action_id, attempt_no)
            raise RuntimeError(
                "simulated crash: effect committed, result not yet registered"
            )

        effect_id, guard_outcome = guard.guard(idempotency_ref, attempt_no, real_effect_fn)
        if guard_outcome in ("PENDING_GUARD", "RECONCILED_GUARD"):
            # Guard short-circuited before touching the real effect again --
            # return a benign string so crewAI's outer retry loop does not
            # even see an exception for this call.
            return f"guarded: {guard_outcome} (no duplicate effect applied)"
        return f"committed: {effect_id}"

    harness_result = run_tool_under_real_crewai_retry(
        guarded_effect_tool, LOGICAL_ACTION_ID, max_attempts=MAX_ATTEMPTS
    )

    # Provider-confirmed resolution (RECONCILED_GUARD): after the run, a
    # reconciler independently confirms the PENDING record's real outcome
    # from the effect store -- never from window_ms alone.
    reconciled_effect_id = guard.reconcile(idempotency_ref, LOGICAL_ACTION_ID, store)

    observed = store.read_independent(LOGICAL_ACTION_ID)
    store.close()

    return {
        "case": "UNGUARDED_RETRY_WITH_IDEMPOTENCY_REF_V1_GUARD",
        "logical_action_id": LOGICAL_ACTION_ID,
        "idempotency_ref": idempotency_ref,
        "crewai_outer_run_attempts": harness_result["run_attempts"],
        "python_level_invocations": calls["n"],
        "guard_events": guard.events,
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
