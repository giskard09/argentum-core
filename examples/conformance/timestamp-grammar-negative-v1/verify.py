#!/usr/bin/env python3
"""Conformance runner for the timestamp-grammar-negative-v1 fixture.

Checks that the action-ref timestamp grammar gate rejects timestamps that
are not canonical RFC 3339 UTC with ASCII digits.

The grammar is `[0-9]`, not `\\d`: in Python 3 `\\d` matches any Unicode
decimal digit, so a pattern written with it accepts non-ASCII digit forms
that the spec does not allow. Same pattern as
plugins/agt_evidence_anchor/action_ref.py (PR #114, PR #115).

This runner is standalone on purpose: it does not import the
recompute-drift-v1 verifier, which stays pinned.

Coverage is currently empty. The fixture reserves a slot for the first
negative vector, to be contributed separately. A zero-vector run is reported
as such and never as a pass for that slot.

Deterministic: stdlib only, no wall-clock, no randomness, no network.

Usage: python3 verify.py
Exit codes: 0 all present vectors fail closed (and the positive control
is accepted), 1 any failure.
"""

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent

CANONICAL_TS = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z$")

# Guard against regressing to \d, \D, \w, \s in the grammar itself.
assert not re.search(r"\\[dDwWsS]", CANONICAL_TS.pattern), "grammar must use [0-9], not shorthand classes"

# Positive control: a canonical ASCII timestamp must pass, so the grammar
# is not rejecting everything.
POSITIVE_CONTROL = "2026-10-04T12:00:00.000Z"


def check_timestamp(ts):
    """Return (ok, reason). ok is True only for canonical RFC 3339 UTC, ASCII digits."""
    if not isinstance(ts, str):
        return False, "timestamp is not a string"
    if not CANONICAL_TS.match(ts):
        return False, "timestamp grammar rejected: not RFC 3339 UTC with [0-9] digits, three fractional digits and Z"
    return True, "canonical"


def load(name):
    with open(HERE / name, encoding="utf-8") as f:
        return json.load(f)


def main():
    failures = 0

    ok, reason = check_timestamp(POSITIVE_CONTROL)
    if ok:
        print("PASS  positive-control              canonical ASCII timestamp accepted")
    else:
        failures += 1
        print("FAIL  positive-control              %s" % reason)

    fixture = load("timestamp-grammar-negative-v1.fixture.json")
    vectors = fixture["vectors"]

    for v in vectors:
        ok, reason = check_timestamp(v["timestamp"])
        if ok:
            failures += 1
            print("FAIL  %-32s grammar accepted a timestamp that must fail closed" % v["id"])
        else:
            print("PASS  %-32s fail-closed: %s" % (v["id"], reason))

    open_slots = [s for s in fixture.get("reserved_slots", []) if s["status"] == "open"]
    for s in open_slots:
        print("OPEN  slot %s                      reserved, no vector in this repo" % s["slot"])

    if failures:
        print("\n%d check(s) failed" % failures)
        return 1
    if not vectors:
        print("\nno negative vectors present: %d slot(s) open. Positive control only." % len(open_slots))
    else:
        print("\nall assertions pass: %d negative vector(s) failed closed" % len(vectors))
    return 0


if __name__ == "__main__":
    sys.exit(main())
