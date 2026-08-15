"""
Canonical action_ref derivation: RFC 8785 JCS + SHA-256.

action_ref = SHA-256(JCS({
    "agent_id":    "<string>",
    "action_type": "<string>",
    "scope":       "<string>",
    "timestamp":   "<RFC 3339 UTC, 3-digit ms precision>"
}))

JCS (RFC 8785) for a dict with only string values is equivalent to
json.dumps with sorted keys, no spaces, and UTF-8 encoding. We implement
it inline to avoid adding an external dependency for this simple case.

timestamp format: "2026-05-15T10:00:00.123Z" (3-digit ms, mandatory Z).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re


class OutOfProfileDomainError(ValueError):
    """Raised when a preimage field falls outside action-ref.md's Domain paragraph.

    Per spec: a verifier MUST return OUT_OF_PROFILE_DOMAIN and stop before any
    digest comparison — never hash-and-hope. `.field` and `.reason` identify
    which field failed and why, for callers that want structured handling
    instead of parsing the message string.
    """

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"OUT_OF_PROFILE_DOMAIN: {field}: {reason}")


_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def _validate_domain(agent_id: str, action_type: str, scope: str, timestamp: str) -> None:
    """Enforce action-ref.md's Domain paragraph. Raises OutOfProfileDomainError.

    - agent_id, action_type, scope: ASCII-only, no surrogate-pair / astral-plane
      characters (ordinal > 0x7F is rejected either way, which subsumes the
      surrogate-pair case).
    - timestamp: exactly `YYYY-MM-DDTHH:MM:SS.mmmZ` — uppercase `T` separator,
      uppercase `Z` suffix, no numeric offset, exactly 3 fractional digits.
    """
    for field_name, value in (("agent_id", agent_id), ("action_type", action_type), ("scope", scope)):
        if not value.isascii():
            raise OutOfProfileDomainError(field_name, "non-ASCII character in field value")
    if not _TIMESTAMP_RE.match(timestamp):
        raise OutOfProfileDomainError(
            "timestamp",
            f"does not match required grammar YYYY-MM-DDTHH:MM:SS.mmmZ: {timestamp!r}",
        )
    # The regex above checks grammar only -- "2026-02-30T25:99:99.000Z" matches
    # it byte-for-byte while denoting no real instant (day 30 doesn't exist in
    # February, hour/minute/second are out of range). MEDIUM finding, self-audit
    # 2026-08-14: a timestamp must denote a real calendar instant, not just have
    # the right shape. strptime with an explicit format raises ValueError on any
    # semantically invalid field (month/day/hour/minute/second range, including
    # non-leap Feb 29) without accepting the offset-less/lenient variants
    # fromisoformat would.
    try:
        datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as e:
        raise OutOfProfileDomainError(
            "timestamp",
            f"matches the required grammar but does not denote a real calendar instant: {timestamp!r} ({e})",
        )


def _jcs_encode(d: dict[str, str]) -> bytes:
    """RFC 8785 JCS encoding for a flat dict of string values.

    Key ordering is lexicographic Unicode code point order, which for
    ASCII-only keys matches alphabetical order. Values are JSON strings
    with no Unicode escaping for codepoints above U+001F (RFC 8785 §3.2.3).
    """
    return json.dumps(
        dict(sorted(d.items())),
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def format_timestamp(dt: datetime.datetime) -> str:
    """Format a datetime as RFC 3339 UTC with 3-digit ms precision.

    Input must be UTC (tzinfo=timezone.utc or naive treated as UTC).
    Output: "2026-05-15T10:00:00.123Z"
    """
    ms = dt.microsecond // 1000
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S.{ms:03d}Z")


def compute_action_ref(
    agent_id: str,
    action_type: str,
    scope: str,
    timestamp: str,
) -> str:
    """Derive action_ref from the four canonical fields.

    timestamp must already be in RFC 3339 UTC format with 3-digit ms precision
    (e.g. "2026-05-15T10:00:00.123Z"). Use format_timestamp() to produce it
    from a datetime object.

    Returns the SHA-256 hex digest (64 lowercase hex characters).

    Raises OutOfProfileDomainError if any field falls outside action-ref.md's
    Domain paragraph (non-ASCII field values, malformed timestamp grammar) —
    per spec, this must happen before any digest is computed or compared.
    """
    _validate_domain(agent_id, action_type, scope, timestamp)
    payload = {
        "agent_id": agent_id,
        "action_type": action_type,
        "scope": scope,
        "timestamp": timestamp,
    }
    canonical = _jcs_encode(payload)
    return hashlib.sha256(canonical).hexdigest()


# ---------------------------------------------------------------------------
# v2 — domain-separated derivation (docs/spec/action-ref.md, "Version negotiation")
#
# v1 above is unchanged and permanently valid. v2 exists alongside it, not in
# place of it. No caller in this repo has been switched to emit v2 by this
# commit — see docs/rfcs/002-action-ref-v2-domain-separation.md for adoption
# sequencing, which has not started yet.
# ---------------------------------------------------------------------------

V2_DOMAIN_TAG = "mycelium.action-ref:v2:"


def compute_action_ref_v2(
    agent_id: str,
    action_type: str,
    scope: str,
    timestamp: str,
) -> str:
    """Derive a v2 action_ref: same four fields and JCS rules as v1, with a
    spec-named domain tag prepended to the canonical bytes before hashing, and
    a 'v2:' prefix on the returned digest so a verifier never has to guess
    which derivation produced a given action_ref string.

    Returns "v2:" + 64 lowercase hex characters.

    Raises OutOfProfileDomainError under the same Domain rules as
    compute_action_ref — v2 shares v1's four-field domain, only the digest
    derivation differs.
    """
    _validate_domain(agent_id, action_type, scope, timestamp)
    payload = {
        "agent_id": agent_id,
        "action_type": action_type,
        "scope": scope,
        "timestamp": timestamp,
    }
    canonical = _jcs_encode(payload)
    digest = hashlib.sha256(V2_DOMAIN_TAG.encode("utf-8") + canonical).hexdigest()
    return f"v2:{digest}"


def action_ref_version(action_ref: str) -> str:
    """Return 'v1' or 'v2' based on the string's own syntax — never a guess.

    v1: bare 64-hex-char string. v2: 'v2:' prefix followed by 64 hex chars.
    Raises ValueError for anything matching neither shape.
    """
    if action_ref.startswith("v2:") and len(action_ref) == 67:
        return "v2"
    if len(action_ref) == 64:
        return "v1"
    raise ValueError(f"unrecognized action_ref format: {action_ref!r}")
