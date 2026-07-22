#!/usr/bin/env python3
"""Standalone conformance runner for verdict-ref-v1. Python 3 stdlib only."""
import hashlib
import json
import sys
from pathlib import Path


def jcs(obj):
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def sha256_hex(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def action_ref(preimage):
    payload = {k: preimage[k] for k in ("agent_id", "action_type", "scope", "timestamp")}
    return sha256_hex(jcs(payload))


def verdict_ref(verdict):
    return sha256_hex(jcs(verdict))


def main():
    vectors = json.loads((Path(__file__).parent / "vectors.json").read_text())["vectors"]
    passed = 0
    for v in vectors:
        computed_action_ref = action_ref(v["preimage"])
        assert computed_action_ref == v["expected_action_ref"], (
            f"{v['id']}: action_ref mismatch"
        )

        if "verdict" in v:
            computed_verdict_ref = verdict_ref(v["verdict"])
            assert computed_verdict_ref == v["expected_verdict_ref"], (
                f"{v['id']}: verdict_ref mismatch"
            )
            independent = v["verdict"]["issuer_id"] != v["preimage"]["agent_id"]
            expected_conformant = v["conformant"]
            if independent != expected_conformant:
                raise AssertionError(
                    f"{v['id']}: independence check gave {independent}, "
                    f"expected conformant={expected_conformant}"
                )

        passed += 1
        print(f"PASS {v['id']}: {v['description'][:70]}")

    print(f"\n{passed}/{len(vectors)} vectors passed.")


if __name__ == "__main__":
    main()
