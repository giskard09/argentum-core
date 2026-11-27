"""Builds vectors-jcs.json for offer-identity-ref: two positive vectors whose x402_response
carries an extra field (the spec says x402_response is the exact object the server served, so any
fields it carries are hashed) with data where RFC 8785 and json.dumps(sort_keys=True) differ: a key outside the BMP, and
number forms.

Additive: vectors.json keeps its bytes and verdicts. The hash of each artifact comes from the repo's
jcs.py and is asserted equal to a value computed once with an independent RFC 8785 implementation
(Node.js: keys sorted with the default UTF-16 sort, numbers as V8 writes them), recorded below.

    python3 build_jcs_vectors.py          # rewrites vectors-jcs.json
    python3 build_jcs_vectors.py --check  # exit 1 if the file on disk differs
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent.parent))
from jcs import jcs_bytes  # noqa: E402

OUT = HERE / "vectors-jcs.json"
BASE_ID = "offer-identity-001"
# Computed once with Node.js (canonicalize = sort keys by default sort, JSON.stringify, SHA-256 of the UTF-8).
NODE_HASH_ASTRAL = "235ee23922975b24ea87a9af570fb1fe87557b0f9bbcc2a8659eea24d61ae2ff"
NODE_HASH_NUMBERS = "3c0b7a3bf401cfa780530a2658aa86777c953dbcf185ac0eb7b818343bea3f37"
CASES = (
    ("jcs-astral-key-001",
     "RFC 8785 key order. The x402_response carries an extra field `ext` with two keys, U+FFFF and U+1F600. RFC 8785 orders keys by UTF-16 code unit, so U+1F600 (D83D DE00) sorts before U+FFFF; ordering by code point gives the reverse and a different offer_identity_ref. Otherwise identical to offer-identity-001.",
     {"￿": 2, "\U0001F600": 1}, NODE_HASH_ASTRAL),
    ("jcs-number-forms-001",
     "RFC 8785 numbers. The x402_response carries an extra field `ext` with 1.0, 0.000001 and 1e21, which ECMAScript Number::toString (RFC 8785) writes as 1, 0.000001 and 1e+21 (Python's repr gives 1.0, 1e-06, 1e+21). Otherwise identical to offer-identity-001.",
     {"s": 0.000001, "n": 1.0, "e": 1e21}, NODE_HASH_NUMBERS),
)


def build() -> dict:
    base = {v["id"]: v for v in json.loads((HERE / "vectors.json").read_text())["vectors"]}[BASE_ID]
    vectors = []
    for vid, desc, ext, node_hash in CASES:
        v = copy.deepcopy(base)
        v["id"], v["description"] = vid, desc
        v["x402_response"]["ext"] = ext
        ref = hashlib.sha256(jcs_bytes(v["x402_response"])).hexdigest()
        assert ref == node_hash, (vid, ref)
        v["offer_identity_ref"] = ref
        vectors.append(v)
    return {
        "spec_version": "offer-identity-ref-v1",
        "description": "Additive vectors: the x402_response carries an extra field with data where RFC 8785 and json.dumps(sort_keys=True) differ (a key outside the BMP; number forms). A verifier that canonicalizes with sort_keys computes another offer_identity_ref and rejects them.",
        "vectors": vectors,
        "provenance": {"authored_by": "giskard09 (argentum-core)", "verification_mode": "asserted", "independently_reproduced_by": []},
    }


def render() -> str:
    return json.dumps(build(), indent=2, ensure_ascii=True) + "\n"


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(0 if OUT.exists() and OUT.read_text() == render() else 1)
    OUT.write_text(render())
    print(f"{len(CASES)} vectors -> {OUT.name}")
