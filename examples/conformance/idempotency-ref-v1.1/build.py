"""
Builds vectors.json for idempotency-ref-v1.1 (docs/spec/idempotency-ref.md).

The four-case logical-identity test defined by impartshadow
(crewAIInc/crewAI#5802, comment 5790417981) and pinned as a regression by
stringsofthemind-oss/once#45 (9ca1eb3):

  A  $100 -> X   execute once
  A  $100 -> X   retry: reconcile, no second effect
  B  $100 -> X   second intentional action: execute despite identical payload
  A  $125 -> X   drifted retry: conflict, fail closed

Deterministic: running it twice produces byte-identical output.
"""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))

from jcs import jcs_dumps  # noqa: E402


def sha256hex(obj) -> str:
    return hashlib.sha256(jcs_dumps(obj).encode("utf-8")).hexdigest()


def artifact(key: str) -> dict:
    return {
        "action_type": "payment.send",
        "agent_id": "crew-runtime-agent-042",
        "idempotency_key": key,
        "scope": "mycelium:payment",
        "version": "idempotency-ref-v1.1",
        "window_ms": 300000,
    }


PAYLOAD_100 = {"amount_cents": 10000, "currency": "USD", "recipient": "merchant_x"}
PAYLOAD_125 = {"amount_cents": 12500, "currency": "USD", "recipient": "merchant_x"}

# Logical action ids minted at admission, before any model/tool execution.
KEY_A = "adm_4f1c9e2a"
KEY_B = "adm_b7d03e55"


def event(eid, key, payload, expected, effects_after, description):
    art = artifact(key)
    return {
        "id": eid,
        "description": description,
        "idempotency_artifact": art,
        "idempotency_ref": sha256hex(art),
        "admitted_payload": payload,
        "admitted_payload_digest": sha256hex(payload),
        "expected": expected,
        "effects_after": effects_after,
    }


def build() -> dict:
    events = [
        event("case-1-first-intentional", KEY_A, PAYLOAD_100, "EXECUTE", 1,
              "First intentional payment A, $100 -> merchant_x. No prior admission under this idempotency_ref: execute once."),
        event("case-2-retry-same-payload", KEY_A, PAYLOAD_100, "DUPLICATE", 1,
              "Retry of A after a lost acknowledgement. Same idempotency_ref, same admitted_payload_digest: reconcile against the prior outcome, no second effect."),
        event("case-3-second-intentional-same-payload", KEY_B, PAYLOAD_100, "EXECUTE", 2,
              "Second intentional payment B with a payload byte-identical to A. B was admitted under its own logical id, so its idempotency_ref differs from A's: execute once. A key derived from payload content would collide here and wrongly deduplicate B (see negative-content-derived-key)."),
        event("case-4-drifted-retry", KEY_A, PAYLOAD_125, "CONFLICT", 2,
              "Retry of A whose payload drifted to $125. Same idempotency_ref as A (the ref carries logical identity, not payload), different admitted_payload_digest: conflict, fail closed. Neither a duplicate of A nor a new action; a changed payload needs a new idempotency_key."),
    ]

    content_keyed = []
    for ev in events:
        art = artifact("sha256:" + ev["admitted_payload_digest"])
        content_keyed.append({"id": ev["id"], "idempotency_artifact": art, "idempotency_ref": sha256hex(art)})

    digest_inside = []
    for ev in events:
        art = dict(ev["idempotency_artifact"], admitted_payload_digest=ev["admitted_payload_digest"])
        digest_inside.append({"id": ev["id"], "idempotency_artifact": art, "idempotency_ref": sha256hex(art)})

    return {
        "spec_version": "idempotency-ref-v1.1",
        "spec": "docs/spec/idempotency-ref.md",
        "description": "Four-case logical-identity test (impartshadow, crewAIInc/crewAI#5802 comment 5790417981; regression in stringsofthemind-oss/once#45, 9ca1eb3). Events are replayed in order against one ledger, all within window_ms. idempotency_ref = SHA-256(JCS(idempotency_artifact)); admitted_payload_digest = SHA-256(JCS(admitted_payload)), carried next to idempotency_ref in the envelope and never inside the artifact.",
        "decision_rule": {
            "EXECUTE": "no prior admission under this idempotency_ref within window_ms",
            "DUPLICATE": "prior admission under this idempotency_ref with the same admitted_payload_digest: reconcile, no new effect",
            "CONFLICT": "prior admission under this idempotency_ref with a different admitted_payload_digest: fail closed, no new effect",
        },
        "events": events,
        "negative_vectors": [
            {
                "id": "negative-content-derived-key",
                "violates": "Invariant 6 (distinct intentional actions MUST carry distinct keys)",
                "description": "idempotency_key = sha256 of the admitted payload. v1.0 Invariant 5 allowed 'a hash of the caller's own pre-execution request'. A and B collide on one idempotency_ref, so case 3 is deduplicated as a retry and payment B never happens.",
                "events": content_keyed,
                "expected_divergence": {"event": "case-3-second-intentional-same-payload", "outcome": "DUPLICATE", "effects_after": 1},
            },
            {
                "id": "negative-no-digest-check",
                "violates": "Invariant 7 (same key + different admitted_payload_digest MUST be a conflict)",
                "description": "v1.0 ledger: dedup on idempotency_ref alone, no admitted_payload_digest. The drifted $125 retry has the same idempotency_ref as A and passes silently as a duplicate of A.",
                "events": "same as events, admitted_payload_digest ignored",
                "expected_divergence": {"event": "case-4-drifted-retry", "outcome": "DUPLICATE", "effects_after": 2},
            },
            {
                "id": "negative-digest-inside-artifact",
                "violates": "Derivation (admitted_payload_digest MUST NOT enter the idempotency_ref preimage)",
                "description": "admitted_payload_digest placed inside idempotency_artifact. The ref now changes with the payload, so the drifted retry gets a fresh idempotency_ref and executes as a new action: a third effect for two intended payments.",
                "events": digest_inside,
                "expected_divergence": {"event": "case-4-drifted-retry", "outcome": "EXECUTE", "effects_after": 3},
            },
        ],
        "credits": "Four-case test: impartshadow/agent-contracts (crewAIInc/crewAI#5802). Regression: stringsofthemind-oss/once#45.",
    }


if __name__ == "__main__":
    out = json.dumps(build(), indent=2, ensure_ascii=False) + "\n"
    (HERE / "vectors.json").write_text(out, encoding="utf-8")
    print("wrote vectors.json")
