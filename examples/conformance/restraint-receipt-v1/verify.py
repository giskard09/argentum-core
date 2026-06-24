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


def verify_vector(vector: dict) -> tuple[bool, str]:
    vid = vector["id"]
    conformant = vector["conformant"]

    if not conformant:
        receipt = vector.get("submitted_receipt", {})
        missing = REQUIRED_FIELDS - set(receipt.keys())
        if missing:
            return True, f"{vid}: PASS — correctly identified as non-conformant (missing: {sorted(missing)})"
        return False, f"{vid}: FAIL — expected non-conformant but all required fields are present"

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
        return False, f"{vid}: FAIL — jcs_payload mismatch\n  computed: {computed_jcs}\n  stated:   {stated_jcs}"

    return True, f"{vid}: PASS — restraint_receipt_ref {computed}"


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
