"""Reference check for trail-head-shape-ref: scores verify_trail against every
vector in vectors.json (verdict, reason and completeness must all match).

It also runs two mutants and requires each to fail at least one vector:

  * lax-checkpoint: the checkpoint/anchor shape check of the verifier before
    "Shape rules" (any int including bool, period_end not looked at);
  * null-is-absent: record keys whose value is null are dropped before
    verifying, so prev_head/agent_seq of null read as absent.

A corpus that such a verifier passes would not show that the rule is checked.

    python3 verify.py    # exit 0 iff every vector matches and both mutants are caught
"""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent.parent))

from plugins.agt_evidence_anchor import trail_head as th  # noqa: E402

FIELDS = ("verdict", "reason", "completeness")


def observed(inp):
    kw = {k: v for k, v in inp.items() if k != "entries"}
    try:
        r = th.verify_trail(copy.deepcopy(inp["entries"]), **copy.deepcopy(kw))
    except Exception as e:  # a verifier that raises has not produced a verdict
        return {"exception": type(e).__name__}
    return {f: r.get(f) for f in FIELDS}


def lax_checkpoint(cp):
    return isinstance(cp, dict) and cp.get("v") == th.CHECKPOINT_V \
        and th._is_hex64(cp.get("head")) and isinstance(cp.get("seq"), int)


def observed_null_is_absent(inp):
    entries = [{k: v for k, v in e.items() if v is not None} for e in inp["entries"]]
    return observed({**inp, "entries": entries})


def main() -> int:
    vectors = json.loads((HERE / "vectors.json").read_text())["vectors"]
    bad = 0
    for v in vectors:
        got = observed(v["input"])
        match = got == v["expected"]
        bad += not match
        print(f"{'OK ' if match else 'BAD'} {v['id']}: {got.get('verdict')}/{got.get('reason')}")
        if not match:
            print(f"    expected {v['expected']}")

    real = th._checkpoint_shape_ok
    th._checkpoint_shape_ok = lax_checkpoint
    try:
        lax = [v["id"] for v in vectors if observed(v["input"]) != v["expected"]]
    finally:
        th._checkpoint_shape_ok = real
    print(f"lax-checkpoint mutant fails {len(lax)} vector(s): {', '.join(lax) or 'none'}")
    nul = [v["id"] for v in vectors if observed_null_is_absent(v["input"]) != v["expected"]]
    print(f"null-is-absent mutant fails {len(nul)} vector(s): {', '.join(nul) or 'none'}")
    if not lax:
        bad += 1
    if not nul:
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
