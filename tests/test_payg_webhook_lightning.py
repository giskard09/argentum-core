"""DEUDA_INTERNA 2026-10-20/26: /payg/webhook/lightning credited topup_payg
unconditionally on every "payment_received" notification, with no check
against the payment already having been processed. phoenixd, like most
webhook senders, redelivers on retry (timeout, non-2xx response, network
blip) -- the same notification can arrive more than once, and each arrival
credited the account again. Fix: dedupe on paymentHash before crediting,
the same existence-check-before-side-effect convention /payment/webhook
already uses, reusing the nonce table /nexus/trail uses for action_ref
replay protection.
"""
import hashlib
import hmac
import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _client(tmp_path):
    for mod in [m for m in list(sys.modules) if m == "argentum"]:
        del sys.modules[mod]
    import argentum  # noqa: WPS433
    argentum.TRAILS_DB = str(tmp_path / "trails.db")
    import mycelium_trails
    mycelium_trails.init_db(argentum.TRAILS_DB)
    argentum._ARB_PAY_OK = False  # no real on-chain calls from tests
    argentum._SMTP_OK = False     # no real email from tests
    return argentum, TestClient(argentum.app), mycelium_trails


def _signed_post(argentum, client, payload):
    body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(argentum.WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/payg/webhook/lightning",
        data=body,
        headers={"X-Phoenix-Signature": sig, "Content-Type": "application/json"},
    )


def test_webhook_credits_on_first_delivery(tmp_path):
    argentum, client, mycelium_trails = _client(tmp_path)
    api_key = mycelium_trails.create_payg_account(argentum.TRAILS_DB, "agent-ln")
    payload = {
        "type": "payment_received",
        "externalId": f"payg:{api_key}:10",
        "paymentHash": "hash-aaa111",
        "amountSat": 1000,
    }
    r = _signed_post(argentum, client, payload)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["balance"] == 10
    account = mycelium_trails.get_payg_account(argentum.TRAILS_DB, api_key)
    assert account["credit_trails"] == 10


def test_webhook_redelivery_is_a_noop_not_a_double_credit(tmp_path):
    """The exact gap: same paymentHash delivered twice must credit once."""
    argentum, client, mycelium_trails = _client(tmp_path)
    api_key = mycelium_trails.create_payg_account(argentum.TRAILS_DB, "agent-ln")
    payload = {
        "type": "payment_received",
        "externalId": f"payg:{api_key}:10",
        "paymentHash": "hash-bbb222",
        "amountSat": 1000,
    }
    first = _signed_post(argentum, client, payload)
    second = _signed_post(argentum, client, payload)  # phoenixd redelivers the same notification

    assert first.json()["status"] == "ok"
    assert second.json()["status"] == "already_processed"
    account = mycelium_trails.get_payg_account(argentum.TRAILS_DB, api_key)
    assert account["credit_trails"] == 10  # not 20


def test_webhook_different_payment_hash_credits_again(tmp_path):
    """Dedup is keyed on paymentHash, not on api_key -- a genuinely new
    payment from the same account must still credit."""
    argentum, client, mycelium_trails = _client(tmp_path)
    api_key = mycelium_trails.create_payg_account(argentum.TRAILS_DB, "agent-ln")
    _signed_post(argentum, client, {
        "type": "payment_received", "externalId": f"payg:{api_key}:10",
        "paymentHash": "hash-ccc333", "amountSat": 1000,
    })
    r2 = _signed_post(argentum, client, {
        "type": "payment_received", "externalId": f"payg:{api_key}:5",
        "paymentHash": "hash-ddd444", "amountSat": 500,
    })
    assert r2.json()["status"] == "ok"
    account = mycelium_trails.get_payg_account(argentum.TRAILS_DB, api_key)
    assert account["credit_trails"] == 15


def test_webhook_bad_signature_rejected(tmp_path):
    argentum, client, mycelium_trails = _client(tmp_path)
    api_key = mycelium_trails.create_payg_account(argentum.TRAILS_DB, "agent-ln")
    body = json.dumps({
        "type": "payment_received", "externalId": f"payg:{api_key}:10",
        "paymentHash": "hash-eee555",
    }).encode("utf-8")
    r = client.post(
        "/payg/webhook/lightning",
        data=body,
        headers={"X-Phoenix-Signature": "not-the-right-signature"},
    )
    assert r.status_code == 401
