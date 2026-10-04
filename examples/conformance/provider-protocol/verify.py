#!/usr/bin/env python3
"""Conformance verifier for the Mycelium Provider Protocol (mycelium-provider-protocol-v1).

Verifies that a provider's compute_action_ref produces bytes byte-identical to the
canonical hash in each vector. Standalone: Python 3 stdlib only.

Exit 0 on full pass. Nonzero with a per-vector diff on any failure.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z\Z")

PREIMAGE_KEYS = ("action_type", "agent_id", "scope", "timestamp")


def compute_action_ref(agent_id: str, action_type: str, scope: str, timestamp: str) -> str:
    """Reference implementation of compute_action_ref per mycelium-provider-protocol.md §1.

    Raises ValueError if timestamp does not match RFC 3339 UTC with 3-digit ms.
    """
    if not TIMESTAMP_RE.match(timestamp):
        raise ValueError(
            f"timestamp must be RFC 3339 UTC with 3-digit ms and Z suffix, got {timestamp!r}"
        )
    payload = dict(sorted({
        "action_type": action_type,
        "agent_id": agent_id,
        "scope": scope,
        "timestamp": timestamp,
    }.items()))
    canonical = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest(), canonical.decode("utf-8")


def preimage_from_input(inp: dict) -> tuple:
    return (inp["agent_id"], inp["action_type"], inp["scope"], inp["timestamp"])


def main() -> int:
    vectors_path = Path(__file__).resolve().parent / "vectors.json"
    suite = json.loads(vectors_path.read_text(encoding="utf-8"))
    failures = []
    accepted = rejected = 0

    for vec in suite["vectors"]:
        vid = vec["id"]

        if vec.get("reject"):
            ts = vec["input"]["timestamp"]
            if TIMESTAMP_RE.match(ts):
                failures.append(
                    f"{vid}: timestamp {ts!r} PASSED grammar but must be rejected ({vec['reason']})"
                )
                continue
            try:
                agent_id, action_type, scope, timestamp = preimage_from_input(vec["input"])
                compute_action_ref(agent_id, action_type, scope, timestamp)
                failures.append(f"{vid}: compute_action_ref did not raise on invalid timestamp {ts!r}")
            except ValueError:
                rejected += 1
            continue

        agent_id, action_type, scope, timestamp = preimage_from_input(vec["input"])
        try:
            got, canonical = compute_action_ref(agent_id, action_type, scope, timestamp)
        except ValueError as e:
            failures.append(f"{vid}: unexpected ValueError — {e}")
            continue

        if "canonical" in vec and canonical != vec["canonical"]:
            failures.append(
                f"{vid}: canonical form mismatch\n"
                f"  expected: {vec['canonical']}\n"
                f"  computed: {canonical}"
            )
            continue

        if got != vec["expected"]:
            failures.append(
                f"{vid}: hash mismatch\n"
                f"  expected: {vec['expected']}\n"
                f"  computed: {got}\n"
                f"  canonical: {canonical}"
            )
            continue

        ok = True
        for i, raw in enumerate(vec.get("input_json_variants", [])):
            variant = json.loads(raw)
            try:
                vgot, _ = compute_action_ref(
                    variant["agent_id"], variant["action_type"],
                    variant["scope"], variant["timestamp"]
                )
            except ValueError as e:
                failures.append(f"{vid}: key-order variant {i} raised ValueError — {e}")
                ok = False
                continue
            if vgot != vec["expected"]:
                failures.append(
                    f"{vid}: key-order variant {i} hash mismatch\n"
                    f"  expected: {vec['expected']}\n"
                    f"  computed: {vgot}\n"
                    f"  variant: {raw}"
                )
                ok = False
        if ok:
            accepted += 1

    total = len(suite["vectors"])
    if failures:
        print(f"FAIL: {len(failures)} failure(s) across {total} vectors\n")
        for f in failures:
            print(f"- {f}")
        return 1
    print(
        f"PASS: {total} vectors "
        f"({accepted} accept recomputed byte-identical, {rejected} reject correctly refused)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
