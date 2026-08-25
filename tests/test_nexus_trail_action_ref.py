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


def _post(client, action_ref, preimage=None):
    return client.post("/nexus/trail", json={
        "action_ref": action_ref,
        "service": "test-service",
        "preimage": preimage if preimage is not None else _FIELDS,
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


# Scope non-empty, self-audit 2026-08-15: action-ref.md previously allowed ""
# as an explicit "not applicable" exception, contradicting the published
# draft-etcheverry-action-ref-02 §6 ("free-form non-empty string", no
# exception). action-ref.md was corrected to match the public I-D. Retroactive
# impact checked before this fix: 0 production trails via /nexus/trail had
# empty scope.

def test_empty_string_scope_rejected(tmp_path):
    _, client = _client(tmp_path)
    fields = dict(_FIELDS, scope="")
    r = _post(client, _jcs_ref(fields), preimage=fields)
    assert r.status_code == 422
    assert r.json()["error"] == "action_ref mismatch"
    assert "non-empty" in r.json()["detail"]


def test_missing_scope_key_rejected(tmp_path):
    _, client = _client(tmp_path)
    r = client.post("/nexus/trail", json={
        "action_ref": _jcs_ref(dict(_FIELDS, scope="")),
        "service": "test-service",
        "preimage": {k: v for k, v in _FIELDS.items() if k != "scope"},
    })
    assert r.status_code == 422


def test_empty_scope_not_silently_stored(tmp_path):
    argentum, client = _client(tmp_path)
    fields = dict(_FIELDS, scope="")
    ref = _jcs_ref(fields)
    _post(client, ref, preimage=fields)

    import mycelium_trails
    row = mycelium_trails.get_trail_by_action_ref(argentum.TRAILS_DB, _FIELDS["agent_id"], ref)
    assert row is None


def test_non_empty_scope_still_accepted(tmp_path):
    """Control inverse -- the fix must not reject legitimate non-empty scopes."""
    _, client = _client(tmp_path)
    r = _post(client, _jcs_ref(_FIELDS))  # _FIELDS already has a real scope
    assert r.status_code == 201


# Unified validator, self-audit 2026-08-15: /nexus/trail was never wired to
# _validate_domain at all (not for ASCII, not for timestamp, not for scope
# until the point fix) -- the earlier "MEDIUM closed" claims for the
# timestamp-grammar fix only held for plugins/agt_evidence_anchor, not this
# endpoint. Fixed by calling the shared validator directly. These tests
# confirm the endpoint and the validator now agree on the same input.

def test_epoch_ms_timestamp_accepted_end_to_end(tmp_path):
    _, client = _client(tmp_path)
    fields = dict(_FIELDS, timestamp="1785179401774")  # real production value
    r = _post(client, _jcs_ref(fields), preimage=fields)
    assert r.status_code == 201


def test_epoch_seconds_masquerading_as_ms_rejected_end_to_end(tmp_path):
    """The exact production anomaly (10-digit epoch-seconds) must now 422."""
    _, client = _client(tmp_path)
    fields = dict(_FIELDS, timestamp="1782783599")
    r = _post(client, _jcs_ref(fields), preimage=fields)
    assert r.status_code == 422
    assert "OUT_OF_PROFILE_DOMAIN" in r.json()["detail"]


def test_impossible_calendar_timestamp_rejected_end_to_end(tmp_path):
    """Same MEDIUM as the plugin path, now actually enforced in production."""
    _, client = _client(tmp_path)
    fields = dict(_FIELDS, timestamp="2026-02-30T25:99:99.000Z")
    r = _post(client, _jcs_ref(fields), preimage=fields)
    assert r.status_code == 422
    assert "OUT_OF_PROFILE_DOMAIN" in r.json()["detail"]


def test_non_ascii_field_rejected_end_to_end(tmp_path):
    """ASCII-only was also never enforced by this endpoint before this fix."""
    _, client = _client(tmp_path)
    fields = dict(_FIELDS, scope="scope:звіт")
    r = _post(client, _jcs_ref(fields), preimage=fields)
    assert r.status_code == 422
    assert "OUT_OF_PROFILE_DOMAIN" in r.json()["detail"]


@pytest.mark.parametrize("ts", [
    "1785179401774",              # epoch-ms
    "2026-05-15T10:00:00.123Z",   # RFC 3339
])
def test_endpoint_and_shared_validator_agree_on_valid_input(tmp_path, ts):
    """Same verdict, both layers -- the whole point of unifying them.

    allow_epoch_ms=True mirrors /nexus/trail's actual call site (argentum.py):
    NEXUS's documented wire format (packet_version 1.0) accepts epoch-ms, unlike
    compute_action_ref/compute_action_ref_v2, which reject it by default since
    the 2026-08-25 fix (aeoess/Pidlisnyi, draft-etcheverry-action-ref#6) -- see
    action_ref.py::_validate_domain.
    """
    from plugins.agt_evidence_anchor.action_ref import _validate_domain
    fields = dict(_FIELDS, timestamp=ts)
    _validate_domain(
        fields["agent_id"], fields["action_type"], fields["scope"], fields["timestamp"],
        allow_epoch_ms=True,
    )  # must not raise

    _, client = _client(tmp_path)
    r = _post(client, _jcs_ref(fields), preimage=fields)
    assert r.status_code == 201


@pytest.mark.parametrize("ts", [
    "1782783599",                 # epoch-seconds masquerading as ms
    "2026-02-30T25:99:99.000Z",   # impossible calendar date
    "not-a-timestamp",
])
def test_endpoint_and_shared_validator_agree_on_invalid_input(tmp_path, ts):
    from plugins.agt_evidence_anchor.action_ref import _validate_domain, OutOfProfileDomainError
    fields = dict(_FIELDS, timestamp=ts)
    with pytest.raises(OutOfProfileDomainError):
        _validate_domain(fields["agent_id"], fields["action_type"], fields["scope"], fields["timestamp"])

    _, client = _client(tmp_path)
    r = _post(client, _jcs_ref(fields), preimage=fields)
    assert r.status_code == 422
