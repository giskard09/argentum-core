"""
jcs-utf16-key-order-v1 conformance verifier

Self-contained (stdlib only): recomputes RFC 8785 canonical bytes for each
vector's input and checks
  - positives: recomputed == expected_canonical, sha256 matches
  - negatives: declared_canonical != recomputed, and it fails for the stated
    reason -- `key_order` (same bytes once keys are re-sorted by code point)
    or `string_escaping` (same bytes once \\uXXXX escapes are decoded).

Only strings, integers, lists and objects appear in these vectors; RFC 8785
number formatting for floats is out of scope here (see jcs.py).
"""
import hashlib
import json
import sys
from pathlib import Path


def canon(o):
    if isinstance(o, dict):
        return {k: canon(o[k]) for k in sorted(o, key=lambda k: k.encode("utf-16-be", "surrogatepass"))}
    if isinstance(o, list):
        return [canon(v) for v in o]
    return o


def jcs(obj):
    return json.dumps(canon(obj), separators=(",", ":"), ensure_ascii=False)


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def failure_cause(obj, declared):
    if declared == json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False):
        return "key_order"
    if json.dumps(json.loads(declared), separators=(",", ":"), ensure_ascii=False) == jcs(obj):
        return "string_escaping"
    return "other"


def main(path=None):
    data = json.loads(Path(path or Path(__file__).parent / "vectors.json").read_text())
    passed = failed = 0
    for v in data["vectors"]:
        vid, obj = v["id"], v["input"]
        got = jcs(obj)
        if v["kind"] == "positive":
            ok = got == v["expected_canonical"] and sha256(got) == v["expected_sha256"]
            msg = "" if ok else f"expected {v['expected_canonical']!r}, got {got!r}"
        else:
            declared = v["declared_canonical"]
            cause = failure_cause(obj, declared)
            ok = (declared != got and sha256(declared) == v["declared_sha256"]
                  and cause == v["expected_failure"])
            msg = "" if ok else f"declared bytes verified or wrong cause ({cause})"
        if ok:
            passed += 1
            print(f"PASS [{vid}]")
        else:
            failed += 1
            print(f"FAIL [{vid}] {msg}")
    print(f"\n{passed}/{passed + failed} vectors PASS")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1] if len(sys.argv) > 1 else None) else 1)
