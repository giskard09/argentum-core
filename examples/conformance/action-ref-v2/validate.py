#!/usr/bin/env python3
"""Stdlib-only validator for action-ref-v2 vectors.

Additive to v1 — does not replace the v1 fixture set or its validator. For
each vector: recomputes both action_ref_v1 (unchanged bare derivation) and
action_ref_v2 (domain-tagged, 'v2:'-prefixed derivation) from the same
preimage, confirms both match the fixture's stored values, confirms they
never collide, and confirms action_ref_version() reads the marker correctly
off each string's own syntax.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
V2_DOMAIN_TAG = "mycelium.action-ref:v2:"


def jcs(obj: dict) -> bytes:
    return json.dumps(dict(sorted(obj.items())), separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_v1(preimage: dict) -> str:
    return hashlib.sha256(jcs(preimage)).hexdigest()


def compute_v2(preimage: dict) -> str:
    return "v2:" + hashlib.sha256(V2_DOMAIN_TAG.encode("utf-8") + jcs(preimage)).hexdigest()


def action_ref_version(action_ref: str) -> str:
    if action_ref.startswith("v2:") and len(action_ref) == 67:
        return "v2"
    if len(action_ref) == 64:
        return "v1"
    raise ValueError(f"unrecognized action_ref format: {action_ref!r}")


def main() -> int:
    fixture = json.loads((HERE / "action-ref-v2.fixture.json").read_text())
    failures = 0
    for vec in fixture["vectors"]:
        errors = []
        payload = jcs(vec["preimage"]).decode("utf-8")
        if payload != vec["jcs_payload"]:
            errors.append(f"canonical bytes mismatch: computed {payload!r} != expected {vec['jcs_payload']!r}")

        v1 = compute_v1(vec["preimage"])
        if v1 != vec["action_ref_v1"]:
            errors.append(f"v1 digest mismatch: computed {v1} != expected {vec['action_ref_v1']}")

        v2 = compute_v2(vec["preimage"])
        if v2 != vec["action_ref_v2"]:
            errors.append(f"v2 digest mismatch: computed {v2} != expected {vec['action_ref_v2']}")

        if v1 == v2:
            errors.append("v1 and v2 collided — domain separation failed")

        if action_ref_version(v1) != "v1":
            errors.append(f"action_ref_version misread v1 string {v1!r}")
        if action_ref_version(v2) != "v2":
            errors.append(f"action_ref_version misread v2 string {v2!r}")

        if errors:
            failures += 1
            print(f"FAIL {vec['id']}:")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"PASS {vec['id']}")

    print()
    if failures:
        print(f"{failures} of {len(fixture['vectors'])} vectors FAILED")
        return 1
    print(f"All {len(fixture['vectors'])} vectors PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
