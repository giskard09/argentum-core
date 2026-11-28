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


# RFC 8785 JCS from the repo's jcs.py. Until 2026-11-26 jcs() was json.dumps(sort_keys=True), which the
# spec says not to use (code-point key order; Python number forms). Run from a checkout of the repository.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from jcs import jcs_bytes  # noqa: E402


def jcs(obj: dict) -> str:
    """Raises ValueError for an integer outside +/-(2^53-1) or a non-finite float (out of the JCS profile)."""
    return jcs_bytes(obj).decode("utf-8")


def sha256hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def verify_vector(vector: dict) -> tuple[bool, list[str]]:
    failures = []

    declared_ref = vector.get("offer_identity_ref", "")
    try:
        computed_ref = sha256hex(jcs(vector["x402_response"]))
    except (ValueError, TypeError) as e:
        computed_ref = None
        failures.append(f"canonical_offer: x402_response cannot be canonicalized under RFC 8785 ({e})")
    if computed_ref is not None and computed_ref != declared_ref:
        failures.append(
            f"canonical_offer: computed {computed_ref} != declared {declared_ref}"
        )

    return len(failures) == 0, failures


def main():
    here = Path(__file__).parent
    vectors = []
    for name in ("vectors.json", "vectors-jcs.json"):
        vectors += json.loads((here / name).read_text())["vectors"]

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
