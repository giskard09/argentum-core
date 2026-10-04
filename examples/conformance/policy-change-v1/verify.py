#!/usr/bin/env python3
"""Conformance verifier for policy-change-v1.

Demonstrates the authorization_ref invariant: action_ref commits to the policy
snapshot active at execution time. A policy update to P' does not invalidate a
prior action_ref — the embedded authorization_ref = SHA-256(JCS(P)) is the
cryptographic proof that P was active.

Standalone: Python 3 stdlib only. Exit 0 on full PASS. Nonzero on any failure.

Three vectors:
  pc-001  snapshot_match           PASS  — action under P, verified against P
  pc-002  snapshot_mismatch        FAIL  — action under P, presented with P'
  pc-003  policy_updated_after_action PASS — P updated to P' post-execution; verifier
                                            confirms P was active via authorization_ref
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z\Z")


def jcs_string(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def jcs_flat(obj: dict) -> str:
    """RFC 8785 JCS for a flat object with all-string values."""
    for k, v in obj.items():
        if not isinstance(v, str):
            raise TypeError(f"preimage value for {k!r} must be a string")
    keys = sorted(obj.keys())
    pairs = [f"{jcs_string(k)}:{jcs_string(obj[k])}" for k in keys]
    return "{" + ",".join(pairs) + "}"


def sha256hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def compute_action_ref(preimage: dict) -> str:
    ts = preimage["timestamp"]
    if not TIMESTAMP_RE.match(ts):
        raise ValueError(f"invalid timestamp: {ts!r}")
    return sha256hex(jcs_flat(preimage))


def compute_authorization_ref(policy_snapshot: dict) -> str:
    return "sha256:" + sha256hex(jcs_flat(policy_snapshot))


def main() -> int:
    here = Path(__file__).parent
    data = json.loads((here / "vectors.json").read_text(encoding="utf-8"))
    snapshots = data["policy_snapshots"]

    failures: list[str] = []

    # ── pc-001: snapshot_match ────────────────────────────────────────────────
    v1 = next(v for v in data["vectors"] if v["id"] == "pc-001")
    snapshot_P = snapshots["policy_P"]["object"]
    auth_ref_P = compute_authorization_ref(snapshot_P)

    # Step 1: verify authorization_ref matches what's embedded in preimage
    embedded_auth_ref = v1["preimage"]["authorization_ref"]
    if auth_ref_P != embedded_auth_ref:
        failures.append(
            f"pc-001: authorization_ref mismatch\n"
            f"  computed: {auth_ref_P}\n"
            f"  embedded: {embedded_auth_ref}"
        )
    else:
        # Step 2: verify canonical form
        canonical = jcs_flat(v1["preimage"])
        if canonical != v1["canonical"]:
            failures.append(
                f"pc-001: canonical mismatch\n"
                f"  computed: {canonical}\n"
                f"  expected: {v1['canonical']}"
            )
        else:
            # Step 3: verify action_ref
            got = compute_action_ref(v1["preimage"])
            if got != v1["expected"]:
                failures.append(
                    f"pc-001: action_ref mismatch\n"
                    f"  computed: sha256:{got}\n"
                    f"  expected: sha256:{v1['expected']}"
                )
            elif v1["expected_result"] != "PASS":
                failures.append(f"pc-001: expected_result should be PASS")
            else:
                print("pc-001 snapshot_match             PASS")

    # ── pc-002: snapshot_mismatch ─────────────────────────────────────────────
    v2 = next(v for v in data["vectors"] if v["id"] == "pc-002")
    snapshot_Pprime = snapshots["policy_Pprime"]["object"]
    auth_ref_Pprime = compute_authorization_ref(snapshot_Pprime)

    # Verifier recomputes action_ref over the presented preimage (with P' auth_ref)
    presented_preimage = v2["presented_preimage"]
    canonical_presented = jcs_flat(presented_preimage)
    if canonical_presented != v2["presented_canonical"]:
        failures.append(
            f"pc-002: presented canonical mismatch\n"
            f"  computed: {canonical_presented}\n"
            f"  expected: {v2['presented_canonical']}"
        )
    else:
        recomputed = compute_action_ref(presented_preimage)
        recomputed_ref = f"sha256:{recomputed}"
        issued_ref = v2["issued_action_ref"]

        # The invariant: recomputed MUST diverge from issued (that's the FAIL case)
        if recomputed_ref == issued_ref:
            failures.append(
                f"pc-002: action_refs should diverge but matched — FAIL not detected\n"
                f"  recomputed: {recomputed_ref}\n"
                f"  issued:     {issued_ref}"
            )
        elif recomputed_ref != v2["recomputed_action_ref"]:
            failures.append(
                f"pc-002: recomputed action_ref mismatch\n"
                f"  computed: {recomputed_ref}\n"
                f"  expected: {v2['recomputed_action_ref']}"
            )
        elif v2["expected_result"] != "FAIL":
            failures.append(f"pc-002: expected_result should be FAIL")
        else:
            print(f"pc-002 snapshot_mismatch          FAIL  ({v2['expected_error_code']})")

    # ── pc-003: policy_updated_after_action ───────────────────────────────────
    v3 = next(v for v in data["vectors"] if v["id"] == "pc-003")

    # Step 1: verifier computes authorization_ref from historical policy_snapshot_P
    auth_ref_historical = compute_authorization_ref(snapshot_P)
    embedded_auth_ref_v3 = v3["issued_preimage"]["authorization_ref"]

    if auth_ref_historical != embedded_auth_ref_v3:
        failures.append(
            f"pc-003: historical authorization_ref mismatch\n"
            f"  computed: {auth_ref_historical}\n"
            f"  embedded: {embedded_auth_ref_v3}"
        )
    else:
        # Step 2: verify the canonical form matches
        canonical_v3 = jcs_flat(v3["issued_preimage"])
        if canonical_v3 != v3["issued_canonical"]:
            failures.append(
                f"pc-003: canonical mismatch\n"
                f"  computed: {canonical_v3}\n"
                f"  expected: {v3['issued_canonical']}"
            )
        else:
            # Step 3: recompute action_ref and confirm it matches issued_action_ref
            got_v3 = compute_action_ref(v3["issued_preimage"])
            issued_action_ref = v3["issued_action_ref"]
            if f"sha256:{got_v3}" != issued_action_ref:
                failures.append(
                    f"pc-003: action_ref mismatch\n"
                    f"  computed: sha256:{got_v3}\n"
                    f"  issued:   {issued_action_ref}"
                )
            else:
                # Confirm current policy P' does NOT match the embedded authorization_ref
                auth_ref_current = compute_authorization_ref(snapshot_Pprime)
                if auth_ref_current == embedded_auth_ref_v3:
                    failures.append(
                        "pc-003: current policy P' should NOT match embedded authorization_ref "
                        "(invariant broken — P and P' are identical)"
                    )
                elif v3["expected_result"] != "PASS":
                    failures.append(f"pc-003: expected_result should be PASS")
                else:
                    print("pc-003 policy_updated_after_action PASS  (P active at execution confirmed)")

    print()
    if failures:
        print(f"FAIL: {len(failures)} failure(s)\n")
        for f in failures:
            print(f"- {f}")
        return 1

    print("PASS: 3/3 vectors  (1 accept recomputed byte-identical, 1 reject correctly detected, 1 historical policy confirmed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
