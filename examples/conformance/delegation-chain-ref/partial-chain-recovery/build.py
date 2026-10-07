"""
Deterministic generator for partial-chain-recovery/vectors.json.

Re-running this script must reproduce vectors.json byte for byte. It derives
every digest with the same functions the reference verifier uses
(../verify.py: jcs, sha256hex, compute_action_ref).

Scope (agreed on x402-foundation/x402#2332, comments 5878267660, 5887938781,
5890759053, 5940312632): "recovery" means restoring missing chain bytes, not
recovering authority. A valid 3-hop chain agent-a -> agent-b -> agent-c ->
agent-d has its delegation_chain_ref fixed; the middle hop (hops[1]) is
omitted from chain_artifact while that reference is held fixed. Against one
initially empty replay registry, in order: FAIL (digest mismatch and broken
continuity), two FAIL controls (a substituted hop in the right position; the
exact hop in the wrong position), PASS after the exact hop is restored in its
original position, then replay_detected on a further submission of the
restored chain. parent_delegation_ref resolution is not exercised.

Usage: python3 build.py
"""

import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load_reference_verifier():
    spec = importlib.util.spec_from_file_location("reference_verify", HERE.parent / "verify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ref = _load_reference_verifier()
jcs, sha256hex, compute_action_ref = ref.jcs, ref.sha256hex, ref.compute_action_ref

EXPIRES_AT = "2026-12-31T00:00:00.000Z"
POLICY_VERSION = "2026-10-01"
SUBSTITUTE_POLICY_VERSION = "2026-10-02"
LEAF_TIMESTAMP = "2026-10-05T12:00:00.000Z"
CHAIN_ID = "chain-partial-chain-recovery-001"
MISSING_HOP_INDEX = 1


def delegation_artifact(delegator, delegatee, capability, scope, parent_ref, policy_version=POLICY_VERSION):
    art = {
        "capability": capability,
        "delegatee": delegatee,
        "delegator": delegator,
        "expires_at": EXPIRES_AT,
        "policy_version": policy_version,
        "scope": scope,
        "version": "delegation-ref-v1",
    }
    if parent_ref is not None:
        art["parent_delegation_ref"] = parent_ref
    return dict(sorted(art.items()))


def hop_from(art):
    return {"delegatee": art["delegatee"], "delegator": art["delegator"],
            "delegation_ref": sha256hex(jcs(art)), "scope": art["scope"]}


def build_original():
    hop_specs = [
        ("agent-a", "agent-b", "delegate", "mycelium:payment"),
        ("agent-b", "agent-c", "delegate", "mycelium:payment"),
        ("agent-c", "agent-d", "payment.route", "mycelium:payment:route"),
    ]
    artifacts, hops, parent = [], [], None
    for delegator, delegatee, capability, scope in hop_specs:
        art = delegation_artifact(delegator, delegatee, capability, scope, parent)
        artifacts.append(art)
        hops.append(hop_from(art))
        parent = hops[-1]["delegation_ref"]
    leaf_preimage = {
        "agent_id": "agent-d",
        "action_type": "payment.route",
        "scope": "mycelium:payment:route",
        "timestamp": LEAF_TIMESTAMP,
    }
    chain = {
        "chain_id": CHAIN_ID,
        "hops": hops,
        "leaf_action_ref": compute_action_ref(leaf_preimage),
        "root_delegator": "agent-a",
        "scope": "mycelium:payment",
        "version": "delegation-chain-ref-v1",
    }
    return chain, artifacts, leaf_preimage


def with_hops(chain, hops):
    c = copy.deepcopy(chain)
    c["hops"] = copy.deepcopy(hops)
    return c


def vector(vid, description, expected, chain, leaf, fixed_ref, registry_after,
           failure_mode=None, additional_failure_modes=None, must_not_fail_with=None, extra=None):
    v = {"id": vid, "description": description, "expected": expected}
    if failure_mode:
        v["failure_mode"] = failure_mode
    if additional_failure_modes:
        v["additional_failure_modes"] = additional_failure_modes
    if must_not_fail_with:
        v["must_not_fail_with"] = must_not_fail_with
    v["expected_registry_after"] = registry_after
    v["chain_artifact"] = chain
    v["leaf_preimage"] = leaf
    v["delegation_chain_ref"] = fixed_ref
    if extra:
        v.update(extra)
    return v


def build():
    original, artifacts, leaf = build_original()
    fixed_ref = sha256hex(jcs(original))
    h0, h1, h2 = original["hops"]

    substitute_art = delegation_artifact("agent-b", "agent-c", "delegate", "mycelium:payment",
                                         h0["delegation_ref"], SUBSTITUTE_POLICY_VERSION)
    h1_sub = hop_from(substitute_art)
    assert h1_sub["delegation_ref"] != h1["delegation_ref"]
    assert {k: h1_sub[k] for k in ("delegatee", "delegator", "scope")} == \
           {k: h1[k] for k in ("delegatee", "delegator", "scope")}

    empty = {"chain_ids": 0, "delegation_refs": 0}
    recorded = {"chain_ids": 1, "delegation_refs": 3}

    vectors = [
        vector(
            "recovery-001-missing-hop",
            "hops[1] (agent-b -> agent-c) is absent from chain_artifact; hops[0] and hops[2] "
            "are the original bytes and delegation_chain_ref is the original reference, held "
            "fixed. Expected FAIL for two reasons: the recomputed digest does not match the "
            "fixed reference, and chain_continuity breaks at hop 0 (agent-b != agent-c). The "
            "failed submission must not be recorded in the replay registry.",
            "FAIL", with_hops(original, [h0, h2]), leaf, fixed_ref, empty,
            failure_mode="delegation_chain_ref mismatch",
            additional_failure_modes=["chain_break at hop 0"]),
        vector(
            "recovery-002-substituted-hop-control",
            "Control. A hop with the same delegator, delegatee and scope as the missing one "
            "but a different delegation_ref (a re-issued grant, policy_version "
            f"{SUBSTITUTE_POLICY_VERSION}, see substitute_delegation_artifact) is placed in "
            "position 1. chain_continuity is satisfied again, so this must NOT fail with "
            "chain_break; it still FAILs because the recomputed digest does not match the "
            "fixed reference. Restoration has to be the exact bytes, not a hop that merely "
            "satisfies continuity. Not recorded in the replay registry.",
            "FAIL", with_hops(original, [h0, h1_sub, h2]), leaf, fixed_ref, empty,
            failure_mode="delegation_chain_ref mismatch",
            must_not_fail_with=["chain_break"],
            extra={"substitute_delegation_artifact": substitute_art}),
        vector(
            "recovery-003-misplaced-hop-control",
            "Control. The exact missing hop is supplied, but appended after hops[2] instead of "
            "restored at position 1. hops order is semantic (delegation-chain-ref.md, "
            "HOPS_REORDERED), so the digest does not match the fixed reference and "
            "chain_continuity breaks at hop 0; other invariants fail as well. Not recorded in "
            "the replay registry.",
            "FAIL", with_hops(original, [h0, h2, h1]), leaf, fixed_ref, empty,
            failure_mode="delegation_chain_ref mismatch",
            additional_failure_modes=["chain_break at hop 0"]),
        vector(
            "recovery-004-exact-restoration",
            "The exact missing hop restored in its original position; chain_artifact is byte-"
            "identical to original_chain_artifact. Expected PASS under the original "
            "delegation_chain_ref. The three failed attempts above did not consume replay "
            "state, so this first valid submission is accepted and now recorded (chain_id "
            "plus all three hop delegation_ref values).",
            "PASS", with_hops(original, [h0, h1, h2]), leaf, fixed_ref, recorded),
        vector(
            "recovery-005-resubmission-after-restoration",
            "Byte-identical resubmission of the restored chain. Every per-vector invariant "
            "still passes; only the replay guard, holding the state recorded by 004, rejects "
            "it as replay_detected. Registry unchanged.",
            "FAIL", with_hops(original, [h0, h1, h2]), leaf, fixed_ref, recorded,
            failure_mode="replay_detected"),
    ]

    return {
        "spec_version": "delegation-chain-ref-v1",
        "description": (
            "Partial-chain recovery: restoration of missing chain bytes under the original "
            "delegation_chain_ref, followed by the replay check. Vectors MUST be run in order "
            "against one initially empty replay registry (state carries across the file). "
            "The middle hop of a valid 3-hop chain is omitted while the reference is held "
            "fixed: FAIL (digest mismatch, broken continuity); a substituted hop in the right "
            "position: FAIL (digest mismatch only); the exact hop in the wrong position: FAIL; "
            "the exact hop restored in its original position: PASS; a further submission of "
            "the restored chain: FAIL replay_detected. Failed attempts are not recorded, per "
            "the reference verifier's recording-order rule. This set tests byte restoration "
            "and failed-attempt replay handling. It does not test recovery of authority, "
            "automatic retrieval of missing artifacts, renewed authority after revocation, "
            "or parent_delegation_ref resolution, which remains a separate open question."
        ),
        "scope_agreed_at": "https://github.com/x402-foundation/x402/issues/2332#issuecomment-5890759053",
        "missing_hop_index": MISSING_HOP_INDEX,
        "original_chain_artifact": original,
        "delegation_chain_ref": fixed_ref,
        "delegation_artifacts": artifacts,
        "vectors": vectors,
        "provenance": {
            "authored_by": "TKCollective (Tanilo)",
            "verification_mode": "asserted",
            "independently_reproduced_by": [
                {
                    "party": "babyblueviper1",
                    "where": "giskard09/argentum-core#123 comment 6047862394; "
                              "script and transcript at "
                              "babyblueviper1/preaction-governance-conformance@08966cf",
                    "when": "2026-10-07T22:10:41Z",
                },
            ],
        },
    }


def main():
    data = build()
    out = HERE / "vectors.json"
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(data['vectors'])} vectors)")


if __name__ == "__main__":
    main()
