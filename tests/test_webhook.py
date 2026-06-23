"""Tests para notify_webhook PAYG — setter/getter + guard SSRF."""
import os
import sys
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mycelium_trails
import webhook_notify


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "trails.db")
    mycelium_trails.init_db(db_path)
    return db_path


# ── setter / getter ───────────────────────────────────────────────────────────

def test_set_and_get_webhook(db):
    api_key = mycelium_trails.create_payg_account(db, "agent-hook")
    acct = mycelium_trails.set_payg_webhook(db, api_key, "https://example.com/hook")
    assert acct["notify_webhook"] == "https://example.com/hook"
    assert mycelium_trails.get_notify_webhook(db, "agent-hook") == "https://example.com/hook"


def test_clear_webhook(db):
    api_key = mycelium_trails.create_payg_account(db, "agent-hook")
    mycelium_trails.set_payg_webhook(db, api_key, "https://example.com/hook")
    mycelium_trails.set_payg_webhook(db, api_key, None)
    assert mycelium_trails.get_notify_webhook(db, "agent-hook") is None


def test_get_webhook_none_when_unset(db):
    mycelium_trails.create_payg_account(db, "agent-nohook")
    assert mycelium_trails.get_notify_webhook(db, "agent-nohook") is None


def test_set_webhook_unknown_api_key(db):
    assert mycelium_trails.set_payg_webhook(db, "no-such-key", "https://example.com") is None


# ── SSRF guard ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/hook",          # loopback
    "http://10.0.0.5/hook",           # private 10/8
    "http://192.168.1.10/hook",       # private 192.168/16
    "http://172.16.0.1/hook",         # private 172.16/12
    "http://169.254.169.254/latest",  # link-local / cloud metadata
    "http://0.0.0.0/hook",            # unspecified
    "ftp://example.com/hook",         # wrong scheme
    "file:///etc/passwd",             # wrong scheme
    "",                                # empty
    "not-a-url",                       # no scheme/host
])
def test_ssrf_blocks_unsafe(url):
    assert webhook_notify.is_safe_webhook_url(url) is False


@pytest.mark.parametrize("url", [
    "https://8.8.8.8/hook",   # public IP literal — sin DNS
    "http://1.1.1.1/hook",    # public IP literal
])
def test_ssrf_allows_public(url):
    assert webhook_notify.is_safe_webhook_url(url) is True


def test_notify_anchor_blocked_url_returns_false():
    # No debe hacer ningún POST a un destino interno.
    assert webhook_notify.notify_anchor(
        "http://127.0.0.1:8017/x", "trail-1", "0xabc", "2026-06-23T00:00:00Z"
    ) is False
