#!/usr/bin/env python3
"""Standalone verifier for the Graph Advocate counterparty-ref-v1 vector set.

Stdlib only. Does NOT import any graph-advocate library — recomputes
SHA-256(JCS(preimage)) independently so a pass cross-checks against the
provider's own implementation.

Run: python3 verify.py
Exit 0 on full pass; non-zero on any vector failure.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

VECTORS_PATH = Path(__file__).parent / "vectors.json"


def jcs(obj: dict) -> str:
    """RFC 8785 JCS canonical JSON.

    Vendored minimal implementation per counterparty-ref-v1 spec: stdlib
    json with sort_keys=True, separators=(',',':'), ensure_ascii=False.
    """
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main() -> int:
    suite = json.loads(VECTORS_PATH.read_text())
    vectors = suite.get("vectors") or []
    passed = failed = rejected_ok = rejected_fail = 0

    for v in vectors:
        vid = v.get("id", "<no-id>")
        if v.get("reject"):
            preimage = v["input"]
            if "timestamp" not in preimage:
                print(f"  REJECT-OK {vid}: timestamp absent — verifier refuses to hash")
                rejected_ok += 1
            else:
                print(f"  REJECT-FAIL {vid}: timestamp present in a reject vector — fixture error")
                rejected_fail += 1
            continue

        preimage = v["input"]
        if "timestamp" not in preimage:
            print(f"  FAIL {vid}: PASS vector missing timestamp")
            failed += 1
            continue

        canonical = jcs(preimage)
        if canonical != v.get("canonical"):
            print(f"  FAIL {vid}: JCS string mismatch")
            print(f"    expected: {v['canonical']!r}")
            print(f"    computed: {canonical!r}")
            failed += 1
            continue

        digest = sha256_hex(canonical)
        if digest != v.get("expected"):
            print(f"  FAIL {vid}: SHA-256 hash mismatch")
            print(f"    expected: {v['expected']}")
            print(f"    computed: {digest}")
            failed += 1
            continue

        print(f"  PASS {vid}: {digest}")
        passed += 1

    total = passed + failed + rejected_ok + rejected_fail
    print()
    print(f"  PASS:      {passed}/{total}")
    print(f"  REJECT-OK: {rejected_ok}/{total}")
    print(f"  FAIL:      {failed + rejected_fail}/{total}")

    if failed == 0 and rejected_fail == 0:
        print()
        print(f"PASS: {total} vectors (provider: {suite['provider']['provider_id']})")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
