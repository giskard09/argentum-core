"""
Verifier for delegation-chain-ref conformance vectors.

Checks five invariants per spec (delegation-chain-ref-v1):
  1. chain_continuity    — hops[i].delegatee == hops[i+1].delegator
  2. root_anchoring      — root_delegator == hops[0].delegator
  3. leaf_anchoring      — leaf_action_ref matches recomputed action_ref from leaf_preimage
  4. monotonic_scope_narrowing — hops[i].scope is equal to or a strict sub-namespace of hops[i-1].scope
  5. hop_signature_valid — if hops[i].hop_signature is present, it must be a valid Ed25519
     signature by hops[i].delegator over JCS({chain_id, delegator, delegatee, scope,
     delegation_ref}) for that hop (cross-org attenuation: without this, chain_continuity
     alone proves nothing about who actually authorized each hop — signatures are what
     turn a claimed chain into a verified one when hops are independent parties with no
     shared authority). The preimage binds delegator/delegatee/scope/chain_id, not just
     delegation_ref alone — see "hop_signature preimage" erratum below for why.
     A delegator with no key in the given key set is NOT_ASSESSED, or FAIL
     delegator_key_not_in_complete_key_set when the caller declares the key set complete
     (keys_are_complete) — never hop_signature_invalid. See evaluate_vector().

Verdicts are PASS / FAIL / NOT_ASSESSED; any adverse finding makes the chain FAIL.

delegation_chain_ref byte-match is also verified against SHA-256(JCS(chain_artifact)).

Dependency: PyNaCl (Ed25519 verification for check 5). Install with
`pip install -r requirements.txt` before running.
"""

import base64
import hashlib
import json
import sys
from pathlib import Path

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey


def jcs(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def sha256hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def compute_action_ref(preimage: dict) -> str:
    payload = {k: preimage[k] for k in ("agent_id", "action_type", "scope", "timestamp")}
    return sha256hex(jcs(dict(sorted(payload.items()))))


def scope_is_narrower_or_equal(parent_scope: str, child_scope: str) -> bool:
    """
    Returns True if child_scope is equal to or a strict sub-namespace of parent_scope.

    Rules:
    - Equal scopes are always valid (no narrowing required).
    - parent_scope ending with ':*' matches any child that starts with the prefix before '*'.
    - Otherwise child_scope must start with parent_scope + ':'.

    Examples:
      parent='mycelium:*',       child='mycelium:payment'        -> True
      parent='mycelium:payment', child='mycelium:payment:route'  -> True
      parent='mycelium:payment', child='mycelium:*'              -> False (widening)
      parent='mycelium:payment', child='mycelium:audit'          -> False (sibling, not subset)
    """
    if parent_scope == child_scope:
        return True
    if parent_scope.endswith(":*"):
        prefix = parent_scope[:-2]  # strip ':*'
        return child_scope == prefix or child_scope.startswith(prefix + ":")
    return child_scope.startswith(parent_scope + ":")


class SeenRegistry:
    """Tracks chain_id and per-hop delegation_ref values already accepted.

    Mirrors the NonceCache pattern in agent_signing.py: a resubmission of a chain_id
    (or reuse of a delegation_ref across a different chain) is a replay regardless of
    whether the underlying artifact would otherwise verify -- an accepted chain must
    not be presentable a second time to claim the same authorization again.

    Recording happens only on `record()`, called by the caller only after every other
    check has passed (see erratum below) -- `contains()` alone never mutates state, so
    a submission that fails for an unrelated reason (bad signature, scope widening,
    ...) cannot poison the registry and cause a later, genuinely valid, resubmission
    to be misreported as a replay.
    """

    def __init__(self):
        self.chain_ids: set[str] = set()
        self.delegation_refs: set[str] = set()

    def contains(self, chain_id: str, hop_delegation_refs: list[str]) -> bool:
        return chain_id in self.chain_ids or any(r in self.delegation_refs for r in hop_delegation_refs)

    def record(self, chain_id: str, hop_delegation_refs: list[str]) -> None:
        self.chain_ids.add(chain_id)
        self.delegation_refs.update(hop_delegation_refs)


def hop_signing_preimage(chain_id: str, hop: dict) -> str:
    return jcs({
        "chain_id": chain_id,
        "delegator": hop["delegator"],
        "delegatee": hop["delegatee"],
        "scope": hop["scope"],
        "delegation_ref": hop["delegation_ref"],
    })


HOP_SIG_VALID = "valid"
HOP_SIG_INVALID = "invalid"
HOP_SIG_KEY_UNRESOLVED = "key_unresolved"


def verify_hop_signature(chain_id: str, hop: dict, hop_signature_b64: str, pubkeys: dict) -> str:
    """Returns HOP_SIG_VALID, HOP_SIG_INVALID or HOP_SIG_KEY_UNRESOLVED.

    A delegator with no key in `pubkeys` is not a bad signature: the signature was never
    checked. Reporting it as invalid would claim an adverse finding the verifier did not
    make (the collapse verify-failure-mode-ref invariant 1 rules out). What an unresolved
    key means for the verdict depends on whether the caller declared the key set complete
    -- see evaluate_vector().
    """
    pub_b64 = pubkeys.get(hop["delegator"])
    if not pub_b64:
        return HOP_SIG_KEY_UNRESOLVED
    try:
        vk = VerifyKey(base64.b64decode(pub_b64))
        preimage = hop_signing_preimage(chain_id, hop)
        vk.verify(preimage.encode("utf-8"), base64.b64decode(hop_signature_b64))
        return HOP_SIG_VALID
    except (BadSignatureError, ValueError, TypeError, KeyError):
        return HOP_SIG_INVALID


def verify_vector(vector: dict, pubkeys: dict | None = None, seen_registry: "SeenRegistry | None" = None,
                  keys_are_complete: bool = False) -> tuple[bool, list[str]]:
    """Two-valued view of evaluate_vector(): conforms only on PASS."""
    verdict, failures, not_assessed = evaluate_vector(vector, pubkeys, seen_registry, keys_are_complete)
    return verdict == "PASS", failures + not_assessed


def evaluate_vector(vector: dict, pubkeys: dict | None = None, seen_registry: "SeenRegistry | None" = None,
                    keys_are_complete: bool = False) -> tuple[str, list[str], list[str]]:
    """Returns (verdict, failures, not_assessed), verdict in PASS / FAIL / NOT_ASSESSED.

    keys_are_complete is declared by the caller, never inferred from the fixture. Absent
    (default False), a delegator missing from `pubkeys` leaves that hop's signature
    NOT_ASSESSED. Declared True, the same absence is a policy rejection (FAIL
    delegator_key_not_in_complete_key_set), still not a bad signature. Any adverse finding
    the verifier did make (a signature that does not verify, a chain break, ...) is FAIL
    regardless of what else could not be assessed.
    """
    failures = []
    not_assessed = []
    chain = vector["chain_artifact"]
    hops = chain["hops"]
    pubkeys = pubkeys or {}

    # 0. delegation_chain_ref byte-match
    expected_dcr = sha256hex(jcs(chain))
    actual_dcr = vector.get("delegation_chain_ref", "")
    if expected_dcr != actual_dcr:
        failures.append(
            f"delegation_chain_ref mismatch: expected {expected_dcr}, got {actual_dcr}"
        )

    # 1. chain_continuity
    for i in range(len(hops) - 1):
        if hops[i]["delegatee"] != hops[i + 1]["delegator"]:
            failures.append(
                f"chain_break at hop {i}: hops[{i}].delegatee={hops[i]['delegatee']!r} "
                f"!= hops[{i+1}].delegator={hops[i+1]['delegator']!r}"
            )

    # 2. root_anchoring
    if chain["root_delegator"] != hops[0]["delegator"]:
        failures.append(
            f"root_anchoring: root_delegator={chain['root_delegator']!r} "
            f"!= hops[0].delegator={hops[0]['delegator']!r}"
        )

    # 3. leaf_anchoring
    if "leaf_preimage" in vector:
        computed_leaf = compute_action_ref(vector["leaf_preimage"])
        if computed_leaf != chain["leaf_action_ref"]:
            failures.append(
                f"leaf_anchoring: recomputed action_ref={computed_leaf} "
                f"!= chain.leaf_action_ref={chain['leaf_action_ref']}"
            )
        # leaf_preimage.scope must match hops[-1].scope
        leaf_scope = vector["leaf_preimage"]["scope"]
        leaf_hop_scope = hops[-1]["scope"]
        if leaf_scope != leaf_hop_scope:
            failures.append(
                f"scope_mismatch_at_leaf: leaf_preimage.scope={leaf_scope!r} "
                f"!= hops[-1].scope={leaf_hop_scope!r}"
            )

    # 4. monotonic_scope_narrowing
    for i in range(1, len(hops)):
        parent = hops[i - 1]["scope"]
        child = hops[i]["scope"]
        if not scope_is_narrower_or_equal(parent, child):
            failures.append(
                f"scope_widening at hop {i}: hops[{i}].scope={child!r} "
                f"is not a sub-namespace of hops[{i-1}].scope={parent!r}"
            )

    # 5. hop_signature_valid — only enforced when hop_signature is present (additive,
    # optional field — hops without it are unaffected, per delegation-ref.md invariant 5
    # pattern of opaque/additional fields entering the hash but not required by the base schema).
    # The signature covers {chain_id, delegator, delegatee, scope, delegation_ref} for the hop,
    # not delegation_ref alone — see "hop_signature preimage" erratum in delegation-chain-ref.md:
    # a bare signature over delegation_ref proves the delegator signed *some* opaque pointer, not
    # that the delegator authorized *this* hop's delegatee/scope, so a chain could be edited to
    # swap in a different scope/delegatee while carrying forward an untouched, still-"valid" signature.
    for i, hop in enumerate(hops):
        if "hop_signature" in hop:
            sig = verify_hop_signature(chain["chain_id"], hop, hop["hop_signature"], pubkeys)
            if sig == HOP_SIG_INVALID:
                failures.append(
                    f"hop_signature_invalid at hop {i}: signature does not verify against "
                    f"delegator={hop['delegator']!r}'s registered pubkey over "
                    f"{{chain_id, delegator, delegatee, scope, delegation_ref}} for this hop"
                )
            elif sig == HOP_SIG_KEY_UNRESOLVED and keys_are_complete:
                failures.append(
                    f"delegator_key_not_in_complete_key_set at hop {i}: "
                    f"delegator={hop['delegator']!r} has no key in a key set the caller declared "
                    f"complete (policy rejection; the signature itself was not checked)"
                )
            elif sig == HOP_SIG_KEY_UNRESOLVED:
                not_assessed.append(
                    f"hop_signature_not_assessed at hop {i}: no key for "
                    f"delegator={hop['delegator']!r} and the key set is not declared complete"
                )

    # 6. replay_detected — chain_id or any hop delegation_ref already accepted before.
    # Recording happens only after every other check has passed: a submission recorded before
    # all checks were known-good would let a rejected (e.g. bad-signature) attempt consume the
    # chain_id/delegation_ref, so a later, genuinely valid, resubmission of the same chain would
    # be misreported as a replay instead of accepted (erratum in delegation-chain-ref.md).
    if seen_registry is not None:
        hop_refs = [h["delegation_ref"] for h in hops]
        if seen_registry.contains(chain["chain_id"], hop_refs):
            failures.append(
                f"replay_detected: chain_id={chain['chain_id']!r} (or one of its hop "
                f"delegation_ref values) was already submitted"
            )
        elif not failures and not not_assessed:
            # A NOT_ASSESSED submission was not accepted either, so it must not consume
            # the chain_id (same reasoning as the recording-order erratum).
            seen_registry.record(chain["chain_id"], hop_refs)

    if failures:
        return "FAIL", failures, not_assessed
    if not_assessed:
        return "NOT_ASSESSED", failures, not_assessed
    return "PASS", failures, not_assessed


def run_file(vectors_path: Path):
    """`expected` is a verdict or a list of acceptable verdicts. A vector may carry its
    own `pubkeys` and `keys_are_complete`; otherwise the file-level ones apply (default:
    not declared complete). An expected FAIL also has to fail for its `failure_mode`."""
    data = json.loads(vectors_path.read_text())
    vectors = data["vectors"]
    seen_registry = SeenRegistry()
    passed = 0
    failed = 0

    print(f"{vectors_path.name} — {len(vectors)} vectors\n")

    for v in vectors:
        vid = v["id"]
        expected = v["expected"] if isinstance(v["expected"], list) else [v["expected"]]
        pubkeys = v.get("pubkeys", data.get("pubkeys", {}))
        complete = v.get("keys_are_complete", data.get("keys_are_complete", False))
        verdict, failures, not_assessed = evaluate_vector(v, pubkeys, seen_registry, complete)

        ok = verdict in expected
        mode = v.get("failure_mode")
        if ok and verdict == "FAIL" and mode:
            ok = any(f.startswith(mode) for f in failures)

        status = "PASS" if ok else "FAIL"
        marker = "✓" if ok else "✗"

        print(f"  {marker} [{status}] {vid}  -> {verdict}")
        if not ok:
            print(f"         expected {'/'.join(expected)}" + (f" ({mode})" if mode else ""))
            for f in failures + not_assessed:
                print(f"         got: {f}")
        elif verdict != "PASS":
            print(f"         {(failures + not_assessed)[0]}")

        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{passed}/{len(vectors)} passed" + (f", {failed} failed" if failed else ""))
    return passed, failed


def main():
    base = Path(__file__).parent
    total_passed = 0
    total_failed = 0
    for fname in ("vectors.json", "cross-org-vectors.json", "replay-vectors.json",
                  "key-completeness-vectors.json"):
        p, f = run_file(base / fname)
        total_passed += p
        total_failed += f
        print()

    print(f"TOTAL: {total_passed} passed, {total_failed} failed")
    if total_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
