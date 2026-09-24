"""Reference check for trail-head-window-ref: scores verify_trail against every
vector in vectors.json (verdict, completeness, reason and window_anchor must all
match).

It also runs an anchor-blind mutant, a verifier that drops the anchor arguments,
and requires it to fail at least one vector. A corpus that such a verifier passes
would not show that the anchor is checked.

    python3 verify.py    # exit 0 iff every vector matches and the mutant is caught
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent.parent))

from plugins.agt_evidence_anchor.trail_head import verify_trail  # noqa: E402

FIELDS = ("verdict", "completeness", "reason", "window_anchor")


def observed(inp, drop_anchor=False):
    kw = {k: v for k, v in inp.items() if k != "entries"}
    if drop_anchor:
        kw = {k: v for k, v in kw.items() if not k.startswith("anchor")}
    r = verify_trail(inp["entries"], **kw)
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
    caught = [v["id"] for v in vectors if observed(v["input"], drop_anchor=True) != v["expected"]]
    print(f"anchor-blind mutant fails {len(caught)} vector(s): {', '.join(caught) or 'none'}")
    if not caught:
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
