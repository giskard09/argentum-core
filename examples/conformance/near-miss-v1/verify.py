#!/usr/bin/env python3
"""Conformance runner for near-miss-v1 vectors.

Tests the near-miss boundary of action-ref-v1: verifier MUST reject each
fail-closed vector with the correct error code, and MUST pass KNOWN_DESIGN_PROPERTY
vectors without rejecting on the documented property.

Deterministic: stdlib only, no wall-clock, no randomness, no network.

Usage: python3 verify.py
Exit codes: 0 all vectors pass, 1 any failure.
"""

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def jcs(obj):
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def sha256_hex(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def recompute_action_ref(preimage):
    return "sha256:" + sha256_hex(jcs(preimage))


# --- verifier stubs for each failure mode ---

def check_ambiguous_issuer_binding(vector):
    """AMBIGUOUS_ISSUER_BINDING: same action_ref, same (claim_type, evidenceType),
    different source_provider_did with disjoint verdicts."""
    envelopes = vector.get("envelopes", [])
    action_ref = vector["preimage_block"]["action_ref"]
    groups = {}
    for env in envelopes:
        eb = env.get("evidence_basis", {})
        if eb.get("action_ref") != action_ref:
            return False, "action_ref mismatch in envelope"
        key = (env.get("claim_type"), eb.get("evidenceType"))
        verdict = env.get("attestation", {}).get("admissibility_result")
        provider = env.get("provider", {}).get("id")
        if key not in groups:
            groups[key] = []
        groups[key].append((provider, verdict))
    for key, entries in groups.items():
        verdicts = {v for _, v in entries}
        providers = {p for p, _ in entries}
        if len(verdicts) > 1 and len(providers) > 1:
            return False, "AMBIGUOUS_ISSUER_BINDING"
    return True, "no ambiguity"


def check_rescoped_replay(vector):
    """RESCOPED_REPLAY: embedded action_ref does not match recomputed over
    the presented tuple."""
    issued = vector["issued_preimage_block"]["action_ref"]
    presented_preimage = vector["presented_preimage_block"]["preimage"]
    recomputed = recompute_action_ref(presented_preimage)
    envelope_ref = vector["envelope"]["evidence_basis"]["action_ref"]
    if envelope_ref != recomputed:
        return False, "RESCOPED_REPLAY"
    return True, "scope binding intact"


def check_semantic_drift(vector):
    """SEMANTIC_DRIFT: action_ref at issuance and verification diverge due to
    action_type vocabulary change."""
    iss = vector["issuance_preimage_block"]["action_ref"]
    ver = vector["verification_preimage_block"]["action_ref"]
    if iss != ver:
        return False, "SEMANTIC_DRIFT"
    return True, "no drift"


def check_known_design_property(vector):
    """KNOWN_DESIGN_PROPERTY: same action_ref across receipts with different state.
    Verifier MUST NOT reject on this basis — shared action_ref is correct by spec."""
    receipts = vector.get("receipts", [])
    refs = {r["action_ref"] for r in receipts}
    if len(refs) != 1:
        return False, "action_refs differ — fixture integrity error"
    states = {r.get("state") for r in receipts}
    terminals = {r.get("terminal") for r in receipts}
    if len(states) < 2:
        return False, "fixture has fewer than 2 distinct state values — loop incomplete"
    # Verifier MUST pass: same action_ref with different terminal values is not a collision
    return True, "KNOWN_DESIGN_PROPERTY — shared action_ref across states is correct"


def walk_parent_chain(chain_entries):
    """Walk composition artifact parent chain with a visited set.

    Returns (ok, error_code_or_none). If a cycle is detected: (False, 'PROVENANCE_LOOP').
    chain_entries: list of {composition_ref, artifact} in lookup order.
    """
    lookup = {e["composition_ref"]: e["artifact"] for e in chain_entries}
    start = chain_entries[0]["composition_ref"]

    visited = set()
    current_ref = start
    while current_ref is not None:
        if current_ref in visited:
            return False, "PROVENANCE_LOOP"
        visited.add(current_ref)
        artifact = lookup.get(current_ref)
        if artifact is None:
            break
        current_ref = artifact.get("parent_composition_ref")
    return True, None


def check_provenance_loop(vector):
    """PROVENANCE_LOOP: parent chain contains a cycle — visited-set detects revisit."""
    chain = vector.get("parent_chain", [])
    ok, error = walk_parent_chain(chain)
    if ok:
        return True, "no loop detected"
    return False, error


# --- fixture integrity checks ---

def verify_jcs_hashes(vector):
    """Verify that jcs_hash fields in parent_chain entries match actual JCS computation."""
    failures = []
    for entry in vector.get("parent_chain", []):
        if "jcs_hash" not in entry or "artifact" not in entry:
            continue
        computed = sha256_hex(jcs(entry["artifact"]))
        if computed != entry["jcs_hash"]:
            failures.append(
                "jcs_hash mismatch for %s: expected %s got %s"
                % (entry["composition_ref"][:12] + "...", entry["jcs_hash"][:12] + "...", computed[:12] + "...")
            )
        if "jcs_canonical" in entry:
            canonical = jcs(entry["artifact"])
            if canonical != entry["jcs_canonical"]:
                failures.append("jcs_canonical mismatch for %s" % entry["composition_ref"][:12] + "...")
    return failures


VERIFIER_MAP = {
    "AMBIGUOUS_ISSUER_BINDING": check_ambiguous_issuer_binding,
    "RESCOPED_REPLAY": check_rescoped_replay,
    "SEMANTIC_DRIFT": check_semantic_drift,
    "KNOWN_DESIGN_PROPERTY": check_known_design_property,
    "PROVENANCE_LOOP": check_provenance_loop,
}


def main():
    fixture_path = HERE / "near-miss-v1.fixture.json"
    with open(fixture_path, encoding="utf-8") as f:
        fixture = json.load(f)

    vectors = fixture["vectors"]
    if not vectors:
        sys.exit("ZERO_CASES: fixture vectors is empty; refusing to report success on nothing")
    failures = 0

    for v in vectors:
        name = v["name"]
        failure_mode = v["failure_mode"]
        expected_result = v.get("expected_result")
        expected_error = v.get("expected_error_code")

        verifier = VERIFIER_MAP.get(failure_mode)
        if verifier is None:
            failures += 1
            print("FAIL  %-42s no verifier registered for failure_mode %s" % (name, failure_mode))
            continue

        ok, reason = verifier(v)

        # Fixture integrity: jcs_hash byte-verification for provenance_loop
        if failure_mode == "PROVENANCE_LOOP":
            jcs_failures = verify_jcs_hashes(v)
            for msg in jcs_failures:
                failures += 1
                print("FAIL  %-42s fixture integrity: %s" % (name, msg))

        if expected_result == "fail-closed":
            if ok:
                failures += 1
                print("FAIL  %-42s verifier accepted — expected fail-closed (%s)" % (name, expected_error))
            elif reason != expected_error:
                failures += 1
                print("FAIL  %-42s wrong error code: got %s expected %s" % (name, reason, expected_error))
            else:
                print("PASS  %-42s fail-closed (%s)" % (name, reason))

        elif expected_result == "KNOWN_DESIGN_PROPERTY":
            if not ok:
                failures += 1
                print("FAIL  %-42s verifier rejected KNOWN_DESIGN_PROPERTY vector: %s" % (name, reason))
            else:
                print("PASS  %-42s %s" % (name, reason))

        else:
            failures += 1
            print("FAIL  %-42s unknown expected_result: %s" % (name, expected_result))

    print()
    if failures:
        print("%d check(s) failed" % failures)
        return 1
    print("all %d vectors pass" % len(vectors))
    return 0


if __name__ == "__main__":
    sys.exit(main())
