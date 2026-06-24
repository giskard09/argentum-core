#!/usr/bin/env python3
"""Conformance vector verifier for restraint-receipt-v1.

Iterates over vectors.json, checks each vector against the restraint receipt
spec invariants, and reports pass/fail with details.
"""

import json
import sys
from pathlib import Path

VECTORS_PATH = Path(__file__).parent / "vectors.json"

REQUIRED_FIELDS = {"action_ref", "decision_id", "verdict", "reason_code", "timestamp_ms"}


def verify_vector(vector: dict) -> dict:
    """Verify a single conformance vector and return its outcome."""
    vector_id = vector.get("id", "UNKNOWN")
    expected_conformant = vector.get("conformant", None)
    expected_verifier_outcome = vector.get("verifier_outcome", None)

    # -- For non-conformant vectors, submitted_receipt is the receipt under test --
    preimage = vector.get("preimage", {})
    submitted_receipt = vector.get("submitted_receipt", preimage)

    # --- REQUIRED_FIELDS check ---
    preimage_keys = set(preimage.keys())
    if not REQUIRED_FIELDS.issubset(preimage_keys):
        missing = REQUIRED_FIELDS - preimage_keys
        return {
            "conformant": False,
            "verifier_outcome": "REJECT",
            "reason": f"preimage missing required fields: {sorted(missing)}",
        }

    # --- Field consistency check: preimage vs submitted_receipt ---
    for field in REQUIRED_FIELDS:
        pre_val = preimage.get(field)
        sub_val = submitted_receipt.get(field)
        if pre_val != sub_val:
            return {
                "conformant": False,
                "verifier_outcome": "REJECT",
                "reason": f"field mismatch: '{field}' — preimage={pre_val!r} vs submitted={sub_val!r}",
            }

    # --- Content-addressed verifier path validation (ACR audit_checkpoints) ---
    if "audit_checkpoints" in preimage:
        checkpoints = preimage["audit_checkpoints"]
        if not isinstance(checkpoints, dict):
            return {
                "conformant": False,
                "verifier_outcome": "REJECT",
                "reason": "audit_checkpoints must be an object",
            }
        if "verifier" not in checkpoints:
            return {
                "conformant": False,
                "verifier_outcome": "REJECT",
                "reason": "audit_checkpoints missing required 'verifier' field",
            }
        if "policy_bundle" not in checkpoints:
            return {
                "conformant": False,
                "verifier_outcome": "REJECT",
                "reason": "audit_checkpoints missing required 'policy_bundle' field",
            }

        # Verify submitted_receipt also has matching audit_checkpoints
        if "audit_checkpoints" in submitted_receipt:
            sub_checkpoints = submitted_receipt["audit_checkpoints"]
            if sub_checkpoints.get("verifier") != checkpoints["verifier"]:
                return {
                    "conformant": False,
                    "verifier_outcome": "REJECT",
                    "reason": "audit_checkpoints verifier mismatch",
                }
            if sub_checkpoints.get("policy_bundle") != checkpoints["policy_bundle"]:
                return {
                    "conformant": False,
                    "verifier_outcome": "REJECT",
                    "reason": "audit_checkpoints policy_bundle hash mismatch",
                }

    # --- All checks passed: conformant ---
    return {"conformant": True, "verifier_outcome": "ACCEPT"}


def main() -> int:
    with open(VECTORS_PATH, encoding="utf-8") as f:
        fixture = json.load(f)

    vectors = fixture.get("vectors", [])
    failures = []
    passed = 0
    total = len(vectors)

    print(f"Verifying {total} conformance vectors from {VECTORS_PATH.name}...\n")

    for vector in vectors:
        vid = vector.get("id", "UNKNOWN")
        expected_conformant = vector.get("conformant")

        outcome = verify_vector(vector)
        actual_conformant = outcome["conformant"]
        verifier_outcome = outcome.get("verifier_outcome", "???")
        reason = outcome.get("reason", "")

        match = actual_conformant == expected_conformant
        status = "PASS" if match else "FAIL"

        if match:
            passed += 1
        else:
            failures.append({
                "id": vid,
                "expected_conformant": expected_conformant,
                "actual_conformant": actual_conformant,
                "verifier_outcome": verifier_outcome,
                "reason": reason,
            })

        print(f"  [{status}] {vid}")
        print(f"         expected conformant={expected_conformant}, actual={actual_conformant}")
        if reason:
            print(f"         reason: {reason}")
        if not match:
            print(f"         verifier_outcome: {verifier_outcome}")

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed")

    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for f in failures:
            print(f"  - {f['id']}: expected conformant={f['expected_conformant']}, "
                  f"got {f['actual_conformant']} ({f.get('reason', 'no reason')})")
        return 1

    print("All vectors passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
