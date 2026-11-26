"""Build vectors.json for trail-head-shape-ref (docs/spec/trail-head-ref-v1.md,
"Shape rules").

Inputs are produced with the reference producer, then mutated one field at a
time. The expected results below are written by hand from the spec, not
computed by the verifier: verify.py scores the verifier against them.

    python3 build.py    # rewrites vectors.json deterministically
"""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(ROOT))

from plugins.agt_evidence_anchor.action_ref import compute_action_ref  # noqa: E402
from plugins.agt_evidence_anchor.merkle import build_merkle_tree, get_proof  # noqa: E402
from plugins.agt_evidence_anchor.trail_head import (  # noqa: E402
    append_entry, checkpoint_digest, make_checkpoint,
)

AGENT = "agent-alpha"
T1 = "2026-09-23T18:00:00.000Z"
K = 3  # the window vectors present seq 3..4 of a 4-entry log


def ref(i):
    return compute_action_ref(AGENT, "payments.transfer", "trail-head-shape",
                              f"2026-09-23T17:{i:02d}:00.000Z")


def log_of(n, agent_seq=False):
    log = []
    for i in range(1, n + 1):
        append_entry(log, AGENT, ref(i), agent_seq=i if agent_seq else None)
    return log


def sealed(cp):
    """Proof and root for a checkpoint object exactly as given (even a malformed
    one), so that only its shape can reject it."""
    d = checkpoint_digest(cp)
    tree = build_merkle_tree([d])
    return {"proof": get_proof(d, tree), "root": tree.root}


def with_cp(entries, cp):
    return {"entries": entries, "checkpoint": cp, **sealed(cp)}


def edited(obj, **kw):
    o = copy.deepcopy(obj)
    for k, v in kw.items():
        if v is ...:
            o.pop(k, None)
        else:
            o[k] = v
    return o


def expected(verdict, reason, completeness):
    return {"verdict": verdict, "reason": reason, "completeness": completeness}


FAILED = "failed"
base = log_of(3)
good_cp = make_checkpoint(AGENT, T1, base)
one = log_of(1)
one_cp = make_checkpoint(AGENT, T1, one)

vectors = []


def add(vid, desc, inp, exp):
    vectors.append({"id": vid, "description": desc, "input": inp, "expected": exp})


add("ths-001-baseline", "Regression: a well-formed full log, no checkpoint.",
    {"entries": base}, expected("continuity_only", "no_checkpoint", "not_evaluated"))

e = copy.deepcopy(base); e[0]["prev_head"] = None
add("ths-002-prev-head-null-at-genesis",
    "prev_head present as null at seq 1. Absent is required; null is not absent.",
    {"entries": e}, expected("malformed", "entry_preimage", FAILED))

e = copy.deepcopy(base); e[1]["prev_head"] = ""
add("ths-003-prev-head-empty-string", "prev_head is \"\" at seq 2.",
    {"entries": e}, expected("malformed", "entry_preimage", FAILED))

e = log_of(3, agent_seq=True)
for x in e:
    x["agent_seq"] = None
add("ths-004-agent-seq-null-on-all",
    "agent_seq present as null on every record. Absent and null are not interchangeable.",
    {"entries": e}, expected("malformed", "entry_preimage", FAILED))

e = log_of(3, agent_seq=True); e[1]["agent_seq"] = False
add("ths-005-agent-seq-false", "agent_seq is false at seq 2.",
    {"entries": e}, expected("malformed", "entry_preimage", FAILED))

e = copy.deepcopy(base); e[0]["note"] = "not covered by head"
add("ths-006-extra-entry-key-ignored",
    "An unknown key on an entry is ignored: it is not covered by head and does not fail the shape check.",
    {"entries": e}, expected("continuity_only", "no_checkpoint", "not_evaluated"))

e = copy.deepcopy(base); e[0]["head"] = e[0]["head"].upper()
add("ths-007-head-uppercase", "head in uppercase hex.",
    {"entries": e}, expected("malformed", "entry_shape", FAILED))

add("ths-008-checkpoint-seq-boolean", "Checkpoint seq is true (a boolean, not an integer), sealed as given.",
    with_cp(one, edited(one_cp, seq=True)), expected("malformed", "checkpoint_shape", FAILED))

add("ths-009-checkpoint-period-end-null", "Checkpoint period_end is null, sealed as given.",
    with_cp(one, edited(one_cp, period_end=None)), expected("malformed", "checkpoint_shape", FAILED))

add("ths-010-checkpoint-period-end-missing", "Checkpoint has no period_end, sealed as given.",
    with_cp(one, edited(one_cp, period_end=...)), expected("malformed", "checkpoint_shape", FAILED))

add("ths-011-checkpoint-period-end-garbage", "Checkpoint period_end is not a timestamp, sealed as given.",
    with_cp(one, edited(one_cp, period_end="garbage")), expected("malformed", "checkpoint_shape", FAILED))

add("ths-012-checkpoint-unknown-key-sealed",
    "A checkpoint with an unknown key, sealed as given, is not rejected by shape: the key is part of the digest.",
    with_cp(one, edited(one_cp, note="part of the digest")), expected("complete", None, "proven"))

# window vectors: the anchor is a checkpoint at seq K-1
full = log_of(4)
window = copy.deepcopy(full[K - 1:])
anchor_cp = make_checkpoint(AGENT, T1, full[:K - 1])


def win(anchor):
    s = sealed(anchor)
    return {"entries": window, "from_seq": K, "anchor": anchor,
            "anchor_proof": s["proof"], "anchor_root": s["root"]}


add("ths-013-anchor-seq-boolean", "Window anchor seq is true, sealed as given.",
    win(edited(anchor_cp, seq=True)), expected("anchor_unproven", "anchor_shape", FAILED))

add("ths-014-anchor-period-end-missing", "Window anchor has no period_end, sealed as given.",
    win(edited(anchor_cp, period_end=...)), expected("anchor_unproven", "anchor_shape", FAILED))

add("ths-015-window-certified-baseline", "Regression: the same window with a well-formed anchor passes the shape check.",
    win(anchor_cp), expected("continuity_only", "no_checkpoint", "not_evaluated"))

out = {
    "spec_version": "trail-head-ref-v1#shape-rules",
    "description": "Shape rules for trail-head-ref v1: each vector changes one field of a well-formed input. `input` holds the arguments of verify_trail; `expected` is what a conformant verifier reports.",
    "vectors": vectors,
    "provenance": "Built by build.py with the reference producer. Expected results are hand-written from docs/spec/trail-head-ref-v1.md, not computed by the verifier.",
}
(HERE / "vectors.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(f"wrote {len(vectors)} vectors")
