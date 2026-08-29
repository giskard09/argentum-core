#!/usr/bin/env python3
"""Stdlib-only validator for action-ref-v2 vectors.

Additive to v1 — does not replace the v1 fixture set or its validator. For
each vector: recomputes both action_ref_v1 (unchanged bare derivation) and
action_ref_v2 (domain-tagged, 'v2:'-prefixed derivation) from the same
preimage, confirms both match the fixture's stored values, confirms the two
underlying digests differ (a defensive invariant assertion — see below, not
a property these three vectors can actually exercise), and confirms
action_ref_version() reads the marker off each string's own grammar, not
just its length and prefix.

The digest-equality check compares the underlying 64-hex digests (v2's
"v2:" presentation prefix stripped before comparing), not the presented
strings — comparing presented strings would compare a 64-char string
against a 67-char one, which can never be equal regardless of the
underlying bytes, making the check permanently vacuous. Even fixed, no
vector in this file (or any vector built the normal way) can drive this
branch to fire: compute_v2 recomputes the v2 digest straight from the
preimage, so a fixture whose stored action_ref_v2 doesn't match what
compute_v2 produces fails on the "v2 digest mismatch" check above, before
digest equality is ever compared. The only way to reach the collision
branch is an actual SHA-256 collision between the domain-tagged and the
bare digest of the same preimage — this assertion exists to catch that
if it ever happens, not to be exercised by ordinary or adversarial vectors.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
V2_DOMAIN_TAG = "mycelium.action-ref:v2:"

_V1_RE = re.compile(r"^[0-9a-f]{64}$")
_V2_RE = re.compile(r"^v2:[0-9a-f]{64}$")


def jcs(obj: dict) -> bytes:
    return json.dumps(dict(sorted(obj.items())), separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_v1(preimage: dict) -> str:
    return hashlib.sha256(jcs(preimage)).hexdigest()


def compute_v2(preimage: dict) -> str:
    return "v2:" + hashlib.sha256(V2_DOMAIN_TAG.encode("utf-8") + jcs(preimage)).hexdigest()


def action_ref_version(action_ref: str) -> str:
    """fullmatch, not match: '$' in the pattern matches end-of-string OR
    immediately before a trailing newline, so re.match alone would accept a
    valid digest with a trailing '\\n' appended. fullmatch requires the whole
    string to match."""
    if _V2_RE.fullmatch(action_ref):
        return "v2"
    if _V1_RE.fullmatch(action_ref):
        return "v1"
    raise ValueError(f"unrecognized action_ref format: {action_ref!r}")


_EXPECTED_PREIMAGE_KEYS = {"agent_id", "action_type", "scope", "timestamp"}


def main() -> int:
    fixture = json.loads((HERE / "action-ref-v2.fixture.json").read_text())

    # Profile metadata: this validator hardcodes hash_algo=sha256,
    # preimage_format=jcs-rfc8785-v1, and domain_tag=V2_DOMAIN_TAG rather than
    # reading them from the fixture -- assert the fixture actually declares
    # what this code implements, so a fixture edited to a different tag or
    # algorithm fails loudly instead of silently being validated against the
    # wrong profile.
    if fixture.get("hash_algo") != "sha256":
        print(f"FIXTURE PROFILE MISMATCH: hash_algo={fixture.get('hash_algo')!r}, validator implements sha256")
        return 1
    if fixture.get("preimage_format") != "jcs-rfc8785-v1":
        print(
            f"FIXTURE PROFILE MISMATCH: preimage_format={fixture.get('preimage_format')!r}, "
            f"validator implements jcs-rfc8785-v1"
        )
        return 1
    if fixture.get("domain_tag") != V2_DOMAIN_TAG:
        print(f"FIXTURE PROFILE MISMATCH: domain_tag={fixture.get('domain_tag')!r}, validator implements {V2_DOMAIN_TAG!r}")
        return 1

    failures = 0
    for vec in fixture["vectors"]:
        errors = []

        preimage_keys = set(vec["preimage"].keys())
        if preimage_keys != _EXPECTED_PREIMAGE_KEYS:
            errors.append(
                f"preimage key set mismatch: got {sorted(preimage_keys)}, "
                f"expected exactly {sorted(_EXPECTED_PREIMAGE_KEYS)}"
            )
        if not all(isinstance(v, str) for v in vec["preimage"].values()):
            errors.append("preimage has a non-string value -- all four fields must be strings")

        payload = jcs(vec["preimage"]).decode("utf-8")
        if payload != vec["jcs_payload"]:
            errors.append(f"canonical bytes mismatch: computed {payload!r} != expected {vec['jcs_payload']!r}")

        v1 = compute_v1(vec["preimage"])
        if v1 != vec["action_ref_v1"]:
            errors.append(f"v1 digest mismatch: computed {v1} != expected {vec['action_ref_v1']}")

        v2 = compute_v2(vec["preimage"])
        if v2 != vec["action_ref_v2"]:
            errors.append(f"v2 digest mismatch: computed {v2} != expected {vec['action_ref_v2']}")

        v2_digest = v2[len("v2:"):]
        if v1 == v2_digest:
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

    neg_failures = 0
    for vec in fixture.get("version_marker_negative_vectors", []):
        try:
            got = action_ref_version(vec["input"])
            neg_failures += 1
            print(f"FAIL {vec['id']}: expected ValueError, action_ref_version returned {got!r}")
        except ValueError:
            print(f"PASS {vec['id']} (rejected: {vec['description']})")

    print()
    total_failures = failures + neg_failures
    total_vectors = len(fixture["vectors"]) + len(fixture.get("version_marker_negative_vectors", []))
    if total_failures:
        print(f"{total_failures} of {total_vectors} vectors FAILED")
        return 1
    print(f"All {total_vectors} vectors PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
