"""
Runs the two MoltyCel-derived vectors (translate.py) against this repo's
real verifier: verify.py's verify_vector() for the structural invariants,
and verify_enforcement.py's enforce_7_5() for AAE-02 7.5 enforcement.

Deterministic: prints a report and its sha256 last. Two runs must print the
same REPORT_SHA256 -- the runner checks that itself (run() is called twice
in main() and the digests are compared) rather than asking a reviewer to
run it twice by hand.
"""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))  # delegation-chain-ref/
sys.path.insert(0, str(HERE.parent / "revoked-ancestor"))  # verify_enforcement
from verify import SeenRegistry, verify_vector  # noqa: E402
from verify_enforcement import enforce_7_5  # noqa: E402

from translate import translate_vector_05, translate_vector_11  # noqa: E402


def run() -> tuple[str, int]:
    lines = []
    failed = 0

    source_11 = json.loads((HERE / "source-vectors" / "11-delegation-cascade-revocation.json").read_text())
    vector_11 = translate_vector_11(source_11)

    structural_ok, structural_failures = verify_vector(vector_11, seen_registry=SeenRegistry())
    enforced_ok, enforced_failures = enforce_7_5(vector_11["chain_artifact"], [vector_11["revocation_artifact"]])

    lines.append(f"[{vector_11['id']}]")
    lines.append(f"  source: {vector_11['source']['repo']}@{vector_11['source']['ref']} "
                 f"{vector_11['source']['path']} (expected {vector_11['source']['source_aae_vector_expected']['result']} "
                 f"at step {vector_11['source']['source_aae_vector_expected']['verification_step']}, "
                 f"reason={vector_11['source']['source_aae_vector_expected']['rejection_reason']})")
    structural_status = "PASS" if structural_ok else "FAIL"
    lines.append(f"  structural (verify.py, no revocation read): {structural_status}")
    for f in structural_failures:
        lines.append(f"    {f}")
    if not structural_ok:
        failed += 1

    enforcement_status = "PASS" if enforced_ok else "FAIL"
    lines.append(f"  AAE-02 7.5 enforcement (verify_enforcement.py enforce_7_5): {enforcement_status}")
    for f in enforced_failures:
        lines.append(f"    {f}")
    # AAE expects REJECT for this scenario; our 7.5 model must also FAIL (not PASS).
    moltycel_expects_reject = vector_11["source"]["source_aae_vector_expected"]["result"] == "REJECT"
    agree = (enforced_ok is False) if moltycel_expects_reject else (enforced_ok is True)
    lines.append(f"  agrees with MoltyCel's expected verdict: {agree}")
    if not agree:
        failed += 1

    lines.append("")

    source_05 = json.loads((HERE / "source-vectors" / "05-single-use-replay.json").read_text())
    vector_05 = translate_vector_05(source_05)

    lines.append(f"[{vector_05['id']}]")
    lines.append(f"  source: {vector_05['source']['repo']}@{vector_05['source']['ref']} "
                 f"{vector_05['source']['path']} (expected {vector_05['source']['source_aae_vector_expected']['result']} "
                 f"at step {vector_05['source']['source_aae_vector_expected']['verification_step']}, "
                 f"reason={vector_05['source']['source_aae_vector_expected']['rejection_reason']})")

    fresh_registry = SeenRegistry()
    first_use_ok, first_use_failures = verify_vector(vector_05, seen_registry=fresh_registry)
    lines.append(f"  control, first presentation (fresh SeenRegistry): {'PASS' if first_use_ok else 'FAIL'}")
    for f in first_use_failures:
        lines.append(f"    {f}")
    if not first_use_ok:
        failed += 1

    already_consumed_registry = SeenRegistry()
    chain_id = vector_05["chain_artifact"]["chain_id"]
    hop_refs = [h["delegation_ref"] for h in vector_05["chain_artifact"]["hops"]]
    already_consumed_registry.record(chain_id, hop_refs)  # ground truth from source: id already in consumed_ids
    replay_ok, replay_failures = verify_vector(vector_05, seen_registry=already_consumed_registry)
    lines.append(f"  replay presentation (registry pre-seeded as already-consumed): {'PASS' if replay_ok else 'FAIL'}")
    for f in replay_failures:
        lines.append(f"    {f}")
    moltycel_expects_reject_05 = vector_05["source"]["source_aae_vector_expected"]["result"] == "REJECT"
    agree_05 = (replay_ok is False) if moltycel_expects_reject_05 else (replay_ok is True)
    lines.append(f"  agrees with MoltyCel's expected verdict: {agree_05}")
    if not agree_05:
        failed += 1

    body = "\n".join(lines)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return body, failed, digest


def main():
    body1, failed1, digest1 = run()
    body2, failed2, digest2 = run()
    assert body1 == body2 and digest1 == digest2, "non-deterministic output between two runs"

    print(body1)
    print(f"\n{failed1} failed (of 2 translated vectors, 4 checks total)")
    print(f"REPORT_SHA256 {digest1}")
    print("(run twice in-process; both runs produced this same digest)")
    sys.exit(1 if failed1 else 0)


if __name__ == "__main__":
    main()
