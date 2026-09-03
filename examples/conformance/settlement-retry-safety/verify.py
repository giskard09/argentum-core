"""
Verifier for settlement-retry-safety-v1 conformance vectors.

Unlike offer-identity-ref/settlement-evidence-ref (hash-derivation vectors —
PASS means SHA-256(JCS(artifact)) matches a declared value), this directory's
vectors are behavioral: PASS means running execute_payment() for real, in a
caller retry loop, against MockFacilitator(mode) reaches the declared
final_verdict with the declared ledger_len/settle_calls/reconcile_calls.
There is no static artifact to recompute a hash of — the thing under test is
what the code does when driven through each fault mode, not a document.

mutation-broken-client-001 is expected to FAIL: it runs a deliberately
broken client (mints a new signature on every retry) against the same
facilitator and asserts a real double charge results. This is the
mutation-testing control confirming the PASS vectors discriminate a correct
client from a broken one, rather than a facilitator mock that settles once
no matter what the client does.
"""

import json
import sys
from pathlib import Path

from facilitator_harness import Challenge402, MockFacilitator, ServerError, TimeoutError_
from pending_settlement_store import PendingSettlementStore, SETTLED
from execute_payment import execute_payment

MAX_ROUNDS = 5


def run_correct_client(mode):
    store = PendingSettlementStore()
    facilitator = MockFacilitator(mode)
    key = f"idem-{mode}"
    rec = None
    for _ in range(MAX_ROUNDS):
        rec = execute_payment(store, facilitator, key, resource="x402:demo-resource")
        if rec["verdict"] == SETTLED:
            break
    if mode == "declared_safe":
        rec2 = execute_payment(store, facilitator, key, resource="x402:demo-resource")
        if rec2["verdict"] != SETTLED or rec2["transaction_ref"] != rec["transaction_ref"]:
            raise AssertionError("declared_safe: duplicate submission diverged from first settlement")
    return {
        "final_verdict": rec["verdict"] if rec else None,
        "ledger_len": len(facilitator.ledger),
        "settle_calls": facilitator.settle_calls,
        "reconcile_calls": facilitator.reconcile_calls,
    }


def run_mutation_control(mode):
    """A broken client that mints a NEW authorization signature each round."""
    facilitator = MockFacilitator(mode)
    key = f"idem-{mode}-mutation"
    for round_n in range(1, MAX_ROUNDS + 1):
        authorization = {"signature": f"sig-{key}-round{round_n}", "resource": "x402:demo-resource"}
        try:
            result = facilitator.settle(authorization)
            if result.get("verdict") == "settled":
                break
        except Challenge402:
            try:
                facilitator.settle(authorization)
            except Exception:
                pass
        except (TimeoutError_, ServerError):
            pass
    return {"ledger_len": len(facilitator.ledger)}


def verify_vector(vector: dict) -> tuple[bool, str, list[str]]:
    """Returns (matched_expectation, observed_status, failure_details)."""
    failures = []
    mode = vector["mode"]

    if vector["id"] == "mutation-broken-client-001":
        outcome = run_mutation_control(mode)
        threshold = vector["expected_outcome"]["ledger_len_gt"]
        discriminated = outcome["ledger_len"] > threshold
        observed_status = "FAIL" if discriminated else "PASS"  # FAIL = real double charge reproduced
        if not discriminated:
            failures.append(
                f"mutation control did not discriminate: ledger_len={outcome['ledger_len']} "
                f"(expected > {threshold}) — the PASS vectors above would not be meaningful"
            )
        matched = observed_status == vector["expected"]
        return matched, observed_status, failures

    outcome = run_correct_client(mode)
    expected = vector["expected_outcome"]
    for field, want in expected.items():
        got = outcome.get(field)
        if got != want:
            failures.append(f"{field}: expected {want}, got {got}")
    observed_status = "PASS" if not failures else "FAIL"
    matched = observed_status == vector["expected"]
    return matched, observed_status, failures


def main():
    fixture_path = Path(__file__).parent / "vectors.json"
    data = json.loads(fixture_path.read_text())
    vectors = data["vectors"]

    print(f"settlement-retry-safety-v1 conformance — {len(vectors)} vectors\n")

    all_pass = True
    for vector in vectors:
        matched, observed_status, failures = verify_vector(vector)
        marker = "OK" if matched else "MISMATCH"
        print(f"[{marker}] {vector['id']} (expected={vector['expected']}) -> observed={observed_status}")
        if not matched:
            all_pass = False
            for f in failures:
                print(f"         {f}")

    print()
    if all_pass:
        print("ALL CHECKS PASS")
        return 0
    print("CHECKS FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
