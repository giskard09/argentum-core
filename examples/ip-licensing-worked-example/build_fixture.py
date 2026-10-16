"""
ip-licensing-worked-example — build script (2026-10-16)

Composes three EXISTING, already-stable specs into one end-to-end IP
licensing scenario — no new primitive is introduced here:

  1. anchoring-precedence-ref-v1  -> creation precedence of the IP asset
  2. delegation-chain-ref-v1      -> license chain of custody (creator -> licensee -> sub-licensee)
  3. action_ref (v1)              -> proof the royalty settlement actually executed

Every hash below is computed, not invented — run this script to
reproduce fixture.json byte-for-byte.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jcs import jcs_bytes  # noqa: E402  (repo-root canonical JCS implementation)


def sha256_hex(preimage: dict) -> str:
    return hashlib.sha256(jcs_bytes(preimage)).hexdigest()


# ---------------------------------------------------------------------------
# Scenario: "Modular Thermal Exchanger Design v2"
# Creator Lucía Reyes registers the design, licenses manufacturing rights to
# a distributor, who sub-licenses regional manufacturing to a factory. The
# factory's royalty payment is the leaf action. Months later a third party
# claims independent invention -- anchoring_precedence_ref is what lets a
# verifier confirm Lucía's registration predates that claim without trusting
# either side's account of events.
# ---------------------------------------------------------------------------

# 1. anchoring-precedence-ref-v1 -- creation precedence
anchoring_envelope = {
    "trail_id": "ip-reg:thermal-exchanger-v2:lucia-reyes",
    "anchor_block_time": 1756728000,          # 2025-09-01T12:00:00Z (registration anchor)
    "mechanism": "on-chain",
    "outcome_ts_ms": 1758369600000,           # 2025-09-20T12:00:00Z (competing claim surfaces)
    "version": "anchoring-precedence-ref-v1",
}
anchoring_precedence_ref = sha256_hex(anchoring_envelope)

# 2a. delegation-ref -- hop 1: creator -> distributor
delegation_artifact_hop1 = {
    "delegator": "ip:lucia-reyes",
    "delegatee": "manufacturing-co",
    "capability": "manufacture",
    "scope": "license:manufacture:thermal-exchanger-v2",
    "expires_at": "2027-09-01T00:00:00.000Z",
    "policy_version": "pil-v1",
    "version": "delegation-ref-v1",
}
delegation_ref_hop1 = sha256_hex(delegation_artifact_hop1)

# 2b. delegation-ref -- hop 2: distributor -> regional factory (sub-license)
delegation_artifact_hop2 = {
    "delegator": "manufacturing-co",
    "delegatee": "regional-fab-co",
    "capability": "manufacture",
    "scope": "license:manufacture:thermal-exchanger-v2:region=LATAM",
    "expires_at": "2027-09-01T00:00:00.000Z",
    "policy_version": "pil-v1",
    "version": "delegation-ref-v1",
}
delegation_ref_hop2 = sha256_hex(delegation_artifact_hop2)

# 3. action_ref (v1) -- leaf action: regional factory settles royalty
action_preimage = {
    "agent_id": "regional-fab-co",
    "action_type": "royalty:settle",
    "scope": "license:manufacture:thermal-exchanger-v2:region=LATAM:q3-2026",
    "timestamp": "2026-10-01T00:00:00.000Z",
}
leaf_action_ref = sha256_hex(action_preimage)

# 2c. delegation-chain-ref-v1 -- binds both hops + the leaf action together
chain_artifact = {
    "chain_id": "chain:thermal-exchanger-v2:lucia-to-regionalfab",
    "hops": [
        {
            "delegator": "ip:lucia-reyes",
            "delegatee": "manufacturing-co",
            "delegation_ref": delegation_ref_hop1,
            "scope": "license:manufacture:thermal-exchanger-v2",
        },
        {
            "delegator": "manufacturing-co",
            "delegatee": "regional-fab-co",
            "delegation_ref": delegation_ref_hop2,
            "scope": "license:manufacture:thermal-exchanger-v2:region=LATAM",
        },
    ],
    "leaf_action_ref": leaf_action_ref,
    "root_delegator": "ip:lucia-reyes",
    "scope": "license:manufacture:thermal-exchanger-v2",
    "version": "delegation-chain-ref-v1",
}
delegation_chain_ref = sha256_hex(chain_artifact)

fixture = {
    "scenario": "ip-licensing-worked-example-v1",
    "precedence": {
        "envelope": anchoring_envelope,
        "anchoring_precedence_ref": anchoring_precedence_ref,
    },
    "custody_chain": {
        "hop_artifacts": [delegation_artifact_hop1, delegation_artifact_hop2],
        "chain_artifact": chain_artifact,
        "delegation_chain_ref": delegation_chain_ref,
    },
    "settlement": {
        "preimage": action_preimage,
        "action_ref": leaf_action_ref,
    },
}

if __name__ == "__main__":
    out = Path(__file__).with_name("fixture.json")
    out.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n")
    print(f"anchoring_precedence_ref = {anchoring_precedence_ref}")
    print(f"delegation_ref (hop1)    = {delegation_ref_hop1}")
    print(f"delegation_ref (hop2)    = {delegation_ref_hop2}")
    print(f"delegation_chain_ref     = {delegation_chain_ref}")
    print(f"action_ref (leaf)        = {leaf_action_ref}")
    print(f"written -> {out}")
