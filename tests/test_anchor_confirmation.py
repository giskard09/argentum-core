"""Conformance test: broadcast -> PENDING/non-null -> COMMITTED/FAILED.

Cierra el gap declarado en docs/spec/guarantee-model.md ("Open item, not a spec gap"):
arb_pay.py:anchor_action_ref escribe tx_hash al broadcast pero no hace polling del
receipt -- PENDING/non-null nunca transicionaba a un terminal explícito. Estas
pruebas verifican la transición completa contra el confirmation_predicate del spec
(tx receipt exists and status == 1) y los dos casos terminales que faltaban:
revert (status == 0) y non-arrival dentro de la freshness window.
"""
import os
import sys
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mycelium_trails
from argentum import _classify_anchor_receipt, ANCHOR_FRESHNESS_TTL_SECONDS


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "trails.db")
    mycelium_trails.init_db(db_path)
    return db_path


def _submitted_trail(db, tx_hash="0xabc123"):
    trail_id = mycelium_trails.record_trail(
        db, "agent-anchor-test", "oasis", "enter", uuid.uuid4().hex, karma_at_time=10,
    )
    mycelium_trails.set_trail_tx_hash(db, trail_id, tx_hash)
    return trail_id


# ── Positivo: broadcast -> PENDING/non-null -> COMMITTED ─────────────────────

def test_broadcast_to_pending_then_committed(db):
    trail_id = _submitted_trail(db)

    row = mycelium_trails.get_submitted_trails(db)[0]
    assert row["trail_id"] == trail_id
    assert row["anchor_submitted_at"] is not None  # PENDING/non-null: handle existe

    now = row["anchor_submitted_at"] + 5  # receipt llega rápido, bien dentro del TTL
    receipt = {"status": "0x1", "blockNumber": "0x2a"}
    action = _classify_anchor_receipt(receipt, row["anchor_submitted_at"], now)
    assert action == "confirm"

    mycelium_trails.confirm_trail_anchor(db, trail_id, block_number=42)

    trail = mycelium_trails.get_trail_by_id(db, trail_id)
    assert trail["anchor_status"] == "anchored"  # COMMITTED
    assert trail["anchor_block"] == 42
    # Trail confirmado ya no aparece en la cola de submitted -- transición cerrada.
    assert trail_id not in [r["trail_id"] for r in mycelium_trails.get_submitted_trails(db)]


# ── Negativo 1: broadcast -> revert -> FAILED (terminal inmediato) ───────────

def test_broadcast_to_revert_fails_immediately(db):
    trail_id = _submitted_trail(db)
    row = mycelium_trails.get_submitted_trails(db)[0]

    now = row["anchor_submitted_at"] + 5  # revert confirmado ya, sin esperar TTL
    receipt = {"status": "0x0", "blockNumber": "0x2a"}
    action = _classify_anchor_receipt(receipt, row["anchor_submitted_at"], now)
    assert action == "fail_revert"

    mycelium_trails.fail_trail_anchor(db, trail_id, "reverted")

    trail = mycelium_trails.get_trail_by_id(db, trail_id)
    assert trail["anchor_status"] == "failed"  # FAILED
    assert trail["anchor_fail_reason"] == "reverted"
    assert trail_id not in [r["trail_id"] for r in mycelium_trails.get_submitted_trails(db)]


# ── Negativo 2: sin receipt, TTL vencido -> FAILED (non-arrival-observed) ────

def test_no_receipt_past_ttl_fails_as_non_arrival(db):
    trail_id = _submitted_trail(db)
    row = mycelium_trails.get_submitted_trails(db)[0]

    now = row["anchor_submitted_at"] + ANCHOR_FRESHNESS_TTL_SECONDS + 1
    action = _classify_anchor_receipt(None, row["anchor_submitted_at"], now)
    assert action == "fail_timeout"

    mycelium_trails.fail_trail_anchor(db, trail_id, "non_arrival_timeout")

    trail = mycelium_trails.get_trail_by_id(db, trail_id)
    assert trail["anchor_status"] == "failed"
    assert trail["anchor_fail_reason"] == "non_arrival_timeout"


# ── Dentro del TTL sin receipt todavía: sigue PENDING, no se falla temprano ──

def test_no_receipt_within_ttl_still_waits(db):
    trail_id = _submitted_trail(db)
    row = mycelium_trails.get_submitted_trails(db)[0]

    now = row["anchor_submitted_at"] + 5
    action = _classify_anchor_receipt(None, row["anchor_submitted_at"], now)
    assert action == "wait"

    trail = mycelium_trails.get_trail_by_id(db, trail_id)
    assert trail["anchor_status"] == "submitted"  # PENDING/non-null, sin cambios
