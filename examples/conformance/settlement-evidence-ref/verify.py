"""
Verifier for settlement-evidence-ref-v1 conformance vectors.

Five checks per spec (docs/spec/settlement-evidence-ref.md):
  1. canonical_settlement — SHA-256(JCS(settlement_artifact)) matches the
     declared settlement_evidence_ref.
  2. ledger_recomputed — payer_debit/payee_credit were independently read
     from the rail's own transaction data, declared in the vector (external
     resolution not performed live, same treatment chain_invariant and
     resolved_by get elsewhere in this repo). A vector with
     ledger_recomputed=false MUST fail — a facilitator's bare success flag
     is never accepted as ledger proof (R5's central prohibition).
  3. debit_credit_paired — both payer_debit and payee_credit are present
     (non-null address/amount/asset), not just one side.
  4. matches_offer — when offer_identity_ref is present and a
     referenced_offer is supplied, the settled amount/asset/payee match
     what the offer required.
  5. transaction_present — `artifact["transaction"]` is a non-empty string.
     The spec already names `transaction` as a required field (T4), but
     until this check existed no vector enforced it structurally: a
     settlement_artifact with `transaction: ""` and both sides otherwise
     paired/recomputed would pass. This is the same shape as x402#2887's
     production bug (a signed receipt left with `transaction: ""` because
     the hash never reached the response) landing undetected in our own
     reference verifier.
"""

import hashlib
import json
import sys
from pathlib import Path


def jcs(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def sha256hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def check_debit_credit_paired(artifact: dict) -> bool:
    debit = artifact.get("payer_debit", {})
    credit = artifact.get("payee_credit", {})
    return all(debit.get(k) is not None for k in ("address", "amount", "asset")) and all(
        credit.get(k) is not None for k in ("address", "amount", "asset")
    )


def check_transaction_present(artifact: dict) -> bool:
    tx = artifact.get("transaction")
    return isinstance(tx, str) and tx != ""


def check_matches_offer(artifact: dict, referenced_offer: dict | None) -> bool:
    if not referenced_offer:
        return True  # no offer to compare against — vacuously fine
    debit = artifact.get("payer_debit", {})
    credit = artifact.get("payee_credit", {})
    return (
        debit.get("amount") == referenced_offer.get("maxAmountRequired")
        and debit.get("asset") == referenced_offer.get("asset")
        and credit.get("address") == referenced_offer.get("payTo")
    )


def verify_vector(vector: dict) -> tuple[bool, list[str]]:
    failures = []
    artifact = vector["settlement_artifact"]

    # 1. canonical_settlement
    computed_ref = sha256hex(jcs(artifact))
    declared_ref = vector.get("settlement_evidence_ref", "")
    if computed_ref != declared_ref:
        failures.append(
            f"canonical_settlement: computed {computed_ref} != declared {declared_ref}"
        )

    checks = vector.get("checks", {})

    # 2. ledger_recomputed
    declared_ledger_recomputed = checks.get("ledger_recomputed", False)
    if not declared_ledger_recomputed:
        failures.append(
            "ledger_recomputed: false — payer_debit/payee_credit not independently "
            "confirmed against the rail, only a facilitator assertion"
        )

    # 3. debit_credit_paired
    computed_paired = check_debit_credit_paired(artifact)
    declared_paired = checks.get("debit_credit_paired", True)
    if computed_paired != declared_paired:
        failures.append(
            f"debit_credit_paired: computed {computed_paired} != declared {declared_paired}"
        )
    if not computed_paired and declared_ledger_recomputed:
        failures.append("debit_credit_paired: false — payer_debit or payee_credit missing")

    # 4. matches_offer
    computed_matches = check_matches_offer(artifact, vector.get("referenced_offer"))
    declared_matches = checks.get("matches_offer", True)
    if computed_matches != declared_matches:
        failures.append(
            f"matches_offer: computed {computed_matches} != declared {declared_matches}"
        )
    if not computed_matches:
        failures.append("matches_offer: false — settled amount/asset/payee diverge from offer")

    # 5. transaction_present
    computed_tx_present = check_transaction_present(artifact)
    declared_tx_present = checks.get("transaction_present", True)
    if computed_tx_present != declared_tx_present:
        failures.append(
            f"transaction_present: computed {computed_tx_present} != declared {declared_tx_present}"
        )
    if not computed_tx_present:
        failures.append(
            "transaction_present: false — settlement_artifact.transaction is missing or empty"
        )

    return len(failures) == 0, failures


def main():
    vectors_path = Path(__file__).parent / "vectors.json"
    data = json.loads(vectors_path.read_text())
    vectors = data["vectors"]

    print(f"settlement-evidence-ref-v1 conformance — {len(vectors)} vectors\n")

    passed = 0
    failed = 0

    for v in vectors:
        vid = v["id"]
        expected = v["expected"]
        conforms, failures = verify_vector(v)

        ok = conforms if expected == "PASS" else not conforms
        marker = "✓" if ok else "✗"
        status = "PASS" if ok else "FAIL"

        print(f"  {marker} [{status}] {vid}")
        if ok and not conforms and expected == "FAIL":
            print(f"         correctly rejected: {failures[0]}")
        elif not ok:
            if expected == "PASS":
                for f in failures:
                    print(f"         unexpected failure: {f}")
            else:
                print(f"         expected FAIL ({v.get('failure_mode', '?')}) but verifier accepted it")

        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{passed}/{len(vectors)} passed", end="")
    if failed:
        print(f", {failed} failed")
        sys.exit(1)
    else:
        print()


if __name__ == "__main__":
    main()
