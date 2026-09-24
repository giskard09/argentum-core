"""Reference verifier for the farley-receipt-signature vectors
(draft-farley-acta-signed-receipts-03, envelope shape, archival mode).

The key is resolved from jwks.json only, never from the receipt (Section 9.5).

    python3 verify.py                    # exit 0 iff every vector matches index.json
    python3 verify.py --no-key-windows   # same, as a verifier that does not honour
                                         # the Section 9.2 SHOULD: windows are withheld
                                         # and SHOULD vectors are scored against
                                         # expected_if_not_honoured
"""
import base64
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
from jcs import jcs_bytes  # noqa: E402
from nacl.exceptions import BadSignatureError  # noqa: E402
from nacl.signing import VerifyKey  # noqa: E402

REQUIRED_PAYLOAD = ("type", "issued_at", "issuer_id")  # Section 2.2


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_jwks(path=os.path.join(HERE, "jwks.json")):
    with open(path) as f:
        return {k["kid"]: k for k in json.load(f)["keys"]}


def verify(r, jwks, key_windows=True):
    if not isinstance(r, dict) or set(r) != {"payload", "signature"}:
        return "REJECT not_envelope_shape"                                   # 6.6
    p, s = r["payload"], r["signature"]
    if not isinstance(s, dict) or set(s) != {"alg", "kid", "sig"}:
        return "REJECT bad_signature_object"                                 # 2.1.1
    if not isinstance(p, dict) or any(f not in p for f in REQUIRED_PAYLOAD):
        return "REJECT missing_required_field"                               # 2.2
    if "signature" in p:
        return "REJECT signature_in_signing_input"                           # 6.6
    if s["alg"] != "EdDSA":
        return "REJECT unsupported_alg"
    if p["issuer_id"] != s["kid"]:
        return "REJECT issuer_kid_mismatch"                                  # 2.2
    k = jwks.get(s["kid"])
    if not k:
        return "REJECT unknown_kid"
    try:
        sig = bytes.fromhex(s["sig"])
    except (TypeError, ValueError):
        return "REJECT bad_signature_encoding"                               # 2.1.1
    try:
        vk = VerifyKey(base64.urlsafe_b64decode(k["x"] + "=="))
        vk.verify(jcs_bytes(p), sig)                                         # 5.2, no pre-hash
    except (BadSignatureError, ValueError):
        return "REJECT signature_invalid"
    t = ts(p["issued_at"])
    if key_windows and (("valid_from" in k and t < ts(k["valid_from"])) or
                        ("valid_until" in k and t >= ts(k["valid_until"]))):
        return "REJECT key_outside_validity_window"                          # 9.2 (SHOULD)
    return "ACCEPT"


def expected(v, key_windows=True):
    e = v["expected"] if key_windows else v.get("expected_if_not_honoured", v["expected"])
    return "ACCEPT" if e == "ACCEPT" else "REJECT " + v["code"]


def run(key_windows=True):
    jwks = load_jwks()
    with open(os.path.join(HERE, "index.json")) as f:
        vectors = json.load(f)["vectors"]
    results = []
    for v in vectors:
        with open(os.path.join(HERE, v["file"])) as f:
            got = verify(json.load(f), jwks, key_windows)
        results.append((v["file"], got, got == expected(v, key_windows)))
    return results


if __name__ == "__main__":
    key_windows = "--no-key-windows" not in sys.argv[1:]
    print("key_windows: " + ("honoured (valid_from/valid_until from jwks.json)" if key_windows
                             else "not honoured (SHOULD vectors scored against expected_if_not_honoured)"))
    results = run(key_windows)
    for name, got, ok in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name:40s} {got}")
    sys.exit(0 if all(ok for _, _, ok in results) else 1)
