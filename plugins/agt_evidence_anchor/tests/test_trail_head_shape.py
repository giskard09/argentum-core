"""Shape rules of docs/spec/trail-head-ref-v1.md, scored against the published
vectors in examples/conformance/trail-head-shape-ref/vectors.json."""
import copy
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from plugins.agt_evidence_anchor.trail_head import verify_trail  # noqa: E402

VECTORS = json.load(open(os.path.join(ROOT, "examples/conformance/trail-head-shape-ref/vectors.json")))["vectors"]


@pytest.mark.parametrize("v", VECTORS, ids=[v["id"] for v in VECTORS])
def test_vector(v):
    inp = copy.deepcopy(v["input"])
    r = verify_trail(inp.pop("entries"), **inp)
    assert {k: r.get(k) for k in ("verdict", "reason", "completeness")} == v["expected"]
