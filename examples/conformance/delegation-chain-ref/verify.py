"""
Verifier for delegation-chain-ref conformance vectors.

Checks four invariants per spec (delegation-chain-ref-v1):
  1. chain_continuity    — hops[i].delegatee == hops[i+1].delegator
  2. root_anchoring      — root_delegator == hops[0].delegator
  3. leaf_anchoring      — leaf_action_ref matches recomputed action_ref from leaf_preimage
  4. monotonic_scope_narrowing — hops[i].scope is equal to or a strict sub-namespace of hops[i-1].scope

delegation_chain_ref byte-match is also verified against SHA-256(JCS(chain_artifact)).
"""

import hashlib
import json
import sys
from pathlib import Path


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


def verify_vector(vector: dict) -> tuple[bool, list[str]]:
    failures = []
    chain = vector["chain_artifact"]
    hops = chain["hops"]

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

    return len(failures) == 0, failures


def main():
    vectors_path = Path(__file__).parent / "vectors.json"
    data = json.loads(vectors_path.read_text())

    vectors = data["vectors"]
    passed = 0
    failed = 0

    print(f"delegation-chain-ref conformance — {len(vectors)} vectors\n")

    for v in vectors:
        vid = v["id"]
        expected = v["expected"]
        conforms, failures = verify_vector(v)

        if expected == "PASS":
            ok = conforms
        else:
            ok = not conforms

        status = "PASS" if ok else "FAIL"
        marker = "✓" if ok else "✗"

        print(f"  {marker} [{status}] {vid}")
        if not ok:
            if expected == "PASS" and failures:
                for f in failures:
                    print(f"         unexpected failure: {f}")
            elif expected == "FAIL" and conforms:
                print(f"         expected FAIL ({v.get('failure_mode', '?')}) but verifier accepted it")
        elif not conforms and expected == "FAIL":
            mode = v.get("failure_mode", "?")
            matched = any(mode.replace("_", " ") in f or mode in f for f in failures)
            print(f"         correctly rejected: {failures[0]}")

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
