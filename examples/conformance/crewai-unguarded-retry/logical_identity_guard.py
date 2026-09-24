"""idempotency-ref v1.1 decision rule, applied at the tool boundary.

Implements "Logical identity and admitted payload (v1.1)" from
../../../docs/spec/idempotency-ref.md: the ledger is keyed by
idempotency_ref (the logical action, minted at admission), and every
admission records admitted_payload_digest next to it -- never inside the
artifact. A dispatch presenting (idempotency_ref, admitted_payload_digest):

  no prior admission          -> EXECUTE   (record admission, run the effect)
  prior, same digest          -> DUPLICATE (return prior outcome, no effect)
  prior, different digest     -> CONFLICT  (fail closed, no effect)

`mode` selects the non-conformant variants the v1.1 negative vectors
describe, so the same crewAI path can show where each one breaks:

  conformant       the rule above
  no_digest_check  v1.0 ledger: dedup on idempotency_ref alone (Invariant 7)
  content_key      idempotency_key = sha256 of the payload (Invariant 6)
  digest_inside    admitted_payload_digest inside the ref preimage
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from jcs import jcs_dumps  # noqa: E402

MODES = ("conformant", "no_digest_check", "content_key", "digest_inside")


def sha256hex(obj) -> str:
    return hashlib.sha256(jcs_dumps(obj).encode("utf-8")).hexdigest()


class LogicalIdentityGuard:
    def __init__(self, artifact_base: dict, mode: str = "conformant") -> None:
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}")
        # Every artifact field except idempotency_key, fixed at admission.
        self._artifact_base = {k: v for k, v in artifact_base.items() if k != "idempotency_key"}
        self.mode = mode
        self._admissions: dict[str, dict] = {}

    def artifact(self, logical_action_id: str, admitted_payload_digest: str) -> dict:
        key = logical_action_id
        if self.mode == "content_key":
            key = "sha256:" + admitted_payload_digest
        art = dict(self._artifact_base, idempotency_key=key)
        if self.mode == "digest_inside":
            art["admitted_payload_digest"] = admitted_payload_digest
        return art

    def dispatch(self, logical_action_id: str, admitted_payload: dict, real_effect_fn) -> dict:
        digest = sha256hex(admitted_payload)
        art = self.artifact(logical_action_id, digest)
        ref = sha256hex(art)

        prior = self._admissions.get(ref)
        if prior is None:
            # Admission is recorded before the effect runs: a retry that
            # races in after a crash finds it and does not execute again.
            self._admissions[ref] = {"digest": digest, "effect_id": None}
            effect_id = real_effect_fn()
            self._admissions[ref]["effect_id"] = effect_id
            outcome = "EXECUTE"
        elif self.mode == "no_digest_check" or prior["digest"] == digest:
            effect_id = prior["effect_id"]
            outcome = "DUPLICATE"
        else:
            effect_id = None
            outcome = "CONFLICT"

        return {
            "outcome": outcome,
            "idempotency_ref": ref,
            "admitted_payload_digest": digest,
            "effect_id": effect_id,
        }
