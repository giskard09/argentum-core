"""
GenericBackend — a second, deliberately non-payment implementation of
SettlementBackend, proving the retry-safety interface extracted in
retry_safety_backend.py is not x402-shaped underneath the names.

Models a generic idempotent write against a non-payment destination — e.g.
a workflow engine's task result store, or a tool that creates a durable
record (ticket, order, file). No signatures, no broadcast hashes, no HTTP
402 challenges: `authorization` here is just `{"key": ..., "payload": ...}`,
`transaction_ref` is an opaque record id, and "reconcile" means "poll the
destination's own record store by key" — the same shape mstevens843/
crashpoint used against LangGraph/Temporal/DBOS (poll the workflow's
checkpoint store instead of trusting the caller's last-seen exit code).

Same four fault categories as facilitator_harness.MockFacilitator, mapped
to their rail-agnostic form (see retry_safety_backend.py's docstring and
docs/spec MAPEO_GENERICO_VS_X402.md for the full correspondence):

| x402 mode (facilitator_harness) | generic mode (this file)     |
|----------------------------------|-------------------------------|
| clean                            | clean                         |
| declared_safe                    | declared_idempotent           |
| accept_then_timeout              | write_then_timeout            |
| 5xx_after_settle                 | error_after_write             |
| slow_answer                      | client_timeout                |
| reconcile_unavailable            | reconcile_unavailable         |
| double_402                       | reissue_instead_of_resume     |

execute_payment.py drives this backend through the exact same code path as
MockFacilitator — no branching on backend type. That's the point: the
"payment" framing in execute_payment.py's docstring is a naming artifact
of where the pattern was first extracted from, not a structural dependency.
"""

from retry_safety_backend import (
    Challenge402,
    ReconcileUnavailable,
    ServerError,
    SettlementBackend,
    TimeoutError_,
)


class GenericBackend(SettlementBackend):
    def __init__(self, mode):
        self.mode = mode
        self.ledger = []  # [{"key": ..., "record_id": ...}]
        self.settle_calls = 0
        self.reconcile_calls = 0

    def _find_by_key(self, key):
        for entry in self.ledger:
            if entry["key"] == key:
                return entry
        return None

    def _find_by_record_id(self, record_id):
        for entry in self.ledger:
            if entry["record_id"] == record_id:
                return entry
        return None

    def _write(self, key, record_id):
        self.ledger.append({"key": key, "record_id": record_id})
        return record_id

    def settle(self, authorization):
        self.settle_calls += 1
        key = authorization["signature"]  # same field name execute_payment.py sets

        existing = self._find_by_key(key)
        if existing is not None:
            return {"verdict": "settled", "transaction_ref": existing["record_id"], "declared_safe": True}

        if self.mode == "clean":
            rid = self._write(key, "rec-CLEAN")
            return {"verdict": "settled", "transaction_ref": rid}

        if self.mode == "declared_idempotent":
            rid = self._write(key, "rec-DSAFE")
            return {"verdict": "settled", "transaction_ref": rid, "declared_safe": True}

        if self.mode == "write_then_timeout":
            if self.settle_calls == 1:
                self._write(key, "rec-WTT")
                raise TimeoutError_("ack-wait timeout after write committed", broadcast_ref="rec-WTT")
            rid = self._write(key, "rec-WTT_DUP")
            return {"verdict": "settled", "transaction_ref": rid, "declared_safe": True}

        if self.mode == "error_after_write":
            if self.settle_calls == 1:
                self._write(key, "rec-EAW")
                raise ServerError("500 immediately after record committed")
            rid = self._write(key, "rec-EAW_DUP")
            return {"verdict": "settled", "transaction_ref": rid, "declared_safe": True}

        if self.mode == "client_timeout":
            if self.settle_calls == 1:
                self._write(key, "rec-CTO")
                raise TimeoutError_("client-side timeout, response never delivered")
            rid = self._write(key, "rec-CTO_DUP")
            return {"verdict": "settled", "transaction_ref": rid, "declared_safe": True}

        if self.mode == "reconcile_unavailable":
            if self.settle_calls == 1:
                self._write(key, "rec-RECU")
                raise TimeoutError_("ack-wait timeout after write committed", broadcast_ref="rec-RECU")
            rid = self._write(key, "rec-RECU_DUP")
            return {"verdict": "settled", "transaction_ref": rid, "declared_safe": True}

        if self.mode == "reissue_instead_of_resume":
            if self.settle_calls == 1:
                raise TimeoutError_("ack-wait timeout, no write recorded yet")
            if self.settle_calls == 2:
                raise Challenge402("destination reissued a fresh directive for a pending write")
            rid = self._write(key, "rec-REISSUE")
            return {"verdict": "settled", "transaction_ref": rid}

        raise ValueError(f"unknown mode {self.mode!r}")

    def reconcile(self, ref):
        self.reconcile_calls += 1
        if self.mode == "reconcile_unavailable" and self.reconcile_calls == 1:
            raise ReconcileUnavailable("record store unreachable")
        entry = self._find_by_record_id(ref)
        if entry is not None:
            return {"verdict": "settled", "transaction_ref": entry["record_id"]}
        return {"verdict": "unknown"}
