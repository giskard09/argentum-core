"""
Verifier for peer-reconciliation-ref-v1 conformance vectors.

Five invariants checked per spec (docs/spec/peer-reconciliation-ref-v1.md):
  1. canonical_envelope        — SHA-256(JCS(envelope)) matches declared peer_reconciliation_ref
  2. structural_validity       — observed=true implies non-null action_ref + complete co_signer;
                                  observed=false implies both are null
  3. signature_validity        — checks.signature_valid_a / checks.signature_valid_b declared in
                                  vector (external resolution; verifier trusts vector declaration,
                                  same pattern as chain_invariant in anchoring-precedence-ref-v1 —
                                  this is a stdlib-only profile, no live Ed25519/JWS verification)
  4. comparator_state          — AGREED / DISAGREED / UNRESOLVED, computed from the three checks
                                  above plus the two action_ref values. UNRESOLVED must never be
                                  collapsed into AGREED or DISAGREED.
  5. supersedes_chain_integrity (v1.1) — present only when the envelope carries a `supersedes`
                                  field. The referenced peer_reconciliation_ref must resolve to a
                                  known prior envelope with the same interaction_id (declared via
                                  vector["known_envelopes"], external resolution not performed
                                  live — same treatment chain_invariant gets in
                                  anchoring-precedence-ref-v1). Absent `supersedes` = exempt.

v1.1 additive fields (docs/spec/peer-reconciliation-ref-v1.md, "v1.1" sections):
  - envelope.supersedes            (optional) — correction pointer, never a rewrite
  - observation.requested_at       (optional, recommended when observed=false)
  - observation.as_of              (optional, informational, not used by the comparator)
None of the three affect canonical_envelope/structural_validity/signature_validity/
comparator_state for an envelope that omits them — the five v1.0 fixtures remain valid
v1.1 vectors unmodified.
"""

import hashlib
import json
import sys
from pathlib import Path


def jcs(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def sha256hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def check_structural_validity(party: dict) -> bool:
    observed = party.get("observed")
    action_ref = party.get("action_ref")
    co_signer = party.get("co_signer")

    if observed is True:
        if action_ref is None:
            return False
        if not isinstance(co_signer, dict):
            return False
        required = ("issuer", "kid", "pubkey", "jws_signature")
        if not all(co_signer.get(k) for k in required):
            return False
        return True

    if observed is False:
        return action_ref is None and co_signer is None

    return False


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

    return True, f"resolves to known prior envelope, same interaction_id"


def compute_comparator_state(vector: dict, struct_a: bool, struct_b: bool) -> str:
    party_a = vector["envelope"]["party_a"]
    party_b = vector["envelope"]["party_b"]
    checks = vector.get("checks", {})

    sig_a_ok = checks.get("signature_valid_a", False)
    sig_b_ok = checks.get("signature_valid_b", False)

    a_ready = struct_a and party_a.get("observed") is True and sig_a_ok
    b_ready = struct_b and party_b.get("observed") is True and sig_b_ok

    if not (a_ready and b_ready):
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

    # 4. comparator_state
    computed_state = compute_comparator_state(vector, struct_a, struct_b)
    declared_state = vector.get("comparator_state", "")
    if computed_state != declared_state:
        failures.append(
            f"comparator_state: computed {computed_state} != declared {declared_state}"
        )

    # 5. supersedes_chain_integrity (v1.1, exempt when supersedes is absent)
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
