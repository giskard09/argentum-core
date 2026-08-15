"""FINDING-001 regression, self-audit 2026-08-14.

/nexus/trail used to accept action_ref computed by either of two schemes:
the official JCS derivation (action-ref.md / draft-etcheverry-action-ref-02
§3.2) or a legacy "colon-separated" scheme (agent_id:action_type:scope:ts),
kept "during transition". Two derivations both reading as conformant on the
same endpoint breaks operator-independence -- a verifier can't tell which
rule produced a given action_ref, so it can't independently confirm any of
them. The fix: JCS is the only accepted derivation; anything else is a 422,
not a silent accept.
"""
import hashlib
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
    return argentum, TestClient(argentum.app)


_FIELDS = {
    "agent_id": "agent-finding-001",
    "action_type": "test:action",
    "scope": "finding-001-regression",
    "timestamp": "1782900000000",
}


def _jcs_ref(fields):
    canonical = json.dumps(
        dict(sorted(fields.items())), separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _colon_ref(fields):
    payload = f"{fields['agent_id']}:{fields['action_type']}:{fields['scope']}:{int(fields['timestamp'])}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _post(client, action_ref):
    return client.post("/nexus/trail", json={
        "action_ref": action_ref,
        "service": "test-service",
        "preimage": _FIELDS,
    })


def test_jcs_derived_action_ref_still_accepted(tmp_path):
    _, client = _client(tmp_path)
    r = _post(client, _jcs_ref(_FIELDS))
    assert r.status_code == 201
    assert r.json()["trail_status"] == "committed"


def test_colon_separated_action_ref_now_rejected(tmp_path):
    """The exact regression: the legacy scheme must no longer be accepted."""
    _, client = _client(tmp_path)
    colon_ref = _colon_ref(_FIELDS)
    assert colon_ref != _jcs_ref(_FIELDS)  # sanity: the two schemes really differ

    r = _post(client, colon_ref)
    assert r.status_code == 422
    assert r.json()["error"] == "action_ref mismatch"


def test_colon_ref_is_not_silently_stored(tmp_path):
    """Not just a 422 -- confirm no trail was recorded for the rejected ref."""
    argentum, client = _client(tmp_path)
    colon_ref = _colon_ref(_FIELDS)
    _post(client, colon_ref)

    import mycelium_trails
    row = mycelium_trails.get_trail_by_action_ref(argentum.TRAILS_DB, _FIELDS["agent_id"], colon_ref)
    assert row is None


def test_arbitrary_garbage_action_ref_rejected(tmp_path):
    _, client = _client(tmp_path)
    r = _post(client, "0" * 64)
    assert r.status_code == 422
