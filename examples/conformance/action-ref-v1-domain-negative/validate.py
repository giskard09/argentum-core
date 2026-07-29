#!/usr/bin/env python3
"""Validator for action-ref-v1-domain-negative vectors.

Each vector's `expect_valid` says whether compute_action_ref should accept
the preimage (raise nothing) or reject it (raise OutOfProfileDomainError,
per action-ref.md's Domain paragraph). For rejected vectors, `expect_error_field`
must match the field named on the raised error.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from plugins.agt_evidence_anchor.action_ref import compute_action_ref, OutOfProfileDomainError  # noqa: E402


def main() -> int:
    fixture = json.loads((HERE / "action-ref-v1-domain-negative.fixture.json").read_text())
    failures = 0
    for vec in fixture["vectors"]:
        p = vec["preimage"]
        errors = []
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
