"""
Verifier for settlement-retry-safety-v1's generic (non-x402) backend —
mirrors verify.py exactly, swapping MockFacilitator for GenericBackend.

Purpose: prove execute_payment.py + pending_settlement_store.py settle
exactly once against a second SettlementBackend implementation that has no
payment framing, no signatures, no broadcast hashes — without a single
line of execute_payment.py or pending_settlement_store.py changing between
this run and verify.py's. See retry_safety_backend.py and
~/Downloads/MAPEO_GENERICO_VS_X402.md for what's shared vs. what's
x402-specific.
"""

import json
import sys
from pathlib import Path

from generic_backend import GenericBackend
from retry_safety_backend import Challenge402, ServerError, TimeoutError_
from pending_settlement_store import PendingSettlementStore, SETTLED
from execute_payment import execute_payment

MAX_ROUNDS = 5


def run_correct_client(mode):
    store = PendingSettlementStore()
    backend = GenericBackend(mode)
    key = f"idem-{mode}"
    rec = None
    for _ in range(MAX_ROUNDS):
        rec = execute_payment(store, backend, key, resource="generic:demo-resource")
        if rec["verdict"] == SETTLED:
            break
    if mode == "declared_idempotent":
        rec2 = execute_payment(store, backend, key, resource="generic:demo-resource")
        if rec2["verdict"] != SETTLED or rec2["transaction_ref"] != rec["transaction_ref"]:
            raise AssertionError("declared_idempotent: duplicate submission diverged from first settlement")
    return {
        "final_verdict": rec["verdict"] if rec else None,
        "ledger_len": len(backend.ledger),
        "settle_calls": backend.settle_calls,
        "reconcile_calls": backend.reconcile_calls,
    }


def run_mutation_control(mode):
    """A broken client that mints a NEW key each round."""
    backend = GenericBackend(mode)
    key = f"idem-{mode}-mutation"
    for round_n in range(1, MAX_ROUNDS + 1):
        authorization = {"signature": f"sig-{key}-round{round_n}", "resource": "generic:demo-resource"}
        try:
            result = backend.settle(authorization)
            if result.get("verdict") == "settled":
                break
        except Challenge402:
            try:
                backend.settle(authorization)
            except Exception:
                pass
        except (TimeoutError_, ServerError):
            pass
    return {"ledger_len": len(backend.ledger)}


def verify_vector(vector: dict) -> tuple[bool, str, list[str]]:
    failures = []
    mode = vector["mode"]

    if vector["id"] == "mutation-broken-client-001-generic":
        outcome = run_mutation_control(mode)
        threshold = vector["expected_outcome"]["ledger_len_gt"]
        discriminated = outcome["ledger_len"] > threshold
        observed_status = "FAIL" if discriminated else "PASS"
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
    fixture_path = Path(__file__).parent / "vectors_generic.json"
    data = json.loads(fixture_path.read_text())
    vectors = data["vectors"]

    print(f"settlement-retry-safety-v1 conformance (generic backend) — {len(vectors)} vectors\n")

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
