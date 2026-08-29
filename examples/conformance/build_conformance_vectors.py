"""
Wraps conformance-export.json (built by build_export.py) with the discovery
convention that decanted in A2A#1628: a `contract` block (canonicalization,
hash algorithm, digest derivation, signature schemes actually in use) and a
`recomputation_procedure` block (inputs, harness, steps, expected output
shape, and an explicit `boundary` — what recomputing these vectors proves
and what it does not).

Source of the convention: Douglas Borthwick, A2A#1628 comment 5462309880
(insumermodel.com/.well-known/state-attestation-test-vectors.json) — path
discoverable from the API origin, negatives in the same file as positives,
verdicts not collapsed into one boolean where more than one dimension is
real. Independently, Kenneives/CTEF (agentgraph.co/.well-known/
cte-test-vectors.json, A2A#1628) converges on the same "one discoverable
.well-known file, contract+boundary documented in-band" shape. Two
independent actors landing on the same shape is the signal DEUDA_INTERNA
(checkpoint 2026-08-31) was waiting on.

This script does not rename or alter any set's `files` payload — those stay
byte-identical to conformance-export.json. It only adds two new top-level
blocks and renames export_version. Contract fields document conventions
that already exist in this repo (jcs.py, action_ref.py, docs/spec/*.md) —
nothing here is a new derivation or a new signature scheme.

Usage: python3 build_conformance_vectors.py [--out conformance-vectors.json]
"""

import argparse
import json
from pathlib import Path

HERE = Path(__file__).parent

CONTRACT = {
    "canonicalization": {
        "rule": "RFC 8785 (JCS)",
        "implementation": "jcs.py (this repo) — jcs_dumps/jcs_bytes",
        "notes": (
            "Object keys sorted by UTF-16 code unit order (not Python's default "
            "Unicode code point order — the two diverge only for astral-plane "
            "keys, e.g. emoji). Non-ASCII serializes as literal UTF-8, never "
            "\\uXXXX. Numbers follow ECMA-262 Number::toString (ECMA-262 "
            "7.1.12.1), not Python's float repr."
        ),
    },
    "hash_algorithm": "SHA-256",
    "digest_derivation": {
        "action_ref_v1": {
            "formula": "SHA-256(JCS(preimage))",
            "preimage_fields": ["agent_id", "action_type", "scope", "timestamp"],
            "spec": "docs/spec/action-ref.md §3.1",
        },
        "action_ref_v2": {
            "formula": "SHA-256(V2_DOMAIN_TAG || JCS(preimage))",
            "notes": "Domain-separated variant of v1 — same four preimage fields, tag prepended before hashing so v1 and v2 digests can never collide.",
            "spec": "plugins/agt_evidence_anchor/action_ref.py (V2_DOMAIN_TAG)",
        },
        "signing_trust_ref": {
            "formula": "SHA-256(JCS(preimage))",
            "preimage_fields": ["signer_type", "signer_id", "action_ref", "timestamp_ms"],
            "spec": "docs/spec/signing-trust-ref.md",
        },
        "other_sets": (
            "Every other set (negotiation_ref, counterparty_ref, "
            "delegation_chain_ref, verdict_ref, etc.) follows the same "
            "SHA-256(JCS(preimage)) pattern with a spec-specific preimage. "
            "Each set documents its own exact preimage and reproduction "
            "snippet in its `purpose` / `reproduce_in_python` / "
            "`classify_reference` field — read that field before recomputing, "
            "do not assume the action_ref_v1 preimage shape applies globally."
        ),
    },
    "signature_schemes_in_use": {
        "EdDSA_Ed25519": {
            "where": [
                "agenttrust-v1 (JWS envelopes, verification.v0.3+composed)",
                "karma badges (/karma/{agent_id}, argentum.py _sign_badge)",
            ],
            "key_selection": (
                "agenttrust-v1 uses a JWS `kid` (e.g. \"agenttrust-ed25519-v1\") "
                "to select the verification key from its own JWKS file "
                "(agenttrust-v1/jwks-agenttrust.json / jwks_url). This is the "
                "only set in this export that uses kid-based key selection — "
                "most sets are plain digest fixtures, not signed envelopes, so "
                "there is no key-selection step to document for them."
            ),
        },
        "BIP_340_Schnorr_secp256k1": {
            "where": ["composed-attestation-bip340-cell"],
        },
        "unsigned": (
            "The majority of sets (action_ref v1/v2 fixtures, trail lifecycle "
            "fixtures, verdict_ref, etc.) are plain digest vectors with no "
            "signature layer — signing in this ecosystem is opt-in per "
            "docs/spec/*.md, not mandatory, and this export does not force a "
            "signature convention onto sets that were never signed."
        ),
    },
    "negatives_in_band": (
        "Every MUST-FAIL / negative case lives in this same published file, "
        "next to its positive counterpart — there is no separate "
        "negatives-only file or route to fetch. The shape is per-spec, not "
        "per-array: some specs put positive and negative vectors in one "
        "array (e.g. verify-failure-mode-ref-v1, near-miss-v1); others keep "
        "the negative case as its own named, independently-versioned set "
        "beside the positive one (e.g. action-ref-v1-baseline next to "
        "action-ref-v1-domain-negative; committed / failed / pending-null / "
        "pending-non-null as four sibling fixtures). Both shapes satisfy the "
        "same principle Douglas's convention states — a verifier never has "
        "to leave this file to find the failure cases — applied at the "
        "level each spec was already versioned at, rather than merging "
        "arrays across differently-versioned specs."
    ),
    "multi_dimension_verdicts": (
        "None of the 61 sets in this export today collapse two real, "
        "independent verdict dimensions into one boolean the way "
        "Douglas's fixture separates signature/condition-hash/freshness/"
        "expiry. Where a set has more than one failure mode "
        "(verify-failure-mode-ref-v1: verify_unreachable / verify_stale / "
        "verify_invalid / verify_ok), it already reports a single "
        "mechanism-neutral reason code rather than a boolean — that "
        "principle is applied here as-is, not forced onto sets where the "
        "distinction isn't real (e.g. a plain action_ref digest fixture has "
        "exactly one thing to verify: does the digest match)."
    ),
}

RECOMPUTATION_PROCEDURE = {
    "inputs": [
        "This file's own `sets.<id>.files` map — byte-identical to the source "
        "vectors.json / fixture.json under examples/conformance/<id>/ in "
        "giskard09/argentum-core.",
    ],
    "harness": "examples/conformance/build_export.py (aggregation only — does not compute or verify any digest itself)",
    "steps": [
        "Pick a set under `sets`.",
        "Read that set's own `purpose` / `reproduce_in_python` / "
        "`classify_reference` field (present in every set) — it states the "
        "exact preimage fields and derivation function for that spec. Do not "
        "assume another set's preimage shape applies.",
        "Recompute the digest, signature check, or classification using the "
        "canonicalization and hash algorithm in `contract` above.",
        "Compare the result to the set's own `expected_action_ref` / "
        "`expected_reason` / `conformant` / equivalent field.",
    ],
    "expected_output_form": (
        "Exact match — hex digest equality, exact reason-code string equality, "
        "or exact boolean equality, per the field each vector defines. No "
        "partial, fuzzy, or prefix match is a pass."
    ),
    "boundary": (
        "This establishes exactly one thing: that a fixture's stated "
        "preimage, canonicalized and hashed/signed per the algorithm in "
        "`contract`, reproduces the exact digest, signature, or verdict "
        "this repo publishes — byte-for-byte, with no partial or fuzzy "
        "match accepted. That is the full extent of what a passing "
        "recomputation certifies. It does NOT certify that any third "
        "party's production system enforces the corresponding policy in "
        "practice — a byte-match here says nothing about whether a real "
        "deployment actually gates the action it claims to gate. It does "
        "NOT certify that a signed envelope's named signer controls the "
        "private key beyond what the signature verification itself proves. "
        "And it does NOT re-run or substitute for a chain read: any "
        "on-chain anchor cited inside a set (tx_hash / block / "
        "anchor_proof) must be independently confirmed by querying the "
        "cited network directly — recomputing this file's digests "
        "confirms none of that. Anything outside a given fixture's own "
        "`vectors` array — endpoints, rate limits, business logic not "
        "represented in the fixture — is outside this procedure's scope "
        "entirely."
    ),
}


def build(export: dict) -> dict:
    out = dict(export)
    out["export_version"] = "conformance-vectors-v1"
    out["public_path"] = "/.well-known/conformance-vectors.json"
    out["contract"] = CONTRACT
    out["recomputation_procedure"] = RECOMPUTATION_PROCEDURE
    out.pop("note", None)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="conformance-export.json")
    ap.add_argument("--out", default="conformance-vectors.json")
    args = ap.parse_args()

    export = json.loads((HERE / args.inp).read_text())
    wrapped = build(export)
    out_path = HERE / args.out
    out_path.write_text(json.dumps(wrapped, indent=2, ensure_ascii=False, sort_keys=False) + "\n")
    print(f"{wrapped['set_count']} sets + contract + recomputation_procedure -> {out_path}")


if __name__ == "__main__":
    main()
