"""Rules of examples/conformance/farley-receipt-signature/vector_verifier.py that
the `vectors-receipt-signature` corpus has no member for. The mutation run
against the corpus left these four standing, so they are pinned here with
receipts signed on the fly (TEST ONLY key).
"""
import base64
import hashlib
import importlib.util
import os

from nacl.signing import SigningKey

from jcs import jcs_bytes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "examples", "conformance", "farley-receipt-signature", "vector_verifier.py")
spec = importlib.util.spec_from_file_location("farley_vector_verifier", PATH)
vv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vv)

_SK = SigningKey(hashlib.sha256(b"argentum-core/test-only/verify-vector").digest())
_X = base64.urlsafe_b64encode(bytes(_SK.verify_key)).rstrip(b"=").decode()
JWKS = {"keys": [{"kty": "OKP", "crv": "Ed25519", "kid": "t:k", "x": _X, "use": "sig"}]}


def _receipt(**extra):
    payload = {"type": "protectmcp:decision", "issued_at": "2026-07-15T12:00:00Z",
               "issuer_id": "t:k", "decision": "allow"}
    payload.update(extra)
    sig = _SK.sign(jcs_bytes(payload)).signature.hex()
    return {"payload": payload, "signature": {"alg": "EdDSA", "kid": "t:k", "sig": sig}}


def test_baseline_valid():
    assert vv.judge(_receipt(), JWKS) == ("valid", None)


def test_unsupported_alg_is_undecidable():
    r = _receipt()
    r["signature"]["alg"] = "ES256"
    assert vv.judge(r, JWKS) == ("undecidable", "unsupported_algorithm")


def test_unknown_kid_is_undecidable():
    r = _receipt()
    r["signature"]["kid"] = "t:other"
    assert vv.judge(r, JWKS) == ("undecidable", "unknown_kid")


def test_receipt_at_chain_position_two_without_link_is_refused():
    genesis = _receipt()
    assert vv.judge(_receipt(), JWKS, chain=[genesis]) == ("invalid", "chain_link_mismatch")


def test_link_with_uppercase_hex_is_malformed():
    genesis = _receipt()
    good = "sha256:" + hashlib.sha256(jcs_bytes(genesis)).hexdigest()
    assert vv.judge(_receipt(previousReceiptHash=good), JWKS, chain=[genesis]) == ("valid", None)
    assert vv.judge(_receipt(previousReceiptHash=good.upper().replace("SHA256", "sha256")), JWKS) \
        == ("invalid", "malformed_chain_link")


def test_link_with_trailing_newline_is_malformed():
    """A `$`-anchored pattern accepts "...\\n"; the link must be exactly
    "sha256:" + 64 lowercase hex."""
    genesis = _receipt()
    good = "sha256:" + hashlib.sha256(jcs_bytes(genesis)).hexdigest()
    for tail in ("\n", "\r\n", " ", "\x00"):
        assert vv.judge(_receipt(previousReceiptHash=good + tail), JWKS, chain=[genesis]) \
            == ("invalid", "malformed_chain_link"), repr(tail)
        assert vv.judge(_receipt(previousReceiptHash=good + tail), JWKS) \
            == ("invalid", "malformed_chain_link"), repr(tail)


def test_issued_at_with_trailing_newline_is_not_a_time():
    assert vv._time("2026-07-15T12:00:00Z") is not None
    for tail in ("\n", "\r\n"):
        assert vv._time("2026-07-15T12:00:00Z" + tail) is None
