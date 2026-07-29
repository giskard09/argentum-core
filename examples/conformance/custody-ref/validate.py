#!/usr/bin/env python3
"""Stdlib-only validator for custody-ref-v1 vectors.

Two independent checks per vector, both required for PASS:

1. Hash integrity: recompute SHA-256 over the JCS-RFC8785 canonical form of
   `preimage` and confirm it matches `custody_ref`. This always holds for
   well-formed fixtures, negative vectors included — a negative vector is a
   correctly-hashed record whose *semantic* claim is false, not a corrupted
   one.

2. Fail-closed structural check (per docs/spec/custody-ref.md): the declared
   `custody_type` is verified against the identities in the record, not
   accepted at face value.
     - same_domain             -> capturer_id == executor_id
     - deployer_domain         -> capturer_id != executor_id
     - independent_third_party -> capturer_id != executor_id
                                  AND capturer_id != deployer_id
                                  AND capturer_id != paired_signing_trust_ref.signer_id

   The `capturer_id != deployer_id` leg (added in v1.1) closes a gap reported
   by magentixai (Sansone, AXES, axes#3): a capturer that IS the deployer's
   own control plane, with the record signed by a genuinely distinct third
   party, previously passed the other two checks and was wrongly accepted as
   `independent_third_party` — see cr-005/cr-006 in the fixture set.

The result of check 2 (PASS/FAIL) must equal the vector's declared
`expect_valid` for the vector to conform.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def jcs(obj):
    return json.dumps(dict(sorted(obj.items())), separators=(",", ":"), ensure_ascii=False)


def check_hash(vec: dict) -> list[str]:
    errors = []
    payload = jcs(vec["preimage"])
    if payload != vec["jcs_payload"]:
        errors.append(f"canonical bytes mismatch: computed {payload!r} != expected {vec['jcs_payload']!r}")
    digest = hashlib.sha256(payload.encode()).hexdigest()
    if digest != vec["custody_ref"]:
        errors.append(f"digest mismatch: computed {digest} != expected {vec['custody_ref']}")
    return errors


def structural_verdict(vec: dict) -> tuple[bool, str]:
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


def main() -> int:
    fixture = json.loads((HERE / "custody-ref-v1.fixture.json").read_text())
    failures = 0
    for vec in fixture["vectors"]:
        errors = check_hash(vec)

        verdict, reason = structural_verdict(vec)
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
