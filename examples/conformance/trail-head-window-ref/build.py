"""Build vectors.json for trail-head-window-ref (docs/spec/trail-head-ref-v1.md,
"Window verification").

Inputs are produced with the reference producer (append_entry, make_checkpoint,
seal_period). The expected results below are written by hand from the spec, not
computed by the verifier: verify.py scores the verifier against them.

    python3 build.py    # rewrites vectors.json deterministically
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(ROOT))

from plugins.agt_evidence_anchor.action_ref import compute_action_ref  # noqa: E402
from plugins.agt_evidence_anchor.merkle import get_proof  # noqa: E402
from plugins.agt_evidence_anchor.trail_head import (  # noqa: E402
    append_entry, checkpoint_digest, compute_head, entry_preimage, make_checkpoint, seal_period,
)

AGENT, OTHER = "agent-alpha", "agent-beta"
T1, T2 = "2026-09-23T18:00:00.000Z", "2026-09-23T19:00:00.000Z"
K = 5  # the window is seq 5..8 of an 8-entry log


def ref(i, agent=AGENT):
    return compute_action_ref(agent, "payments.transfer", "trail-head-window",
                              f"2026-09-23T17:{i:02d}:00.000Z")


def log_of(n, agent=AGENT):
    log = []
    for i in range(1, n + 1):
        append_entry(log, agent, ref(i, agent))
    return log


def sealed(log, period_end):
    cps = [make_checkpoint(AGENT, period_end, log), make_checkpoint(OTHER, period_end, log_of(2, OTHER))]
    root, tree, _ = seal_period(cps)
    return {"checkpoint": cps[0], "proof": get_proof(checkpoint_digest(cps[0]), tree), "root": root}


def as_anchor(s):
    return {"anchor": s["checkpoint"], "anchor_proof": s["proof"], "anchor_root": s["root"]}


def rechain(refs, start_seq, prev):
    out = []
    for i, r in enumerate(refs):
        pre = entry_preimage(AGENT, start_seq + i, r, prev)
        e = dict(pre)
        del e["v"]
        e["head"] = compute_head(agent_id=AGENT, seq=start_seq + i, action_ref=r, prev_head=prev)
        out.append(e)
        prev = e["head"]
    return out


LOG = log_of(8)
WIN = LOG[K - 1:]
TAIL = sealed(LOG, T2)
ANCHOR = as_anchor(sealed(LOG[:K - 1], T1))
# Attacker re-chains seq 5..8 from a prev_head of its own choosing.
FAKE = rechain([ref(40 + i) for i in range(4)], K, "ab" * 32)


def ok(verdict, completeness, reason, window_anchor):
    return {"verdict": verdict, "completeness": completeness, "reason": reason,
            "window_anchor": window_anchor}


def fail(verdict, reason):
    return {"verdict": verdict, "completeness": "failed", "reason": reason, "window_anchor": None}


CASES = [
    ("thw-001-full-log-no-checkpoint", "Regression: full log from seq 1, no checkpoint.",
     {"entries": LOG}, ok("continuity_only", "not_evaluated", "no_checkpoint", "genesis")),
    ("thw-002-full-log-tail-checkpoint", "Regression: full log sealed at seq 8.",
     {"entries": LOG, **TAIL}, ok("complete", "proven", None, "genesis")),
    ("thw-003-window-certified-anchor", "Honest window 5..8 with a checkpoint at seq 4 proven in its root.",
     {"entries": WIN, "from_seq": K, **ANCHOR},
     ok("continuity_only", "not_evaluated", "no_checkpoint", "certified")),
    ("thw-004-window-uncertified-anchor", "Honest window 5..8, start taken from the records: scope is declared.",
     {"entries": WIN, "from_seq": K},
     ok("continuity_only", "not_evaluated", "no_checkpoint", "uncertified")),
    ("thw-005-window-tail-checkpoint", "Honest window 5..8 sealed at seq 8: proven from seq 5 only, never complete.",
     {"entries": WIN, "from_seq": K, **TAIL},
     ok("window_complete", "proven_from_seq", None, "uncertified")),
    ("thw-006-rewrite-with-start-no-evidence", "Window re-chained from a chosen prev_head, nothing external: indistinguishable, documented limit.",
     {"entries": FAKE, "from_seq": K},
     ok("continuity_only", "not_evaluated", "no_checkpoint", "uncertified")),
    ("thw-007-rewrite-with-start-certified-anchor", "Same rewrite against a certified anchor.",
     {"entries": FAKE, "from_seq": K, **ANCHOR}, fail("anchor_mismatch", "prev_head_differs_from_anchor")),
    ("thw-008-rewrite-with-start-tail-checkpoint", "Same rewrite against the tail checkpoint.",
     {"entries": FAKE, "from_seq": K, **TAIL}, fail("checkpoint_mismatch", "head_differs_from_checkpoint")),
    ("thw-009-window-truncated-no-checkpoint", "Window cut to 5..6, nothing external.",
     {"entries": WIN[:2], "from_seq": K},
     ok("continuity_only", "not_evaluated", "no_checkpoint", "uncertified")),
    ("thw-010-window-truncated-tail-checkpoint", "Window cut to 5..6 against the checkpoint at seq 8.",
     {"entries": WIN[:2], "from_seq": K, **TAIL}, fail("truncated", "log_shorter_than_checkpoint")),
    ("thw-011-headless-log-not-a-window", "Seq 5..8 presented without declaring a window: a full log missing its head.",
     {"entries": WIN}, fail("broken", "seq_gap")),
]

doc = {
    "spec_version": "trail-head-ref-v1#window-verification",
    "description": "Window verification for trail-head-ref v1: a log presented from seq k > 1. "
                   "`input` holds the arguments of verify_trail; `expected` is what a conformant verifier reports.",
    "vectors": [{"id": i, "description": d, "input": inp, "expected": exp} for i, d, inp, exp in CASES],
}
(HERE / "vectors.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
print(f"wrote {len(CASES)} vectors")
