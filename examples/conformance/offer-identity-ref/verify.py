"""
Verifier for offer-identity-ref-v1 conformance vectors.

One invariant checked per spec (docs/spec/offer-identity-ref.md):
  canonical_offer — SHA-256(JCS(x402_response)) matches the declared
  offer_identity_ref. x402_response is the exact x402Response object
  (x402Version + accepts[] of PaymentRequirements) served at S1, field names
  taken verbatim from x402-foundation/x402's x402Specs.ts.

There is deliberately no separate "was this offer substituted" check (T1):
per spec invariant 5, a substituted offer and a corrupted reference produce
the identical failure mode — a recompute mismatch. See vector
offer-substitution-mismatch-001 for the T1 shape modeled directly.
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

    computed_ref = sha256hex(jcs(vector["x402_response"]))
    declared_ref = vector.get("offer_identity_ref", "")
    if computed_ref != declared_ref:
        failures.append(
            f"canonical_offer: computed {computed_ref} != declared {declared_ref}"
        )

    return len(failures) == 0, failures


def main():
    vectors_path = Path(__file__).parent / "vectors.json"
    data = json.loads(vectors_path.read_text())
    vectors = data["vectors"]

    print(f"offer-identity-ref-v1 conformance — {len(vectors)} vectors\n")

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
