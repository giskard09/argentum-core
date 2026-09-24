"""Conformance runner for idempotency-ref v1.1 through crewAI's real
ToolUsage.use(), same convention as verify.py / verify_restart.py.

Runs logical_identity_case.py once per guard mode and checks it against
../idempotency-ref-v1.1/vectors.json, the same file the spec-level
verifier replays:

  conformant  every event gives the declared outcome and effect count, with
              the idempotency_ref and admitted_payload_digest of the vector
              (computed from the arguments crewAI delivered to the tool);
              case 2 arrives through crewAI's own re-dispatch.
  negatives   each non-conformant guard first diverges exactly where its
              negative vector declares, and on a different case each time:
              content_key on case 3, no_digest_check and digest_inside on
              case 4 with different outcomes (DUPLICATE vs EXECUTE).

Requires crewai installed (pip install crewai). Run: python3 verify_logical_identity.py
"""

from __future__ import annotations

import contextlib
import io
import sys

import logical_identity_case

NEGATIVE_MODES = {
    "negative-content-derived-key": "content_key",
    "negative-no-digest-check": "no_digest_check",
    "negative-digest-inside-artifact": "digest_inside",
}


def first_divergence(observed, events):
    for got, ev in zip(observed, events):
        if (got["outcome"], got["effects_after"]) != (ev["expected"], ev["effects_after"]):
            return {"event": ev["id"], "outcome": got["outcome"], "effects_after": got["effects_after"]}
    return None


def main() -> int:
    vectors = logical_identity_case.load_vectors()
    events = vectors["events"]
    print("crewai-unguarded-retry / idempotency-ref v1.1 logical identity -- 4 cases + 3 negatives")

    with contextlib.redirect_stdout(io.StringIO()):
        runs = {mode: logical_identity_case.main(mode)
                for mode in ("conformant", *NEGATIVE_MODES.values())}

    ok = True
    conf = runs["conformant"]

    if conf["crewai_invocations"] != 4 or conf["dispatches"][0]["tool_invocations"] != 2:
        print(f"  [FAIL] dispatch shape: expected case 2 via crewAI re-dispatch, got {conf['dispatches']}")
        ok = False

    for got, ev in zip(conf["events"], events):
        checks = {
            "outcome": (got["outcome"], ev["expected"]),
            "effects_after": (got["effects_after"], ev["effects_after"]),
            "idempotency_ref": (got["idempotency_ref"], ev["idempotency_ref"]),
            "admitted_payload_digest": (got["admitted_payload_digest"], ev["admitted_payload_digest"]),
        }
        bad = {k: v for k, v in checks.items() if v[0] != v[1]}
        if bad:
            print(f"  [FAIL] {ev['id']}: {bad}")
            ok = False
        else:
            print(f"  [PASS] {ev['id']}: {got['outcome']}, effects={got['effects_after']}, ref/digest match vectors")

    for neg in vectors["negative_vectors"]:
        mode = NEGATIVE_MODES[neg["id"]]
        run = runs[mode]
        div = first_divergence(run["events"], events)
        refs_ok = True
        if isinstance(neg["events"], list):
            refs_ok = [e["idempotency_ref"] for e in run["events"]] == [e["idempotency_ref"] for e in neg["events"]]
        if div == neg["expected_divergence"] and refs_ok:
            print(f"  [PASS] {neg['id']} ({mode}): diverges at {div['event']} -> {div['outcome']}, effects={div['effects_after']}")
        else:
            print(f"  [FAIL] {neg['id']} ({mode}): divergence={div}, expected={neg['expected_divergence']}, refs_ok={refs_ok}")
            ok = False

    print()
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
