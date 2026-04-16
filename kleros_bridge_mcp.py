"""
kleros-bridge MCP tool — SKELETON v0 (2026-04-15)

Bridges ARGENTUM disputes to Kleros Court v2 on Arbitrum One.
No real tx yet — this is the interface and stubbed flows pending
ArgentumArbitrable deploy + ReputationRegistry wiring.

Flow:
    1. agent (karma >= MINIMUM_KARMA_TO_DISPUTE=10) calls `open_dispute`
    2. tool builds evidence bundle (action_id, attestations, proof URL)
    3. posts evidence to EvidenceModule, creates dispute on KlerosCore
    4. returns disputeID; status polled via `get_dispute_status`
    5. on ruling, `apply_ruling` slashes karma per outcome

Kleros Arbitrum One addresses (verified 2026-04-15):
    KlerosCore       0x991d2df165670b9cac3B022f4B68D65b664222ea
    EvidenceModule   0x48e052B4A6dC4F30e90930F1CeaAFd83b3981EB3
    DisputeTemplateRegistry 0x0cFBaCA5C72e7Ca5fFABE768E135654fB3F2a5A2
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("kleros-bridge")

KLEROS_CORE = "0x991d2df165670b9cac3B022f4B68D65b664222ea"
EVIDENCE_MODULE = "0x48e052B4A6dC4F30e90930F1CeaAFd83b3981EB3"
DISPUTE_TEMPLATE_REGISTRY = "0x0cFBaCA5C72e7Ca5fFABE768E135654fB3F2a5A2"
ARGENTUM_ARBITRABLE = None  # pending deploy

DISPUTE_TYPES = {
    "false_attestation": {"metaEvidence": "metaEvidence/false_attestation.json", "courts": ["general"]},
    "false_action":      {"metaEvidence": "metaEvidence/false_action.json",      "courts": ["general"]},
    "sybil":             {"metaEvidence": "metaEvidence/sybil.json",             "courts": ["general"]},
    "attribution":       {"metaEvidence": "metaEvidence/attribution.json",       "courts": ["general"]},
}


@mcp.tool()
def open_dispute(action_id: str, dispute_type: str, evidence_uri: str, agent_id: str) -> dict:
    """Open a Kleros dispute over an ARGENTUM action. STUB."""
    if dispute_type not in DISPUTE_TYPES:
        return {"error": f"unknown dispute_type; valid: {list(DISPUTE_TYPES)}"}
    # TODO: check karma >= MINIMUM_KARMA_TO_DISPUTE
    # TODO: build evidence bundle, call ArgentumArbitrable.createDispute()
    return {
        "status": "not_implemented",
        "action_id": action_id,
        "dispute_type": dispute_type,
        "evidence_uri": evidence_uri,
        "agent_id": agent_id,
        "arbitrator": KLEROS_CORE,
    }


@mcp.tool()
def get_dispute_status(dispute_id: int) -> dict:
    """Poll Kleros for dispute state. STUB."""
    # TODO: eth_call KlerosCore.disputes(disputeID)
    return {"status": "not_implemented", "dispute_id": dispute_id}


@mcp.tool()
def submit_evidence(dispute_id: int, evidence_uri: str) -> dict:
    """Add evidence to an ongoing dispute. STUB."""
    # TODO: EvidenceModule.submitEvidence
    return {"status": "not_implemented", "dispute_id": dispute_id, "evidence_uri": evidence_uri}


@mcp.tool()
def apply_ruling(dispute_id: int) -> dict:
    """Execute ruling from Kleros on ARGENTUM (slash karma / restore). STUB."""
    # TODO: read ruling, map to karma ops in argentum-core
    return {"status": "not_implemented", "dispute_id": dispute_id}


@mcp.tool()
def list_dispute_types() -> dict:
    """Return supported dispute categories and their Kleros template IDs."""
    return DISPUTE_TYPES


if __name__ == "__main__":
    mcp.run()
