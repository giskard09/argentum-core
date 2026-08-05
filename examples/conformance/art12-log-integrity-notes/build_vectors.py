#!/usr/bin/env python3
"""Generator for the art12-log-integrity-notes vectors.

Every digest in vectors.json is computed here, never written by hand.
Run: python3 build_vectors.py   (rewrites vectors.json in place)

Scope note: these vectors exercise the ASSURANCE PATH described in
docs/compliance/regulatory-compliance.md Note (1) -- whether a party that did
not produce a log record can determine that it was not rewritten. They are not
"EU AI Act Article 12 conformance vectors"; Article 12 prescribes no technical
mechanism, so no such thing exists. See README.md.
"""
import hashlib
import json
from pathlib import Path

PROFILE = "jcs-rfc8785-v1"


def jcs(obj: dict) -> str:
    """JCS (RFC 8785) for the flat, ASCII, scalar-valued shapes this fixture uses.

    Same domain restriction as docs/spec/action-ref.md: ASCII field values,
    RFC 3339 timestamps in YYYY-MM-DDTHH:MM:SS.mmmZ form, no surrogate pairs,
    no -0.0. Outside that domain the verifier must stop with
    OUT_OF_PROFILE_DOMAIN before any digest comparison.
    """
    return json.dumps(dict(sorted(obj.items())), separators=(",", ":"), ensure_ascii=False)


def digest(obj: dict) -> str:
    return "sha256:" + hashlib.sha256(jcs(obj).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# A synthetic high-risk-AI log record.
#
# Field shape is modelled on Art. 12(3)(a)-(d), which are the only enumerated
# minimum log contents in the Article -- and which apply ONLY to Annex III
# point 1(a) systems (remote biometric identification). We use that shape
# precisely because it is the one place the Regulation is concrete. It is an
# illustration of the verification path, not a claim that these fields are
# required of all high-risk systems.
# ---------------------------------------------------------------------------
BASE_RECORD = {
    # Art. 12(3)(a) -- period of each use
    "use_start": "2026-08-03T09:14:22.480Z",
    "use_end": "2026-08-03T09:14:23.115Z",
    # Art. 12(3)(b) -- reference database checked against
    "reference_database": "synthetic-watchlist-v7",
    # Art. 12(3)(c) -- input data for which the search led to a match
    "matched_input_ref": "sha256:0f3a1c77c4a1b5f7e2d9a04b8c6e1f35d27b90aa4e6c8137fb52d0e9a7c41b68",
    # Art. 12(3)(d) -- natural person involved in verification (Art. 14(5))
    "human_verifier_ref": "did:example:verifier-4471",
    # Art. 12(2)(a) -- relevance for risk identification under Art. 79(1)
    "risk_event_class": "match_confirmed_by_human",
    # correlation to the action itself
    "action_ref": "sha256:9752a870dac7100010453be9494ec631c78fd55bb7cb41355cf03592da3862ce",
}

# The record as it is presented to a reader AFTER the anchor was written,
# with use_end moved back to hide that the human verification window was
# shorter than policy requires. One field, 635 ms.
TAMPERED_RECORD = dict(BASE_RECORD, use_end="2026-08-03T09:14:29.900Z")

# Same tampered content, but the operator has re-signed it with a key that
# genuinely validates. The signature is not part of the digest preimage --
# that is the entire point of vector a12-004.
OPERATOR_SIGNATURE_OVER_TAMPERED = "ed25519:synthetic-signature-valid-under-operator-key"

# Out-of-domain: non-ASCII verifier identifier. Must be rejected before any
# digest comparison, not canonicalised on a best-effort basis.
OUT_OF_DOMAIN_RECORD = dict(BASE_RECORD, human_verifier_ref="did:example:verificador-Ñ4471")

base_digest = digest(BASE_RECORD)
tampered_digest = digest(TAMPERED_RECORD)

# What was committed to an external surface at the time of the event. The
# fixture is anchor-agnostic on purpose: no transaction hash is asserted here,
# because none was made for this synthetic record. Live anchoring is shown in
# the worked-example repositories, each of which carries its own real tx.
ANCHORED_DIGEST = base_digest

vectors = [
    {
        "id": "a12-001",
        "name": "third_party_reader_confirms_unmodified_record",
        "description": (
            "A reader who did not produce the record (market surveillance authority under "
            "Art. 79(1), or a post-market monitoring recipient under Art. 72) holds the log "
            "record and the externally anchored digest. It recomputes SHA-256(JCS(record)) "
            "and finds a match. No operator key and no operator infrastructure are used. "
            "Result: PASS."
        ),
        "record": BASE_RECORD,
        "anchored_digest": ANCHORED_DIGEST,
        "expected_result": "PASS",
    },
    {
        "id": "a12-002",
        "name": "human_verifier_bound_in_preimage",
        "description": (
            "Art. 12(3)(d) requires identifying the natural person involved in verification. "
            "Because human_verifier_ref is inside the hashed preimage, substituting the "
            "verifier after the fact changes the digest. This vector asserts only that the "
            "field is bound -- it does NOT assert that the identifier is truthful. Binding "
            "is not identity assurance."
        ),
        "record": BASE_RECORD,
        "anchored_digest": ANCHORED_DIGEST,
        "field_under_test": "human_verifier_ref",
        "expected_result": "PASS",
    },
    {
        "id": "a12-003",
        "name": "record_edited_after_anchor_is_detected",
        "description": (
            "use_end is moved 6.8 s later to make the human verification window appear "
            "compliant. Nothing else changes. The reader recomputes and diverges from the "
            "anchored digest. Result: FAIL."
        ),
        "record": TAMPERED_RECORD,
        "anchored_digest": ANCHORED_DIGEST,
        "expected_result": "FAIL",
        "expected_error_code": "RECORD_MODIFIED_AFTER_ANCHOR",
    },
    {
        "id": "a12-004",
        "name": "valid_operator_signature_does_not_rescue_a_modified_record",
        "description": (
            "The operator re-signs the modified record with a key that validates correctly. "
            "A verifier checking only the signature accepts it. A verifier recomputing "
            "against the external anchor still rejects it. This is the vector that "
            "distinguishes operator-signed receipts from operator-independent evidence: the "
            "signature attests that someone holding the operator key asserted the record, "
            "not that the record is the one that existed at the time of the event."
        ),
        "record": TAMPERED_RECORD,
        "operator_signature": OPERATOR_SIGNATURE_OVER_TAMPERED,
        "operator_signature_validates": True,
        "anchored_digest": ANCHORED_DIGEST,
        "expected_result": "FAIL",
        "expected_error_code": "RECORD_MODIFIED_AFTER_ANCHOR",
    },
    {
        "id": "a12-005",
        "name": "verifier_without_operator_key_or_access_reaches_a_verdict",
        "description": (
            "Same inputs as a12-001, asserted as a capability rather than a value: the "
            "verifier is given only the record and the anchored digest -- no operator public "
            "key, no API credential, no access to operator infrastructure -- and still "
            "reaches a determinate verdict. This is the property Art. 12(2) implies for its "
            "three classes of reader and does not specify how to obtain."
        ),
        "record": BASE_RECORD,
        "anchored_digest": ANCHORED_DIGEST,
        "verifier_inputs": ["record", "anchored_digest"],
        "verifier_inputs_denied": [
            "operator_public_key",
            "operator_api_credential",
            "operator_infrastructure_access",
        ],
        "expected_result": "PASS",
    },
    {
        "id": "a12-006",
        "name": "out_of_profile_domain_is_rejected_before_comparison",
        "description": (
            "human_verifier_ref carries a non-ASCII character, outside the profile domain "
            "declared in docs/spec/action-ref.md. The verifier must stop with "
            "OUT_OF_PROFILE_DOMAIN before any digest comparison -- it must not canonicalise "
            "on a best-effort basis and must not fall back to another implementation's "
            "string handling. One pinned behaviour per profile."
        ),
        "record": OUT_OF_DOMAIN_RECORD,
        "anchored_digest": ANCHORED_DIGEST,
        "expected_result": "FAIL",
        "expected_error_code": "OUT_OF_PROFILE_DOMAIN",
    },
]

doc = {
    "fixture_id": "art12-log-integrity-notes",
    "version": "v1",
    "spec": "docs/compliance/regulatory-compliance.md#1-eu-ai-act-art-12",
    "hash_algo": "sha256",
    "preimage_format": PROFILE,
    "generated_at": "2026-08-05",
    "purpose": (
        "Vectors for the verification path left unspecified by EU AI Act Art. 12: whether a "
        "party that did not produce a log record can determine that the record was not "
        "rewritten before it was read. Art. 12(2) describes three classes of reader who did "
        "not produce the log (Art. 79(1) risk identification, Art. 72 post-market "
        "monitoring, Art. 26(5) deployer monitoring) and prescribes no mechanism by which "
        "any of them gains that confidence. These vectors demonstrate one mechanism. They "
        "are NOT Article 12 conformance vectors -- the Article prescribes no technical "
        "mechanism, so conformance vectors for it cannot exist."
    ),
    "not_a_claim": [
        "Art. 12 does not require tamper-evidence, anchoring, or third-party recomputability.",
        "Passing these vectors does not make a system compliant with Art. 12 or any part of the AI Act.",
        "The Art. 12(3) field shape used here applies only to Annex III point 1(a) systems; it is used as an illustration because it is the only place the Article is concrete.",
        "No transaction hash is asserted: this fixture is anchor-agnostic and its records are synthetic.",
        "Binding a verifier identifier in the preimage proves the field was not substituted, not that the identifier is truthful.",
    ],
    "reproduce_in_python": (
        "import hashlib, json\n"
        "def jcs(obj): return json.dumps(dict(sorted(obj.items())), separators=(',',':'), ensure_ascii=False)\n"
        "record_digest = 'sha256:' + hashlib.sha256(jcs(record).encode()).hexdigest()"
    ),
    "digests": {
        "base_record": base_digest,
        "tampered_record": tampered_digest,
        "anchored_digest": ANCHORED_DIGEST,
    },
    "vectors": vectors,
}

out = Path(__file__).parent / "vectors.json"
out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
print(f"wrote {out}")
print(f"  base_record     {base_digest}")
print(f"  tampered_record {tampered_digest}")
print(f"  divergence      {'yes' if base_digest != tampered_digest else 'NO -- BUG'}")
