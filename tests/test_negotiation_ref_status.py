"""negotiation_ref_status: el colapso silencioso de la descarga del PDF RSA.

Hasta 2026-09-22 el handler /webhook/docuseal hacía `except Exception: pass`
alrededor de la descarga del PDF firmado: si fallaba (URL fuera de la
allowlist, status != 200, error de red), negotiation_ref quedaba None y el
trail se registraba igual -- "no se pudo obtener el artefacto" era
indistinguible de "no hubo negociación". Es el colapso que prohíbe
verify-failure-mode-ref invariante 1 (reason codes must remain
distinguishable). Estos tests fijan que cada causa termina en un estado
propio, persistido en el trail y visible en verify_chain().
"""
import asyncio
import hashlib
import json
import os
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mycelium_trails

PDF_BYTES = b"%PDF-1.7 signed RSA test fixture"
ALLOWED_URL = "https://docuseal.com/file/signed.pdf"


def _load_argentum(tmp_path):
    for mod in [m for m in list(sys.modules) if m == "argentum"]:
        del sys.modules[mod]
    import argentum  # noqa: WPS433
    argentum.TRAILS_DB = str(tmp_path / "trails.db")
    mycelium_trails.init_db(argentum.TRAILS_DB)
    argentum._ARB_PAY_OK = False  # no real on-chain calls from tests
    argentum._SMTP_OK = False
    return argentum


class _Resp:
    def __init__(self, status_code, content=b""):
        self.status_code = status_code
        self.content = content


def _fake_client(get_result=None, get_exc=None, post_exc=httpx.ConnectError("pioneer down")):
    """AsyncClient falso: get() devuelve/lanza lo pedido, post() (Pioneer) falla."""

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url):
            if get_exc is not None:
                raise get_exc
            return get_result

        async def post(self, url, json=None):
            raise post_exc

    return _Client


def _fetch(argentum, url):
    return asyncio.run(argentum._fetch_negotiation_ref(url))


# ── _fetch_negotiation_ref: una causa, un estado ─────────────────────────────

def test_fetch_ok_hashes_pdf(tmp_path, monkeypatch):
    argentum = _load_argentum(tmp_path)
    monkeypatch.setattr(argentum, "_safe_docuseal_url", lambda u: True)
    monkeypatch.setattr(argentum.httpx, "AsyncClient", _fake_client(get_result=_Resp(200, PDF_BYTES)))
    assert _fetch(argentum, ALLOWED_URL) == (hashlib.sha256(PDF_BYTES).hexdigest(), "ok")


def test_fetch_not_allowlisted_never_hits_network(tmp_path, monkeypatch):
    argentum = _load_argentum(tmp_path)
    # Guard SSRF real (esquema http -> rechazo sin DNS); get() explotaría si se llamara.
    monkeypatch.setattr(argentum.httpx, "AsyncClient", _fake_client(get_exc=AssertionError("fetched")))
    assert _fetch(argentum, "http://evil.example/signed.pdf") == (None, "not_allowlisted")


def test_fetch_network_exception_is_unreachable(tmp_path, monkeypatch):
    argentum = _load_argentum(tmp_path)
    monkeypatch.setattr(argentum, "_safe_docuseal_url", lambda u: True)
    monkeypatch.setattr(argentum.httpx, "AsyncClient", _fake_client(get_exc=httpx.ConnectTimeout("timeout")))
    assert _fetch(argentum, ALLOWED_URL) == (None, "unreachable")


def test_fetch_non_200_is_http_error(tmp_path, monkeypatch):
    argentum = _load_argentum(tmp_path)
    monkeypatch.setattr(argentum, "_safe_docuseal_url", lambda u: True)
    monkeypatch.setattr(argentum.httpx, "AsyncClient", _fake_client(get_result=_Resp(503)))
    assert _fetch(argentum, ALLOWED_URL) == (None, "http_error")


def test_fetch_empty_body_is_not_hashed(tmp_path, monkeypatch):
    """sha256(b"") no es la huella de ningún acuerdo -- no debe pasar por "ok"."""
    argentum = _load_argentum(tmp_path)
    monkeypatch.setattr(argentum, "_safe_docuseal_url", lambda u: True)
    monkeypatch.setattr(argentum.httpx, "AsyncClient", _fake_client(get_result=_Resp(200, b"")))
    assert _fetch(argentum, ALLOWED_URL) == (None, "empty_body")


def test_fetch_no_document(tmp_path):
    argentum = _load_argentum(tmp_path)
    assert _fetch(argentum, "") == (None, "no_document")


def test_failure_modes_never_collapse(tmp_path, monkeypatch):
    """La regresión exacta: allowlist, red y HTTP no pueden terminar en el mismo valor."""
    argentum = _load_argentum(tmp_path)
    results = [_fetch(argentum, "http://evil.example/signed.pdf")]
    monkeypatch.setattr(argentum, "_safe_docuseal_url", lambda u: True)
    monkeypatch.setattr(argentum.httpx, "AsyncClient", _fake_client(get_exc=httpx.ConnectError("x")))
    results.append(_fetch(argentum, ALLOWED_URL))
    monkeypatch.setattr(argentum.httpx, "AsyncClient", _fake_client(get_result=_Resp(404)))
    results.append(_fetch(argentum, ALLOWED_URL))

    statuses = [status for _, status in results]
    assert len(set(statuses)) == 3
    assert all(ref is None for ref, _ in results)
    assert set(statuses) <= mycelium_trails.NEGOTIATION_REF_STATUSES - {"ok"}


# ── persistencia + verify_chain ───────────────────────────────────────────────

def test_record_trail_persists_status_and_verify_chain_reports_it(tmp_path):
    db = str(tmp_path / "trails.db")
    mycelium_trails.init_db(db)
    tid = mycelium_trails.record_trail(
        db, agent_id="pioneer-agent-001", service="mycelium.safeagent",
        operation="rsa_activation", nonce="n1", negotiation_ref_status="unreachable",
    )
    assert mycelium_trails.get_trail_by_id(db, tid)["negotiation_ref_status"] == "unreachable"
    result = mycelium_trails.verify_chain(db, tid)
    assert result["negotiation_linkage"] == "absent"
    assert result["negotiation_ref_status"] == "unreachable"


def test_record_trail_rejects_unknown_status(tmp_path):
    db = str(tmp_path / "trails.db")
    mycelium_trails.init_db(db)
    assert mycelium_trails.record_trail(
        db, agent_id="a", service="s", operation="o", nonce="n",
        negotiation_ref_status="probably_fine",
    ) is None


def test_verify_chain_unreached_has_no_status(tmp_path):
    db = str(tmp_path / "trails.db")
    mycelium_trails.init_db(db)
    result = mycelium_trails.verify_chain(db, "no-such-trail")
    assert result["negotiation_linkage"] is None
    assert result["negotiation_ref_status"] is None


# ── webhook end-to-end (Pioneer caído -> fallback record_trail) ───────────────

def test_webhook_fallback_records_unreachable_status(tmp_path, monkeypatch):
    argentum = _load_argentum(tmp_path)
    monkeypatch.setattr(argentum, "DOCUSEAL_TOKEN", "tok")
    monkeypatch.setattr(argentum, "_safe_docuseal_url", lambda u: True)
    monkeypatch.setattr(argentum.httpx, "AsyncClient", _fake_client(get_exc=httpx.ConnectError("down")))

    r = TestClient(argentum.app).post(
        "/webhook/docuseal",
        headers={"X-DocuSeal-Token": "tok"},
        json={"event_type": "form.completed",
              "data": {"id": 7, "email": "s@example.com", "documents": [{"url": ALLOWED_URL}]}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["via_pioneer"] is False
    assert body["negotiation_ref"] is None
    assert body["negotiation_ref_status"] == "unreachable"
    trail = mycelium_trails.get_trail_by_id(argentum.TRAILS_DB, body["trail_id"])
    assert trail["negotiation_ref_status"] == "unreachable"


# ── /nexus/trail (camino de Pioneer) ──────────────────────────────────────────

_FIELDS = {
    "agent_id": "pioneer-agent-001",
    "action_type": "rsa_activation",
    "scope": "mycelium.safeagent",
    "timestamp": "1782900000000",
}


def _nexus_post(client, **extra):
    ref = hashlib.sha256(json.dumps(
        dict(sorted(_FIELDS.items())), separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()
    return client.post("/nexus/trail", json={
        "action_ref": ref, "service": "mycelium.safeagent", "preimage": _FIELDS,
        "origin": "pioneer", **extra,
    })


def test_nexus_trail_stores_status(tmp_path):
    argentum = _load_argentum(tmp_path)
    r = _nexus_post(TestClient(argentum.app), negotiation_ref_status="http_error")
    assert r.status_code == 201
    assert r.json()["negotiation_ref_status"] == "http_error"
    trail = mycelium_trails.get_trail_by_id(argentum.TRAILS_DB, r.json()["trail_id"])
    assert trail["negotiation_ref_status"] == "http_error"


def test_nexus_trail_without_status_unchanged(tmp_path):
    argentum = _load_argentum(tmp_path)
    r = _nexus_post(TestClient(argentum.app))
    assert r.status_code == 201
    assert r.json()["negotiation_ref_status"] is None


@pytest.mark.parametrize("extra", [
    {"negotiation_ref_status": "probably_fine"},                      # vocabulario desconocido
    {"negotiation_ref_status": "ok"},                                 # ok sin hash
    {"negotiation_ref_status": "unreachable", "negotiation_ref": "ab" * 32},  # falla con hash
])
def test_nexus_trail_rejects_bad_status(tmp_path, extra):
    argentum = _load_argentum(tmp_path)
    r = _nexus_post(TestClient(argentum.app), **extra)
    assert r.status_code == 400
