#!/usr/bin/env python3
"""Conformance verifier for evidence-anchor-static-analysis-v0.

Recomputes every action_ref from its intent-tuple preimage, offline, and checks the
three invariants (rescan idempotency, distinct events, evidence independence). A verifier
confirms the scan anchor without access to AgentGraph infrastructure.

    python3 verify.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import rfc8785


def action_ref(preimage: dict) -> tuple[bytes, str]:
    canon = rfc8785.dumps(preimage)
    return canon, hashlib.sha256(canon).hexdigest()


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    fx = json.load(open(os.path.join(here, "fixture.json")))
    errors: list[str] = []
    refs: dict[str, str] = {}

    for v in fx["vectors"]:
        canon, ref = action_ref(v["preimage"])
        if canon.hex() != v["preimage_canonical_bytes_hex"]:
            errors.append(f"{v['label']}: canonical bytes mismatch")
        if ref != v["action_ref"]:
            errors.append(f"{v['label']}: action_ref {ref} != {v['action_ref']}")
        if any(k in v["preimage"] for k in ("verdict", "findings", "grade", "outcome")):
            errors.append(f"{v['label']}: verdict leaked into action_ref preimage")
        refs[v["label"]] = ref
        bad = [e for e in errors if e.startswith(v["label"])]
        print(f"  {'OK ' if not bad else 'XX '} {v['label']:26} {v['expectation']:4} {ref[:16]}…")

    if refs.get("POS-1_clean_mcp") != refs.get("INV-1_rescan_stable_ref"):
        errors.append("invariant rescan_idempotency: same preimage must give same action_ref")
    if refs.get("POS-1_clean_mcp") == refs.get("INV-2_later_distinct_ref"):
        errors.append("invariant distinct_events: later timestamp must give different action_ref")

    print("-" * 56)
    if errors:
        for e in errors:
            print("FAIL:", e)
        return 1
    print(f"PASS — {len(fx['vectors'])}/{len(fx['vectors'])} action_refs reproduce + 3 invariants hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
