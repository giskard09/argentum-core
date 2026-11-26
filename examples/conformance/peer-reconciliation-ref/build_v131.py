"""Build vectors-v1.3.1.json for peer-reconciliation-ref (docs/spec/peer-reconciliation-ref-v1.md,
v1.3.1). Additive: vectors.json keeps its 26 vectors, bytes and verdicts. Each new vector is a
copy of an existing passing envelope with ONE thing changed. Expected results (`checks`,
`comparator_state`) are written here by hand from the spec, not computed by verify.py; only
`peer_reconciliation_ref` is computed (SHA-256 of the JCS of the envelope, spec "Derivation").

    python3 build_v131.py    # rewrites vectors-v1.3.1.json deterministically
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent.parent))
from jcs import jcs_bytes  # noqa: E402

base = {v["id"]: v for v in json.loads((HERE / "vectors.json").read_text())["vectors"]}
AGREED = base["agreed-001"]
CORR = base["correction-supersedes-001"]


def ref(env):
    return hashlib.sha256(jcs_bytes(env)).hexdigest()


def vec(vid, src, description, mode, detail, mutate, checks, comparator, known=None):
    env = copy.deepcopy(src["envelope"])
    mutate(env)
    v = {
        "id": vid,
        "description": description,
        "expected": "FAIL",
        "failure_mode": mode,
        "failure_detail": detail,
        "envelope": env,
        "peer_reconciliation_ref": ref(env),
    }
    if known is not None:
        v["known_envelopes"] = known
    v["checks"] = checks
    v["comparator_state"] = comparator
    return v


def checks(structural=True, sig_a=True, sig_b=True, binding=True, distinct=True, chain=None):
    c = {"canonical_envelope": True, "structural_validity": structural,
         "signature_valid_a": sig_a, "signature_valid_b": sig_b}
    if chain is not None:
        c["supersedes_chain_integrity"] = chain
    c["signature_binding"] = binding
    c["party_distinctness"] = distinct
    return c


def known(src, **over):
    k = copy.deepcopy(src["known_envelopes"])
    for key in k:
        for f, val in over.items():
            if val is ...:
                k[key].pop(f, None)
            else:
                k[key][f] = val
    return k


V = []

V.append(vec("party-id-empty-001", AGREED,
    "v1.3.1 negative. party_a.party_id is the empty string. party_id must be a non-empty string of printable ASCII (section 7), so the block is structurally invalid. The pair is UNRESOLVED.",
    "structural_validity", "party_a.party_id is the empty string",
    lambda e: e["party_a"].update(party_id=""),
    checks(structural=False), "UNRESOLVED"))

V.append(vec("observed-string-true-001", AGREED,
    "v1.3.1 negative. party_a.observed is the string \"true\", not the JSON boolean true. observed must be a JSON boolean, so the block is structurally invalid and cannot count as an observation. The pair is UNRESOLVED.",
    "structural_validity", "party_a.observed is the string \"true\"",
    lambda e: e["party_a"].update(observed="true"),
    checks(structural=False), "UNRESOLVED"))

V.append(vec("observed-integer-one-001", AGREED,
    "v1.3.1 negative. party_a.observed is the number 1, not the JSON boolean true. Same rule as observed-string-true-001: only a JSON boolean is an observed value. The pair is UNRESOLVED.",
    "structural_validity", "party_a.observed is the number 1",
    lambda e: e["party_a"].update(observed=1),
    checks(structural=False), "UNRESOLVED"))

def unobserved_with_ref(e):
    e["party_b"].update(observed=False, co_signer=None)
V.append(vec("unobserved-with-action-ref-001", AGREED,
    "v1.3.1 negative. party_b says observed=false but still carries an action_ref (its co_signer is null). observed=false requires both action_ref and co_signer to be null (section 2): a value with no signature behind it is malformed by construction. The pair is UNRESOLVED.",
    "structural_validity", "party_b.observed=false with a non-null action_ref",
    unobserved_with_ref, checks(structural=False, sig_b=False), "UNRESOLVED"))

def unobserved_with_cosigner(e):
    e["party_b"].update(observed=False, action_ref=None)
    e["party_b"]["co_signer"]["pubkey"] = e["party_a"]["co_signer"]["pubkey"]
V.append(vec("unobserved-with-cosigner-001", AGREED,
    "v1.3.1 negative. party_b says observed=false and has no action_ref, but carries a co_signer, and that co_signer's pubkey is party_a's. observed=false requires co_signer to be null, so the block is structurally invalid. party_distinctness still holds: it compares keys only when both parties are observed=true, and here only party_a is. The pair is UNRESOLVED.",
    "structural_validity", "party_b.observed=false with a non-null co_signer",
    unobserved_with_cosigner, checks(structural=False, sig_b=False), "UNRESOLVED"))

V.append(vec("cosigner-missing-kid-001", AGREED,
    "v1.3.1 negative. party_a is observed=true and its co_signer has no kid. A complete co_signer needs issuer, kid, pubkey, jws_signature and signed_fields (section 2); one missing is enough. The pair is UNRESOLVED.",
    "structural_validity", "party_a.co_signer has no kid",
    lambda e: e["party_a"]["co_signer"].pop("kid"),
    checks(structural=False), "UNRESOLVED"))

def both_invalid(e):
    e["party_a"]["co_signer"]["pubkey"] = "not-a-key"
    e["party_b"]["co_signer"]["pubkey"] = "not-a-key"
V.append(vec("pubkey-both-invalid-001", AGREED,
    "v1.3.1 negative. Both co_signers present the same pubkey value, and it is not a base64 SPKI Ed25519 key. A pubkey that is not such a key makes its block structurally invalid (section 7); it is not 'a key', so there is no key to compare and party_distinctness is not what fails. The pair is UNRESOLVED.",
    "structural_validity", "both co_signer.pubkey values are the same invalid string",
    both_invalid, checks(structural=False, distinct=True), "UNRESOLVED"))

V.append(vec("signature-invalid-a-001", AGREED,
    "v1.3.1 negative. Everything is valid and the two action_refs match, but party_a's declared signature_valid_a is false. One invalid signature is enough: the pair is UNRESOLVED, never AGREED. signature_validity fails.",
    "signature_validity", "checks.signature_valid_a is false for an observed=true party",
    lambda e: None, checks(sig_a=False), "UNRESOLVED"))

V.append(vec("signature-invalid-b-001", AGREED,
    "v1.3.1 negative. Same as signature-invalid-a-001 on the other side: party_b observed=true, declared signature_valid_b false, everything else valid. The pair is UNRESOLVED. signature_validity fails.",
    "signature_validity", "checks.signature_valid_b is false for an observed=true party",
    lambda e: None, checks(sig_b=False), "UNRESOLVED"))

OTHER_INTERACTION = "9b8a7c6d-5e4f-4a3b-9c2d-1e0f9a8b7c6d"
V.append(vec("supersedes-interaction-id-mismatch-001", CORR,
    "v1.3.1 negative. A correction whose supersedes pointer resolves to a known envelope with a different interaction_id. A correction must correct the same interaction (section 6). Everything else matches correction-supersedes-001 and the comparator state is AGREED; only supersedes_chain_integrity fails.",
    "supersedes_chain_integrity", "known_envelopes entry has a different interaction_id",
    lambda e: None, checks(chain=False), "AGREED",
    known=known(CORR, interaction_id=OTHER_INTERACTION)))

V.append(vec("supersedes-no-resolved-by-001", CORR,
    "v1.3.1 negative. A correction whose known_envelopes entry declares no resolved_by. Each entry must name the source that supplied it (section 6); without it nothing shows the record did not come from the party that points at it. Everything else matches correction-supersedes-001; only supersedes_chain_integrity fails.",
    "supersedes_chain_integrity", "known_envelopes entry has no resolved_by",
    lambda e: None, checks(chain=False), "AGREED",
    known=known(CORR, resolved_by=...)))

out = {
    "spec_version": "peer-reconciliation-ref-v1.3.1",
    "description": "Additive negative vectors for peer-reconciliation-ref v1.3.1. Each is an existing passing envelope with one thing changed, and each exercises a rule the spec already states that no vector in vectors.json covered. A vector counts as passed only if the verifier rejects it under its failure_mode and does not merely disagree with its declared checks (spec, 'Conformance: what a negative vector must show').",
    "vectors": V,
    "provenance": {
        "authored_by": "giskard09 (argentum-core)",
        "verification_mode": "asserted",
        "independently_reproduced_by": [],
    },
}

if __name__ == "__main__":
    (HERE / "vectors-v1.3.1.json").write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n")
    print(f"{len(V)} vectors -> vectors-v1.3.1.json")
