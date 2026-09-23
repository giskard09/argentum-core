"""
Verifier for idempotency-ref-v1.1 conformance vectors.

Checks (docs/spec/idempotency-ref.md):
  1. hashes — idempotency_ref = SHA-256(JCS(idempotency_artifact)) and
     admitted_payload_digest = SHA-256(JCS(admitted_payload)) for every event.
  2. digest_outside_ref — admitted_payload_digest is not a field of the
     artifact, and the drifted retry (case 4) keeps A's idempotency_ref.
  3. decision_rule — replaying the events in order against one ledger gives
     the declared outcome and effect count for each of the four cases.
  4. negatives — each negative vector, replayed as its non-conformant
     implementation would, first diverges exactly where it declares. Each one
     fails on a different check: key distinctness, digest check, ref preimage.

Usage: python3 verify.py   (exit 0 = all checks pass)
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


def decide(ledger: dict, ref: str, digest: str, check_digest: bool = True) -> str:
    """Reference decision rule. ledger maps idempotency_ref -> admitted digest."""
    prior = ledger.get(ref)
    if prior is None:
        ledger[ref] = digest
        return "EXECUTE"
    if not check_digest or prior == digest:
        return "DUPLICATE"
    return "CONFLICT"


def replay(pairs, check_digest: bool = True):
    """pairs: [(id, ref, digest)] -> [(id, outcome, effects_after)]"""
    ledger, effects, out = {}, 0, []
    for eid, ref, digest in pairs:
        outcome = decide(ledger, ref, digest, check_digest)
        effects += outcome == "EXECUTE"
        out.append((eid, outcome, effects))
    return out


def first_divergence(got, events):
    for (eid, outcome, effects), ev in zip(got, events):
        if (outcome, effects) != (ev["expected"], ev["effects_after"]):
            return {"event": eid, "outcome": outcome, "effects_after": effects}
    return None


def verify(doc: dict) -> list[str]:
    errors = []
    events = doc["events"]

    for ev in events:
        if sha256hex(ev["idempotency_artifact"]) != ev["idempotency_ref"]:
            errors.append(f"{ev['id']}: idempotency_ref mismatch")
        if sha256hex(ev["admitted_payload"]) != ev["admitted_payload_digest"]:
            errors.append(f"{ev['id']}: admitted_payload_digest mismatch")
        if "admitted_payload_digest" in ev["idempotency_artifact"]:
            errors.append(f"{ev['id']}: admitted_payload_digest inside idempotency_artifact")

    by_id = {ev["id"]: ev for ev in events}
    if by_id["case-4-drifted-retry"]["idempotency_ref"] != by_id["case-1-first-intentional"]["idempotency_ref"]:
        errors.append("case-4: drifted retry must keep A's idempotency_ref")
    if by_id["case-4-drifted-retry"]["admitted_payload_digest"] == by_id["case-1-first-intentional"]["admitted_payload_digest"]:
        errors.append("case-4: drifted retry must carry a different admitted_payload_digest")
    if by_id["case-3-second-intentional-same-payload"]["admitted_payload_digest"] != by_id["case-1-first-intentional"]["admitted_payload_digest"]:
        errors.append("case-3: B must carry a payload byte-identical to A")

    pairs = [(ev["id"], ev["idempotency_ref"], ev["admitted_payload_digest"]) for ev in events]
    div = first_divergence(replay(pairs), events)
    if div:
        errors.append(f"decision_rule: {div}")

    digests = {ev["id"]: ev["admitted_payload_digest"] for ev in events}
    for neg in doc["negative_vectors"]:
        if neg["id"] == "negative-no-digest-check":
            got = replay(pairs, check_digest=False)
        else:
            for nev in neg["events"]:
                if sha256hex(nev["idempotency_artifact"]) != nev["idempotency_ref"]:
                    errors.append(f"{neg['id']}/{nev['id']}: idempotency_ref mismatch")
            got = replay([(n["id"], n["idempotency_ref"], digests[n["id"]]) for n in neg["events"]])
        div = first_divergence(got, events)
        if div != neg["expected_divergence"]:
            errors.append(f"{neg['id']}: expected divergence {neg['expected_divergence']}, got {div}")

    return errors


def main() -> int:
    doc = json.loads((HERE / "vectors.json").read_text(encoding="utf-8"))
    errors = verify(doc)
    for ev in doc["events"]:
        print(f"{ev['id']:42s} expected {ev['expected']:9s} effects {ev['effects_after']}")
    for neg in doc["negative_vectors"]:
        d = neg["expected_divergence"]
        print(f"{neg['id']:42s} diverges at {d['event']} -> {d['outcome']}")
    if errors:
        for e in errors:
            print("FAIL", e)
        return 1
    print(f"OK: {len(doc['events'])} events, {len(doc['negative_vectors'])} negatives")
    return 0


if __name__ == "__main__":
    sys.exit(main())
