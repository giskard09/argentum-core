"""
Verifier for peer-reconciliation-ref-v1 conformance vectors.

Seven invariants checked per spec (docs/spec/peer-reconciliation-ref-v1.md):
  1. canonical_envelope        — SHA-256(JCS(envelope)) matches declared peer_reconciliation_ref
  2. structural_validity       — observed=true implies non-null action_ref + complete co_signer
                                  (issuer/kid/pubkey/jws_signature/signed_fields all present,
                                  signed_fields a non-empty list — shape only, not content;
                                  v1.3: pubkey must be a strict base64 SPKI Ed25519 key, and every
                                  block needs a valid party_id: printable ASCII, no space);
                                  observed=false implies action_ref and co_signer are both null
  3. signature_validity        — checks.signature_valid_a / checks.signature_valid_b declared in
                                  vector (external resolution; verifier trusts vector declaration,
                                  same pattern as chain_invariant in anchoring-precedence-ref-v1 —
                                  this is a stdlib-only profile, no live Ed25519/JWS verification)
  4. signature_binding (v1.2)  — unlike signature_validity, this is NOT externally trusted: it is
                                  computed directly from co_signer.signed_fields, which the
                                  verifier can read itself. Fails when an observed=true party's
                                  signed_fields does not cover {party_id, action_ref,
                                  interaction_id}. Closes a replay gap: a cryptographically valid
                                  signature that only covers party identity (not the specific
                                  action_ref it is presented alongside) can be paired with a
                                  different action_ref without re-signing anything. See
                                  REQUIRED_SIGNED_FIELDS below and the "v1.2" section of the spec.
  5. comparator_state          — AGREED / DISAGREED / UNRESOLVED, computed from
                                  structural_validity + signature_validity + signature_binding
                                  plus the two action_ref values. UNRESOLVED must never be
                                  collapsed into AGREED or DISAGREED.
  6. supersedes_chain_integrity (v1.1) — present only when the envelope carries a `supersedes`
                                  field. The referenced peer_reconciliation_ref must resolve to a
                                  known prior envelope with the same interaction_id (declared via
                                  vector["known_envelopes"], external resolution not performed
                                  live — same treatment chain_invariant gets in
                                  anchoring-precedence-ref-v1). Each known_envelopes entry must
                                  also declare `resolved_by`, naming the source that supplied it,
                                  and that source must NOT be either party_id of the current
                                  envelope — otherwise the same party that emits `supersedes`
                                  could also fabricate the "prior" envelope it claims to correct,
                                  making the check structurally unable to fail. Absent
                                  `supersedes` = exempt.
  7. party_distinctness (v1.3) — computed from the envelope, like signature_binding: party_a and
                                  party_b MUST carry different party_id values (ASCII case folded),
                                  and when both are observed=true their co_signer pubkeys MUST be
                                  different keys, compared as the 32 decoded bytes, not as text. Closes
                                  the cheapest form of "the same operator on both sides" (same id
                                  twice, or one key behind two ids). It does NOT detect one
                                  operator holding two distinct keys under two distinct ids; that
                                  stays a declared limit in the spec. NOT additive: it changes
                                  which envelopes can be AGREED. No existing fixture changes
                                  result and no declared hash changes.

v1.1 additive fields (docs/spec/peer-reconciliation-ref-v1.md, "v1.1" sections):
  - envelope.supersedes            (optional) — correction pointer, never a rewrite
  - observation.requested_at       (optional, recommended when observed=false)
  - observation.as_of              (optional, informational, not used by the comparator)
None of the three affect canonical_envelope/structural_validity/signature_validity/
comparator_state for an envelope that omits them — the five v1.0 fixtures remain valid
v1.1 vectors unmodified.

v1.2 (docs/spec/peer-reconciliation-ref-v1.md, "v1.2" section) — NOT additive the way v1.1's
fields were: `co_signer.signed_fields` is now a REQUIRED part of a structurally complete
co_signer (checked in #2), and REQUIRED_SIGNED_FIELDS below is a MUST on its content (checked
independently in #4). This is a deliberate, declared break from "an envelope that omits a new
field evaluates exactly as before" — the whole point is that a co_signer which does not bind
action_ref was always insecure against the replay this version closes, so grandfathering the old
shape as still-valid would defeat the fix. All v1.0/v1.1 fixtures in this file were updated in
place to declare signed_fields (this changed their declared peer_reconciliation_ref, since the
field is inside the hashed envelope) — see the "v1.2" section of the spec for the full rationale
and the GenAI-Security-Project/agent-control-standard#33 finding that prompted this self-audit.
"""

REQUIRED_SIGNED_FIELDS = {"party_id", "action_ref", "interaction_id"}

import base64
import binascii
import hashlib
import json
import re
import sys
from pathlib import Path

# RFC 8785 JCS from the repo's jcs.py, not json.dumps(sort_keys=True): the spec says "not
# json.dumps(sort_keys=True)" (that sorts by code point, JCS by UTF-16 code unit). Same
# import pattern as farley-receipt-signature/verify.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from jcs import jcs_bytes  # noqa: E402


def jcs(obj: dict) -> str:
    return jcs_bytes(obj).decode("utf-8")


def sha256hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# v1.3. A co_signer.pubkey is a base64 SPKI Ed25519 key: 12-byte prefix + 32 key bytes = 44 bytes.
SPKI_ED25519_PREFIX = base64.b64decode("MCowBQYDK2VwAyEA")
PARTY_ID_RE = re.compile(r"[\x21-\x7e]+")  # non-empty, printable ASCII, no space or control


def party_id_valid(party_id) -> bool:
    return isinstance(party_id, str) and PARTY_ID_RE.fullmatch(party_id) is not None


def pubkey_bytes(pubkey):
    """The 32 raw Ed25519 key bytes of a base64 SPKI pubkey, or None if it is not one.

    Strict base64 (validate=True: no whitespace, no characters outside the alphabet, padding
    required), exactly 44 decoded bytes, SPKI Ed25519 prefix. The canonical re-encoding is NOT
    required: eight fixture keys carry non-zero trailing bits, and the same key written with
    different trailing bits decodes to the same 32 bytes, which is what distinctness compares.
    """
    if not isinstance(pubkey, str):
        return None
    try:
        raw = base64.b64decode(pubkey, validate=True)
    except (binascii.Error, ValueError):
        return None
    if len(raw) != 44 or raw[:12] != SPKI_ED25519_PREFIX:
        return None
    return raw[12:]


def check_structural_validity(party: dict) -> bool:
    observed = party.get("observed")
    action_ref = party.get("action_ref")
    co_signer = party.get("co_signer")

    if not party_id_valid(party.get("party_id")):
        return False

    if observed is True:
        if action_ref is None:
            return False
        if not isinstance(co_signer, dict):
            return False
        required = ("issuer", "kid", "pubkey", "jws_signature")
        if not all(co_signer.get(k) for k in required):
            return False
        if pubkey_bytes(co_signer.get("pubkey")) is None:
            return False
        signed_fields = co_signer.get("signed_fields")
        if not isinstance(signed_fields, list) or not signed_fields:
            return False
        return True

    if observed is False:
        return action_ref is None and co_signer is None

    return False


def check_signature_binding(party: dict) -> bool:
    """v1.2. Computed directly from signed_fields -- not externally trusted the way
    signature_valid_* is. Exempt (True) when observed is not True, since there is no
    co_signer to check. Requires structural_validity to have already confirmed
    signed_fields is a non-empty list; here we only check its *content*."""
    if party.get("observed") is not True:
        return True
    co_signer = party.get("co_signer")
    if not isinstance(co_signer, dict):
        return False
    signed_fields = co_signer.get("signed_fields")
    if not isinstance(signed_fields, list):
        return False
    return REQUIRED_SIGNED_FIELDS.issubset(set(signed_fields))


def check_supersedes_chain_integrity(vector: dict) -> tuple[bool, str]:
    """v1.1. Returns (ok, detail). Exempt (ok=True) when `supersedes` is absent."""
    envelope = vector["envelope"]
    supersedes = envelope.get("supersedes")
    if supersedes is None:
        return True, "exempt (no supersedes field)"

    known = vector.get("known_envelopes", {})
    prior = known.get(supersedes)
    if prior is None:
        return False, f"supersedes {supersedes[:16]}… does not resolve to a known prior envelope"

    if prior.get("interaction_id") != envelope.get("interaction_id"):
        return False, (
            f"supersedes resolves to interaction_id {prior.get('interaction_id')!r} "
            f"but this envelope's interaction_id is {envelope.get('interaction_id')!r}"
        )

    resolved_by = prior.get("resolved_by")
    # v1.3: same identifier rule and same case-insensitive comparison as party_distinctness, so a
    # party cannot attest its own correction by writing its id differently ("SAFEAGENT-GUARDIAN",
    # "safeagent-guardian ").
    current_parties = {
        pid.lower()
        for pid in (envelope["party_a"].get("party_id"), envelope["party_b"].get("party_id"))
        if party_id_valid(pid)
    }
    if not resolved_by:
        return False, "known_envelopes entry has no resolved_by — provenance not declared"
    if not party_id_valid(resolved_by):
        return False, (
            f"known_envelopes entry resolved_by={resolved_by!r} is not a valid identifier "
            f"(non-empty printable ASCII, no space or control character)"
        )
    if resolved_by.lower() in current_parties:
        return False, (
            f"known_envelopes entry resolved_by={resolved_by!r} is one of this envelope's own "
            f"parties — a party cannot independently resolve the prior envelope it also emits "
            f"the supersedes pointer for"
        )

    return True, "resolves to known prior envelope, same interaction_id, independent resolved_by"


def check_party_distinctness(envelope: dict) -> bool:
    """v1.3. party_a and party_b must carry different party_id values (compared without regard
    to ASCII case); when both are observed=true their co_signer pubkeys must be different KEYS,
    compared as the 32 decoded key bytes, never as text. Computed from the envelope. A value that
    is not a valid party_id or pubkey is a structural_validity failure, reported there."""
    a, b = envelope["party_a"], envelope["party_b"]
    ia, ib = a.get("party_id"), b.get("party_id")
    if party_id_valid(ia) and party_id_valid(ib) and ia.lower() == ib.lower():
        return False
    if a.get("observed") is True and b.get("observed") is True:
        ka = pubkey_bytes((a.get("co_signer") or {}).get("pubkey"))
        kb = pubkey_bytes((b.get("co_signer") or {}).get("pubkey"))
        if ka is not None and ka == kb:
            return False
    return True


def compute_comparator_state(
    vector: dict, struct_a: bool, struct_b: bool, bind_a: bool, bind_b: bool,
    distinct: bool,
) -> str:
    party_a = vector["envelope"]["party_a"]
    party_b = vector["envelope"]["party_b"]
    checks = vector.get("checks", {})

    sig_a_ok = checks.get("signature_valid_a", False)
    sig_b_ok = checks.get("signature_valid_b", False)

    a_ready = struct_a and party_a.get("observed") is True and sig_a_ok and bind_a
    b_ready = struct_b and party_b.get("observed") is True and sig_b_ok and bind_b

    if not (a_ready and b_ready and distinct):
        return "UNRESOLVED"

    if party_a["action_ref"] == party_b["action_ref"]:
        return "AGREED"
    return "DISAGREED"


def verify_vector(vector: dict) -> tuple[bool, list[str]]:
    failures = []
    envelope = vector["envelope"]

    # 1. canonical_envelope
    computed_ref = sha256hex(jcs(envelope))
    declared_ref = vector.get("peer_reconciliation_ref", "")
    if computed_ref != declared_ref:
        failures.append(
            f"canonical_envelope: computed {computed_ref} != declared {declared_ref}"
        )

    # 2. structural_validity
    struct_a = check_structural_validity(envelope["party_a"])
    struct_b = check_structural_validity(envelope["party_b"])
    declared_struct = vector.get("checks", {}).get("structural_validity", True)
    struct_ok = struct_a and struct_b
    if struct_ok != declared_struct:
        failures.append(
            f"structural_validity: computed {struct_ok} != declared {declared_struct}"
        )
    if not struct_ok:
        failures.append(
            "structural_validity: party_a valid={} party_b valid={}".format(struct_a, struct_b)
        )

    # 3. signature_validity
    checks = vector.get("checks", {})
    for label, party_key in (("a", "party_a"), ("b", "party_b")):
        party = envelope[party_key]
        if party.get("observed") is True and not checks.get(f"signature_valid_{label}", False):
            failures.append(f"signature_validity: signature_valid_{label} declared false")

    # 4. signature_binding (v1.2) -- computed, not externally trusted
    bind_a = check_signature_binding(envelope["party_a"])
    bind_b = check_signature_binding(envelope["party_b"])
    declared_binding = checks.get("signature_binding", True)
    binding_ok = bind_a and bind_b
    if binding_ok != declared_binding:
        failures.append(
            f"signature_binding: computed {binding_ok} != declared {declared_binding}"
        )
    for label, bind_ok, party_key in (("a", bind_a, "party_a"), ("b", bind_b, "party_b")):
        party = envelope[party_key]
        if party.get("observed") is True and not bind_ok:
            signed_fields = (party.get("co_signer") or {}).get("signed_fields")
            failures.append(
                f"signature_binding: party_{label} signed_fields={signed_fields!r} "
                f"does not cover {sorted(REQUIRED_SIGNED_FIELDS)}"
            )

    # 5. party_distinctness (v1.3) -- computed from the envelope
    distinct = check_party_distinctness(envelope)
    # The computed result always decides. The declared value is only a cross-check, and the 11
    # pre-v1.3 vectors do not declare it (their bytes are cited by others and stay untouched):
    # absent means "pre-v1.3 vector, nothing declared", never "declared true".
    declared_distinct = checks.get("party_distinctness")
    if declared_distinct is not None and distinct != declared_distinct:
        failures.append(
            f"party_distinctness: computed {distinct} != declared {declared_distinct}"
        )
    if not distinct:
        failures.append(
            "party_distinctness: party_a and party_b share a party_id, or both are observed "
            "with the same co_signer.pubkey"
        )

    # 6. comparator_state
    computed_state = compute_comparator_state(vector, struct_a, struct_b, bind_a, bind_b, distinct)
    declared_state = vector.get("comparator_state", "")
    if computed_state != declared_state:
        failures.append(
            f"comparator_state: computed {computed_state} != declared {declared_state}"
        )

    # 6. supersedes_chain_integrity (v1.1, exempt when supersedes is absent)
    chain_ok, chain_detail = check_supersedes_chain_integrity(vector)
    if not chain_ok:
        failures.append(f"supersedes_chain_integrity: {chain_detail}")

    return len(failures) == 0, failures


def main():
    vectors_path = Path(__file__).parent / "vectors.json"
    data = json.loads(vectors_path.read_text())
    vectors = data["vectors"]

    print(f"peer-reconciliation-ref-v1 conformance — {len(vectors)} vectors\n")

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
