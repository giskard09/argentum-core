"""
pending_settlement_store — real state store backing settlement-retry-safety.

Same 3-state vocabulary as idempotency-ref-v1 (PENDING/COMMITTED/FAILED),
specialized to a 3-way settlement verdict (settled/refused-not-charged/
indeterminate) per the x402#3208 discussion (whawk46 comment,
2026-09-03T04:17:08Z). A record with an indeterminate verdict locks the
authorization: the store's `get()` is the only thing a caller consults
before deciding whether to sign a NEW authorization or re-present the one
already on file. Never mutated in place except by these methods — no
timer-based auto-resolution (same rule as idempotency-ref.md's orphaned
PENDING treatment).
"""

import time

SETTLED = "settled"
REFUSED = "refused-not-charged"
INDETERMINATE = "indeterminate"


class PendingSettlementStore:
    def __init__(self):
        self._records = {}

    def get(self, idempotency_key):
        return self._records.get(idempotency_key)

    def start(self, idempotency_key, authorization):
        rec = {
            "idempotency_key": idempotency_key,
            "verdict": INDETERMINATE,
            "authorization": authorization,
            "broadcast_ref": None,
            "transaction_ref": None,
            "started_at": time.time(),
        }
        self._records[idempotency_key] = rec
        return rec

    def mark_indeterminate(self, idempotency_key, broadcast_ref):
        rec = self._records[idempotency_key]
        rec["verdict"] = INDETERMINATE
        rec["broadcast_ref"] = broadcast_ref
        return rec

    def mark_settled(self, idempotency_key, transaction_ref, declared_safe=False):
        rec = self._records[idempotency_key]
        rec["verdict"] = SETTLED
        rec["transaction_ref"] = transaction_ref
        rec["declared_safe"] = declared_safe
        return rec

    def mark_refused(self, idempotency_key, reason):
        rec = self._records[idempotency_key]
        rec["verdict"] = REFUSED
        rec["reason"] = reason
        return rec
