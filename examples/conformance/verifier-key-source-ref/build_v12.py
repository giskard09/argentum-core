"""Build vectors-v1.2.json for verifier-key-source-ref (docs/spec/verifier-key-source-ref-v1.md,
"Rules a verifier must apply"). Additive: vectors.json keeps its six vectors and
verdicts. Each vector changes one field of a record that passes. Expected results
are written by hand from the spec, not computed by the verifier.

    python3 build_v12.py    # rewrites vectors-v1.2.json deterministically
"""
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
base = json.loads((HERE / "vectors.json").read_text())
ENV = base["canonical_envelope_ref"]
H1, H2, H3 = "a1" * 32, "b2" * 32, "c3" * 32
CERT = "2026-06-28T10:00:00.000Z"


def rec(sid, role, **kw):
    r = {"signer_id": sid, "key_id": sid + "-key", "key_source": "embedded", "public_key_hash": H1,
         "signature_input_hash": ENV, "verification_result": "pass",
         "key_resolution_time": "2026-06-28T09:00:00.000Z", "key_resolution_evidence_hash": H2,
         "verifier_role": role}
    for k, v in kw.items():
        if v is ...:
            r.pop(k, None)
        else:
            r[k] = v
    return r


def two(**second):
    return [rec("signer-a", "admission"), rec("signer-b", "co-signer", **second)]


REG = {"admission": ["signer-a"], "co-signer": ["signer-b"]}
V = []


def add(vid, desc, expected, records, mode=None, cert=CERT, registry=None):
    v = {"id": vid, "description": desc, "expected": expected, "signer_records": records}
    if mode:
        v["failure_mode"] = mode
    if cert is not ...:
        v["fixture_certification_time"] = cert
    if registry is not None:
        v["role_registry"] = registry
    V.append(v)


add("vk-001-two-embedded-pass", "Regression: two embedded signers, complete records, certification time declared. A pass of recomputability; identity_binding is declared_only.", "PASS", two())
add("vk-002-registry-checked-pass", "Both signer_ids are listed for their declared roles in the supplied role_registry: identity_binding is registry_checked.", "PASS", two(), registry=REG)
add("vk-003-registry-signer-not-listed", "A role_registry is supplied and signer-b is not listed for co-signer.", "FAIL", two(), "signer_identity_unbound", registry={"admission": ["signer-a"], "co-signer": ["someone-else"]})
add("vk-004-registry-role-undeclared", "A role_registry is supplied and signer-b carries no verifier_role.", "FAIL", two(verifier_role=...), "signer_identity_unbound", registry=REG)
add("vk-005-mixed-precision-stale", "key_resolution_time 10:00:00.500Z is half a second after the certification time 10:00:00Z. As strings it sorts before; as instants it is later.", "FAIL", two(key_resolution_time="2026-06-28T10:00:00.500Z"), "stale_external_key", cert="2026-06-28T10:00:00Z")
add("vk-006-same-instant-different-precision", "key_resolution_time 10:00:00.000Z equals the certification time 10:00:00Z as an instant: precedes-or-equals holds.", "PASS", two(key_resolution_time="2026-06-28T10:00:00.000Z"), cert="2026-06-28T10:00:00Z")
add("vk-007-key-resolution-time-absent", "key_resolution_time absent: the relation cannot be established.", "FAIL", two(key_resolution_time=...), "key_resolution_time_missing")
add("vk-008-key-resolution-time-null", "key_resolution_time present as null.", "FAIL", two(key_resolution_time=None), "key_resolution_time_missing")
add("vk-009-key-resolution-time-empty", "key_resolution_time present as an empty string.", "FAIL", two(key_resolution_time=""), "key_resolution_time_missing")
add("vk-010-certification-time-absent", "Otherwise complete records, but the vector declares no certification time.", "FAIL", two(), "fixture_certification_time_missing", cert=...)
add("vk-011-key-source-unknown", "key_source 'telepathy' is not one of the four values.", "FAIL", two(key_source="telepathy"), "key_source_unknown")
add("vk-012-embedded-evidence-hash-only", "key_source embedded, no public_key_hash, only an evidence hash: the evidence hash does not stand in for the public key hash.", "FAIL", two(public_key_hash=None), "missing_key_material")
add("vk-013-hash-not-hex", "public_key_hash is present but is not 64 lowercase hex.", "FAIL", two(public_key_hash="x"), "hash_format_invalid")
add("vk-014-out-of-scope", "verification_result out_of_scope does not satisfy admission independence.", "FAIL", two(verification_result="out_of_scope"), "multisig_overclaim_or_unverifiable")
add("vk-015-verification-result-unknown", "verification_result 'ok' is not one of the four values.", "FAIL", two(verification_result="ok"), "verification_result_unknown")
add("vk-016-timestamp-garbage", "key_resolution_time is not a timestamp.", "FAIL", two(key_resolution_time="yesterday"), "timestamp_invalid")
add("vk-017-jwks-evidence-hash-only-pass", "published_jwks with no public_key_hash but an evidence hash is valid per the key_source table.", "PASS", two(key_source="published_jwks", public_key_hash=None))

out = {"spec_version": "verifier-key-source-ref-v1.2",
       "description": "Additive vectors for verifier-key-source-ref v1.2: positive cases and the rules in 'Rules a verifier must apply'. Each vector changes one field of a record that passes. A vector may carry role_registry as a test input (a real verifier receives it from outside the fixture).",
       "canonical_envelope_ref": ENV,
       "vectors": V,
       "provenance": "Built by build_v12.py. Expected results are hand-written from docs/spec/verifier-key-source-ref-v1.md, not computed by the verifier."}
(HERE / "vectors-v1.2.json").write_text(json.dumps(out, indent=2) + "\n")
print(f"wrote {len(V)} vectors")
