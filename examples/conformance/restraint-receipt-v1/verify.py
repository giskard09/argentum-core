"""
Verify restraint-receipt-v1 conformance vectors.

Usage:
    python3 verify.py              # verify all vectors in vectors.json
    python3 verify.py RR-ACCEPT-001  # verify a single vector by id
"""

import hashlib
import json
import sys
from pathlib import Path

REQUIRED_FIELDS = {"action_ref", "decision_id", "verdict", "reason_code", "timestamp_ms"}
VALID_VERDICTS = {"denied", "deferred"}


def jcs(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def compute_restraint_receipt_ref(preimage: dict) -> str:
    return hashlib.sha256(jcs(preimage).encode()).hexdigest()


def verify_conformant(vector: dict) -> tuple[bool, str]:
    vid = vector["id"]
    preimage = vector["preimage"]

    missing = REQUIRED_FIELDS - set(preimage.keys())
    if missing:
        return False, f"{vid}: FAIL — preimage missing required fields: {sorted(missing)}"

    if preimage["verdict"] not in VALID_VERDICTS:
        return False, f"{vid}: FAIL — verdict must be 'denied' or 'deferred', got '{preimage['verdict']}'"

    computed = compute_restraint_receipt_ref(preimage)
    expected = vector["restraint_receipt_ref"]

    if computed != expected:
        return False, (
            f"{vid}: FAIL — hash mismatch\n"
            f"  computed: {computed}\n"
            f"  expected: {expected}"
        )

    computed_jcs = jcs(preimage)
    stated_jcs = vector.get("jcs_payload", "")
    if stated_jcs and computed_jcs != stated_jcs:
        return False, (
            f"{vid}: FAIL — jcs_payload mismatch\n"
            f"  computed: {computed_jcs}\n"
            f"  stated:   {stated_jcs}"
        )

    return True, f"{vid}: PASS — restraint_receipt_ref {computed}"


def verify_non_conformant(vector: dict) -> tuple[bool, str]:
    """
    Verify non-conformant vectors. Each failure mode has its own check.
    All checks must pass (i.e. the verifier correctly detects the violation).
    """
    vid = vector["id"]

    # RR-REJECT-001: missing required field
    if "missing_field" in vector:
        receipt = vector.get("submitted_receipt", {})
        missing = REQUIRED_FIELDS - set(receipt.keys())
        if missing:
            return True, f"{vid}: PASS — correctly identified as non-conformant (missing: {sorted(missing)})"
        return False, f"{vid}: FAIL — expected non-conformant (missing field) but all required fields present"

    submitted = vector.get("submitted_receipt", {})

    # RR-REJECT-002: tampered restraint_receipt_ref
    if "expected_restraint_receipt_ref" in vector:
        preimage_fields = {k: submitted[k] for k in REQUIRED_FIELDS if k in submitted}
        recomputed = compute_restraint_receipt_ref(preimage_fields)
        submitted_hash = submitted.get("restraint_receipt_ref", "")
        if recomputed == submitted_hash:
            return False, f"{vid}: FAIL — tampered hash not detected (recomputed == submitted)"
        expected = vector["expected_restraint_receipt_ref"]
        if recomputed != expected:
            return False, (
                f"{vid}: FAIL — recomputed hash does not match expected\n"
                f"  recomputed: {recomputed}\n"
                f"  expected:   {expected}"
            )
        return True, (
            f"{vid}: PASS — tampered hash detected "
            f"(recomputed {recomputed[:16]}… ≠ submitted {submitted_hash[:16]}…)"
        )

    # RR-REJECT-003: preimage field substitution (verdict changed)
    if "verifier_recomputes_from_submitted_fields" in vector:
        preimage_fields = {k: submitted[k] for k in REQUIRED_FIELDS if k in submitted}
        verdict = preimage_fields.get("verdict", "")
        if verdict not in VALID_VERDICTS:
            # verdict itself is invalid — that's the primary rejection
            recomputed = compute_restraint_receipt_ref(preimage_fields)
            expected_recompute = vector["verifier_recomputes_from_submitted_fields"]
            if recomputed != expected_recompute:
                return False, (
                    f"{vid}: FAIL — recomputed hash from substituted fields does not match expected\n"
                    f"  recomputed: {recomputed}\n"
                    f"  expected:   {expected_recompute}"
                )
            return True, (
                f"{vid}: PASS — substitution detected: "
                f"verdict '{verdict}' is non-conformant; "
                f"recompute from submitted fields {recomputed[:16]}… "
                f"≠ stated {submitted.get('restraint_receipt_ref', '')[:16]}…"
            )
        return False, f"{vid}: FAIL — expected non-conformant verdict but '{verdict}' passed validation"

    # RR-REJECT-004: quiet drift (audit_checkpoints not anchored)
    if "audit_checkpoints" in submitted and "decision_record" not in vector and "presented_policy_bundle" not in vector:
        # The invariant: restraint_receipt_ref is computed from 5 core fields only,
        # but audit_checkpoints declares a verifier surface that isn't anchored.
        # Verifier detects: the policy binding cannot be verified from the receipt alone.
        preimage_fields = {k: submitted[k] for k in REQUIRED_FIELDS if k in submitted}
        missing = REQUIRED_FIELDS - set(preimage_fields.keys())
        if missing:
            return False, f"{vid}: FAIL — submitted_receipt missing required fields: {sorted(missing)}"
        # The verifier CAN recompute the hash but identifies that audit_checkpoints
        # declares an unanchored verifier surface — quiet drift.
        recomputed = compute_restraint_receipt_ref(preimage_fields)
        stated_hash = submitted.get("restraint_receipt_ref", "")
        if recomputed != stated_hash:
            return False, (
                f"{vid}: FAIL — hash mismatch in addition to quiet drift\n"
                f"  recomputed: {recomputed}\n"
                f"  stated:     {stated_hash}"
            )
        # Hash matches but audit_checkpoints is unanchored — REJECT for quiet drift
        checkpoints = submitted["audit_checkpoints"]
        if "policy_bundle" in checkpoints and "verifier_id" in checkpoints:
            return True, (
                f"{vid}: PASS — quiet drift detected: "
                f"audit_checkpoints declares verifier surface (policy_bundle, verifier_id) "
                f"not anchored in the five-field preimage; verifier surface cannot be confirmed"
            )
        return False, f"{vid}: FAIL — expected audit_checkpoints with policy_bundle and verifier_id"

    # RR-REJECT-005: policy_bundle digest mismatch
    if "presented_policy_bundle" in vector:
        bundle = vector["presented_policy_bundle"]
        actual_hash = "sha256:" + hashlib.sha256(jcs(bundle).encode()).hexdigest()
        expected_actual = vector["actual_policy_bundle_hash"]
        if actual_hash != expected_actual:
            return False, (
                f"{vid}: FAIL — actual bundle hash does not match fixture\n"
                f"  computed: {actual_hash}\n"
                f"  expected: {expected_actual}"
            )
        stated_hash = submitted.get("audit_checkpoints", {}).get("policy_bundle", "")
        if actual_hash == stated_hash:
            return False, f"{vid}: FAIL — policy_bundle digest mismatch not detected (hashes match)"
        return True, (
            f"{vid}: PASS — policy_bundle digest mismatch detected: "
            f"actual {actual_hash[7:23]}… ≠ stated {stated_hash[7:23]}…"
        )

    # RR-REJECT-006: verifier_id mismatch
    if "decision_record" in vector:
        decision = vector["decision_record"]
        checkpoints = submitted.get("audit_checkpoints", {})
        receipt_verifier = checkpoints.get("verifier_id", "")
        decision_verifier = decision.get("verifier_id", "")
        if receipt_verifier == decision_verifier:
            return False, f"{vid}: FAIL — verifier_id mismatch not detected (both are '{receipt_verifier}')"
        return True, (
            f"{vid}: PASS — verifier_id mismatch detected: "
            f"audit_checkpoints claims '{receipt_verifier}' "
            f"but decision record has '{decision_verifier}'"
        )

    return False, f"{vid}: FAIL — unhandled non-conformant case (no matching check)"


def verify_vector(vector: dict) -> tuple[bool, str]:
    if vector["conformant"]:
        return verify_conformant(vector)
    return verify_non_conformant(vector)


def main():
    vectors_path = Path(__file__).parent / "vectors.json"
    data = json.loads(vectors_path.read_text())
    vectors = data["vectors"]

    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target:
        vectors = [v for v in vectors if v["id"] == target]
        if not vectors:
            print(f"No vector with id '{target}'")
            sys.exit(1)

    passed = 0
    failed = 0
    for vector in vectors:
        ok, msg = verify_vector(vector)
        print(msg)
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
