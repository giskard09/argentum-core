"""Build vectors.json for trail-head-cadence-ref (docs/spec/trail-head-ref-v1.md,
"Cadence ceiling").

Inputs are produced with the reference producer (append_entry, make_checkpoint).
The expected results below are written by hand from the spec, not computed by
the verifier: verify.py scores the verifier against them.

    python3 build.py    # rewrites vectors.json deterministically
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(ROOT))

from plugins.agt_evidence_anchor.action_ref import compute_action_ref  # noqa: E402
from plugins.agt_evidence_anchor.trail_head import append_entry, make_checkpoint  # noqa: E402

A, B = "agent_cad_001", "agent_cad_002"
T = "2026-10-23T{:02d}:00:{}Z"
CEILING = 3600


def log_of(n, agent):
    log = []
    for i in range(1, n + 1):
        append_entry(log, agent, compute_action_ref(
            agent, "payments.transfer", "trail-head-cadence", f"2026-10-23T00:{i:02d}:00.000Z"))
    return log


def extend(log, agent, i_from, i_to):
    for i in range(i_from, i_to + 1):
        append_entry(log, agent, compute_action_ref(
            agent, "payments.transfer", "trail-head-cadence", f"2026-10-23T00:{i:02d}:00.000Z"))
    return log


def mixed_cps():
    log = log_of(9, A)
    out = [cp(A, pe(0), log)]
    out.append(cp(A, pe(1), extend(log, A, 10, 12)))
    out.append(cp(A, pe(2), log))
    out.append(cp(A, pe(3), extend(log, A, 13, 15)))
    return out


def cp(agent, period_end, log):
    return make_checkpoint(agent, period_end, log)


def pe(h, ms="00.000"):
    return T.format(h, ms)


def vec(vid, description, checkpoints, ceiling, expected):
    return {
        "id": vid,
        "description": description,
        "input": {"checkpoints": checkpoints, "declared_max_period_s": ceiling},
        "expected": expected,
    }


def breach(prev_pe, pe_s, gap_s, ceiling):
    return {
        "verdict": "period_exceeds_declared_maximum",
        "reason": None,
        "prev_period_end": prev_pe,
        "period_end": pe_s,
        "gap_s": gap_s,
        "declared_max_period_s": ceiling,
    }


def ok():
    return {
        "verdict": "ok",
        "reason": None,
        "prev_period_end": None,
        "period_end": None,
        "gap_s": None,
        "declared_max_period_s": None,
    }


def malformed(reason):
    return {
        "verdict": "malformed",
        "reason": reason,
        "prev_period_end": None,
        "period_end": None,
        "gap_s": None,
        "declared_max_period_s": None,
    }


def main() -> int:
    log_a, log_b = log_of(9, A), log_of(3, B)
    vectors = [
        vec(
            "cad-001-within-ceiling",
            "Hourly checkpoints; every adjacent gap equals the declared period. "
            "Ceiling equals the period: passes.",
            [cp(A, pe(h), log_a) for h in (0, 1, 2)], CEILING, ok(),
        ),
        vec(
            "cad-002-gap-exceeds-ceiling",
            "A two-hour gap in an hourly-ceiling stream: first breach reported.",
            [cp(A, pe(h), log_a) for h in (0, 2)], CEILING,
            breach(pe(0), pe(2), 7200.0, CEILING),
        ),
        vec(
            "cad-003-gap-equals-ceiling",
            "Gap exactly equal to the declared maximum: passes. The comparison "
            "is strictly greater-than.",
            [cp(A, pe(h), log_a) for h in (0, 1)], CEILING, ok(),
        ),
        vec(
            "cad-004-unsorted-within-ceiling",
            "Presented out of order; after sorting the gaps are all within the "
            "ceiling: passes.",
            [cp(A, pe(h), log_a) for h in (2, 0, 1)], CEILING, ok(),
        ),
        vec(
            "cad-005-unsorted-reveals-breach",
            "Presented out of order; sorting reveals a three-hour gap the "
            "presented order hid: first breach reported.",
            [cp(A, pe(h), log_a) for h in (4, 0, 1)], CEILING,
            breach(pe(1), pe(4), 10800.0, CEILING),
        ),
        vec(
            "cad-006-single-checkpoint",
            "Fewer than two checkpoints has no gap to measure: passes.",
            [cp(A, pe(0), log_a)], CEILING, ok(),
        ),
        vec(
            "cad-007-empty",
            "An empty stream has no gap to measure: passes.",
            [], CEILING, ok(),
        ),
        vec(
            "cad-008-two-breaches",
            "Two gaps over the ceiling; the first one in sorted order is "
            "reported.",
            [cp(A, pe(h), log_a) for h in (0, 2, 4)], CEILING,
            breach(pe(0), pe(2), 7200.0, CEILING),
        ),
        vec(
            "cad-009-mixed-empty-filled-periods",
            "Entries appended between some checkpoints and not others: seq "
            "and head advance only on filled periods while period_end "
            "advances every period — an empty seal sits inside a filled "
            "stream. Gaps stay hourly: passes.",
            mixed_cps(), CEILING, ok(),
        ),
        vec(
            "cad-010-one-ms-over",
            "3600.001 seconds between consecutive period_ends: breaches a "
            "3600-second ceiling.",
            [cp(A, pe(0), log_a), cp(A, pe(1, "00.001"), log_a)], CEILING,
            breach(pe(0), pe(1, "00.001"), 3600.001, CEILING),
        ),
        vec(
            "cad-011-missing-period-end",
            "A checkpoint with no period_end cannot be sorted into the stream: "
            "malformed/period_end.",
            [{k: v for k, v in cp(A, pe(0), log_a).items() if k != "period_end"},
             cp(A, pe(1), log_a)],
            CEILING, malformed("period_end"),
        ),
        vec(
            "cad-012-bad-period-end-format",
            "A period_end that does not parse cannot be sorted into the "
            "stream: malformed/period_end.",
            [{**cp(A, pe(0), log_a), "period_end": "not-a-timestamp"},
             cp(A, pe(1), log_a)],
            CEILING, malformed("period_end"),
        ),
        vec(
            "cad-013-not-a-list",
            "checkpoints that is not a list: malformed/not_a_list.",
            {"oops": "not_a_list"}, CEILING, malformed("not_a_list"),
        ),
        vec(
            "cad-014-mixed-agent-masking",
            "Two agents each breach the ceiling alone (2h gaps); interleaved "
            "[A,B,A,B] the sorted gaps look compliant. Mixed streams are "
            "malformed/agent_mixed, never measured — silent masking must "
            "surface as a verdict.",
            [cp(A, pe(0), log_a), cp(B, pe(1), log_b),
             cp(A, pe(2), log_a), cp(B, pe(3), log_b)],
            CEILING, malformed("agent_mixed"),
        ),
    ]
    doc = {
        "spec_version": "trail-head-ref-v1#cadence-ceiling",
        "description": (
            "Declared-maximum cadence check: a consumer declares "
            "declared_max_period_s and the verifier compares consecutive "
            "period_end gaps (sorted) against it. Proposed vectors for the "
            "cadence-ceiling section (added 2026-10-23, now implemented in "
            "the upstream reference module)."
        ),
        "vectors": vectors,
        "provenance": {
            "authored_by": "paymnts (nmatt1)",
            "verification_mode": "asserted",
            "independently_reproduced_by": [],
        },
    }
    out = HERE / "vectors.json"
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"wrote {out} ({len(vectors)} vectors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
