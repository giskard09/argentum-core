"""CASO A — UNGUARDED_RETRY.

1. Fix logical_action_id before the tool/model step.
2. The tool commits a local effect (counter increment + effect row, one
   SQLite transaction).
3. Inject failure AFTER the effect commits, BEFORE crewAI registers the
   tool's result (a bare `raise` immediately after the commit call).
4. Let crewAI's real retry/re-dispatch (crewai.tools.tool_usage.ToolUsage,
   unmocked) re-invoke the tool with the SAME logical_action_id.
5. Read the effect store independently, after the run.

Run: python3 unguarded_case.py
"""

from __future__ import annotations

import json
import sys

from effect_store import EffectStore
from harness import run_tool_under_real_crewai_retry

LOGICAL_ACTION_ID = "unguarded-retry-001"
DB_PATH = "/tmp/argentum_crewai_unguarded.db"
MAX_ATTEMPTS = 3


def main() -> dict:
    store = EffectStore(DB_PATH)
    calls = {"n": 0}

    def unguarded_effect_tool(logical_action_id: str) -> str:
        calls["n"] += 1
        # Step 2+3: effect commits, THEN failure is injected -- the exact
        # ordering the spec requires (never before the commit).
        store.apply_effect(logical_action_id, calls["n"])
        raise RuntimeError(
            "simulated crash: effect committed, result not yet registered"
        )

    harness_result = run_tool_under_real_crewai_retry(
        unguarded_effect_tool, LOGICAL_ACTION_ID, max_attempts=MAX_ATTEMPTS
    )
    observed = store.read_independent(LOGICAL_ACTION_ID)
    store.close()

    return {
        "case": "UNGUARDED_RETRY",
        "logical_action_id": LOGICAL_ACTION_ID,
        "crewai_outer_run_attempts": harness_result["run_attempts"],
        "python_level_invocations": calls["n"],
        "last_failure": harness_result["last_failure"],
        "effect_observation": observed,
        "bug_confirmed": bool(observed["readable"] and observed["effect_count"] and observed["effect_count"] > 1),
    }


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["bug_confirmed"] else 1)
