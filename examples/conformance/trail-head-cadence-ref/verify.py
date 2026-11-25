"""Reference check for trail-head-cadence-ref: scores verify_checkpoint_cadence
against every vector in vectors.json (verdict, reason and the breach fields must
all match).

It also runs an agent-blind mutant — the same inputs with agent_id stripped —
and requires it to fail at least one vector. A corpus that passes with the
agent check bypassed would not show that mixed streams are rejected.

    python3 verify.py    # exit 0 iff every vector matches and the mutant is caught
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent.parent))

from plugins.agt_evidence_anchor.trail_head import verify_checkpoint_cadence  # noqa: E402

FIELDS = (
    "verdict",
    "reason",
    "prev_period_end",
    "period_end",
    "gap_s",
    "declared_max_period_s",
)


def observed(inp, drop_agent=False):
    cps = inp["checkpoints"]
    if drop_agent and isinstance(cps, list):
        cps = [{k: v for k, v in c.items() if k != "agent_id"} for c in cps]
    r = verify_checkpoint_cadence(cps, inp["declared_max_period_s"])
    return {f: r.get(f) for f in FIELDS}


def main() -> int:
    vectors = json.loads((HERE / "vectors.json").read_text())["vectors"]
    bad = 0
    for v in vectors:
        got = observed(v["input"])
        match = got == v["expected"]
        bad += not match
        print(f"{'OK ' if match else 'BAD'} {v['id']}: {got['verdict']}/{got['reason']}")
        if not match:
            print(f"    expected {v['expected']}")
    caught = [
        v["id"]
        for v in vectors
        if observed(v["input"], drop_agent=True) != v["expected"]
    ]
    print(f"agent-blind mutant fails {len(caught)} vector(s): {', '.join(caught) or 'none'}")
    if not caught:
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
