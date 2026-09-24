"""CI gate for examples/conformance/farley-receipt-signature
(draft-farley-acta-signed-receipts-03, envelope shape).

1. Every vector matches the outcome declared in index.json.
2. build.py regenerates the committed files byte for byte.
3. Mutations of a conformant receipt are refused by the reference
   verifier, so the checks it claims are actually exercised.
"""
import copy
import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VEC = os.path.join(ROOT, "examples", "conformance", "farley-receipt-signature")


def _load(name):
    spec = importlib.util.spec_from_file_location("farley_" + name, os.path.join(VEC, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


verify = _load("verify")
build = _load("build")


def _conformant():
    with open(os.path.join(VEC, "signature-input-drift.conformant.json")) as f:
        return json.load(f)


def test_all_vectors_match_index():
    results = verify.run()
    assert len(results) == 4
    assert all(ok for _, _, ok in results), results


def test_build_is_deterministic(tmp_path):
    build.write(str(tmp_path))
    for name in os.listdir(tmp_path):
        with open(os.path.join(VEC, name), "rb") as a, open(os.path.join(tmp_path, name), "rb") as b:
            assert a.read() == b.read(), name


def test_superseded_pair_is_minimal():
    with open(os.path.join(VEC, "superseded-key.reject.json")) as f:
        rej = json.load(f)["payload"]
    with open(os.path.join(VEC, "superseded-key.conformant.json")) as f:
        ok = json.load(f)["payload"]
    assert [k for k in rej if rej[k] != ok[k]] == ["issued_at"]
    assert set(rej) == set(ok)


def test_mutations_are_refused():
    jwks = verify.load_jwks()
    base = _conformant()
    assert verify.verify(base, jwks) == "ACCEPT"

    def mut(fn):
        r = copy.deepcopy(base)
        fn(r)
        return verify.verify(r, jwks)

    assert mut(lambda r: r.__setitem__("extra", 1)) == "REJECT not_envelope_shape"
    assert mut(lambda r: r["signature"].__setitem__("alg", "ES256")) == "REJECT unsupported_alg"
    assert mut(lambda r: r["payload"].__setitem__("signature", "x")) == "REJECT signature_in_signing_input"
    assert mut(lambda r: r["payload"].__setitem__("decision", "deny")) == "REJECT signature_invalid"
    assert mut(lambda r: r["payload"].pop("issued_at")) == "REJECT missing_required_field"
    assert mut(lambda r: r["signature"].__setitem__("sig", "zz")) == "REJECT bad_signature_encoding"
    assert mut(lambda r: r["signature"].__setitem__("kid", "sb:issuer:unknown")) == "REJECT issuer_kid_mismatch"


def test_signed_input_published_and_explains_each_verdict():
    """index.json carries the exact signed bytes, so a re-run can check the
    cause of each reject, not only the verdict: every signature verifies over
    its signed_input_hex, and the drift reject's input is not JCS(payload)."""
    import base64

    from nacl.signing import VerifyKey

    from jcs import jcs_bytes

    with open(os.path.join(VEC, "index.json")) as f:
        index = json.load(f)
    with open(os.path.join(VEC, "jwks.json")) as f:
        keys = {k["kid"]: k for k in json.load(f)["keys"]}
    for v in index["vectors"]:
        with open(os.path.join(VEC, v["file"])) as f:
            receipt = json.load(f)
        signed = bytes.fromhex(v["signed_input_hex"])
        x = keys[receipt["signature"]["kid"]]["x"]
        vk = VerifyKey(base64.urlsafe_b64decode(x + "=" * (-len(x) % 4)))
        vk.verify(signed, bytes.fromhex(receipt["signature"]["sig"]))
        is_jcs = signed == jcs_bytes(receipt["payload"])
        assert is_jcs == (v["file"] != "signature-input-drift.reject.json"), v["file"]


def test_should_vectors_score_both_runs():
    """A SHOULD vector carries expected_if_not_honoured, so a verifier that
    does not implement Section 9.2 is not scored as a failure; a MUST vector
    never does. A run that declares the windows honoured but does not apply
    them still fails, on superseded-key.reject only, so the corpus keeps
    does-not-implement separate from implements-it-wrong."""
    with open(os.path.join(VEC, "index.json")) as f:
        vectors = json.load(f)["vectors"]
    for v in vectors:
        if v["requirement"].startswith("MUST"):
            assert "expected_if_not_honoured" not in v, v["file"]
        else:
            assert v["expected_if_not_honoured"] in ("ACCEPT", "REJECT"), v["file"]

    assert all(ok for _, _, ok in verify.run(key_windows=False))

    jwks = verify.load_jwks()
    wrong = []
    for v in vectors:
        with open(os.path.join(VEC, v["file"])) as f:
            got = verify.verify(json.load(f), jwks, key_windows=False)
        if got != verify.expected(v, key_windows=True):
            wrong.append(v["file"])
    assert wrong == ["superseded-key.reject.json"]
