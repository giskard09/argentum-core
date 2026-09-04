"""
MockFacilitator — a real (not stubbed-to-pass) x402-shaped facilitator used
to drive execute_payment() through the seven battery modes named in
x402-foundation/x402#3208 (aurumflux20): accept_then_timeout,
5xx_after_settle, double_402, slow_answer, reconcile_unavailable,
declared_safe, clean.

The facilitator keeps its own settlement ledger (list of {signature, tx}).
A call to settle() with a signature already in the ledger returns the
SAME transaction_ref instead of writing a new entry — this is the
facilitator-side idempotency the client depends on when it re-presents an
authorization instead of minting a new one. Fault injection is per-mode,
keyed off call_count, so a mode that "settles on retry" only does so
because the harness models the underlying broadcast as having actually
landed on the first call — the same asymmetry idempotency-ref.md names for
orphaned PENDING: a lost response is not evidence the effect didn't happen.

2026-09-04: exceptions and the settle()/reconcile() shape now live in
retry_safety_backend.py (rail-agnostic) and are re-exported here unchanged
— execute_payment.py's `from facilitator_harness import ...` keeps working
with no edit. MockFacilitator is the x402 implementation of
SettlementBackend; generic_backend.GenericBackend is a second, non-payment
implementation of the same interface (see retry_safety_backend.py).
"""

from retry_safety_backend import (
    Challenge402,
    ReconcileUnavailable,
    ServerError,
    SettlementBackend,
    TimeoutError_,
)

__all__ = [
    "Challenge402",
    "ReconcileUnavailable",
    "ServerError",
    "TimeoutError_",
    "MockFacilitator",
]


class MockFacilitator(SettlementBackend):
    def __init__(self, mode):
        self.mode = mode
        self.ledger = []  # [{"signature": ..., "tx": ...}]
        self.settle_calls = 0
        self.reconcile_calls = 0

    def _find_by_sig(self, sig):
        for entry in self.ledger:
            if entry["signature"] == sig:
                return entry
        return None

    def _find_by_broadcast(self, ref):
        for entry in self.ledger:
            if entry["tx"] == ref:
                return entry
        return None

    def _write(self, sig, tx):
        self.ledger.append({"signature": sig, "tx": tx})
        return tx

    def settle(self, authorization):
        self.settle_calls += 1
        sig = authorization["signature"]

        existing = self._find_by_sig(sig)
        if existing is not None:
            return {"verdict": "settled", "transaction_ref": existing["tx"], "declared_safe": True}

        if self.mode == "clean":
            tx = self._write(sig, "0xCLEAN")
            return {"verdict": "settled", "transaction_ref": tx}

        if self.mode == "declared_safe":
            tx = self._write(sig, "0xDSAFE")
            return {"verdict": "settled", "transaction_ref": tx, "declared_safe": True}

        if self.mode == "accept_then_timeout":
            if self.settle_calls == 1:
                self._write(sig, "0xATT")
                # receipt-wait fails, but the broadcast ref IS surfaced to
                # the caller (this is the #3083 pattern: preserve the hash).
                raise TimeoutError_("receipt-wait timeout after broadcast", broadcast_ref="0xATT")
            # sig unmatched by the top-level dedup means this is a NEW
            # authorization — a broken client that minted one on retry
            # genuinely gets charged again here, on purpose.
            tx = self._write(sig, "0xATT_DUP")
            return {"verdict": "settled", "transaction_ref": tx, "declared_safe": True}

        if self.mode == "5xx_after_settle":
            if self.settle_calls == 1:
                self._write(sig, "0x5XX")
                # 500 body carries no broadcast ref — caller cannot reconcile
                # directly, must fall back to re-presenting the authorization.
                raise ServerError("500 immediately after ledger commit")
            tx = self._write(sig, "0x5XX_DUP")
            return {"verdict": "settled", "transaction_ref": tx, "declared_safe": True}

        if self.mode == "slow_answer":
            if self.settle_calls == 1:
                self._write(sig, "0xSLOW")
                raise TimeoutError_("client-side timeout, server response never delivered")
            tx = self._write(sig, "0xSLOW_DUP")
            return {"verdict": "settled", "transaction_ref": tx, "declared_safe": True}

        if self.mode == "reconcile_unavailable":
            if self.settle_calls == 1:
                self._write(sig, "0xRECU")
                raise TimeoutError_("receipt-wait timeout after broadcast", broadcast_ref="0xRECU")
            tx = self._write(sig, "0xRECU_DUP")
            return {"verdict": "settled", "transaction_ref": tx, "declared_safe": True}

        if self.mode == "double_402":
            if self.settle_calls == 1:
                raise TimeoutError_("receipt-wait timeout, no broadcast recorded yet")
            if self.settle_calls == 2:
                # Adversarial/buggy facilitator re-challenges instead of
                # resuming the pending authorization it already saw.
                raise Challenge402("fresh 402 issued for a pending authorization")
            tx = self._write(sig, "0xD402")
            return {"verdict": "settled", "transaction_ref": tx}

        raise ValueError(f"unknown mode {self.mode!r}")

    def reconcile(self, broadcast_ref):
        self.reconcile_calls += 1
        if self.mode == "reconcile_unavailable" and self.reconcile_calls == 1:
            raise ReconcileUnavailable("rpc unavailable")
        entry = self._find_by_broadcast(broadcast_ref)
        if entry is not None:
            return {"verdict": "settled", "transaction_ref": entry["tx"]}
        return {"verdict": "unknown"}
