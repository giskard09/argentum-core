"""
Verifier for verifier-key-source-ref-v1 conformance vectors (spec v1.2).

Invariants checked per signer_record (see docs/spec/verifier-key-source-ref-v1.md,
"Invariants" and "Rules a verifier must apply"):
  1. key_source_declared         - key_source present and one of the four values
  2. signature_input_bound       - signature_input_hash == canonical_envelope_ref
  3. signer_identity_bound       - without a role_registry: ONLY rejects the sentinel
                                   signer_id 'anonymous-key-holder' (identity_binding:
                                   declared_only). With a role_registry: signer_id must be
                                   listed for the record's verifier_role (registry_checked).
  4. key_resolution_not_stale    - key_resolution_time <= fixture_certification_time,
                                   compared as UTC instants; either missing fails closed
  5. multisig_completeness       - verification_result == 'pass' and key material present
                                   per key_source, hashes 64 lowercase hex

A vector FAILS if any signer_record violates any invariant. The result also carries
identity_binding, separately from the failures.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

UNBOUND_SIGNER_IDS = {"anonymous-key-holder"}
KEY_SOURCES = {"embedded", "published_jwks", "pinned_registry", "cached_prior"}
VERIFICATION_RESULTS = {"pass", "fail", "unverifiable", "out_of_scope"}
NEEDS_PUBLIC_KEY_HASH = {"embedded", "pinned_registry"}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def parse_instant(ts):
    """RFC 3339 UTC date-time ending in Z -> aware datetime; ValueError otherwise."""
    if not isinstance(ts, str) or not _TS.match(ts):
        raise ValueError(f"not an RFC 3339 UTC timestamp: {ts!r}")
    return datetime.fromisoformat(ts[:-1] + "+00:00").astimezone(timezone.utc)


def _absent(v):
    return v is None or v == ""


def verify_signer_record(
    record: dict,
    canonical_envelope_ref: str,
    fixture_certification_time,
    role_registry=None,
) -> list[str]:
    failures = []
    sid = record.get("signer_id", "")

    # 1. key_source_declared (+ closed set)
    ks = record.get("key_source")
    if not ks:
        failures.append(f"key_source_ambiguous: signer_id={sid!r} - key_source is absent or null")
    elif ks not in KEY_SOURCES:
        failures.append(f"key_source_unknown: signer_id={sid!r} - key_source={ks!r}")

    # 2. signature_input_bound
    sig_input = record.get("signature_input_hash", "")
    if sig_input != canonical_envelope_ref:
        failures.append(
            f"signature_input_drift: signer_id={sid!r} - "
            f"signature_input_hash={str(sig_input)[:16]!r}... != canonical={canonical_envelope_ref[:16]!r}..."
        )

    # 3. signer_identity_bound
    if role_registry is None:
        if sid in UNBOUND_SIGNER_IDS:
            failures.append(
                f"signer_identity_unbound: signer_id={sid!r} is the declared-unbound sentinel "
                "(no role registry was supplied, so no link to a role was checked)"
            )
    else:
        role = record.get("verifier_role")
        listed = role_registry.get(role) if isinstance(role, str) else None
        if not isinstance(listed, list) or sid not in listed:
            failures.append(
                f"signer_identity_unbound: signer_id={sid!r} is not listed for verifier_role={role!r} in the role registry"
            )

    # 4. key_resolution_not_stale
    krt = record.get("key_resolution_time")
    if _absent(krt):
        failures.append(f"key_resolution_time_missing: signer_id={sid!r}")
    elif _absent(fixture_certification_time):
        pass  # reported once per vector (fixture_certification_time_missing)
    else:
        try:
            if parse_instant(krt) > parse_instant(fixture_certification_time):
                failures.append(
                    f"stale_external_key: signer_id={sid!r} - "
                    f"key_resolution_time={krt!r} > fixture_certification_time={fixture_certification_time!r}"
                )
        except ValueError as e:
            failures.append(f"timestamp_invalid: signer_id={sid!r} - {e}")

    # 5. per-record completeness
    vr = record.get("verification_result", "")
    if vr not in VERIFICATION_RESULTS:
        failures.append(f"verification_result_unknown: signer_id={sid!r} - verification_result={vr!r}")
    elif vr != "pass":
        failures.append(
            f"multisig_overclaim_or_unverifiable: signer_id={sid!r} - "
            f"verification_result={vr!r} (not 'pass')"
        )

    pkh, evh = record.get("public_key_hash"), record.get("key_resolution_evidence_hash")
    for name, val in (("public_key_hash", pkh), ("key_resolution_evidence_hash", evh)):
        if not _absent(val) and not (isinstance(val, str) and _HEX64.match(val)):
            failures.append(f"hash_format_invalid: signer_id={sid!r} - {name} is not 64 lowercase hex")
    if ks in NEEDS_PUBLIC_KEY_HASH:
        has_key = not _absent(pkh)
    else:
        has_key = not _absent(pkh) or not _absent(evh)
    if ks in KEY_SOURCES and not has_key:
        need = "public_key_hash" if ks in NEEDS_PUBLIC_KEY_HASH else "public_key_hash or key_resolution_evidence_hash"
        failures.append(f"missing_key_material: signer_id={sid!r} - key_source={ks!r} requires {need}")

    return failures


def verify_vector(vector: dict, canonical_envelope_ref: str):
    """Returns (conforms, failures, identity_binding)."""
    failures = []
    cert_time = vector.get("fixture_certification_time")
    registry = vector.get("role_registry")
    records = vector.get("signer_records", [])
    if records and _absent(cert_time):
        failures.append("fixture_certification_time_missing: no certification time, key_resolution_time cannot be compared")

    for record in records:
        failures.extend(verify_signer_record(record, canonical_envelope_ref, cert_time, registry))

    identity_binding = "registry_checked" if registry is not None else "declared_only"
    return len(failures) == 0, failures, identity_binding


# A vector's failure_mode names the reason it was written to exercise. The
# verifier's codes for two of them are longer; the rest are equal.
FAILURE_MODE_CODE = {
    "missing_cosigner_key": "missing_key_material",
    "multisig_overclaim": "multisig_overclaim_or_unverifiable",
}


def reasons(failures):
    return [f.split(":", 1)[0] for f in failures]


def load_vectors():
    here = Path(__file__).parent
    data = json.loads((here / "vectors.json").read_text())
    extra = json.loads((here / "vectors-v1.2.json").read_text())
    assert extra["canonical_envelope_ref"] == data["canonical_envelope_ref"]
    return data["canonical_envelope_ref"], list(data["vectors"]) + extra["vectors"]


def score(vector, canonical_envelope_ref):
    """(ok, conforms, failures, identity_binding, want) for one vector."""
    conforms, failures, binding = verify_vector(vector, canonical_envelope_ref)
    expected = vector["expected"]
    ok = conforms if expected == "PASS" else not conforms
    mode = vector.get("failure_mode")
    want = FAILURE_MODE_CODE.get(mode, mode)
    if ok and expected != "PASS" and want and want not in reasons(failures):
        ok = False  # rejected, but not for the reason the vector exists to test
    return ok, conforms, failures, binding, want


def main():
    canonical_envelope_ref, vectors = load_vectors()

    print(f"verifier-key-source-ref-v1.2 conformance - {len(vectors)} vectors\n")

    passed = 0
    failed = 0

    for v in vectors:
        vid = v["id"]
        expected = v["expected"]
        ok, conforms, failures, binding, want = score(v, canonical_envelope_ref)
        marker = "\u2713" if ok else "\u2717"
        status = "PASS" if ok else "FAIL"

        print(f"  {marker} [{status}] {vid}  (identity_binding: {binding})")
        if ok and not conforms:
            hit = next((f for f in failures if f.split(":", 1)[0] == want), failures[0])
            print(f"         correctly rejected: {hit}")
        elif not ok:
            if expected == "PASS":
                for f in failures:
                    print(f"         unexpected failure: {f}")
            elif conforms:
                print(f"         expected FAIL ({v.get('failure_mode', '?')}) but verifier accepted it")
            else:
                print(f"         rejected, but not for {want!r}; reasons: {reasons(failures)}")

        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{passed}/{len(vectors)} passed", end="")
    if failed:
        print(f", {failed} failed")
        sys.exit(1)
    print()


if __name__ == "__main__":
    main()
