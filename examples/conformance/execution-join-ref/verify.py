"""
Reference verifier for execution-join-ref-v1 conformance vectors.

This is the FIRST verifier ever built for this spec. The fixture
(vectors.json) pre-dates it with every digest hand-asserted
("verification_mode": "asserted") -- nothing in this directory had ever
actually been run until this file was written. Unlike the sibling
conformance directories in this repo (anchoring-precedence-ref,
peer-reconciliation-ref), this verifier is NOT fully self-contained: the
spec's canonicalization-profile layer (docs/spec/execution-join-ref-v1.md,
"canonicalization_profile_id") is explicitly repo-level infrastructure
(profiles/, profiles/profile_registry.py, shared with
governance-block-join-ref-v1), so this script imports the real repo jcs.py
and profiles/profile_registry.py rather than reimplementing a local copy.
It must be run from inside a checkout of this repo.

Seven invariants, checked in spec order; the first that fails is the
reported failure_mode:

  1. canonical_envelope   — for every ref with a supplied preimage: all of
                             that preimage shape's required fields (per the
                             spec's "JCS preimage shapes") are present, AND
                             SHA-256(JCS(preimage)) matches the envelope's
                             declared value for that ref. A ref with NO
                             supplied preimage is not checked here -- this
                             vector is not exercising that ref, the same
                             "preimages present for what's under test only"
                             convention the fixture already uses (e.g.
                             AUTHORIZED_EFFECTIVE_CALL only supplies a
                             decision_id preimage, reusing action_ref/
                             attempt_id/result_id values already established
                             elsewhere in the fixture).
  2. chain_integrity      — decision_id's preimage.action_ref matches the
                             envelope's action_ref; result_id's preimage.
                             attempt_id matches the envelope's attempt_id.
                             (NOT proof_ref -- despite the spec's invariant-2
                             prose mentioning it, the fixture's own vectors
                             demonstrate proof_ref binding is exclusively
                             invariant 5's job: PROOF_BINDING_FAILED declares
                             chain_integrity=true while proof_binding=false.
                             See the note in docs/spec/execution-join-ref-v1.md
                             fixed alongside this verifier.)
  3. no_duplicate_attempt — whether this attempt_id has been seen before for
                             this action_ref. This requires a registry that
                             spans records *outside* any single vector (the
                             fixture deliberately reuses the same attempt_id
                             across most of its vectors for narrative economy
                             -- recomputing this live from vectors.json alone
                             would produce false positives). Declared in
                             checks.no_duplicate_attempt, same "declared,
                             externally-audited fact" treatment chain_invariant
                             gets in anchoring-precedence-ref-v1.
  4. result_uniqueness    — same treatment as #3, for the same structural
                             reason (RESULT_ID_CONFLICT's entire point is two
                             *different* records sharing one result_id with
                             different outcome -- a property of a registry
                             across records, not of one record's JCS bytes).
  5. proof_binding        — if proof_ref is present and its preimage is
                             supplied, its preimage.attempt_id must match the
                             envelope's attempt_id (not a rewrite's).
  6. effective_call_binding — the action_ref actually dispatched (the
                             envelope's effective_action_ref if present,
                             otherwise action_ref itself) must be covered by
                             a decision: decision_id's preimage.action_ref
                             must equal that target ref, its outcome must be
                             "permit" (fixed 2026-10-23, mutation-tested gap
                             reported by astrogilda/probityai, same fix
                             already applied in the sibling
                             execution-join-ref-remora-bridge repo at
                             2cc79c9, 2026-10-10 -- a decision that
                             structurally covers the ref but denies or
                             defers it authorizes nothing, same observable
                             consequence as no covering decision at all;
                             reuses EFFECTIVE_CALL_REBINDING_FAILED rather
                             than a new code, since the spec defines none
                             for "covers but doesn't permit"), AND (if the
                             decision preimage declares policy_expires_ms)
                             that policy must not have already expired at
                             the decision's own ts_ms. Only computed when a
                             decision_id preimage is supplied.
  7. post_commit_consistency (additive, this change) — see
                             POST_COMMIT_DIVERGENCE below.

Canonicalization profile gate (checked before #1-#2 and #6, only when
decision_id's preimage declares canonicalization_profile_id): if the id does
not resolve in profiles/profile_registry.py, halt -- do not attempt digest
comparison -- and report UNSUPPORTED_CANONICAL_PROFILE with #1/#2/#6 left
null (matching the fixture's own "null means the verifier halted before
that check, not that it passed" convention, see UNSUPPORTED_CANONICAL_PROFILE
and VERIFIER_OFFLINE vectors).

VERIFIER_OFFLINE / RESULT_ID_CONFLICT special case: a vector with no
`preimages` key at all supplies nothing this verifier can independently
recompute. Every check in `checks` is then taken as declared (same
treatment as #3/#4 above, just total rather than partial for that vector).
This is not a separate code path -- it falls out naturally from steps 1/2/5/6
each being no-ops when their preimage is absent.

POST_COMMIT_DIVERGENCE (v1.1, additive -- docs/spec/execution-join-ref-v1.md
"Post-commit divergence" section): a NEW, OPTIONAL, separately-recomputable
ref, `post_commit_ref` (preimage: result_id, observed_hash, observed_at_ms,
observer_id, version). When present, invariant 7 checks that
post_commit_observation.result_id matches the envelope's result_id (binding)
and that observed_hash matches the original result_id preimage's
output_hash. A mismatch is NOT a retroactive failure of invariants 1-6 --
the original join record stays exactly as valid as it was; this invariant
exists to detect and name a *later* divergence between the committed output
and a subsequent observation, without collapsing the two into one state.
Absent `post_commit_ref` = exempt, same pattern as supersedes_chain_integrity
in peer-reconciliation-ref-v1.
"""

import hashlib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "profiles"))

import jcs  # noqa: E402  (repo-root helper, see module docstring for why this
import profile_registry  # noqa: E402  verifier is not self-contained like its siblings)


REQUIRED_FIELDS = {
    "action_ref": {"actor_id", "input_hash", "scope", "ts_ms", "version"},
    "effective_action_ref": {"actor_id", "input_hash", "scope", "ts_ms", "version"},
    "decision_id": {"action_ref", "outcome", "policy_id", "ts_ms", "version"},
    "attempt_id": {"action_ref", "attempt_seq", "executor_id", "ts_ms", "version"},
    "result_id": {"attempt_id", "outcome", "output_hash", "ts_ms", "version"},
    "proof_ref": {"attempt_id", "evidence_type", "external_ref", "ts_ms", "version"},
    "post_commit_observation": {"result_id", "observed_hash", "observed_at_ms", "observer_id", "version"},
}


def sha256hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def recompute(preimage: dict) -> str | None:
    """Returns the hash, or None if jcs.py rejects the preimage as out of
    the RFC 8785 safe-integer domain (OUT_OF_PROFILE_DOMAIN territory --
    this fixture carries no vector for it yet, but a verifier must not
    silently coerce or crash on one either)."""
    try:
        return sha256hex(jcs.jcs_bytes(preimage, ensure_ascii=False))
    except ValueError:
        return None


def _check(key: str, computed_ok: bool, declared: dict, computed: dict, failures: list[str]) -> None:
    """Record a computed invariant result. Two independent things can make
    this vector non-conformant, and both are appended to `failures`:
    (a) the invariant is itself false (a real defect in the record -- this
        is what makes `conforms` correct regardless of whether the fixture
        predicted it), and (b) the fixture's declared value disagrees with
        what was just computed (a fixture-authoring bug, caught the same way
        this whole exercise caught profile_registry.py's missing `import
        json` and exists for the same reason: nothing here had ever been
        run before)."""
    computed[key] = computed_ok
    if not computed_ok:
        failures.append(f"{key}: computed false")
    if key in declared and declared[key] is not None and declared[key] != computed_ok:
        failures.append(f"{key}: computed {computed_ok} != declared {declared[key]!r} (fixture mismatch)")


def verify_vector(vector: dict) -> tuple[bool, list[str], dict]:
    """Returns (conforms, failures, computed) where computed is a dict of
    whichever invariants this vector's supplied preimages let us compute
    directly, for diagnostic printing -- not every key will be present."""
    env = vector["envelope"]
    preimages = vector.get("preimages")
    declared = vector.get("checks", {})
    failures: list[str] = []
    computed: dict = {}

    # VERIFIER_OFFLINE: no preimage material at all, but the envelope has
    # populated refs it is making claims about. "Nothing to recompute" must
    # never read as "nothing is wrong" -- that is the entire point of this
    # being a distinct code, never collapsed into a pass. Distinguished from
    # RESULT_ID_CONFLICT (which also lacks `preimages` but declares concrete,
    # non-null checks) by the sentinel failure_mode the fixture already uses.
    if preimages is None:
        if vector.get("failure_mode") == "VERIFIER_OFFLINE":
            for key in ("canonical_envelope", "chain_integrity", "no_duplicate_attempt",
                        "result_uniqueness", "proof_binding"):
                computed[key] = None
            failures.append("VERIFIER_OFFLINE: no preimage material supplied, cannot recompute any ref")
            return False, failures, computed
        preimages = {}

    # Canonicalization profile gate -- only decision_id ever carries this.
    # A failure here is a real failure (profile resolution itself failed),
    # not merely a mismatch against a declared value.
    decision_pre = preimages.get("decision_id")
    if decision_pre is not None and "canonicalization_profile_id" in decision_pre:
        profile_id = decision_pre["canonicalization_profile_id"]
        if not profile_registry.is_supported(profile_id):
            for key in ("canonical_envelope", "chain_integrity", "effective_call_binding"):
                computed[key] = None
            failures.append(
                f"UNSUPPORTED_CANONICAL_PROFILE: canonicalization_profile_id {profile_id!r} "
                f"not found in profile registry; halted before digest comparison"
            )
            return False, failures, computed

    # 1. canonical_envelope -- per ref, only for refs with a supplied preimage.
    malformed_refs = set()
    canonical_ok = True
    for ref_name, preimage in preimages.items():
        if ref_name == "post_commit_observation":
            continue  # invariant 7, checked separately below
        required = REQUIRED_FIELDS.get(ref_name)
        if required is not None and not required.issubset(preimage.keys()):
            canonical_ok = False
            malformed_refs.add(ref_name)
            continue
        digest = recompute(preimage)
        declared_ref = env.get(ref_name)
        if digest is None or digest != declared_ref:
            canonical_ok = False
    if preimages:
        _check("canonical_envelope", canonical_ok, declared, computed, failures)

    # 2. chain_integrity -- decision_id<->action_ref, result_id<->attempt_id.
    # Deliberately excludes proof_ref: see module docstring.
    chain_checked = False
    chain_ok = True
    if decision_pre is not None:
        chain_checked = True
        if "decision_id" in malformed_refs or decision_pre.get("action_ref") != env.get("action_ref"):
            chain_ok = False
    result_pre = preimages.get("result_id")
    if result_pre is not None:
        chain_checked = True
        if result_pre.get("attempt_id") != env.get("attempt_id"):
            chain_ok = False
    if chain_checked:
        _check("chain_integrity", chain_ok, declared, computed, failures)

    # 3 & 4. no_duplicate_attempt / result_uniqueness -- declared, external
    # registry facts (see module docstring for why these can't be
    # recomputed from a single vector in this fixture).
    for key in ("no_duplicate_attempt", "result_uniqueness"):
        if key in declared and declared[key] is False:
            failures.append(f"{key}: declared false for this vector (external registry fact)")

    # 5. proof_binding.
    proof_pre = preimages.get("proof_ref")
    if proof_pre is not None and env.get("proof_ref") is not None:
        proof_ok = proof_pre.get("attempt_id") == env.get("attempt_id")
        _check("proof_binding", proof_ok, declared, computed, failures)

    # 6. effective_call_binding -- computed whenever there is something to
    # check coverage against: either a decision_id preimage was supplied, or
    # the envelope itself declares effective_action_ref (a rewrite). In the
    # latter case with no decision_id preimage, there is nothing that can
    # possibly demonstrate coverage, so this is false by construction --
    # "no preimage to check" must not read as "nothing to find," same
    # principle as the VERIFIER_OFFLINE handling above.
    if decision_pre is not None or env.get("effective_action_ref") is not None:
        target_ref = env.get("effective_action_ref") or env.get("action_ref")
        decision_covers = (
            decision_pre is not None
            and "decision_id" not in malformed_refs
            and decision_pre.get("action_ref") == target_ref
            and decision_pre.get("outcome") == "permit"
        )
        policy_ok = True
        if decision_pre is not None and "policy_expires_ms" in decision_pre:
            if decision_pre["policy_expires_ms"] < decision_pre.get("ts_ms", 0):
                policy_ok = False
        eff_ok = canonical_ok and decision_covers and policy_ok
        _check("effective_call_binding", eff_ok, declared, computed, failures)

    # 7. post_commit_consistency (v1.1, additive) -- exempt when absent.
    pc_pre = preimages.get("post_commit_observation")
    if pc_pre is not None:
        pc_required = REQUIRED_FIELDS["post_commit_observation"]
        if not pc_required.issubset(pc_pre.keys()):
            _check("post_commit_consistency", False, declared, computed, failures)
        else:
            pc_digest = recompute(pc_pre)
            pc_ref_ok = pc_digest == env.get("post_commit_ref")
            binds_this_result = pc_pre.get("result_id") == env.get("result_id")
            result_pre_for_pc = preimages.get("result_id")
            matches_output = (
                result_pre_for_pc is not None
                and pc_pre.get("observed_hash") == result_pre_for_pc.get("output_hash")
            )
            pc_ok = pc_ref_ok and binds_this_result and matches_output
            _check("post_commit_consistency", pc_ok, declared, computed, failures)

    # 8. authority_check_order (v1.3, additive) -- exempt when decision_id's
    # preimage carries neither authority_verified_at_ms nor
    # revocation_check_at_ms. Checks temporal coherence only -- see the spec's
    # "Gap -- delegation, revocation and freshness" for why this cannot
    # resolve revocation or staleness itself.
    if decision_pre is not None:
        avm = decision_pre.get("authority_verified_at_ms")
        rcm = decision_pre.get("revocation_check_at_ms")
        if avm is not None or rcm is not None:
            ts_ms = decision_pre.get("ts_ms")
            order_ok = True
            if avm is not None and ts_ms is not None and avm > ts_ms:
                order_ok = False
            if rcm is not None and ts_ms is not None and rcm > ts_ms:
                order_ok = False
            if avm is not None and rcm is not None and avm > rcm:
                order_ok = False
            _check("authority_check_order", order_ok, declared, computed, failures)

    return (len(failures) == 0), failures, computed


def _expected_reason_confirmed(vector: dict, computed: dict, failures: list[str]) -> bool:
    """For an `expected: FAIL` vector: not just "did it fail" but "did it fail
    for the declared reason". Without this, a FAIL vector whose real defect
    was mutated away still reads as a correct rejection as long as *some*
    unrelated failure is present in `failures` -- e.g. a stale `checks` entry
    left over from before the mutation, which `_check()` reports as a
    "fixture mismatch" rather than the invariant actually being exercised.
    (Found by astrogilda/probityai via mutation testing, 2026-10-23: remove a
    FAIL vector's defect without updating `checks` to match, and the old
    summary logic -- `ok = not conforms` -- still printed "correctly
    rejected" under the vector's original failure_code, because `conforms`
    was still False for the unrelated stale-declaration reason.)

    Ground truth for "the declared reason" is the vector's own `checks` dict:
    whichever keys it declares False are the invariants this vector exists to
    fail. At least one of those must still be False in `computed` -- the key
    recomputing, independently, to the same answer the fixture declares, not
    merely "the overall tally has a nonzero failure count".

    Two more keys are declared-only by design (no_duplicate_attempt,
    result_uniqueness -- see verify_vector()'s own comment: these require a
    registry spanning records outside any single vector, so they are never
    written to `computed` at all, only asserted via a dedicated `failures`
    string). Confirmed via that same string.

    Two codes never declare a False key in `checks` -- they halt before any
    invariant is computed at all (UNSUPPORTED_CANONICAL_PROFILE, structural
    profile-resolution failure; VERIFIER_OFFLINE, no preimage material).
    Confirmed via the sentinel string verify_vector() already prefixes to its
    one failure entry for each.
    """
    declared_only_keys = {"no_duplicate_attempt", "result_uniqueness"}
    declared_false = [k for k, val in vector.get("checks", {}).items() if val is False]
    for key in declared_false:
        if key in declared_only_keys:
            if any(f.startswith(f"{key}:") for f in failures):
                return True
        elif computed.get(key) is False:
            return True
    if declared_false:
        return False
    sentinel = vector.get("failure_mode") or vector.get("failure_code") or ""
    return bool(sentinel) and any(f.startswith(f"{sentinel}:") for f in failures)


def main():
    vectors_path = Path(__file__).parent / "vectors.json"
    data = json.loads(vectors_path.read_text())
    vectors = data["vectors"]

    print(f"execution-join-ref-v1 conformance — {len(vectors)} vectors\n")

    passed = 0
    failed = 0

    for v in vectors:
        vid = v["id"]
        expected = v["expected"]
        conforms, failures, computed = verify_vector(v)

        if expected == "PASS":
            ok = conforms
        else:
            ok = (not conforms) and _expected_reason_confirmed(v, computed, failures)
        marker = "✓" if ok else "✗"
        status = "PASS" if ok else "FAIL"
        code = v.get("failure_code") or v.get("failure_mode", "?")

        print(f"  {marker} [{status}] {vid}")
        if ok and not conforms and expected == "FAIL":
            print(f"         correctly rejected ({code}): {failures[0] if failures else '(declared)'}")
        elif not ok:
            if expected == "PASS":
                for f in failures:
                    print(f"         unexpected failure: {f}")
            elif conforms:
                print(f"         expected FAIL ({code}) but verifier accepted it")
            else:
                print(f"         expected FAIL ({code}), but the failure doesn't reproduce it: {failures}")

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
