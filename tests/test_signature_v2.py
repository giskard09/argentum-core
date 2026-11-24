"""Signature v2 (opt-in, additive): binds service, method, path and body. v1 keeps working."""
import os
import sys
import time
import types
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import agent_signing as A  # noqa: E402

NOW = int(time.time())


# ---- unit level: runs against any module `m` that looks like agent_signing -----------------
def check_verify(m):
    sk, vk = m.generate_keypair()
    ld = lambda _a: vk  # noqa: E731
    body = {"a": 1, "b": "x", "signature": "s", "timestamp": 1, "nonce": "n", "sig_v": 2}
    h = m.body_sha256(body)

    def ok(sign_kw=None, verify_kw=None, nonce=None):
        nonce = nonce or uuid.uuid4().hex
        sk_kw = dict(aud="svc", method="POST", path="/p", body_sha256_hex=h)
        sk_kw.update(sign_kw or {})
        sig = m.sign_request_v2(sk, "ag", NOW, nonce, sk_kw["aud"], sk_kw["method"], sk_kw["path"], sk_kw["body_sha256_hex"])
        vk_kw = dict(sig_v=2, aud="svc", method="POST", path="/p", body_sha256_hex=h)
        vk_kw.update(verify_kw or {})
        return m.verify_request("ag", sig, NOW, nonce, now=NOW, pubkey_loader=ld, nonce_cache=m.NonceCache(), **vk_kw)

    assert ok() is True
    assert ok(verify_kw={"aud": "other"}) is False          # another service
    assert ok(verify_kw={"path": "/q"}) is False            # another route
    assert ok(verify_kw={"method": "GET"}) is False         # another method
    assert ok(verify_kw={"body_sha256_hex": "0" * 64}) is False  # another body
    assert ok(verify_kw={"method": "post"}) is True         # method is case-insensitive
    # v2 never falls back to v1 and v1 never passes as v2
    sig_v1 = m.sign_request(sk, "ag", NOW, "n-v1")
    assert m.verify_request("ag", sig_v1, NOW, "n-v1", now=NOW, pubkey_loader=ld, nonce_cache=m.NonceCache(),
                            sig_v=2, aud="svc", method="POST", path="/p", body_sha256_hex=h) is False
    sig_v2 = m.sign_request_v2(sk, "ag", NOW, "n-v2", "svc", "POST", "/p", h)
    assert m.verify_request("ag", sig_v2, NOW, "n-v2", now=NOW, pubkey_loader=ld, nonce_cache=m.NonceCache()) is False
    assert m.verify_request("ag", sig_v1, NOW, "n-v1b", now=NOW, pubkey_loader=ld, nonce_cache=m.NonceCache()) is False  # nonce differs
    assert m.verify_request("ag", m.sign_request(sk, "ag", NOW, "n-v1c"), NOW, "n-v1c", now=NOW, pubkey_loader=ld,
                            nonce_cache=m.NonceCache()) is True   # plain v1 still verifies
    # v2 needs every field supplied by the server
    for missing in ("aud", "method", "path", "body_sha256_hex"):
        assert ok(verify_kw={missing: None}) is False, missing
    # unknown version: not even a valid v1 signature passes under an unknown sig_v
    assert ok(verify_kw={"sig_v": 3}) is False
    assert m.verify_request("ag", m.sign_request(sk, "ag", NOW, "n-v3"), NOW, "n-v3", now=NOW, pubkey_loader=ld,
                            nonce_cache=m.NonceCache(), sig_v=3) is False
    # the v2 payload names its own version
    assert b'"sig_v":2' in m.build_payload_v2("ag", NOW, "n", "svc", "POST", "/p", h)
    # the body hash ignores the signature fields only
    assert m.body_sha256({"a": 1}) == m.body_sha256({"a": 1, "signature": "z", "nonce": "q", "timestamp": 9, "sig_v": 2})
    assert m.body_sha256({"a": 1}) != m.body_sha256({"a": 2})


def test_v2_signature_unit():
    check_verify(A)


# ---- integration: the argentum routes -------------------------------------------------------
def _app(tmp_path):
    sys.modules.pop("argentum", None)
    import argentum
    argentum.DB_PATH = tmp_path / "argentum.db"
    argentum.init_db()
    conn = argentum.get_db()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(wisdom)")]
    if "total_karma_real" not in cols:
        conn.execute("ALTER TABLE wisdom ADD COLUMN total_karma_real REAL DEFAULT 0.0")
    conn.execute("INSERT INTO trails (id, author_id, author_name, name, description, steps, price_sats, created_at) "
                 "VALUES ('t1', 'auth', 'A', 'n', 'd', '[]', 10, ?)", (argentum.now(),))
    conn.commit(); conn.close()
    return argentum, TestClient(argentum.app)


def _signed_body(body, path, sk, agent, aud="argentum", method="POST", v=2, ts=None):
    ts = ts or int(time.time()); nonce = uuid.uuid4().hex
    if v == 2:
        sig = A.sign_request_v2(sk, agent, ts, nonce, aud, method, path, A.body_sha256(body))
        return {**body, "signature": sig, "timestamp": ts, "nonce": nonce, "sig_v": 2}
    sig = A.sign_request(sk, agent, ts, nonce)
    return {**body, "signature": sig, "timestamp": ts, "nonce": nonce}


def check_integration(tmp_path):
    argentum, client = _app(tmp_path)
    sk, vk = A.generate_keypair()
    exe = {"executor_id": "exe-1", "executor_name": "E", "status": "success"}
    with patch.object(A, "_fetch_pubkey", return_value=vk), patch.object(A, "_fetch_pubkey_at", return_value=vk):
        def post(path, body):
            r = client.post(path, json=body)
            assert r.status_code == 200, r.text
            return r.json()

        r = post("/trails/t1/execute", _signed_body(exe, "/trails/t1/execute", sk, "exe-1"))
        assert (r["signed"], r["sig_v"]) == (True, 2), r
        r = post("/trails/t1/execute", _signed_body(exe, "/trails/t1/execute", sk, "exe-1", v=1))
        assert (r["signed"], r["sig_v"]) == (True, 1), r                      # v1 untouched
        r = post("/trails/t1/execute", exe)
        assert (r["signed"], r["sig_v"]) == (False, None), r                  # unsigned untouched
        # same v2 signature for another path / body / service / method -> not signed
        b = _signed_body(exe, "/trails/t2/execute", sk, "exe-1")
        assert post("/trails/t1/execute", b)["signed"] is False               # signed for another trail
        b = _signed_body(exe, "/trails/t1/execute", sk, "exe-1")
        b["status"] = "fail"
        assert post("/trails/t1/execute", b)["signed"] is False               # body changed after signing
        assert post("/trails/t1/execute", _signed_body(exe, "/trails/t1/execute", sk, "exe-1", aud="spore"))["signed"] is False
        assert post("/trails/t1/execute", _signed_body(exe, "/trails/t1/execute", sk, "exe-1", method="GET"))["signed"] is False
        # v2 signature without declaring sig_v (so read as v1), and a v1 signature declaring v2
        b = _signed_body(exe, "/trails/t1/execute", sk, "exe-1"); b.pop("sig_v")
        assert post("/trails/t1/execute", b)["signed"] is False
        b = _signed_body(exe, "/trails/t1/execute", sk, "exe-1", v=1); b["sig_v"] = 2
        assert post("/trails/t1/execute", b)["signed"] is False
        b = _signed_body(exe, "/trails/t1/execute", sk, "exe-1"); b["sig_v"] = 3
        assert post("/trails/t1/execute", b)["signed"] is False
        b = _signed_body(exe, "/trails/t1/execute", sk, "exe-1", v=1); b["sig_v"] = 3   # valid v1 signature, unknown version
        assert post("/trails/t1/execute", b)["signed"] is False
        # a signature captured on one route does not work on another
        reg = {"author_id": "exe-1", "author_name": "x", "name": "n", "description": "d",
               "steps": [{"service": "s", "tool": "t"}], "price_sats": 100}
        cap = _signed_body(exe, "/trails/t1/execute", sk, "exe-1")
        stolen = {**reg, **{k: cap[k] for k in ("signature", "timestamp", "nonce", "sig_v")}}
        assert post("/trails", stolen)["signed"] is False
        # sync handlers (report / rate) also take v2
        conn = argentum.get_db()
        conn.execute("INSERT INTO trail_executions (id, trail_id, executor_id, executor_name, status, created_at) "
                     "VALUES ('e9', 't1', 'someone', 'S', 'success', ?)", (argentum.now(),))
        conn.commit(); conn.close()
        rate = {"execution_id": "e9", "rating": 4, "rater_id": "rater-1"}
        r = post("/trails/t1/rate", _signed_body(rate, "/trails/t1/rate", sk, "rater-1"))
        assert (r["signed"], r["sig_v"]) == (True, 2), r


def test_v2_signature_on_argentum_routes(tmp_path):
    check_integration(tmp_path)
