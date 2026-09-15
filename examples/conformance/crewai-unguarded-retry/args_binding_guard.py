"""Argument-binding extension to idempotency-ref-v1.

Addresses gap #4 of the five regression cases nsolland mapped against this
worked example (crewAIInc/crewAI#7449, 2026-09-14/15, our own issue):
`logical_action_id` alone identifies WHICH action a retry belongs to, never
WHAT the retry actually asks for. `idempotency_ref` (idempotency-ref.md
invariant 5) is deliberately keyed only on `logical_action_id` -- never on
arguments -- to avoid the opposite false-negative failure the spec already
documents (a SHA(args)-keyed scheme missing a true retry whose
model-regenerated arguments differ only superficially, see
idempotency-ref.md "When a retry re-enters through the model"). But that
same design leaves nothing in `idempotency_guard.py` to notice when a
second attempt's arguments are not a superficial rewording but a
materially different request (a different amount, a different
recipient). nsolland's point: that case should force a NEW authorization
decision, never reuse the first attempt's permit.

This module does not replace idempotency_guard.IdempotencyGuard -- it wraps
it with a pre-check, standing in for the `action_ref` binding a real
`decision_binding_ref` (../../../docs/spec/decision-binding-ref-v1.0.md)
would carry: the authorization decision was made against specific action
content, and a change to that content invalidates the binding.
"""

from __future__ import annotations

import hashlib

from idempotency_guard import jcs


def derive_args_digest(arguments: dict) -> str:
    return hashlib.sha256(jcs(arguments).encode()).hexdigest()


class ArgumentMismatchError(Exception):
    def __init__(
        self, idempotency_ref: str, logical_action_id: str | None,
        bound_digest: str, presented_digest: str,
    ) -> None:
        self.idempotency_ref = idempotency_ref
        self.logical_action_id = logical_action_id
        self.bound_digest = bound_digest
        self.presented_digest = presented_digest
        super().__init__(
            "ARGUMENT_MISMATCH_REQUIRES_NEW_DECISION: logical_action_id="
            f"{logical_action_id!r} was bound to args_digest={bound_digest} "
            "by the first attempt's authorization decision; this attempt "
            f"presents args_digest={presented_digest}. Refusing to reuse "
            "the existing permit -- a fresh authority decision is "
            "required for this action content before it may proceed."
        )


class ArgumentBoundGuard:
    """Wraps an IdempotencyGuard with an args_digest binding check.

    On the FIRST attempt observed for a given idempotency_ref, binds
    args_digest alongside it. On every SUBSEQUENT attempt, compares the
    presented args_digest to the bound one BEFORE the wrapped guard is
    consulted at all. A mismatch raises ArgumentMismatchError -- it never
    silently returns the first attempt's effect_id (which would discard
    the caller's real, changed request) and never silently executes a
    second, different effect under the same idempotency_ref (which would
    let a materially different action ride on an authorization it was
    never covered by).
    """

    def __init__(self, guard) -> None:
        self._guard = guard
        self._bound_args: dict[str, str] = {}

    def guard(self, idempotency_ref: str, attempt_no: int, arguments: dict, real_effect_fn):
        presented_digest = derive_args_digest(arguments)
        bound_digest = self._bound_args.get(idempotency_ref)

        if bound_digest is None:
            self._bound_args[idempotency_ref] = presented_digest
        elif bound_digest != presented_digest:
            self._guard.events.append(
                {
                    "attempt_no": attempt_no,
                    "guard_outcome": "ARGUMENT_MISMATCH_REQUIRES_NEW_DECISION",
                    "idempotency_ref": idempotency_ref,
                    "effect_id": None,
                    "bound_args_digest": bound_digest,
                    "presented_args_digest": presented_digest,
                }
            )
            raise ArgumentMismatchError(
                idempotency_ref, arguments.get("logical_action_id"),
                bound_digest, presented_digest,
            )

        return self._guard.guard(idempotency_ref, attempt_no, real_effect_fn)
