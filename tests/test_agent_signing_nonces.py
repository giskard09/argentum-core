"""agent_signing nonce store: persistence, expiry by time, fail-closed when full, safe keys,
bounds, and the asymmetric timestamp window."""
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import agent_signing as A  # noqa: E402

SK, VK = A.generate_keypair()
NOW = int(time.time())


def loader(_agent):
    return VK


def check(agent, nonce, ts=NOW, now=NOW, cache=None):
    sig = A.sign_request(SK, agent, ts, nonce)
    return A.verify_request(agent, sig, ts, nonce, now=now, pubkey_loader=loader, nonce_cache=cache)


def check_all(m):
    """Assert the behaviour on module `m` (the real one, or a mutant of it)."""
    import tempfile
    sk, vk = m.generate_keypair()
    ld = lambda _a: vk  # noqa: E731

    def chk(agent, nonce, ts=NOW, now=NOW, cache=None):
        sig = m.sign_request(sk, agent, ts, nonce)
        return m.verify_request(agent, sig, ts, nonce, now=now, pubkey_loader=ld, nonce_cache=cache)

    # single use
    c = m.NonceCache()
    assert chk("a", "n1", cache=c) is True
    assert chk("a", "n1", cache=c) is False

    # survives a restart (same file, new object); expiry purges by TIME, not by storage order
    path = os.path.join(tempfile.mkdtemp(), "n.db")
    c1 = m.NonceCache(db_path=path)
    assert chk("a", "n-persist", cache=c1) is True
    c2 = m.NonceCache(db_path=path)  # "restart"
    assert chk("a", "n-persist", now=NOW + 30, cache=c2) is False
    row = sqlite3.connect(path).execute("SELECT expires_at FROM nonces").fetchone()
    assert row[0] == NOW + m.SIGNATURE_TTL_SECONDS + 2  # kept until the signature cannot verify
    c3 = m.NonceCache(db_path=path)
    assert c3.check_and_store("old", expires_at=time.time() - 5) is True
    assert c3.check_and_store("other") is True            # this call purges the expired one
    assert c3.check_and_store("old", expires_at=time.time() + 60) is True  # purged, so it is new again

    # full: refuse, never clear
    c = m.NonceCache(max_size=3)
    assert [chk("a", f"f{i}", cache=c) for i in range(3)] == [True, True, True]
    assert chk("a", "f3", cache=c) is False              # full: refused
    assert chk("a", "f0", cache=c) is False              # an old nonce is STILL blocked (no wipe)

    # one agent cannot fill the table
    c = m.NonceCache(per_agent_max=2)
    assert chk("greedy", "x1", cache=c) and chk("greedy", "x2", cache=c)
    assert chk("greedy", "x3", cache=c) is False
    assert chk("other", "y1", cache=c) is True

    # unambiguous key: ("a", "b:c") and ("a:b", "c") are different
    c = m.NonceCache()
    assert chk("a", "b:c", cache=c) is True and chk("a:b", "c", cache=c) is True
    assert chk("a", "b:c", cache=c) is False

    # bounds
    c = m.NonceCache()
    assert chk("a", "n" * (m.MAX_NONCE_LEN + 1), cache=c) is False
    assert chk("a", "n" * m.MAX_NONCE_LEN, cache=c) is True
    assert chk("x" * (m.MAX_AGENT_ID_LEN + 1), "nn", cache=c) is False

    # window: up to 60 s old, only a few seconds ahead
    f = m.SIGNATURE_FUTURE_TOLERANCE_SECONDS
    assert chk("w", "w-past60", ts=NOW - 60, cache=m.NonceCache()) is True
    assert chk("w", "w-past61", ts=NOW - 61, cache=m.NonceCache()) is False
    assert chk("w", "w-fut", ts=NOW + f, cache=m.NonceCache()) is True
    assert chk("w", "w-fut+1", ts=NOW + f + 1, cache=m.NonceCache()) is False

    # nothing escapes verify_request: non-finite or absurd timestamps are plain refusals
    for bad in (float("inf"), float("-inf"), float("nan"), 10 ** 400, None, "x", [1]):
        sig = m.sign_request(sk, "a", NOW, "n-bad")
        assert m.verify_request("a", sig, bad, "n-bad", now=NOW, pubkey_loader=ld, nonce_cache=m.NonceCache()) is False, bad

    # durable flag: a file store says so, memory does not
    assert m.NonceCache().durable is False
    assert m.NonceCache(db_path=os.path.join(tempfile.mkdtemp(), "d.db")).durable is True
    assert m.NonceCache(db_path=os.path.join(tempfile.mkdtemp(), "no-such-dir", "d.db")).durable is False  # cannot open: memory

    # a store failure refuses (fail closed), it does not accept
    c = m.NonceCache()
    c._conn.close()
    assert chk("a", "closed", cache=c) is False


def test_nonce_store_behaviour():
    check_all(A)


def test_defaults_are_the_documented_ones():
    assert A.SIGNATURE_TTL_SECONDS == 60 and A.SIGNATURE_FUTURE_TOLERANCE_SECONDS == 30
    assert A.NONCE_CACHE_MAX >= 10_000 and A.MAX_NONCE_LEN == 128


def test_status_reports_whether_the_nonce_store_is_durable(tmp_path):
    from fastapi.testclient import TestClient
    sys.modules.pop("argentum", None)
    import argentum
    argentum.DB_PATH = tmp_path / "argentum.db"
    argentum.init_db()
    client = TestClient(argentum.app)
    assert client.get("/status").json()["nonce_store_durable"] is False   # tests run on the in-memory store
    argentum.agent_signing._nonce_cache.durable = True
    try:
        assert client.get("/status").json()["nonce_store_durable"] is True
    finally:
        argentum.agent_signing._nonce_cache.durable = False
