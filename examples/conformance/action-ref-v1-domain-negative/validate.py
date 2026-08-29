#!/usr/bin/env python3
"""Validator for action-ref-v1-domain-negative vectors.

Each vector's `expect_valid` says whether compute_action_ref should accept
the preimage (raise nothing) or reject it (raise OutOfProfileDomainError,
per action-ref.md's Domain paragraph). For rejected vectors, `expect_error_field`
must match the field named on the raised error.

For rejected vectors, this validator also asserts that zero SHA-256 digests
were computed during the call -- SOURCE.md claims "the check runs before any
digest is computed", but until this assertion existed that was true only by
observation of the current implementation, not something a future regression
would be caught failing: a rewrite that computed the digest and then decided
to reject based on the timestamp/agent_id/scope fields (instead of rejecting
before hashing) would still raise OutOfProfileDomainError and pass every
other check here, silently invalidating the claim. hashlib.sha256 is wrapped
for the duration of each call to count invocations.
"""
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from plugins.agt_evidence_anchor.action_ref import compute_action_ref, OutOfProfileDomainError  # noqa: E402

_real_sha256 = hashlib.sha256


def _counting_sha256(*args, **kwargs):
    _counting_sha256.calls += 1
    return _real_sha256(*args, **kwargs)


def main() -> int:
    fixture = json.loads((HERE / "action-ref-v1-domain-negative.fixture.json").read_text())
    failures = 0
    for vec in fixture["vectors"]:
        p = vec["preimage"]
        errors = []
        _counting_sha256.calls = 0
        with patch("hashlib.sha256", _counting_sha256):
            try:
                compute_action_ref(p["agent_id"], p["action_type"], p["scope"], p["timestamp"])
                accepted = True
                field = None
            except OutOfProfileDomainError as e:
                accepted = False
                field = e.field

        if accepted != vec["expect_valid"]:
            errors.append(f"expected valid={vec['expect_valid']}, got valid={accepted}")
        if not accepted and field != vec.get("expect_error_field"):
            errors.append(f"expected error field {vec.get('expect_error_field')!r}, got {field!r}")
        if not accepted and _counting_sha256.calls != 0:
            errors.append(
                f"domain check rejected but {_counting_sha256.calls} SHA-256 digest(s) were "
                f"computed before the rejection -- the check must run before any digest"
            )

        if errors:
            failures += 1
            print(f"FAIL {vec['id']}:")
            for e in errors:
                print(f"  - {e}")
        else:
            status = "accepted" if accepted else f"rejected ({field})"
            print(f"PASS {vec['id']} ({status})")

    print()
    if failures:
        print(f"{failures} of {len(fixture['vectors'])} vectors FAILED")
        return 1
    print(f"All {len(fixture['vectors'])} vectors PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
