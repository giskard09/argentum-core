#!/usr/bin/env python3
"""Conformance runner for the recompute-drift-v1 fixtures.

Checks the action-ref-v1 recomputation property:

  * every positive vector recomputes byte-identical from its preimage
  * every negative vector fails closed, before invocation, either at the
    timestamp grammar gate or on canonical digest mismatch

The verifier under test is verify_claim() below. It has exactly one code
path: grammar gate, one canonical recomputation, one comparison. There is
no fallback recompute over any drifted serialization, no preimage retry,
no coercion, no normalization. The fixture-integrity section further down
recomputes the drifted digests, but only to check that the fixture data
itself is byte-derived; its results never feed the verifier verdict.

Deterministic: stdlib only, no wall-clock, no randomness, no network.

Usage: python3 verify.py
Exit codes: 0 all vectors pass, 1 any failure.
"""

import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent

# Canonical timestamp grammar per docs/spec/action-ref.md: RFC 3339 UTC,
# exactly three fractional digits, mandatory Z. One valid byte sequence
# per instant.
CANONICAL_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

REQUIRED_FIELDS = ("action_type", "agent_id", "scope", "timestamp")


def jcs(obj):
    """RFC 8785 JCS for a flat object of string values (spec safe band)."""
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def sha256_hex(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def verify_claim(payload, claimed_action_ref):
    """The verifier under test. Single path, fail-closed.

    Returns (ok, reason). ok is True only when the canonical recomputation
    over the payload tuple, as received, equals the claimed action_ref.
    """
    for field in REQUIRED_FIELDS:
        if field not in payload:
            return False, "missing required field: %s" % field
    ts = payload["timestamp"]
    if not isinstance(ts, str) or not CANONICAL_TS.match(ts):
        return False, "timestamp grammar rejected: not RFC 3339 UTC with three fractional digits and Z"
    for field in ("action_type", "agent_id", "scope"):
        if not isinstance(payload[field], str):
            return False, "field %s is not a string" % field
    recomputed = sha256_hex(jcs(payload))
    if recomputed != claimed_action_ref:
        return False, "recomputed action_ref does not match claim"
    return True, "match"


def load(name):
    with open(HERE / name, encoding="utf-8") as f:
        return json.load(f)


def main():
    failures = 0

    # ---- positive vectors: must recompute byte-identical ----
    positive = load("recompute-drift-v1-positive.fixture.json")
    for v in positive["vectors"]:
        ok, reason = verify_claim(v["preimage"], v["action_ref"])
        canonical = jcs(v["preimage"])
        payload_ok = canonical == v["jcs_payload"]
        bytes_ok = canonical.encode("utf-8").hex() == v["preimage_canonical_bytes_hex"]
        if ok and payload_ok and bytes_ok:
            print("PASS  %-32s recomputed byte-identical" % v["id"])
        else:
            failures += 1
            print("FAIL  %-32s %s (payload_ok=%s bytes_ok=%s)" % (v["id"], reason, payload_ok, bytes_ok))

    # ---- negative vectors: verdict must be failure, before invocation ----
    negative = load("recompute-drift-v1-negative.fixture.json")
    for v in negative["vectors"]:
        ok, reason = verify_claim(v["invocation_payload"], v["claimed_action_ref"])
        if ok:
            failures += 1
            print("FAIL  %-32s verifier accepted a vector that must fail closed" % v["id"])
            continue
        stage = "grammar" if reason.startswith("timestamp grammar") else "recompute"
        expected_stage = {"grammar_reject": "grammar", "recompute_mismatch": "recompute"}[v["expected_failure_stage"]]
        if stage != expected_stage:
            failures += 1
            print("FAIL  %-32s failed at %s, expected %s" % (v["id"], stage, expected_stage))
        else:
            print("PASS  %-32s fail-closed (%s): %s" % (v["id"], v["failure_mode"], reason))

    # ---- fixture integrity: drifted digests are byte-derived, not invented ----
    # These checks recompute the drifted forms to confirm the fixture data.
    # They are not part of verify_claim() and never rescue a claim.
    for v in negative["vectors"]:
        drifted = v.get("drifted_serialization") or v.get("drifted_jcs_payload")
        if drifted is None or sha256_hex(drifted) != v["claimed_action_ref"]:
            failures += 1
            print("FAIL  %-32s fixture integrity: claimed_action_ref is not the digest of the stated drifted bytes" % v["id"])
        if v["claimed_action_ref"] == v["correct_action_ref"]:
            failures += 1
            print("FAIL  %-32s fixture integrity: claimed and correct digests collide" % v["id"])
        canonical_payload = v.get("canonical_form_payload") or v["invocation_payload"]
        if sha256_hex(jcs(canonical_payload)) != v["correct_action_ref"]:
            failures += 1
            print("FAIL  %-32s fixture integrity: correct_action_ref does not recompute" % v["id"])

    if failures:
        print("\n%d check(s) failed" % failures)
        return 1
    print("\nall assertions pass: %d positive recomputed byte-identical, %d negative failed closed"
          % (len(positive["vectors"]), len(negative["vectors"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
