"""Tests for action_ref derivation (JCS + SHA-256)."""

import hashlib
import json

import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from plugins.agt_evidence_anchor.action_ref import (
    compute_action_ref,
    format_timestamp,
    OutOfProfileDomainError,
    _validate_domain,
)
import datetime


# Known-good vector: JCS of the 4-field payload, then SHA-256.
# JCS key order (lexicographic): action_type < agent_id < scope < timestamp
_VECTOR_FIELDS = {
    "agent_id": "test-agent",
    "action_type": "stripe:charge",
    "scope": "agt-evidence",
    "timestamp": "2026-05-15T10:00:00.123Z",
}
# JCS canonical form (keys sorted, no spaces):
_VECTOR_JCS = '{"action_type":"stripe:charge","agent_id":"test-agent","scope":"agt-evidence","timestamp":"2026-05-15T10:00:00.123Z"}'
_VECTOR_ACTION_REF = hashlib.sha256(_VECTOR_JCS.encode("utf-8")).hexdigest()


def test_compute_action_ref_known_vector():
    result = compute_action_ref(
        agent_id=_VECTOR_FIELDS["agent_id"],
        action_type=_VECTOR_FIELDS["action_type"],
        scope=_VECTOR_FIELDS["scope"],
        timestamp=_VECTOR_FIELDS["timestamp"],
    )
    assert result == _VECTOR_ACTION_REF


def test_compute_action_ref_deterministic():
    a = compute_action_ref("agent-1", "file:write", "audit", "2026-05-15T00:00:00.000Z")
    b = compute_action_ref("agent-1", "file:write", "audit", "2026-05-15T00:00:00.000Z")
    assert a == b


def test_compute_action_ref_different_fields_produce_different_refs():
    ref1 = compute_action_ref("agent-1", "file:write", "audit", "2026-05-15T00:00:00.000Z")
    ref2 = compute_action_ref("agent-2", "file:write", "audit", "2026-05-15T00:00:00.000Z")
    assert ref1 != ref2


def test_compute_action_ref_output_is_64_hex_chars():
    ref = compute_action_ref("a", "b", "c", "2026-01-01T00:00:00.000Z")
    assert len(ref) == 64
    assert all(c in "0123456789abcdef" for c in ref)


def test_jcs_key_ordering():
    """Verify that our JCS encoding sorts keys lexicographically."""
    fields = {
        "agent_id": "x",
        "action_type": "y",
        "scope": "z",
        "timestamp": "t",
    }
    # lexicographic order: action_type, agent_id, scope, timestamp
    canonical = json.dumps(dict(sorted(fields.items())), separators=(",", ":"), ensure_ascii=False)
    assert canonical == '{"action_type":"y","agent_id":"x","scope":"z","timestamp":"t"}'


def test_format_timestamp_3digit_ms():
    dt = datetime.datetime(2026, 5, 15, 10, 0, 0, 123000)
    result = format_timestamp(dt)
    assert result == "2026-05-15T10:00:00.123Z"


def test_format_timestamp_zero_ms():
    dt = datetime.datetime(2026, 1, 1, 0, 0, 0, 0)
    result = format_timestamp(dt)
    assert result == "2026-01-01T00:00:00.000Z"


def test_format_timestamp_ends_with_Z():
    dt = datetime.datetime(2026, 5, 15, 12, 30, 45, 7000)
    result = format_timestamp(dt)
    assert result.endswith("Z")
    assert "." in result
    # ms part is always 3 digits
    ms_part = result.split(".")[1].rstrip("Z")
    assert len(ms_part) == 3


# MEDIUM finding, self-audit 2026-08-14: the timestamp grammar-gate (_TIMESTAMP_RE)
# only checked shape (\d{4}-\d{2}-\d{2}T...) -- "2026-02-30T25:99:99.000Z" matches
# that regex byte-for-byte while denoting no real instant. A timestamp must denote
# a real calendar instant, not just have the right grammar.

@pytest.mark.parametrize("bad_timestamp,why", [
    ("2026-02-30T25:99:99.000Z", "everything out of range at once"),
    ("2026-02-30T10:00:00.000Z", "Feb 30 doesn't exist in any year"),
    ("2026-02-29T00:00:00.000Z", "2026 is not a leap year"),
    ("2026-13-01T00:00:00.000Z", "month 13"),
    ("2026-04-31T00:00:00.000Z", "April has 30 days"),
    ("2026-05-15T25:00:00.000Z", "hour 25"),
    ("2026-05-15T10:60:00.000Z", "minute 60"),
    ("2026-05-15T10:00:60.000Z", "second 60"),
])
def test_grammatically_valid_but_impossible_timestamp_rejected(bad_timestamp, why):
    with pytest.raises(OutOfProfileDomainError) as exc_info:
        _validate_domain("agent", "action", "scope", bad_timestamp)
    assert exc_info.value.field == "timestamp"


@pytest.mark.parametrize("good_timestamp", [
    "2026-05-15T10:00:00.123Z",
    "2028-02-29T00:00:00.000Z",  # 2028 IS a leap year -- must still be accepted
    "2026-12-31T23:59:59.999Z",
    "2026-01-01T00:00:00.000Z",
])
def test_real_calendar_instants_still_accepted(good_timestamp):
    _validate_domain("agent", "action", "scope", good_timestamp)  # must not raise


def test_grammar_gate_still_rejects_malformed_shape():
    # unaffected by this fix -- still caught by _TIMESTAMP_RE before strptime runs
    with pytest.raises(OutOfProfileDomainError) as exc_info:
        _validate_domain("agent", "action", "scope", "2026-05-15 10:00:00.123Z")  # space not T
    assert exc_info.value.field == "timestamp"


# Scope non-empty, self-audit 2026-08-15: action-ref.md previously allowed ""
# as a "not applicable" exception, contradicting the published
# draft-etcheverry-action-ref-02 §6 (non-empty, no exception). The local spec
# was corrected to match the public I-D. See av-007 in
# examples/conformance/action-ref-v1-domain-negative/ (reversed from
# expect_valid: true).

def test_empty_scope_rejected():
    with pytest.raises(OutOfProfileDomainError) as exc_info:
        _validate_domain("agent", "action", "", "2026-05-15T10:00:00.123Z")
    assert exc_info.value.field == "scope"


def test_empty_scope_rejected_via_compute_action_ref():
    with pytest.raises(OutOfProfileDomainError) as exc_info:
        compute_action_ref("agent", "action", "", "2026-05-15T10:00:00.123Z")
    assert exc_info.value.field == "scope"


def test_non_empty_scope_still_accepted():
    _validate_domain("agent", "action", "trade:execute", "2026-05-15T10:00:00.123Z")  # must not raise


# Unified validator, self-audit 2026-08-15: /nexus/trail is the only real
# production caller of this validation logic and only ever accepted RFC 3339
# OR epoch-ms strings (NEXUS packet_version 1.0). _validate_domain now
# supports both, so /nexus/trail can call the shared validator instead of
# reimplementing timestamp checking on its own -- the same "reimplements
# apart and drifts" pattern that caused FINDING-001 and the earlier
# timestamp-grammar MEDIUM.

@pytest.mark.parametrize("epoch_ms", [
    "1785179401774",  # real production value (nandana-design-partner-test)
    "1577836800000",  # exactly _EPOCH_MS_MIN (2020-01-01T00:00:00Z)
    "4102444799999",  # just inside _EPOCH_MS_MAX (2099-12-31T23:59:59.999Z)
])
def test_epoch_ms_within_range_accepted(epoch_ms):
    _validate_domain("agent", "action", "scope", epoch_ms)  # must not raise


@pytest.mark.parametrize("bad_epoch_ms,why", [
    ("1782783599", "10 digits -- epoch SECONDS, not ms; the real production "
                    "anomaly this bound was designed to catch (maps to "
                    "1970-01-21 if misread as ms)"),
    ("0", "epoch itself, 1970-01-01, before the plausible operating window"),
    ("9999999999999999", "absurdly far future, outside the upper bound"),
])
def test_epoch_ms_outside_range_rejected(bad_epoch_ms, why):
    with pytest.raises(OutOfProfileDomainError) as exc_info:
        _validate_domain("agent", "action", "scope", bad_epoch_ms)
    assert exc_info.value.field == "timestamp"


def test_epoch_ms_and_rfc3339_both_accepted_for_compute_action_ref():
    """Control inverse -- neither format broke the other when both were added."""
    ref_rfc3339 = compute_action_ref("agent-x", "action", "scope", "2026-05-15T10:00:00.000Z")
    ref_epoch = compute_action_ref("agent-x", "action", "scope", "1747303200000")
    assert len(ref_rfc3339) == 64
    assert len(ref_epoch) == 64
    assert ref_rfc3339 != ref_epoch  # different preimage strings, different digests, as expected
