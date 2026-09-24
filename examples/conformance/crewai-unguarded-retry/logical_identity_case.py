"""idempotency-ref v1.1 -- the four-case logical-identity test, dispatched
through crewAI's real ToolUsage.use() instead of replayed against a ledger.

Same events, keys and payloads as ../idempotency-ref-v1.1/vectors.json
(test defined by impartshadow in crewAI issue 5802; regression in
stringsofthemind-oss once PR 45):

  case 1  A  $100 -> X   first intentional payment         EXECUTE
  case 2  A  $100 -> X   retry after lost acknowledgement  DUPLICATE
  case 3  B  $100 -> X   second intentional payment        EXECUTE
  case 4  A  $125 -> X   drifted retry                     CONFLICT

How each event reaches the tool:

  cases 1+2  ONE ToolUsage.use() call. The tool's effect commits, then the
             acknowledgement is lost (the tool raises), and crewAI's own
             re-dispatch resends the identical ToolCalling. Case 2 is that
             re-dispatch, not a second call we make.
  case 3     a separate use() call: a new intentional action, admitted
             under its own logical id B.
  case 4     a separate use() call with logical id A and amount 12500: a
             model-regenerated re-proposal. crewAI's re-dispatch never
             changes arguments (see harness.run_single_tool_call), so a
             drifted retry only reaches the tool from above ToolUsage.

The guard decides inside the tool, before the effect. Effects are counted
by an independent read of the SQLite effect store after every invocation,
not from guard state.

Run: python3 logical_identity_case.py [conformant|no_digest_check|content_key|digest_inside]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from effect_store import EffectStore
from harness import run_single_tool_call, run_tool_call_under_real_crewai_retry
from logical_identity_guard import LogicalIdentityGuard

VECTORS = Path(__file__).resolve().parent.parent / "idempotency-ref-v1.1" / "vectors.json"
TOOL_NAME = "payment_effect_tool"
DB_PATH = "/tmp/argentum_crewai_logical_identity_{mode}.db"


def load_vectors() -> dict:
    return json.loads(VECTORS.read_text(encoding="utf-8"))


def main(mode: str = "conformant") -> dict:
    vectors = load_vectors()
    events = vectors["events"]
    store = EffectStore(DB_PATH.format(mode=mode))
    guard = LogicalIdentityGuard(events[0]["idempotency_artifact"], mode=mode)
    invocations: list[dict] = []
    lose_ack_once = {"pending": True}

    def payment_effect_tool(
        logical_action_id: str, amount_cents: int, currency: str, recipient: str
    ) -> str:
        admitted_payload = {"amount_cents": amount_cents, "currency": currency, "recipient": recipient}
        n = len(invocations) + 1

        def real_effect_fn():
            return store.apply_effect(logical_action_id, n)

        decision = guard.dispatch(logical_action_id, admitted_payload, real_effect_fn)
        decision["effects_after"] = store.read_independent(logical_action_id)["counter_value"]
        decision["logical_action_id"] = logical_action_id
        decision["admitted_payload"] = admitted_payload
        invocations.append(decision)

        if lose_ack_once["pending"]:
            lose_ack_once["pending"] = False
            raise RuntimeError("simulated lost acknowledgement: effect committed, result not delivered")
        return json.dumps({"outcome": decision["outcome"], "effect_id": decision["effect_id"]})

    def arguments(ev: dict) -> dict:
        return dict(ev["admitted_payload"], logical_action_id=ev["idempotency_artifact"]["idempotency_key"])

    plan = [
        ([events[0], events[1]], "ToolUsage.use() + crewAI re-dispatch", run_tool_call_under_real_crewai_retry),
        ([events[2]], "ToolUsage.use()", run_single_tool_call),
        ([events[3]], "ToolUsage.use()", run_single_tool_call),
    ]
    dispatches = []
    for evs, path, run in plan:
        before = len(invocations)
        result = run(payment_effect_tool, TOOL_NAME, arguments(evs[0]))
        dispatches.append({"events": [ev["id"] for ev in evs], "path": path,
                           "tool_invocations": len(invocations) - before, "result": result})
    total_effects = store.read_independent(events[0]["idempotency_artifact"]["idempotency_key"])["counter_value"]
    store.close()

    observed = [
        dict(inv, id=ev["id"]) for inv, ev in zip(invocations, events)
    ]
    return {
        "case": "LOGICAL_IDENTITY_4_CASES",
        "mode": mode,
        "crewai_invocations": len(invocations),
        "dispatches": dispatches,
        "events": observed,
        "total_effects": total_effects,
    }


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1] if len(sys.argv) > 1 else "conformant"), indent=2))
