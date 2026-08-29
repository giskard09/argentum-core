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

timestamp format: RFC 3339 UTC, "2026-05-15T10:00:00.123Z" (3-digit ms,
mandatory Z). compute_action_ref/compute_action_ref_v2 reject any other
form -- including an epoch-ms integer string -- with OUT_OF_PROFILE_DOMAIN;
convert it to RFC 3339 before calling. The single exception is NEXUS's own
documented wire format (packet_version 1.0), handled separately at
/nexus/trail via _validate_domain(..., allow_epoch_ms=True) -- not part of
this canonical action_ref derivation. See _validate_domain for the exact
domain rule.
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
_EPOCH_MS_RE = re.compile(r"^\d+$")

# Sane bound for the epoch-ms branch, self-audit 2026-08-15. Any all-digit
# string is grammatically an integer, but a value like "1782783599" (10
# digits -- epoch *seconds*, not ms) interpreted as ms lands on 1970-01-21,
# not a real agent trail date. Bounding to a plausible operating window turns
# that into a rejection instead of a silently-accepted nonsense timestamp --
# same "grammar isn't enough, must denote a real instant" principle as the
# RFC 3339 calendar check below, applied to the numeric branch. Wide enough
# to never need touching for the life of this profile.
_EPOCH_MS_MIN = int(datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc).timestamp() * 1000)
_EPOCH_MS_MAX = int(datetime.datetime(2100, 1, 1, tzinfo=datetime.timezone.utc).timestamp() * 1000)


def _validate_domain(
    agent_id: str, action_type: str, scope: str, timestamp: str, *, allow_epoch_ms: bool = False
) -> None:
    """Enforce action-ref.md's Domain paragraph. Raises OutOfProfileDomainError.

    - agent_id, action_type, scope: ASCII-only, no surrogate-pair / astral-plane
      characters (ordinal > 0x7F is rejected either way, which subsumes the
      surrogate-pair case).
    - scope: non-empty. Corrected 2026-08-15 -- action-ref.md previously
      allowed "" as an explicit "not applicable" exception here, contradicting
      draft-etcheverry-action-ref-02 §6 ("free-form non-empty string", no
      exception). The I-D is the public document already committed to; the
      local spec was wrong and is now aligned to it. See av-007 in
      examples/conformance/action-ref-v1-domain-negative/ for the reversed
      conformance vector (previously expect_valid: true).
    - timestamp: exactly `YYYY-MM-DDTHH:MM:SS.mmmZ` (RFC 3339, uppercase
      `T`/`Z`, no numeric offset, exactly 3 fractional digits) -- this is the
      ONLY form the canonical action_ref profile hashes; action-ref.md's
      Conversion note requires converting an epoch-ms integer to this form
      BEFORE hashing, precisely so two representations of the same instant
      never produce two different digests. `allow_epoch_ms=True` widens this
      to also accept an all-digit epoch-millisecond string, for the single
      legitimate exception: NEXUS's documented wire format (packet_version
      1.0), which is a separate, non-canonical derivation path -- see
      argentum.py's /nexus/trail. compute_action_ref/compute_action_ref_v2
      (the canonical action_ref v1/v2 functions this spec governs) call this
      with the default False and reject epoch-ms as OUT_OF_PROFILE_DOMAIN.

      FIX 2026-08-25 (aeoess/Pidlisnyi, draft-etcheverry-action-ref#6): a
      2026-08-15 "unification" of this validator (see git history) made
      `allow_epoch_ms` the unconditional default, so compute_action_ref
      itself hashed a raw epoch-ms string unconverted -- reproduced by hand:
      compute_action_ref(..., "1778839200123") and
      compute_action_ref(..., "2026-05-15T10:00:00.123Z") for the exact same
      instant returned two different digests, exactly the non-conformance
      the Conversion note exists to prevent. Restored strict-by-default here;
      NEXUS's /nexus/trail call site now passes allow_epoch_ms=True
      explicitly instead of relying on a shared default.
    """
    for field_name, value in (("agent_id", agent_id), ("action_type", action_type), ("scope", scope)):
        if not value.isascii():
            raise OutOfProfileDomainError(field_name, "non-ASCII character in field value")
    if not scope:
        raise OutOfProfileDomainError("scope", "must be a non-empty string -- no \"not applicable\" exception")

    if allow_epoch_ms and _EPOCH_MS_RE.match(timestamp):
        ms = int(timestamp)
        if not (_EPOCH_MS_MIN <= ms <= _EPOCH_MS_MAX):
            # ms itself can be large enough that reconstructing a datetime for
            # the diagnostic overflows (e.g. 17 digits -> year 300000+, past
            # datetime.MAXYEAR) -- the rejection must not depend on that
            # succeeding, only the message detail does.
            try:
                as_date = str(datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc))
            except (ValueError, OverflowError, OSError):
                as_date = "unrepresentable as a datetime -- too far out of range"
            raise OutOfProfileDomainError(
                "timestamp",
                f"all-digit (epoch-ms) but outside the plausible range "
                f"[{_EPOCH_MS_MIN}, {_EPOCH_MS_MAX}]: {timestamp!r} (as a date: {as_date})",
            )
        return

    if not _TIMESTAMP_RE.match(timestamp):
        accepted = (
            "RFC 3339 (YYYY-MM-DDTHH:MM:SS.mmmZ) or all-digit epoch-ms"
            if allow_epoch_ms
            else "RFC 3339 (YYYY-MM-DDTHH:MM:SS.mmmZ) -- epoch-ms integers must be converted "
                 "to this form before hashing, per the Conversion note in action-ref.md"
        )
        raise OutOfProfileDomainError(
            "timestamp",
            f"does not match the accepted grammar -- {accepted}: {timestamp!r}",
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

    RFC 8785 §3.2.3 orders keys by UTF-16 code unit, not Unicode code point --
    they only diverge for astral-plane keys. `sorted()` below uses Python's
    code-point comparison, which for the four ASCII-only keys this profile
    uses (action_type, agent_id, scope, timestamp) coincides with UTF-16
    order, so no divergence in practice today; not a general-purpose JCS
    key sort. Values are JSON strings with no Unicode escaping for
    codepoints above U+001F (RFC 8785 §3.2.3).
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

    timestamp must already be a string, RFC 3339 UTC with 3-digit ms
    precision (e.g. "2026-05-15T10:00:00.123Z" -- use format_timestamp() to
    produce it from a datetime object). An epoch-ms integer string is
    rejected with OUT_OF_PROFILE_DOMAIN -- convert it to RFC 3339 first, per
    action-ref.md's Conversion note. (NEXUS's own epoch-ms wire format is a
    separate, non-canonical derivation path handled at /nexus/trail, not
    here -- see _validate_domain's allow_epoch_ms.)

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


_V1_RE = re.compile(r"^[0-9a-f]{64}$")
_V2_RE = re.compile(r"^v2:[0-9a-f]{64}$")


def action_ref_version(action_ref: str) -> str:
    """Return 'v1' or 'v2' based on the string's own syntax — never a guess.

    v1: 64 lowercase hex chars. v2: 'v2:' prefix followed by 64 lowercase hex
    chars. Grammar is enforced, not just length/prefix -- a same-length string
    with uppercase hex or non-hex characters is not a valid action_ref of
    either version and raises ValueError, same as a wrong-length string.

    Uses fullmatch, not match: re.match anchors only the start, and `$` in a
    pattern matches at the end of the string OR immediately before a trailing
    newline, so `re.match` alone would accept a value with a trailing '\n'
    appended (e.g. 64 hex chars + '\n') as a clean v1/v2 string. fullmatch
    requires the entire string to match, with no exception for a trailing
    newline.
    """
    if _V2_RE.fullmatch(action_ref):
        return "v2"
    if _V1_RE.fullmatch(action_ref):
        return "v1"
    raise ValueError(f"unrecognized action_ref format: {action_ref!r}")
