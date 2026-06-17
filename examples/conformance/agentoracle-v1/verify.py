#!/usr/bin/env python3
"""Conformance verifier for agentoracle-v1 (verification.v0.3 receipts carrying
a forward-pointing action_ref per draft-giskard-aeoess-action-ref).

Standalone: Python 3 stdlib only. A minimal RFC 8785 (JCS) serializer is
vendored below, scoped to the action_ref preimage domain (a flat JSON object
whose values are all strings). It is an independent recomputation, not a
wrapper around the AgentOracle SDK or any other library, so a pass here
cross-checks the SHA-256 hashes in vectors.json against a second
implementation. The Node sibling (verify.mjs) is a third, in another language.

Exit 0 on full pass. Nonzero with a per-vector diff on any failure.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

# RFC 3339 UTC, uppercase T and Z, exactly three fractional digits.
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
PREIMAGE_KEYS = ("action_type", "agent_id", "scope", "timestamp")


def jcs_string(s: str) -> str:
    """RFC 8785 string form: ECMA-262 JSON.stringify rules. json.dumps with
    ensure_ascii=False matches: shortest form, two-character escapes for the
    named controls, \\u00xx for the rest of C0, everything else literal.
    """
    return json.dumps(s, ensure_ascii=False)


def jcs_canonicalize_flat_strings(obj: dict) -> str:
    """RFC 8785 canonicalization for the action_ref preimage domain: a flat
    object whose values are all strings. Keys sorted by UTF-16 code units
    (section 3.2.3); Python's default str sort is code-point order which
    matches code-unit order for the BMP characters used in DID and field names.
    """
    for k, v in obj.items():
        if not isinstance(v, str):
            raise TypeError(f"preimage value for {k!r} must be a string, got {type(v).__name__}")
    keys = sorted(obj.keys())
    pairs = [f"{jcs_string(k)}:{jcs_string(obj[k])}" for k in keys]
    return "{" + ",".join(pairs) + "}"


def compute_action_ref_v1(preimage: dict) -> str:
    ts = preimage["timestamp"]
    if not TIMESTAMP_RE.match(ts):
        raise ValueError(
            f"timestamp must be RFC 3339 UTC with three fractional digits and a Z suffix "
            f"(YYYY-MM-DDTHH:MM:SS.mmmZ), got {ts!r}"
        )
    canonical = jcs_canonicalize_flat_strings(preimage)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def preimage_from_input(inp: dict) -> dict:
    return {k: inp[k] for k in PREIMAGE_KEYS}


def main() -> int:
    here = Path(__file__).parent
    suite = json.loads((here / "vectors.json").read_text(encoding="utf-8"))

    failures: list[str] = []
    accepted = 0
    rejected = 0

    for vec in suite["vectors"]:
        vid = vec["id"]
        if vec.get("reject"):
            ts = vec["input"]["timestamp"]
            if TIMESTAMP_RE.match(ts):
                failures.append(
                    f"{vid}: timestamp {ts!r} PASSED the grammar but must be rejected ({vec['reason']})"
                )
                continue
            try:
                compute_action_ref_v1(preimage_from_input(vec["input"]))
                failures.append(
                    f"{vid}: compute_action_ref_v1 did not raise on invalid timestamp {ts!r}"
                )
            except (ValueError, KeyError):
                rejected += 1
            continue

        preimage = preimage_from_input(vec["input"])
        canonical = jcs_canonicalize_flat_strings(preimage)
        if "canonical" in vec and canonical != vec["canonical"]:
            failures.append(
                f"{vid}: canonical form mismatch\n  expected: {vec['canonical']}\n  computed: {canonical}"
            )
            continue
        got = compute_action_ref_v1(preimage)
        if got != vec["expected"]:
            failures.append(
                f"{vid}: hash mismatch\n  expected: {vec['expected']}\n  computed: {got}\n  canonical: {canonical}"
            )
            continue
        # Cross-check: verification.v0.3 embeds the action_ref as a
        # sha256-prefixed string at context.action_ref.
        rc = vec.get("receipt_context")
        if rc and rc.get("verification_v0_3_field") != f"sha256-{vec['expected']}":
            failures.append(
                f"{vid}: verification.v0.3 embedding mismatch\n  expected: sha256-{vec['expected']}\n  declared: {rc.get('verification_v0_3_field')}"
            )
            continue
        ok = True
        for i, variant_json in enumerate(vec.get("input_json_variants", [])):
            variant = json.loads(variant_json)
            vgot = compute_action_ref_v1(preimage_from_input(variant))
            if vgot != vec["expected"]:
                failures.append(
                    f"{vid}: key-order variant {i} hash mismatch\n  expected: {vec['expected']}\n  computed: {vgot}\n  variant: {variant_json}"
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
    print(f"PASS: {total} vectors ({accepted} accept recomputed byte-identical, {rejected} reject correctly refused)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
