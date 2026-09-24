"""Build receipt-signature vectors (reject + conformant twin per case) against
draft-farley-acta-signed-receipts-03, envelope shape.

TEST KEYS ONLY: Ed25519 seeds are derived deterministically from public
labels, so anyone can regenerate the vectors byte for byte.

    python3 build.py            # writes into this directory
    python3 build.py OUT_DIR    # writes into OUT_DIR
"""
import base64
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
from jcs import jcs_bytes  # noqa: E402
from nacl.signing import SigningKey  # noqa: E402

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def key(label):
    seed = hashlib.sha256(("agent-evidence-vectors/test-only/" + label).encode()).digest()
    sk = SigningKey(seed)
    return sk, bytes(sk.verify_key)


def b58(b):
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = B58[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + s


def kid(pk):
    # Section 2.1.1: sb:issuer:<first 12 chars of base58(public key)>
    return "sb:issuer:" + b58(pk)[:12]


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def sign(sk, msg):
    return sk.sign(msg).signature


def payload(k, issued_at="2026-07-15T12:00:00Z"):
    return {"type": "protectmcp:decision", "issued_at": issued_at,
            "issuer_id": k, "tool_name": "payments.transfer", "decision": "allow",
            "policy_digest": "sha256:" + hashlib.sha256(b"test-policy-v1").hexdigest()}


def env(p, k, sig):
    return {"payload": p, "signature": {"alg": "EdDSA", "kid": k, "sig": sig.hex()}}


def build():
    skA, pkA = key("key-A-superseded")
    skB, pkB = key("key-B-current")
    kidA, kidB = kid(pkA), kid(pkB)

    jwks = {"keys": [
        {"kty": "OKP", "crv": "Ed25519", "kid": kidA, "x": b64u(pkA), "use": "sig",
         "valid_from": "2026-01-01T00:00:00Z", "valid_until": "2026-06-01T00:00:00Z"},
        {"kty": "OKP", "crv": "Ed25519", "kid": kidB, "x": b64u(pkB), "use": "sig",
         "valid_from": "2026-06-01T00:00:00Z"},
    ]}

    out = {}
    # Case 1: signature-input-drift. Reject signs pretty-printed payload bytes,
    # twin signs JCS(payload).
    p = payload(kidB)
    pretty = json.dumps(p, indent=2).encode()
    assert pretty != jcs_bytes(p)
    out["signature-input-drift.reject"] = env(p, kidB, sign(skB, pretty))
    out["signature-input-drift.conformant"] = env(p, kidB, sign(skB, jcs_bytes(p)))
    signed = {"signature-input-drift.reject": pretty,
              "signature-input-drift.conformant": jcs_bytes(p)}
    # Case 2: superseded key. Minimal pair: both signed with key A; the only
    # difference is issued_at, inside A's window (twin) or after valid_until (reject).
    pA_out = payload(kidA)
    pA_in = payload(kidA, "2026-03-15T12:00:00Z")
    out["superseded-key.reject"] = env(pA_out, kidA, sign(skA, jcs_bytes(pA_out)))
    out["superseded-key.conformant"] = env(pA_in, kidA, sign(skA, jcs_bytes(pA_in)))
    signed["superseded-key.reject"] = jcs_bytes(pA_out)
    signed["superseded-key.conformant"] = jcs_bytes(pA_in)
    out["jwks"] = jwks

    out["index"] = {
        "profile": "draft-farley-acta-signed-receipts-03, envelope shape",
        "verification_mode": "archival (Section 9.1). A verifier applying the live-presentation freshness window (24h RECOMMENDED) would reject all four as stale; that is out of scope here.",
        "key_source": "jwks.json (external to the receipts, per Section 9.5)",
        "test_keys": "TEST ONLY. Ed25519 seeds = SHA-256('agent-evidence-vectors/test-only/' + label); see build.py",
        "should_vectors": "A SHOULD vector carries two outcomes. expected is the verdict when the verifier honours the SHOULD with the material it needs (here: the valid_from/valid_until windows in jwks.json, Section 9.2). expected_if_not_honoured is the verdict when it does not: SHOULD is not MUST, so an ACCEPT on superseded-key.reject is conformant from a verifier that does not implement the window check or was not given the windows. A run declares which case it is in (verify.py: key_windows honoured, or --no-key-windows) and is scored against that outcome, so does-not-implement Section 9.2 stays separate from implements-it-wrong.",
        "signed_input": "signed_input_hex is the exact byte string each signature was made over, so a re-run can check why a reject fails, not only that it does. For signature-input-drift.reject it is Python json.dumps(payload, indent=2), not JCS(payload): the signature verifies over these bytes and fails over JCS(payload).",
        "vectors": [
            {"file": "signature-input-drift.reject.json", "expected": "REJECT", "code": "signature_invalid",
             "requirement": "MUST (Sections 5.1, 5.2, 6.6)",
             "note": "Signed over the pretty-printed payload bytes, not JCS(payload)."},
            {"file": "signature-input-drift.conformant.json", "expected": "ACCEPT", "code": None,
             "requirement": "MUST (Sections 5.1, 5.2, 6.6)", "note": "Same payload, signed over JCS(payload)."},
            {"file": "superseded-key.reject.json", "expected": "REJECT", "code": "key_outside_validity_window",
             "requirement": "SHOULD (Section 9.2)", "expected_if_not_honoured": "ACCEPT",
             "note": "Valid signature under key A; issued_at is after A's valid_until. issued_at is asserted by the signer, so this catches a key used after an honest rotation, not a compromised key backdating within the window."},
            {"file": "superseded-key.conformant.json", "expected": "ACCEPT", "code": None,
             "requirement": "SHOULD (Section 9.2)", "expected_if_not_honoured": "ACCEPT",
             "note": "Minimal pair: same key A, issued_at inside A's window. Only issued_at differs from the reject."}]}
    for v in out["index"]["vectors"]:
        v["signed_input_hex"] = signed[v["file"][:-len(".json")]].hex()
    return out


def write(out_dir):
    for name, obj in build().items():
        with open(os.path.join(out_dir, name + ".json"), "w") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")


if __name__ == "__main__":
    write(sys.argv[1] if len(sys.argv) > 1 else HERE)
