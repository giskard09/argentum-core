"""Odd JSON bodies over HTTP with sig_v=2 are unsigned (or refused), never a server error."""
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
    sys.modules.pop("argentum", None)
    import argentum
    argentum.DB_PATH = tmp_path / "argentum.db"
    argentum.init_db()
    conn = argentum.get_db()
    conn.execute("INSERT INTO trails (id, author_id, author_name, name, description, steps, price_sats, created_at) "
                 "VALUES ('t1', 'au', 'au', 'n', 'd', '[]', 10, ?)", (argentum.now(),))
    conn.commit()
    conn.close()
    return TestClient(argentum.app, raise_server_exceptions=False)


@pytest.mark.parametrize("extra", ['"x": 1152921504606846977', '"x": "\\ud800"', '"x": NaN', '"x": 1e400',
                                   '"x": ' + "[" * 400 + "]" * 400])
def test_odd_body_is_never_a_500_and_never_signed(tmp_path, extra):
    c = _client(tmp_path)
    sk, vk = agent_signing.generate_keypair()
    ts, nonce = int(time.time()), uuid.uuid4().hex
    sig = agent_signing.sign_request_v2(sk, "ex", ts, nonce, "argentum", "POST", "/trails/t1/execute", "0" * 64)
    raw = ('{"executor_id": "ex", "executor_name": "x", "status": "success", "signature": "%s", "timestamp": %d, '
           '"nonce": "%s", "sig_v": 2, %s}' % (sig, ts, nonce, extra))
    with patch.object(agent_signing, "_fetch_pubkey", return_value=vk), \
         patch.object(agent_signing, "_fetch_pubkey_at", return_value=vk):
        r = c.post("/trails/t1/execute", content=raw.encode(), headers={"content-type": "application/json"})
    assert r.status_code < 500, r.text[:200]
    if r.status_code == 200:
        assert r.json()["author_karma_awarded"] == 0
        assert r.json()["sig_v"] is None
