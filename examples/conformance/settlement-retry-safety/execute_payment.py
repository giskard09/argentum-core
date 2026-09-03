"""
execute_payment — synthetic x402 client implementing the receiver-obligation
rule whawk46 stated on x402#3208 (2026-09-03T04:17:08Z): an indeterminate
settlement state locks the invoice and preserves the broadcast hash;
the caller MUST NOT re-challenge (sign a fresh authorization) while a
pending record exists for the same idempotency_key — it re-presents the
SAME signed authorization instead.

One call = one round of a caller's retry loop. A caller drives it in a
`while verdict != settled: execute_payment(...)` loop, same as any real
retry wrapper — the safety property under test is that however many rounds
that loop takes, the facilitator's ledger ends up with exactly one entry.
"""

from facilitator_harness import ReconcileUnavailable, ServerError, Challenge402, TimeoutError_
from pending_settlement_store import INDETERMINATE, REFUSED, SETTLED


def execute_payment(store, facilitator, idempotency_key, resource):
    rec = store.get(idempotency_key)

    if rec is None:
        authorization = {"signature": f"sig-{idempotency_key}", "resource": resource}
        rec = store.start(idempotency_key, authorization)
    else:
        authorization = rec["authorization"]

    if rec["verdict"] in (SETTLED, REFUSED):
        # Duplicate submission of an already-terminal key — short-circuit,
        # no facilitator call at all.
        return rec

    # Indeterminate (or freshly started): if we already hold a broadcast
    # ref, try reconciling before spending another settle attempt.
    if rec.get("broadcast_ref"):
        try:
            recon = facilitator.reconcile(rec["broadcast_ref"])
            if recon["verdict"] == "settled":
                return store.mark_settled(idempotency_key, recon["transaction_ref"])
        except ReconcileUnavailable:
            pass  # fall through to re-presenting the authorization

    try:
        result = facilitator.settle(authorization)
    except Challenge402:
        # MUST NOT sign a new authorization on re-challenge while pending —
        # re-present the SAME one directly instead of accepting the new 402.
        try:
            result = facilitator.settle(authorization)
        except (TimeoutError_, ServerError) as e:
            store.mark_indeterminate(idempotency_key, getattr(e, "broadcast_ref", None))
            return store.get(idempotency_key)
    except (TimeoutError_, ServerError) as e:
        store.mark_indeterminate(idempotency_key, getattr(e, "broadcast_ref", None))
        return store.get(idempotency_key)

    return store.mark_settled(
        idempotency_key,
        result["transaction_ref"],
        declared_safe=result.get("declared_safe", False),
    )
