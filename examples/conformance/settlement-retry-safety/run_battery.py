"""
Runs the seven battery modes named in x402-foundation/x402#3208
(aurumflux20) against execute_payment() + PendingSettlementStore for real —
each mode drives execute_payment() in a caller-style retry loop (bounded to
5 rounds) until it reaches a terminal verdict, then asserts the facilitator
ledger settled the authorization exactly once.
"""

from facilitator_harness import MockFacilitator
from pending_settlement_store import PendingSettlementStore, SETTLED
from execute_payment import execute_payment

MODES = [
    "clean",
    "declared_safe",
    "accept_then_timeout",
    "5xx_after_settle",
    "slow_answer",
    "reconcile_unavailable",
    "double_402",
]

MAX_ROUNDS = 5


def run_mode(mode, extra_calls=0):
    store = PendingSettlementStore()
    facilitator = MockFacilitator(mode)
    key = f"idem-{mode}"

    rec = None
    rounds = 0
    for rounds in range(1, MAX_ROUNDS + 1):
        rec = execute_payment(store, facilitator, key, resource="x402:demo-resource")
        if rec["verdict"] == SETTLED:
            break

    # declared_safe also requires: a duplicate client-side submission of
    # the SAME key after settlement still settles exactly once.
    if mode == "declared_safe":
        rec2 = execute_payment(store, facilitator, key, resource="x402:demo-resource")
        assert rec2["verdict"] == SETTLED
        assert rec2["transaction_ref"] == rec["transaction_ref"]

    ok = rec is not None and rec["verdict"] == SETTLED and len(facilitator.ledger) == 1
    return {
        "mode": mode,
        "ok": ok,
        "rounds": rounds,
        "settle_calls": facilitator.settle_calls,
        "reconcile_calls": facilitator.reconcile_calls,
        "ledger_len": len(facilitator.ledger),
        "final_verdict": rec["verdict"] if rec else None,
        "transaction_ref": rec.get("transaction_ref") if rec else None,
    }


def main():
    results = [run_mode(m) for m in MODES]
    width = max(len(m) for m in MODES)
    all_ok = True
    for r in results:
        status = "PASS" if r["ok"] else "FAIL"
        all_ok = all_ok and r["ok"]
        print(
            f"{status}  {r['mode']:<{width}}  rounds={r['rounds']}  "
            f"settle_calls={r['settle_calls']}  reconcile_calls={r['reconcile_calls']}  "
            f"ledger_len={r['ledger_len']}  tx={r['transaction_ref']}"
        )
    print()
    print(f"{sum(1 for r in results if r['ok'])}/{len(results)} modes settled exactly once")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
