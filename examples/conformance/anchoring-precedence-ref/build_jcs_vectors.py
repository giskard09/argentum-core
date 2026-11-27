"""Builds vectors-jcs.json for anchoring-precedence-ref: two positive vectors whose envelope carries
an extra field (the spec says an envelope "must contain at minimum" five fields, so more are allowed)
with data where RFC 8785 and json.dumps(sort_keys=True) differ: a key outside the BMP, and number forms.

Additive: vectors.json keeps its bytes and verdicts. The hash of each envelope comes from the repo's
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
BASE_ID = "precedence-positive-001"
CASES = (
    ("jcs-astral-key-001",
     "RFC 8785 key order. The envelope carries an extra field `ext` with two keys, U+FFFF and U+1F600. RFC 8785 orders keys by UTF-16 code unit, so U+1F600 (D83D DE00) sorts before U+FFFF; ordering by code point gives the reverse and a different anchoring_precedence_ref. All five invariants pass.",
     {"￿": 2, "\U0001F600": 1},
     "NODE_HASH_ASTRAL"),
    ("jcs-number-forms-001",
     "RFC 8785 numbers. The envelope carries an extra field `ext` with 1.0, 0.000001 and 1e21, which ECMAScript Number::toString (RFC 8785) writes as 1, 0.000001 and 1e+21 (Python's repr gives 1.0, 1e-06, 1e+21). All five invariants pass.",
     {"s": 0.000001, "n": 1.0, "e": 1e21},
     "NODE_HASH_NUMBERS"),
)
# Computed once with Node.js (canonicalize = sort keys by default sort, JSON.stringify, SHA-256 of the UTF-8).
NODE_HASH_ASTRAL = "6928ce01c1597e927c138f4fa6446084559585df749448f69ae686f7babc1a38"
NODE_HASH_NUMBERS = "7be44d6b21f9a33bc03261995f83c621be05cbfb83c2ec6211cc064e95d6f764"


def build() -> dict:
    base = {v["id"]: v for v in json.loads((HERE / "vectors.json").read_text())["vectors"]}[BASE_ID]
    vectors = []
    for vid, desc, ext, node_name in CASES:
        v = copy.deepcopy(base)
        v["id"], v["description"] = vid, desc
        v["envelope"]["ext"] = ext
        ref = hashlib.sha256(jcs_bytes(v["envelope"])).hexdigest()
        assert ref == globals()[node_name], (vid, ref)
        v["anchoring_precedence_ref"] = v["admission_hash"] = ref
        vectors.append(v)
    return {
        "spec_version": "anchoring-precedence-ref-v1",
        "description": "Additive vectors: the envelope carries an extra field with data where RFC 8785 and json.dumps(sort_keys=True) differ (a key outside the BMP; number forms). A verifier that canonicalizes with sort_keys computes another anchoring_precedence_ref and rejects them.",
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
