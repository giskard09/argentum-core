"""Tests for v0.4 Ed25519 signature rollout across WRITE endpoints.

Covers submit_action, report_action, open_dispute and rate_trail_execution.
Verifies opt-in behaviour: unsigned requests keep working, signed requests
report signed=True in the response and (where applicable) persist it.
"""
import os
import sys
import time
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import agent_signing  # noqa: E402


def _client(tmp_path):
    # Fresh import so each test gets a clean module-level state
    for mod in [m for m in list(sys.modules) if m == "argentum"]:
        del sys.modules[mod]
    import argentum  # noqa: WPS433
    argentum.DB_PATH = tmp_path / "argentum.db"
    argentum.init_db()
    return argentum, TestClient(argentum.app)


def _signed_payload(agent_id: str):
    sk_b64, vk_b64 = agent_signing.generate_keypair()
    ts = int(time.time())
    nonce = uuid.uuid4().hex
    sig = agent_signing.sign_request(sk_b64, agent_id, ts, nonce)
    return vk_b64, {"signature": sig, "timestamp": ts, "nonce": nonce}


def test_submit_action_unsigned_keeps_working(tmp_path):
    _, client = _client(tmp_path)
    r = client.post(
        "/action/submit",
        json={
            "entity_id":   "alice",
            "entity_name": "Alice",
            "entity_type": "agent",
            "action_type": "WITNESS",
            "description": "unsigned submit",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["signed"] is False
    assert body["status"] == "pending"


def test_submit_action_signed_persists_and_reports(tmp_path):
    argentum, client = _client(tmp_path)
    agent_id = "alice-signed"
    vk, sig_fields = _signed_payload(agent_id)

    with patch.object(agent_signing, "_fetch_pubkey", return_value=vk):
        r = client.post(
            "/action/submit",
            json={
                "entity_id":   agent_id,
                "entity_name": "Alice",
                "entity_type": "agent",
                "action_type": "WITNESS",
                "description": "signed submit",
                **sig_fields,
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["signed"] is True

    # DB sanity
    conn = argentum.get_db()
    row = conn.execute(
        "SELECT signed FROM actions WHERE id = ?", (body["action_id"],)
    ).fetchone()
    conn.close()
    assert row["signed"] == 1


def test_report_action_signed_flag(tmp_path):
    argentum, client = _client(tmp_path)

    # Stand-alone "verified" action to be reported
    aid = "abcd1234"
    conn = argentum.get_db()
    conn.execute(
        "INSERT INTO actions (id, entity_id, entity_name, entity_type, "
        "action_type, description, proof, status, karma_value, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (aid, "poster", "Poster", "agent", "WITNESS", "bad claim",
         None, "verified", 5, argentum.now()),
    )
    conn.commit(); conn.close()

    reporter = "reporter-signed"
    vk, sig_fields = _signed_payload(reporter)
    with patch.object(agent_signing, "_fetch_pubkey", return_value=vk):
        r = client.post(
            f"/action/{aid}/report",
            json={"reporter_id": reporter, "reason": "false claim", **sig_fields},
        )
    assert r.status_code == 200, r.text
    assert r.json()["signed"] is True


def test_open_dispute_signed_flag(tmp_path):
    argentum, client = _client(tmp_path)

    aid = "dispute01"
    reporter = "reporter-karma"
    conn = argentum.get_db()
    conn.execute(
        "INSERT INTO actions (id, entity_id, entity_name, entity_type, "
        "action_type, description, proof, status, karma_value, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (aid, "poster", "Poster", "agent", "WITNESS", "claim",
         None, "verified", 5, argentum.now()),
    )
    # Reporter with enough karma to dispute
    conn.execute(
        "INSERT INTO wisdom (entity_id, entity_name, entity_type, total_karma, "
        "verified_actions, attestations_given) VALUES (?, ?, ?, ?, ?, ?)",
        (reporter, "Reporter", "agent", 50, 0, 0),
    )
    conn.commit(); conn.close()

    vk, sig_fields = _signed_payload(reporter)
    with patch.object(agent_signing, "_fetch_pubkey", return_value=vk):
        r = client.post(
            f"/action/{aid}/dispute",
            json={"reporter_id": reporter, "reason": "fake proof", **sig_fields},
        )
    assert r.status_code == 200, r.text
    assert r.json()["signed"] is True


def test_rate_trail_signed_flag(tmp_path):
    argentum, client = _client(tmp_path)

    trail_id = "trail01"
    exec_id = "exec01"
    conn = argentum.get_db()
    conn.execute(
        "INSERT INTO trails (id, author_id, author_name, name, description, "
        "steps, price_sats, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (trail_id, "author", "Author", "trail-name", "desc",
         "[]", 10, argentum.now()),
    )
    conn.execute(
        "INSERT INTO trail_executions (id, trail_id, executor_id, executor_name, "
        "status, output_hash, payment_hash, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (exec_id, trail_id, "other-executor", "Other", "success",
         None, None, argentum.now()),
    )
    conn.commit(); conn.close()

    rater = "rater-signed"
    vk, sig_fields = _signed_payload(rater)
    with patch.object(agent_signing, "_fetch_pubkey", return_value=vk):
        r = client.post(
            f"/trails/{trail_id}/rate",
            json={
                "execution_id": exec_id,
                "rating":       5,
                "rater_id":     rater,
                **sig_fields,
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rating"] == 5
    assert body["signed"] is True


def test_rate_trail_unsigned_keeps_working(tmp_path):
    argentum, client = _client(tmp_path)

    trail_id = "trail02"
    exec_id = "exec02"
    conn = argentum.get_db()
    conn.execute(
        "INSERT INTO trails (id, author_id, author_name, name, description, "
        "steps, price_sats, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (trail_id, "author", "Author", "trail-name", "desc",
         "[]", 10, argentum.now()),
    )
    conn.execute(
        "INSERT INTO trail_executions (id, trail_id, executor_id, executor_name, "
        "status, output_hash, payment_hash, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (exec_id, trail_id, "other-executor", "Other", "success",
         None, None, argentum.now()),
    )
    conn.commit(); conn.close()

    r = client.post(
        f"/trails/{trail_id}/rate",
        json={"execution_id": exec_id, "rating": 4},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rating"] == 4
    assert body["signed"] is False
