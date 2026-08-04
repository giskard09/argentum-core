#!/usr/bin/env python3
"""Independent verifier for decision-binding-context-digest-v1 vectors.

Recomputes every digest from scratch (JCS preimage -> SHA-256) and checks
it against the value recorded in vectors.json -- never trusts the stored
hash. Run: python3 verify.py
"""
import hashlib
import json
import sys
from pathlib import Path


def jcs(obj: dict) -> str:
    return json.dumps(dict(sorted(obj.items())), separators=(",", ":"), ensure_ascii=False)


def sha256_ref(obj: dict) -> str:
    return "sha256:" + hashlib.sha256(jcs(obj).encode("utf-8")).hexdigest()


def main() -> int:
    vectors_path = Path(__file__).parent / "vectors.json"
    data = json.loads(vectors_path.read_text())

    ok = True

    # Context sets: recompute context_digest = SHA-256(JCS(assembled_context))
    context_digests = {}
    for name, entry in data["context_sets"].items():
        computed = sha256_ref(entry["assembled_context"])
        expected = entry["context_digest"]
        context_digests[name] = computed
        status = "PASS" if computed == expected else "FAIL"
        if computed != expected:
            ok = False
        print(f"[{status}] context_set={name} context_digest={computed}")

    print()

    for v in data["vectors"]:
        vid = v["id"]
        name = v["name"]

        if v["expected_result"] == "PASS" and "preimage" in v:
            computed_ref = sha256_ref(v["preimage"])
            expected_ref = v["decision_binding_ref"]
            passed = computed_ref == expected_ref
            status = "PASS" if passed else "FAIL"
            if not passed:
                ok = False
            print(f"[{status}] {vid} ({name}) decision_binding_ref={computed_ref}")

        elif v["expected_result"] == "FAIL" and v.get("expected_error_code") == "CONTEXT_SET_MISMATCH":
            embedded_digest = v["embedded_preimage"]["context_digest"]
            presented_set_name = v["presented_context_set"]
            recomputed = context_digests[presented_set_name]
            mismatch_detected = recomputed != embedded_digest
            status = "PASS" if mismatch_detected else "FAIL"
            if not mismatch_detected:
                ok = False
            print(
                f"[{status}] {vid} ({name}) "
                f"embedded={embedded_digest} recomputed={recomputed} "
                f"-> {'CONTEXT_SET_MISMATCH (correctly rejected)' if mismatch_detected else 'UNEXPECTED MATCH'}"
            )

        else:
            print(f"[SKIP] {vid} ({name}) — unrecognized vector shape")

    print()
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
