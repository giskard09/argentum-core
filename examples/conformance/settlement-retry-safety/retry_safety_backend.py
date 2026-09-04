"""
retry_safety_backend — rail-agnostic interface + shared exception vocabulary
for the retry-safety pattern this directory implements.

Extracted from facilitator_harness.py (2026-09-04) once the mapping against
idempotency-ref.md Invariant 5 confirmed the x402-specific surface is thin:
the state model (PENDING/COMMITTED/FAILED -> here: settled/refused/
indeterminate), the orphaned-state rule, and the lock+read-back-before-
retry pattern are all rail-agnostic. What's specific to any one rail is the
concrete transport (HTTP 402 vs. a tool call vs. a workflow step) behind
`settle()`/`reconcile()`.

`execute_payment.py` and `pending_settlement_store.py` are untouched by this
extraction — they already only depend on the four exception names and the
two-method shape defined here (duck typing), so any object satisfying
`SettlementBackend` is a drop-in `facilitator` argument. `facilitator_harness.
MockFacilitator` (x402) is one such implementation; `generic_backend.
GenericBackend` (this directory) is a second, non-payment one, proving the
interface is not x402-shaped underneath the names.

Naming note: `Challenge402` keeps its x402-flavored name because renaming it
would require touching execute_payment.py's import (out of scope for this
extraction — see PROVENANCE.md). The FAULT it represents — a destination
that reissues a fresh challenge instead of resuming a pending attempt — is
rail-agnostic; only the exception's name is not. A future rename is a
mechanical follow-up, not a design change.
"""

from abc import ABC, abstractmethod


class TimeoutError_(Exception):
    """A write may or may not have landed; no response was received."""

    def __init__(self, message, broadcast_ref=None):
        super().__init__(message)
        self.broadcast_ref = broadcast_ref


class ServerError(Exception):
    """A write may or may not have landed; the destination reported a fault."""

    def __init__(self, message, broadcast_ref=None):
        super().__init__(message)
        self.broadcast_ref = broadcast_ref


class ReconcileUnavailable(Exception):
    """The out-of-band reconciliation path is temporarily unreachable."""


class Challenge402(Exception):
    """Destination reissuing a fresh challenge instead of resuming a pending attempt."""


class SettlementBackend(ABC):
    """
    Rail-agnostic shape a retry-safe destination must expose.

    `settle(authorization)` attempts (or resumes) the durable effect for the
    given request artifact and returns `{"verdict": "settled", "transaction_ref": ...}`
    on success, or raises one of the four exceptions above.

    `reconcile(ref)` asks the destination, out of band, whether a
    previously-attempted-but-unconfirmed effect actually landed. Returns
    `{"verdict": "settled", "transaction_ref": ...}` if it did, or
    `{"verdict": "unknown"}` if the destination cannot yet say.
    """

    @abstractmethod
    def settle(self, authorization):
        raise NotImplementedError

    @abstractmethod
    def reconcile(self, ref):
        raise NotImplementedError
