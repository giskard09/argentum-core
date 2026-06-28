"""
Verifier for verifier-key-source-ref-v1 conformance vectors.

Five invariants checked per signer_record:
  1. key_source_declared         — key_source is non-null
  2. signature_input_bound       — signature_input_hash == canonical_envelope_ref
  3. signer_identity_bound       — signer_id not 'anonymous-key-holder' or equivalent unbound id
                                   (in production: check against declared verifier role registry)
  4. key_resolution_not_stale    — key_resolution_time <= fixture_certification_time (if declared)
  5. multisig_completeness       — all signer_records have verification_result == 'pass'
                                   and either public_key_hash or key_resolution_evidence_hash present

A vector FAILS if any signer_record violates any invariant.
"""

import json
import sys
from pathlib import Path

UNBOUND_SIGNER_IDS = {"anonymous-key-holder"}


def parse_iso(ts: str) -> str:
    return ts


def iso_lte(a: str, b: str) -> bool:
    return a <= b


def verify_signer_record(
    record: dict,
    canonical_envelope_ref: str,
    fixture_certification_time: str | None,
) -> list[str]:
    failures = []
    sid = record.get("signer_id", "")

    # 1. key_source_declared
    if not record.get("key_source"):
        failures.append(
            f"key_source_ambiguous: signer_id={sid!r} — key_source is absent or null"
        )

    # 2. signature_input_bound
    sig_input = record.get("signature_input_hash", "")
    if sig_input != canonical_envelope_ref:
        failures.append(
            f"signature_input_drift: signer_id={sid!r} — "
            f"signature_input_hash={sig_input[:16]!r}… != canonical={canonical_envelope_ref[:16]!r}…"
        )

    # 3. signer_identity_bound
    if sid in UNBOUND_SIGNER_IDS:
        failures.append(
            f"signer_identity_unbound: signer_id={sid!r} is not bound to a declared verifier role"
        )

    # 4. key_resolution_not_stale
    if fixture_certification_time:
        key_time = record.get("key_resolution_time", "")
        if key_time and key_time > fixture_certification_time:
            failures.append(
                f"stale_external_key: signer_id={sid!r} — "
                f"key_resolution_time={key_time!r} > fixture_certification_time={fixture_certification_time!r}"
            )

    # 5. per-record completeness: verification_result must be 'pass'
    vr = record.get("verification_result", "")
    if vr != "pass":
        failures.append(
            f"multisig_overclaim_or_unverifiable: signer_id={sid!r} — "
            f"verification_result={vr!r} (not 'pass')"
        )

    # 5b. key material must be present for recomputability
    has_key = bool(record.get("public_key_hash")) or bool(record.get("key_resolution_evidence_hash"))
    if not has_key:
        failures.append(
            f"missing_key_material: signer_id={sid!r} — "
            "neither public_key_hash nor key_resolution_evidence_hash present"
        )

    return failures


def verify_vector(vector: dict, canonical_envelope_ref: str) -> tuple[bool, list[str]]:
    failures = []
    cert_time = vector.get("fixture_certification_time")
    records = vector.get("signer_records", [])

    for record in records:
        failures.extend(verify_signer_record(record, canonical_envelope_ref, cert_time))

    return len(failures) == 0, failures


def main():
    vectors_path = Path(__file__).parent / "vectors.json"
    data = json.loads(vectors_path.read_text())

    canonical_envelope_ref = data["canonical_envelope_ref"]
    vectors = data["vectors"]

    print(f"verifier-key-source-ref-v1 conformance — {len(vectors)} vectors\n")

    passed = 0
    failed = 0

    for v in vectors:
        vid = v["id"]
        expected = v["expected"]
        conforms, failures = verify_vector(v, canonical_envelope_ref)

        ok = conforms if expected == "PASS" else not conforms
        marker = "✓" if ok else "✗"
        status = "PASS" if ok else "FAIL"

        print(f"  {marker} [{status}] {vid}")
        if ok and not conforms:
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
