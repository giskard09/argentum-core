"""
Reference verifier for the Case E worked example (see README.md).

Named Case E, not Case D: ogasurfproject-jpg already has a Case D in this
issue (astrogilda's, frozen at 33c22f5a) -- renamed per their request
(comment, 2026-10-18T15:34:49Z) before this went into the comparison table.

Composes execution-join-ref-v1's post_commit_consistency invariant
(docs/spec/execution-join-ref-v1.md, "Post-commit divergence (v1.1/v1.2)",
PR#137, 2026-10-18) onto the request_occurrence/task/execution-receipt
object shapes frozen by ogasurfproject-jpg/horizon-shield#51 and defined
in COMPANION_v0.md / PILOT_v0.md at the pinned commit (see README.md).
Both vectors' task/request_occurrence, and Case A's execution_receipt and
post_commit_observation.observed_hash, are the pilot's own real, committed
live_smoke outputs (commit dcbdc5d2) -- not stand-ins. Case E's
execution_receipt reuses the real pre-correction (souba-db 2.2.0) digest
and seen_block.height ogasurfproject-jpg posted in full, untruncated hex;
see NOTICE.md for why `signature` and `seen_block.hash` are absent rather
than invented for that one record (it was an unlogged smoke test, never
committed as a file).

Five checks, three of them declared (not computed here) on purpose:

  1. canonical_envelope        — computed. task_sha256, request_sha256, and
                                  execution_receipt.outcome.response_sha256
                                  all recompute from their own preimages via
                                  the repo's real jcs.py (RFC 8785).
  2. chain_integrity           — computed. request_occurrence.task_sha256
                                  matches the task; execution_receipt.
                                  request_sha256 matches the request.
  3. authority_and_payment     — DECLARED, not computed. This is MUSUBI's
                                  and APS's job (budget, delegation, payment
                                  rail) -- out of scope for this worked
                                  example on purpose. Trusted exactly as
                                  declared in the vector.
  4. acceptance                — DECLARED, not computed. This is
                                  babyblueviper1's work-acceptance-record's
                                  job (criteria committed before the call,
                                  checked after, signed by the checker key).
                                  Trusted exactly as declared in the vector.
  5. post_commit_consistency   — computed. The ONLY thing this worked
                                  example actually contributes: does a
                                  later, independent post_commit_observation
                                  of the audited output still match the
                                  response_sha256 the execution_receipt
                                  committed to at settlement? See
                                  docs/spec/execution-join-ref-v1.md for the
                                  full invariant this reuses verbatim,
                                  field names adapted to this pilot's
                                  request_sha256/response_sha256 instead of
                                  execution-join-ref's own result_id/
                                  output_hash.

This file intentionally does NOT reimplement MUSUBI/APS accounting or
invinoveritas acceptance checking -- declaring #3 and #4 rather than
computing them is the point, not a shortcut: this is a fourth,
complementary check, additive to the three roles the pilot's own
participants already cover.
"""

import hashlib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO_ROOT))

import jcs  # noqa: E402  (repo-root RFC 8785 canonicalizer, see module docstring)


def sha256hex(obj: dict) -> str:
    return hashlib.sha256(jcs.jcs_bytes(obj, ensure_ascii=False)).hexdigest()


def verify_vector(vector: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []

    task = vector["task"]
    request_occurrence = vector["request_occurrence"]
    execution_receipt = vector["execution_receipt"]
    post_commit = vector["post_commit_observation"]
    declared = vector.get("declared", {})
    checks = vector.get("checks", {})

    # 1. canonical_envelope. Note: execution_receipt.outcome.response_sha256
    # is NOT recomputed here -- it is HORIZON SHIELD's actual audit_estimate
    # output (real in both vectors: c2920477… and ccfbae3d… are the pilot's
    # own real responses, independently re-hashed against the full audit
    # object and matched during authoring -- see NOTICE.md), an external
    # service call this worked example does not run or mock. It is treated
    # the same way the pilot's own payment/acceptance checks are: a
    # committed value this verifier binds against (invariant 5 below), not
    # one it recomputes from scratch.
    task_sha256 = sha256hex(task)
    request_sha256 = sha256hex(request_occurrence)

    canonical_ok = True
    if task_sha256 != request_occurrence.get("task_sha256"):
        canonical_ok = False
        failures.append(
            f"canonical_envelope: recomputed task_sha256={task_sha256} != "
            f"request_occurrence.task_sha256={request_occurrence.get('task_sha256')}"
        )
    if request_sha256 != execution_receipt.get("request_sha256"):
        canonical_ok = False
        failures.append(
            f"canonical_envelope: recomputed request_sha256={request_sha256} != "
            f"execution_receipt.request_sha256={execution_receipt.get('request_sha256')}"
        )
    declared_canonical = checks.get("canonical_envelope")
    if declared_canonical is not None and declared_canonical != canonical_ok:
        failures.append(f"canonical_envelope: computed {canonical_ok} != declared {declared_canonical}")

    # 2. chain_integrity (same two bindings as canonical_envelope above in this
    # worked example -- the pilot's own request_occurrence/execution_receipt
    # shape makes task binding and request binding the same two checks;
    # kept as a separate named invariant to match execution-join-ref-v1's own
    # chain_integrity/canonical_envelope separation).
    chain_ok = canonical_ok
    declared_chain = checks.get("chain_integrity")
    if declared_chain is not None and declared_chain != chain_ok:
        failures.append(f"chain_integrity: computed {chain_ok} != declared {declared_chain}")

    # 3 & 4. authority_and_payment / acceptance -- DECLARED, not computed.
    for key in ("authority_and_payment", "acceptance"):
        if declared.get(key) is False:
            failures.append(f"{key}: declared false (external to this worked example)")

    # 5. post_commit_consistency -- computed.
    response_sha256 = execution_receipt["outcome"]["response_sha256"]
    pc_request_ok = post_commit.get("request_sha256") == execution_receipt.get("request_sha256")
    pc_matches_output = post_commit.get("observed_hash") == response_sha256
    pc_ok = pc_request_ok and pc_matches_output
    declared_pc = checks.get("post_commit_consistency")
    if not pc_ok:
        failures.append(
            f"post_commit_consistency: post_commit_observation.observed_hash="
            f"{post_commit.get('observed_hash')} != execution_receipt.outcome."
            f"response_sha256={response_sha256} (bound to the same request: {pc_request_ok})"
        )
    if declared_pc is not None and declared_pc != pc_ok:
        failures.append(f"post_commit_consistency: computed {pc_ok} != declared {declared_pc}")

    # post_commit_observation.dataset_sha256 (execution-join-ref-v1.2,
    # optional, additive) is intentionally not read above: it is purely
    # informational (which external dataset this observation was recomputed
    # against), never part of the pc_ok computation, and never changes
    # PASS/FAIL. See docs/spec/execution-join-ref-v1.md "Post-commit
    # divergence" for the field itself; main() below prints it for whichever
    # vectors carry it, same treatment as every other descriptive field.

    return len(failures) == 0, failures


def main():
    vectors_path = Path(__file__).parent / "vectors.json"
    data = json.loads(vectors_path.read_text())
    vectors = data["vectors"]

    print(f"horizon-shield-pilot-case-e — {len(vectors)} vectors\n")

    passed = 0
    failed = 0
    for v in vectors:
        vid = v["id"]
        expected = v["expected"]
        conforms, failures = verify_vector(v)
        ok = conforms if expected == "PASS" else not conforms
        marker = "✓" if ok else "✗"
        status = "PASS" if ok else "FAIL"

        print(f"  {marker} [{status}] {vid}")
        dataset_sha256 = v.get("post_commit_observation", {}).get("dataset_sha256")
        if dataset_sha256 is not None:
            print(f"         post_commit_observation.dataset_sha256={dataset_sha256} (informational)")
        if ok and not conforms and expected == "FAIL":
            print(f"         correctly rejected ({v.get('failure_code', '?')}): {failures[0]}")
        elif not ok:
            for f in failures:
                print(f"         {f}")

        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{passed}/{len(vectors)} passed", end="")
    if failed:
        print(f", {failed} failed")
        sys.exit(1)
    else:
        print()


if __name__ == "__main__":
    main()
