"""
Verifier for anchoring-precedence-ref-v1 conformance vectors.

Five invariants checked per spec:
  1. canonical_envelope      — SHA-256(JCS(envelope)) matches declared anchoring_precedence_ref
  2. admission_invariant     — admission_hash (if present) matches canonical_envelope_hash
  3. anchoring_existence     — anchor_block_time is non-null
  4. anchoring_precedence    — anchor_block_time * 1000 < outcome_ts_ms (strict)
  5. chain_invariant         — checks[chain_invariant] declared true in vector
                               (external resolution; verifier trusts vector declaration)
"""

import hashlib
import json
import sys
from pathlib import Path


def jcs(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def sha256hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def verify_vector(vector: dict) -> tuple[bool, list[str]]:
    failures = []
    envelope = vector["envelope"]

    # 1. canonical_envelope
    computed_ref = sha256hex(jcs(envelope))
    declared_ref = vector.get("anchoring_precedence_ref", "")
    if computed_ref != declared_ref:
        failures.append(
            f"canonical_envelope: computed {computed_ref} != declared {declared_ref}"
        )

    # 2. admission_invariant
    if "admission_hash" in vector:
        admission = vector["admission_hash"]
        if admission != computed_ref:
            failures.append(
                f"admission_invariant: admission_hash {admission[:16]}… "
                f"!= canonical_envelope_hash {computed_ref[:16]}…"
            )

    # 3. anchoring_existence
    anchor_block_time = envelope.get("anchor_block_time")
    if anchor_block_time is None:
        failures.append("anchoring_existence: anchor_block_time is null — no external commitment")

    # 4. anchoring_precedence
    outcome_ts_ms = envelope.get("outcome_ts_ms")
    if anchor_block_time is not None and outcome_ts_ms is not None:
        anchor_ms = anchor_block_time * 1000
        if anchor_ms >= outcome_ts_ms:
            failures.append(
                f"anchoring_precedence: anchor_block_time * 1000 = {anchor_ms} "
                f">= outcome_ts_ms = {outcome_ts_ms} (not strictly before outcome)"
            )

    # 5. chain_invariant — declared in vector; external resolution not performed here
    checks = vector.get("checks", {})
    if checks.get("chain_invariant") is False:
        failures.append("chain_invariant: declared false — trail_id does not resolve to proposed action")

    return len(failures) == 0, failures


def main():
    vectors_path = Path(__file__).parent / "vectors.json"
    data = json.loads(vectors_path.read_text())
    vectors = data["vectors"]

    print(f"anchoring-precedence-ref-v1 conformance — {len(vectors)} vectors\n")

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
        if ok and not conforms and expected == "FAIL":
            print(f"         correctly rejected: {failures[0]}")
        elif not ok:
            if expected == "PASS":
                for f in failures:
                    print(f"         unexpected failure: {f}")
            else:
                print(f"         expected FAIL ({v.get('failure_mode', '?')}) but verifier accepted it")

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
