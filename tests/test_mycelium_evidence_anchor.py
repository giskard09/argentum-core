"""Tests for MyceliumAnchor — EvidenceAnchor community plugin."""

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from mycelium_evidence_anchor import (
    AnchorVerifyStatus,
    MyceliumAnchor,
    _compute_action_ref,
)


def _fake_trail_id():
    return "test-trail-0000-0000-0000-000000000001"


def _fake_tx():
    return "0xabc123"


def _anchor_response(trail_id, tx_hash, anchored_at="2026-05-14T10:00:00.000Z"):
    return {"trail_id": trail_id, "tx_hash": tx_hash, "anchored_at": anchored_at}


def _verify_response(evidence_hash, tx_hash, verified=True):
    return {
        "verified": verified,
        "tx_hash": tx_hash,
        "claims": {"evidence_hash": evidence_hash},
    }


# ---------------------------------------------------------------------------

class TestComputeActionRef:
    def test_deterministic(self):
        a = _compute_action_ref("agent-1", "agt:evidence_anchor", "agt-evidence", 1000)
        b = _compute_action_ref("agent-1", "agt:evidence_anchor", "agt-evidence", 1000)
        assert a == b

    def test_differs_on_agent(self):
        a = _compute_action_ref("agent-1", "agt:evidence_anchor", "agt-evidence", 1000)
        b = _compute_action_ref("agent-2", "agt:evidence_anchor", "agt-evidence", 1000)
        assert a != b

    def test_hex_sha256(self):
        ref = _compute_action_ref("x", "y", "z", 0)
        assert len(ref) == 64
        int(ref, 16)  # must be valid hex


# ---------------------------------------------------------------------------

class TestMyceliumAnchorAnchor:
    def _make_anchor(self):
        return MyceliumAnchor(agent_id="test-agent", base_url="https://test.example")

    @patch("mycelium_evidence_anchor.requests.post")
    def test_anchor_returns_receipt(self, mock_post):
        trail_id = _fake_trail_id()
        tx = _fake_tx()
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: _anchor_response(trail_id, tx),
        )

        anchor = self._make_anchor()
        evidence_hash = hashlib.sha256(b"test payload").hexdigest()
        receipt = anchor.anchor(evidence_hash, {})

        assert receipt.backend == "mycelium-trails"
        assert receipt.anchor_id == trail_id
        assert receipt.evidence_hash == evidence_hash
        assert receipt.metadata["tx_hash"] == tx

    @patch("mycelium_evidence_anchor.requests.post")
    def test_anchor_passes_parent_trail_id(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: _anchor_response(_fake_trail_id(), _fake_tx()),
        )
        anchor = self._make_anchor()
        anchor.anchor("hash", {"parent_trail_id": "parent-id", "root_trail_id": "root-id"})

        payload = mock_post.call_args.kwargs["json"]
        assert payload["parent_trail_id"] == "parent-id"
        assert payload["root_trail_id"] == "root-id"

    @patch("mycelium_evidence_anchor.requests.post")
    def test_anchor_raises_on_http_error(self, mock_post):
        import requests as req
        mock_post.side_effect = req.RequestException("timeout")
        anchor = self._make_anchor()
        with pytest.raises(RuntimeError, match="anchor failed"):
            anchor.anchor("hash", {})


# ---------------------------------------------------------------------------

class TestMyceliumAnchorVerify:
    def _make_anchor(self):
        return MyceliumAnchor(agent_id="test-agent", base_url="https://test.example")

    def _receipt(self, evidence_hash, tx=_fake_tx()):
        from mycelium_evidence_anchor import AnchorReceipt
        return AnchorReceipt(
            backend="mycelium-trails",
            anchor_id=_fake_trail_id(),
            anchored_at="2026-05-14T10:00:00.000Z",
            evidence_hash=evidence_hash,
            metadata={"tx_hash": tx, "action_ref": "abc123", "agent_id": "test-agent"},
        )

    @patch("mycelium_evidence_anchor.requests.get")
    def test_verify_verified(self, mock_get):
        eh = hashlib.sha256(b"payload").hexdigest()
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: _verify_response(eh, _fake_tx()),
        )
        anchor = self._make_anchor()
        result = anchor.verify(eh, self._receipt(eh))
        assert result.status == AnchorVerifyStatus.VERIFIED
        assert result.inclusion_proof is not None

    @patch("mycelium_evidence_anchor.requests.get")
    def test_verify_not_found(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"verified": False},
        )
        anchor = self._make_anchor()
        result = anchor.verify("hash", self._receipt("hash"))
        assert result.status == AnchorVerifyStatus.NOT_FOUND

    @patch("mycelium_evidence_anchor.requests.get")
    def test_verify_hash_mismatch(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: _verify_response("different_hash", _fake_tx()),
        )
        anchor = self._make_anchor()
        result = anchor.verify("my_hash", self._receipt("my_hash"))
        assert result.status == AnchorVerifyStatus.HASH_MISMATCH

    @patch("mycelium_evidence_anchor.requests.get")
    def test_verify_backend_unavailable(self, mock_get):
        import requests as req
        mock_get.side_effect = req.RequestException("connection refused")
        anchor = self._make_anchor()
        result = anchor.verify("hash", self._receipt("hash"))
        assert result.status == AnchorVerifyStatus.BACKEND_UNAVAILABLE
        assert "connection refused" in result.error_detail
