"""
Deterministic generator for mid-hop-revocation/vectors.json.

Re-running this script must reproduce vectors.json byte for byte. It derives
every digest with the same functions the reference verifier uses
(../verify.py: jcs, sha256hex, compute_action_ref), so the fixture cannot drift
from the verifier's own derivation.

Scope (agreed on x402-foundation/x402#2332, comments 5878267660, 5887938781,
5890759053, 5940312632): a structural differential only. The same chain and
leaf bytes are verified with and without a revocation artifact for the
mid-chain hop (hops[1]); both PASS. A broken-continuity control is verified
the same two ways; both FAIL. The revocation artifact targets the hop with
`revoked_delegation_ref` as merged in giskard09/argentum-core#112
(c277309b), not with `revoked_action_ref` as a stand-in.

Usage: python3 build.py
"""

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

FIELD_PIN = "c277309b0d51dd3dca87d3c7c07688a80021a467"
EXPIRES_AT = "2026-12-31T00:00:00.000Z"
POLICY_VERSION = "2026-10-01"
LEAF_TIMESTAMP = "2026-10-05T12:00:00.000Z"
REVOKED_AT = "2026-10-03T09:00:00.000Z"
REVOKED_HOP_INDEX = 1


def delegation_artifact(delegator, delegatee, capability, scope, parent_ref):
    art = {
        "capability": capability,
        "delegatee": delegatee,
        "delegator": delegator,
        "expires_at": EXPIRES_AT,
        "policy_version": POLICY_VERSION,
        "scope": scope,
        "version": "delegation-ref-v1",
    }
    if parent_ref is not None:
        art["parent_delegation_ref"] = parent_ref
    return dict(sorted(art.items()))


def build_chain(chain_id, hop2_delegator):
    """3-hop chain agent-a -> agent-b -> agent-c -> agent-d, scope narrowing at the leaf hop.

    hop2_delegator == "agent-c" gives a continuous chain. Any other value breaks
    chain_continuity at hop 1 (hops[1].delegatee != hops[2].delegator) and nothing
    else: the delegation_chain_ref is recomputed over the broken artifact, so the
    only failure the reference verifier reports is chain_break.
    """
    hop_specs = [
        ("agent-a", "agent-b", "delegate", "mycelium:payment"),
        ("agent-b", "agent-c", "delegate", "mycelium:payment"),
        (hop2_delegator, "agent-d", "payment.route", "mycelium:payment:route"),
    ]
    artifacts, hops, parent = [], [], None
    for delegator, delegatee, capability, scope in hop_specs:
        art = delegation_artifact(delegator, delegatee, capability, scope, parent)
        delegation_ref = sha256hex(jcs(art))
        artifacts.append(art)
        hops.append({"delegatee": delegatee, "delegator": delegator,
                     "delegation_ref": delegation_ref, "scope": scope})
        parent = delegation_ref
    leaf_preimage = {
        "agent_id": "agent-d",
        "action_type": "payment.route",
        "scope": "mycelium:payment:route",
        "timestamp": LEAF_TIMESTAMP,
    }
    chain = {
        "chain_id": chain_id,
        "hops": hops,
        "leaf_action_ref": compute_action_ref(leaf_preimage),
        "root_delegator": "agent-a",
        "scope": "mycelium:payment",
        "version": "delegation-chain-ref-v1",
    }
    return chain, artifacts, leaf_preimage


def revocation_for(chain):
    hop = chain["hops"][REVOKED_HOP_INDEX]
    artifact = dict(sorted({
        "reason": "grant_withdrawn",
        "revocation_key": "rev_mid_hop_001",
        "revoked_at": REVOKED_AT,
        "revoked_delegation_ref": hop["delegation_ref"],
        "revoker": hop["delegator"],
        "scope": hop["scope"],
        "version": "revocation-ref-v1",
    }.items()))
    action_preimage = {
        "action_type": "authorization.revoke",
        "agent_id": hop["delegator"],
        "scope": hop["scope"],
        "timestamp": REVOKED_AT,
    }
    return {
        "revocation_artifact": artifact,
        "revocation_ref": sha256hex(jcs(artifact)),
        "revocation_action_preimage": action_preimage,
        "revocation_action_ref": compute_action_ref(action_preimage),
    }


def vector(vid, description, expected, chain, artifacts, leaf, revocation=None, failure_mode=None):
    v = {"id": vid, "description": description, "expected": expected}
    if failure_mode:
        v["failure_mode"] = failure_mode
    v["chain_artifact"] = chain
    v["delegation_artifacts"] = artifacts
    v["leaf_preimage"] = leaf
    v["delegation_chain_ref"] = sha256hex(jcs(chain))
    if revocation:
        v.update(revocation)
    return v


def build():
    chain1, arts1, leaf1 = build_chain("chain-mid-hop-revocation-001", "agent-c")
    chain2, arts2, leaf2 = build_chain("chain-mid-hop-revocation-002", "agent-x")
    revocation = revocation_for(chain1)
    assert chain2["hops"][REVOKED_HOP_INDEX] == chain1["hops"][REVOKED_HOP_INDEX]

    vectors = [
        vector(
            "mid-hop-revocation-001-baseline",
            "Continuous 3-hop chain (agent-a -> agent-b -> agent-c -> agent-d), "
            "mycelium:payment narrowing to mycelium:payment:route at the leaf hop. "
            "No revocation artifact submitted. Fresh replay registry.",
            "PASS", chain1, arts1, leaf1),
        vector(
            "mid-hop-revocation-001-with-revocation",
            "Byte-identical chain_artifact and leaf_preimage to the baseline. The vector "
            "additionally carries a revocation_artifact whose revoked_delegation_ref is "
            "hops[1].delegation_ref (agent-b's grant to agent-c), revoked at "
            f"{REVOKED_AT}, before the leaf action at {LEAF_TIMESTAMP}. The reference "
            "verifier's structural verdict is expected to be identical to the baseline: "
            "none of its checks reads revocation_artifact, revocation_ref or "
            "revoked_delegation_ref. Fresh replay registry.",
            "PASS", chain1, arts1, leaf1, revocation),
        vector(
            "mid-hop-revocation-002-broken-continuity-baseline",
            "Control. hops[0] and hops[1] are byte-identical to chain 001; hops[2] is "
            "granted by agent-x, not by hops[1].delegatee agent-c, so chain_continuity "
            "breaks at hop 1. delegation_chain_ref is recomputed over this artifact, so "
            "chain_break is the only failure. No revocation artifact. Fresh replay registry.",
            "FAIL", chain2, arts2, leaf2, failure_mode="chain_break at hop 1"),
        vector(
            "mid-hop-revocation-002-broken-continuity-with-revocation",
            "Control, byte-identical chain_artifact and leaf_preimage to "
            "002-broken-continuity-baseline, submitted with the same revocation_artifact "
            "as 001-with-revocation (hops[1] is the same hop in both chains). Expected to "
            "FAIL for the same single reason, chain_break at hop 1: revocation metadata "
            "neither changes a passing structural verdict nor masks a failing one. "
            "Fresh replay registry.",
            "FAIL", chain2, arts2, leaf2, revocation, failure_mode="chain_break at hop 1"),
    ]

    return {
        "spec_version": "delegation-chain-ref-v1",
        "description": (
            "Mid-hop revocation, structural differential. The same chain_artifact and "
            "leaf_preimage are verified twice, with and without a revocation_artifact for "
            "the mid-chain hop (hops[1]); both PASS. A broken-continuity control is verified "
            "the same two ways; both FAIL with the same single failure. Each vector runs "
            "against a fresh replay registry. The revocation artifact targets the hop with "
            "revoked_delegation_ref (revocation-ref.md, merged in argentum-core#112 at "
            "c277309b); it carries no revoked_action_ref. This set asserts only that "
            "revocation metadata does not change the reference verifier's structural "
            "verdict. It asserts nothing about present authority, cascade rejection or "
            "future-use blocking, and does not cover parent_delegation_ref resolution."
        ),
        "scope_agreed_at": "https://github.com/x402-foundation/x402/issues/2332#issuecomment-5890759053",
        "field_definition_pin": {
            "field": "revoked_delegation_ref",
            "spec": "docs/spec/revocation-ref.md",
            "commit": FIELD_PIN,
            "pull_request": "https://github.com/giskard09/argentum-core/pull/112",
        },
        "revoked_hop_index": REVOKED_HOP_INDEX,
        "pairs": [
            {"baseline": "mid-hop-revocation-001-baseline",
             "with_revocation": "mid-hop-revocation-001-with-revocation",
             "expected": "PASS"},
            {"baseline": "mid-hop-revocation-002-broken-continuity-baseline",
             "with_revocation": "mid-hop-revocation-002-broken-continuity-with-revocation",
             "expected": "FAIL"},
        ],
        "vectors": vectors,
        "provenance": {
            "authored_by": "TKCollective (Tanilo)",
            "verification_mode": "asserted",
            "independently_reproduced_by": [],
        },
    }


def main():
    data = build()
    out = HERE / "vectors.json"
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(data['vectors'])} vectors)")


if __name__ == "__main__":
    main()
