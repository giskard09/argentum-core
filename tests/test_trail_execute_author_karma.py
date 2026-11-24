"""A trail's author earns no karma from their own execution (same identity, however written)."""
import os
import sys
import time
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import agent_signing  # noqa: E402


def _setup(tmp_path):
    sys.modules.pop("argentum", None)
    import argentum
    argentum.DB_PATH = tmp_path / "argentum.db"
    argentum.init_db()
    conn = argentum.get_db()
    conn.execute(
        "INSERT INTO trails (id, author_id, author_name, name, description, steps, price_sats, created_at) "
        "VALUES ('t1', 'Author-1', 'Author', 'n', 'd', '[]', 10, ?)", (argentum.now(),))
    conn.commit(); conn.close()
    return argentum, TestClient(argentum.app)


def _karma(argentum, entity_id):
    conn = argentum.get_db()
    row = conn.execute("SELECT total_karma FROM wisdom WHERE entity_id = ?", (entity_id,)).fetchone()
    conn.close()
    return row["total_karma"] if row else 0


def _run(client, executor_id, status="success"):
    sk, vk = agent_signing.generate_keypair()
    ts, nonce = int(time.time()), uuid.uuid4().hex
    body = {"executor_id": executor_id, "executor_name": "x", "status": status,
            "signature": agent_signing.sign_request(sk, executor_id, ts, nonce),
            "timestamp": ts, "nonce": nonce}
    with patch.object(agent_signing, "_fetch_pubkey", return_value=vk):
        return client.post("/trails/t1/execute", json=body)


def test_other_executor_still_earns_the_author_karma(tmp_path):
    a, c = _setup(tmp_path)
    r = _run(c, "someone-else")
    assert r.status_code == 200, r.text
    assert r.json()["author_karma_awarded"] == a.TRAIL_AUTHOR_KARMA_REWARD
    assert r.json()["author_karma_withheld"] is None
    assert _karma(a, "Author-1") == a.TRAIL_AUTHOR_KARMA_REWARD


def test_author_running_own_trail_earns_nothing_but_is_recorded(tmp_path):
    a, c = _setup(tmp_path)
    for written in ("Author-1", "author-1", "  AUTHOR-1 "):
        r = _run(c, written)
        assert r.status_code == 200, r.text
        assert r.json()["author_karma_awarded"] == 0, written
        assert r.json()["author_karma_withheld"] == "executor_is_author", written
    assert _karma(a, "Author-1") == 0
    conn = a.get_db()
    assert conn.execute("SELECT executions FROM trails WHERE id='t1'").fetchone()["executions"] == 3
    conn.close()


def test_same_identity_helper():
    sys.modules.pop("argentum", None)
    import argentum
    assert argentum._same_identity("A-1", "a-1") and argentum._same_identity(" a ", "A")
    assert not argentum._same_identity("a", "b") and not argentum._same_identity(None, "a")
