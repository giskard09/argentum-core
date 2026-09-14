"""idempotency-ref-v1 guard, applied at the tool boundary.

Implements the PENDING/COMMITTED lifecycle from
../../../docs/spec/idempotency-ref.md against the fixed, caller-supplied
logical_action_id -- never from model-regenerated tool-call arguments
(invariant 5 of the spec, the vasilisnasopoulos gap). The key is derived
once, before the model/tool is ever invoked for this operation, and is
identical on every retry of the same logical action because it is a
property of the request, not of the attempt.
"""

from __future__ import annotations

import hashlib
import json


def jcs(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def derive_idempotency_ref(logical_action_id: str, action_type: str, agent_id: str) -> str:
    artifact = {
        "action_type": action_type,
        "agent_id": agent_id,
        "idempotency_key": logical_action_id,
        "scope": "crewai:tool-invocation",
        "version": "idempotency-ref-v1",
        "window_ms": 300000,
    }
    return hashlib.sha256(jcs(artifact).encode()).hexdigest()


class IdempotencyGuard:
    """In-memory PENDING/COMMITTED store, keyed by idempotency_ref.

    PENDING_GUARD: a second attempt observes an existing PENDING record for
    the same idempotency_ref and short-circuits *before* calling the real
    effect -- it does not know yet whether attempt 1 committed, so it must
    not re-run the effect.
    RECONCILED_GUARD: once the first attempt's effect actually lands, the
    record transitions to COMMITTED with the real effect_id. Any later
    attempt (including one racing in after the crash) finds a COMMITTED
    record and returns the original outcome instead of executing again.
    """

    def __init__(self) -> None:
        self._records: dict[str, dict] = {}
        self.events: list[dict] = []

    def guard(self, idempotency_ref: str, attempt_no: int, real_effect_fn):
        existing = self._records.get(idempotency_ref)
        if existing is not None and existing["trail_status"] == "COMMITTED":
            self.events.append(
                {"attempt_no": attempt_no, "guard_outcome": "RECONCILED_GUARD",
                 "idempotency_ref": idempotency_ref, "effect_id": existing["effect_id"]}
            )
            return existing["effect_id"], "RECONCILED_GUARD"

        if existing is not None and existing["trail_status"] == "PENDING":
            self.events.append(
                {"attempt_no": attempt_no, "guard_outcome": "PENDING_GUARD",
                 "idempotency_ref": idempotency_ref, "effect_id": None}
            )
            # Provider-confirmed resolution would poll here; for this worked
            # example the crash is synchronous within the same process, so
            # the PENDING record IS what the crashed attempt left behind --
            # correct behavior is to refuse a duplicate effect, not to guess.
            return None, "PENDING_GUARD"

        self._records[idempotency_ref] = {"trail_status": "PENDING", "effect_id": None}
        try:
            effect_id = real_effect_fn()
        except Exception:
            # Effect may or may not have committed before the raise -- the
            # record stays PENDING. This is the orphaned-PENDING case the
            # spec forbids resolving on window_ms alone (see spec section
            # "Trail lifecycle with idempotency_ref").
            raise
        self._records[idempotency_ref] = {"trail_status": "COMMITTED", "effect_id": effect_id}
        self.events.append(
            {"attempt_no": attempt_no, "guard_outcome": "COMMITTED",
             "idempotency_ref": idempotency_ref, "effect_id": effect_id}
        )
        return effect_id, "COMMITTED"

    def reconcile(self, idempotency_ref: str, logical_action_id: str, effect_store) -> str | None:
        """Provider-confirmed resolution of an orphaned PENDING (spec:
        'Trail lifecycle with idempotency_ref' -- the only source of
        evidence is a query to the underlying provider by the effect's own
        identifier, never window_ms elapsing on its own). Queries
        effect_store independently, the same way ArgentumReconciler polled
        GET /trails/verify against mycelium-runtime in the Nandana case.
        Mutates the record only on confirmed evidence, and only from
        PENDING -- never re-derives or overwrites a COMMITTED record."""
        existing = self._records.get(idempotency_ref)
        if existing is None or existing["trail_status"] != "PENDING":
            return None
        observed = effect_store.read_independent(logical_action_id)
        if not observed["readable"] or observed["effect_count"] == 0:
            return None
        real_effect_id = observed["effect_ids"][0]
        self._records[idempotency_ref] = {"trail_status": "COMMITTED", "effect_id": real_effect_id}
        self.events.append(
            {"attempt_no": None, "guard_outcome": "RECONCILED_GUARD",
             "idempotency_ref": idempotency_ref, "effect_id": real_effect_id}
        )
        return real_effect_id
