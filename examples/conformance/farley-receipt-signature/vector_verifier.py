"""Verifier of signed decision receipts (draft-farley-acta-signed-receipts-03,
envelope shape, archival mode) with the command-line contract of the
`vectors-receipt-signature` corpus of probityai/agent-evidence-vectors:

    AEV_RECEIPT_JWKS=<key set> [AEV_RECEIPT_CONTEXT=<context.json>] \
        python3 vector_verifier.py <receipt.json>

Last non-empty stdout line: {"verdict": "valid|invalid|undecidable", "code": ...}
Exit status: 0 valid, 1 invalid, 2 undecidable.

Written from the text of the draft (Sections 2.1, 2.2, 5.2, 6.6, 6.7, 6.9, 9.2,
9.5) and the corpus's requirements table, not from the corpus's own reader.
The only code shared with this repository is jcs.py (RFC 8785).
Results are DIRECTED: the expected verdicts were visible while writing it.
This is not the reference reader and certifies nothing.

Choices the draft does not make (each is a place a reader could differ):
  * the end of a key's validity window is outside it, the start inside
    (RFC 7519 nbf/exp); Section 9.2 does not say. The corpus's rs-c-3 asks for it.
  * key revocation (revoked_at) is not read: no revision of the draft defines it
    (corpus gap RS-G-001).
  * a commitment's logging time is not read (corpus gap RS-G-002).
  * only the envelope shape is verified; the flat shape is answered undecidable.
"""
import base64
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
from jcs import jcs_bytes  # noqa: E402

# RFC 3339 date-time. A time-zone designator is required (draft Section 2.2).
_RFC3339 = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(\.\d+)?"
    r"(?:([Zz])|([+-])(\d{2}):(\d{2}))")
_LINK = re.compile(r"sha256:[0-9a-f]{64}")  # used with fullmatch: `$` would accept a trailing LF


def _time(value):
    """RFC 3339 -> aware datetime in UTC, or None when it is not one that
    writes its offset out."""
    if not isinstance(value, str):
        return None
    m = _RFC3339.fullmatch(value)
    if not m:
        return None
    y, mo, d, h, mi, s, frac, z, sign, oh, om = m.groups()
    try:
        # second 60 (leap) is not representable; treat as not applicable
        base = datetime(int(y), int(mo), int(d), int(h), int(mi), int(s),
                        int(((frac or ".0")[1:] + "000000")[:6]), tzinfo=timezone.utc)
    except ValueError:
        return None
    if z:
        return base
    offset = timedelta(hours=int(oh), minutes=int(om))
    return base - offset if sign == "+" else base + offset


def _answer(verdict, code):
    print(json.dumps({"verdict": verdict, "code": code}, separators=(",", ":")))
    return {"valid": 0, "invalid": 1, "undecidable": 2}[verdict]


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _key_for(jwks, kid):
    for k in jwks.get("keys", []):
        if isinstance(k, dict) and k.get("kid") == kid:
            return k
    return None


def _chain_link(previous_receipt):
    """Section 6.7: sha256: + hex SHA-256(JCS(entire signed receipt))."""
    return "sha256:" + hashlib.sha256(jcs_bytes(previous_receipt)).hexdigest()


def judge(receipt, jwks, context=None, chain=None):
    """Return (verdict, code)."""
    # Section 6.6: determine the shape first.
    if not isinstance(receipt, dict):
        return "undecidable", "malformed_receipt"
    sig = receipt.get("signature")
    if isinstance(sig, str):
        return "undecidable", "unsupported_shape"  # flat shape: not implemented
    if set(receipt) != {"payload", "signature"} or not isinstance(sig, dict):
        return "undecidable", "malformed_receipt"
    payload = receipt["payload"]
    if not isinstance(payload, dict):
        return "undecidable", "malformed_receipt"

    # Section 6.6: the object canonicalized must not carry a signature member,
    # whatever its value (null, empty string, a string).
    if "signature" in payload:
        return "invalid", "signature_in_signing_input"

    alg, kid, sig_hex = sig.get("alg"), sig.get("kid"), sig.get("sig")
    if not (isinstance(alg, str) and isinstance(kid, str) and isinstance(sig_hex, str)):
        return "undecidable", "malformed_receipt"
    # Section 6.9: verify against the declared algorithm; EdDSA is the baseline.
    if alg != "EdDSA":
        return "undecidable", "unsupported_algorithm"

    # Section 9.5: the key comes from the external key set, never the receipt.
    key = _key_for(jwks, kid)
    if key is None or key.get("kty") != "OKP" or key.get("crv") != "Ed25519":
        return "undecidable", "unknown_kid"

    # Section 5.2 / 6.6: Ed25519 over JCS(payload) directly, no pre-hash.
    try:
        from nacl.exceptions import BadSignatureError
        from nacl.signing import VerifyKey
        public = base64.urlsafe_b64decode(key["x"] + "=" * (-len(key["x"]) % 4))
        raw_sig = bytes.fromhex(sig_hex)
        VerifyKey(public).verify(jcs_bytes(payload), raw_sig)
    except (BadSignatureError, ValueError, KeyError, TypeError):
        return "invalid", "signature_invalid"

    # Section 9.2 (SHOULD): the key's validity window, when the key set has one.
    has_window = "valid_from" in key or "valid_until" in key
    if has_window:
        issued = _time(payload.get("issued_at"))
        start = _time(key["valid_from"]) if "valid_from" in key else None
        end = _time(key["valid_until"]) if "valid_until" in key else None
        bad_bound = ("valid_from" in key and start is None) or ("valid_until" in key and end is None)
        if issued is None or bad_bound:
            return "undecidable", "window_not_applicable"
        if (start is not None and issued < start) or (end is not None and issued >= end):
            return "invalid", "key_outside_validity_window"

    # Section 6.7: previousReceiptHash.
    if "previousReceiptHash" in payload:
        link = payload["previousReceiptHash"]
        if not (isinstance(link, str) and _LINK.fullmatch(link)):
            return "invalid", "malformed_chain_link"
        if chain:
            if link != _chain_link(chain[-1]):
                return "invalid", "chain_link_mismatch"
    elif chain:
        # at a chain position > 1 a receipt must link to the one before it
        return "invalid", "chain_link_mismatch"

    return "valid", None


def main(argv):
    if len(argv) != 2:
        return _answer("undecidable", "usage")
    jwks_path = os.environ.get("AEV_RECEIPT_JWKS")
    if not jwks_path:
        return _answer("undecidable", "no_key_set")
    try:
        receipt = _load(argv[1])
        jwks = _load(jwks_path)
        chain = None
        ctx_path = os.environ.get("AEV_RECEIPT_CONTEXT")
        if ctx_path:
            ctx = _load(ctx_path)
            chain = [_load(p) for p in ctx.get("chain", [])]
            # ctx["commitment"] / ["commitmentLoggedAt"]: not read (gap RS-G-002)
    except (OSError, ValueError):
        return _answer("undecidable", "unreadable_input")
    verdict, code = judge(receipt, jwks, chain=chain)
    return _answer(verdict, code)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
