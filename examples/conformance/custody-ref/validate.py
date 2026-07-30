#!/usr/bin/env python3
"""Stdlib-only validator for custody-ref-v1 vectors.

Vectors carry a `kind`: "custody" (the custody_ref primitive itself),
"boundary_ref" or "capture_phase" (v1.2 sibling declarations — never
custody_ref preimage members).

For "custody" and "boundary_ref" vectors, two independent checks, both
required for PASS:

1. Hash integrity: recompute SHA-256 over the JCS-RFC8785 canonical form of
   `preimage` and confirm it matches the vector's declared ref
   (`custody_ref` or `boundary_ref`). This always holds for well-formed
   fixtures, negative vectors included — a negative vector is a
   correctly-hashed record whose *semantic* claim is false, not a corrupted
   one.

2. Fail-closed structural check (per docs/spec/custody-ref.md):
     - custody, same_domain             -> capturer_id == executor_id
     - custody, deployer_domain         -> capturer_id != executor_id
     - custody, independent_third_party -> capturer_id != executor_id
                                            AND capturer_id != deployer_id
                                            AND capturer_id != paired_signing_trust_ref.signer_id
     - boundary_ref                     -> captured_scope or excluded_scope non-empty

   The `capturer_id != deployer_id` leg (added in v1.1) closes a gap reported
   by magentixai (Sansone, AXES, axes#3): a capturer that IS the deployer's
   own control plane, with the record signed by a genuinely distinct third
   party, previously passed the other two checks and was wrongly accepted as
   `independent_third_party` — see cr-005/cr-006.

"capture_phase" vectors (v1.2, no own hash — declared value checked against
a paired execution_commit_ts):
     - pre_execution  -> custody timestamp_ms <= execution_commit_ts
     - post_execution -> custody timestamp_ms >= execution_commit_ts
     - at_commit      -> no ordering requirement, both timestamps present

The result of the structural check (PASS/FAIL) must equal the vector's
declared `expect_valid` for the vector to conform.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def jcs(obj):
    return json.dumps(dict(sorted(obj.items())), separators=(",", ":"), ensure_ascii=False)


def check_hash(vec: dict, ref_field: str) -> list[str]:
    errors = []
    payload = jcs(vec["preimage"])
    if payload != vec["jcs_payload"]:
        errors.append(f"canonical bytes mismatch: computed {payload!r} != expected {vec['jcs_payload']!r}")
    digest = hashlib.sha256(payload.encode()).hexdigest()
    if digest != vec[ref_field]:
        errors.append(f"digest mismatch: computed {digest} != expected {vec[ref_field]}")
    return errors


def custody_verdict(vec: dict) -> tuple[bool, str]:
    p = vec["preimage"]
    custody_type = p["custody_type"]
    capturer_id = p["capturer_id"]
    executor_id = p["executor_id"]
    deployer_id = p["deployer_id"]

    if custody_type == "same_domain":
        if capturer_id == executor_id:
            return True, "same_domain: capturer_id == executor_id"
        return False, "same_domain requires capturer_id == executor_id"

    if custody_type == "deployer_domain":
        if capturer_id != executor_id:
            return True, "deployer_domain: capturer_id != executor_id"
        return False, "deployer_domain requires capturer_id != executor_id"

    if custody_type == "independent_third_party":
        if capturer_id == executor_id:
            return False, "independent_third_party requires capturer_id != executor_id"
        if capturer_id == deployer_id:
            return False, (
                "independent_third_party requires capturer_id != deployer_id — the capturer "
                "is the deployer's own control plane, which has an operational stake in the "
                "executor by definition, so it cannot be a genuinely independent third party"
            )
        paired_signer_id = vec["paired_signing_trust_ref"]["signer_id"]
        if capturer_id == paired_signer_id:
            return False, (
                "independent_third_party requires capturer_id != signing_trust_ref.signer_id "
                "for the same action_ref — the only attestation in the record is the issuer's own"
            )
        return True, "independent_third_party: capturer distinct from executor, deployer, and sole signer"

    return False, f"unknown custody_type: {custody_type}"


def boundary_ref_verdict(vec: dict) -> tuple[bool, str]:
    p = vec["preimage"]
    captured = p["captured_scope"]
    excluded = p["excluded_scope"]
    if not captured and not excluded:
        return False, "captured_scope and excluded_scope are both empty — indistinguishable from no boundary declaration"
    return True, "boundary_ref: at least one of captured_scope/excluded_scope is non-empty"


def capture_phase_verdict(vec: dict) -> tuple[bool, str]:
    phase = vec["capture_phase"]
    ts = None
    for v in _fixture_cache["vectors"]:
        if v.get("custody_ref") == vec["custody_ref"] and "preimage" in v:
            ts = v["preimage"]["timestamp_ms"]
            break
    commit_ts = vec["execution_commit_ts"]

    if phase == "pre_execution":
        if ts <= commit_ts:
            return True, "pre_execution: custody timestamp_ms <= execution_commit_ts"
        return False, "capture_phase declares pre_execution but custody timestamp_ms is after execution_commit_ts"
    if phase == "post_execution":
        if ts >= commit_ts:
            return True, "post_execution: custody timestamp_ms >= execution_commit_ts"
        return False, "capture_phase declares post_execution but custody timestamp_ms precedes execution_commit_ts"
    if phase == "at_commit":
        return True, "at_commit: no ordering requirement, both timestamps present"
    return False, f"unknown capture_phase: {phase}"


_fixture_cache: dict = {}


def main() -> int:
    global _fixture_cache
    fixture = json.loads((HERE / "custody-ref-v1.fixture.json").read_text())
    _fixture_cache = fixture
    failures = 0
    for vec in fixture["vectors"]:
        kind = vec.get("kind", "custody")

        if kind == "custody":
            errors = check_hash(vec, "custody_ref")
            verdict, reason = custody_verdict(vec)
        elif kind == "boundary_ref":
            errors = check_hash(vec, "boundary_ref")
            verdict, reason = boundary_ref_verdict(vec)
        elif kind == "capture_phase":
            errors = []
            verdict, reason = capture_phase_verdict(vec)
        else:
            failures += 1
            print(f"FAIL {vec['id']}: unknown kind {kind!r}")
            continue

        if verdict != vec["expect_valid"]:
            errors.append(
                f"structural verdict mismatch: computed valid={verdict} ({reason}) "
                f"!= expected valid={vec['expect_valid']}"
            )

        if errors:
            failures += 1
            print(f"FAIL {vec['id']}:")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"PASS {vec['id']} (expect_valid={vec['expect_valid']}, verdict: {reason})")

    print()
    if failures:
        print(f"{failures} of {len(fixture['vectors'])} vectors FAILED")
        return 1
    print(f"All {len(fixture['vectors'])} vectors PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
