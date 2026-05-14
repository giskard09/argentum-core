"""
Mycelium Trails — community plugin for the AGT EvidenceAnchor SPI.

Implements EvidenceAnchor (anchor + verify) by writing to Mycelium Trails
on Base mainnet and reading back via the argentum.rgiskard.xyz API.

Install:
    pip install requests  # only external dependency

Registration (explicit, as required by AGT):
    from mycelium_evidence_anchor import MyceliumAnchor
    agt_registry.register("mycelium", MyceliumAnchor())

Conforms to: MYCELIUM-EXTERNAL-ANCHOR-PROPOSAL.md (v3)
SPI: EvidenceAnchor ABC (agt-evidence package)
"""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import requests

# ---------------------------------------------------------------------------
# Inline SPI stubs — used when agt-evidence is not installed.
# Replace with: from agt_evidence import EvidenceAnchor, AnchorReceipt, ...
# ---------------------------------------------------------------------------

class AnchorVerifyStatus(str, Enum):
    VERIFIED = "VERIFIED"
    NOT_FOUND = "NOT_FOUND"
    HASH_MISMATCH = "HASH_MISMATCH"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"


@dataclass
class InclusionProof:
    tx_hash: str
    block_number: Optional[int] = None
    explorer_url: Optional[str] = None


@dataclass
class AnchorReceipt:
    backend: str
    anchor_id: str        # trail_id
    anchored_at: str      # RFC 3339 UTC
    evidence_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnchorVerifyResult:
    status: AnchorVerifyStatus
    evidence_hash: str
    inclusion_proof: Optional[InclusionProof] = None
    error_detail: Optional[str] = None


class EvidenceAnchor(ABC):
    @abstractmethod
    def anchor(self, evidence_hash: str, metadata: dict[str, Any]) -> AnchorReceipt: ...

    @abstractmethod
    def verify(self, evidence_hash: str, receipt: AnchorReceipt) -> AnchorVerifyResult: ...


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

_BASE_URL = "https://argentum.rgiskard.xyz"
_BACKEND_NAME = "mycelium-trails"
_DEFAULT_TIMEOUT = 10  # seconds


class MyceliumAnchor(EvidenceAnchor):
    """
    AGT EvidenceAnchor community plugin backed by Mycelium Trails on Base mainnet.

    anchor() writes a trail record and returns a receipt containing the trail_id
    and the Base tx hash. verify() confirms the evidence_hash is recorded at that
    trail_id via the public /trails/verify endpoint.

    Append-only guarantee: Mycelium Trails are immutable once anchored on Base.
    Modification or deletion of anchored records is not permitted.
    """

    def __init__(
        self,
        agent_id: str = "agt-evidence-anchor",
        base_url: str = _BASE_URL,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self.agent_id = agent_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # anchor
    # ------------------------------------------------------------------

    def anchor(self, evidence_hash: str, metadata: dict[str, Any]) -> AnchorReceipt:
        """
        Writes evidence_hash to Mycelium Trails.

        metadata keys used (all optional):
          - action_type  (str)  default: "agt:evidence_anchor"
          - scope        (str)  default: "agt-evidence"
          - agent_id     (str)  overrides instance agent_id for this call
        """
        agent_id = metadata.get("agent_id", self.agent_id)
        action_type = metadata.get("action_type", "agt:evidence_anchor")
        scope = metadata.get("scope", "agt-evidence")
        ts = int(time.time())

        action_ref = _compute_action_ref(agent_id, action_type, scope, ts)

        payload = {
            "agent_id": agent_id,
            "service": "agt-evidence",
            "operation": action_type,
            "action_ref": action_ref,
            "payment_hash": evidence_hash,  # evidence_hash doubles as payment_hash for AGT use
            "timestamp": ts,
            "claims": {
                "evidence_hash": evidence_hash,
                "source": "agt-evidence-anchor",
                **{k: v for k, v in metadata.items() if k not in ("agent_id", "action_type", "scope")},
            },
            "success": True,
            "scope": scope,
        }

        # Optional chaining fields
        if "parent_trail_id" in metadata:
            payload["parent_trail_id"] = metadata["parent_trail_id"]
        if "root_trail_id" in metadata:
            payload["root_trail_id"] = metadata["root_trail_id"]

        try:
            resp = requests.post(
                f"{self.base_url}/trails",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"MyceliumAnchor.anchor failed: {exc}") from exc

        trail_id = data.get("trail_id", "")
        tx_hash = data.get("tx_hash") or data.get("payment_hash", "")
        anchored_at = data.get("anchored_at") or data.get("timestamp", "")

        return AnchorReceipt(
            backend=_BACKEND_NAME,
            anchor_id=trail_id,
            anchored_at=anchored_at,
            evidence_hash=evidence_hash,
            metadata={
                "tx_hash": tx_hash,
                "action_ref": action_ref,
                "agent_id": agent_id,
            },
        )

    # ------------------------------------------------------------------
    # verify
    # ------------------------------------------------------------------

    def verify(self, evidence_hash: str, receipt: AnchorReceipt) -> AnchorVerifyResult:
        """
        Confirms evidence_hash is recorded at receipt.anchor_id (trail_id).

        Calls GET /trails/verify?agent_id=X&action_ref=Y — no API key required.
        Falls back to GET /trails/{trail_id} if action_ref is not in receipt metadata.
        """
        action_ref = receipt.metadata.get("action_ref")
        agent_id = receipt.metadata.get("agent_id", self.agent_id)

        try:
            if action_ref:
                resp = requests.get(
                    f"{self.base_url}/trails/verify",
                    params={"agent_id": agent_id, "action_ref": action_ref},
                    timeout=self.timeout,
                )
            else:
                resp = requests.get(
                    f"{self.base_url}/trails/{receipt.anchor_id}",
                    timeout=self.timeout,
                )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            return AnchorVerifyResult(
                status=AnchorVerifyStatus.BACKEND_UNAVAILABLE,
                evidence_hash=evidence_hash,
                error_detail=str(exc),
            )

        if not data.get("verified", False) and "trail_id" not in data:
            return AnchorVerifyResult(
                status=AnchorVerifyStatus.NOT_FOUND,
                evidence_hash=evidence_hash,
            )

        # Confirm the evidence_hash stored in claims matches
        stored_hash = (
            data.get("claims", {}).get("evidence_hash")
            or data.get("payment_hash")
        )
        if stored_hash and stored_hash != evidence_hash:
            return AnchorVerifyResult(
                status=AnchorVerifyStatus.HASH_MISMATCH,
                evidence_hash=evidence_hash,
                error_detail=f"stored: {stored_hash}",
            )

        tx_hash = data.get("tx_hash") or receipt.metadata.get("tx_hash", "")
        proof = InclusionProof(
            tx_hash=tx_hash,
            explorer_url=f"https://basescan.org/tx/{tx_hash}" if tx_hash else None,
        ) if tx_hash else None

        return AnchorVerifyResult(
            status=AnchorVerifyStatus.VERIFIED,
            evidence_hash=evidence_hash,
            inclusion_proof=proof,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_action_ref(agent_id: str, action_type: str, scope: str, timestamp: int) -> str:
    payload = f"{agent_id}:{action_type}:{scope}:{timestamp}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
