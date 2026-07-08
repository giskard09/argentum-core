#!/usr/bin/env python3
"""verify.py — compat vectors against MCP SEP-3004 (Tamper-Evident Audit Record
Contract, modelcontextprotocol/modelcontextprotocol#3004).

Three independently-checkable pieces, run against SEP-3004's own published rule
text (§2.1-§2.4 of the PR diff) — not against any third-party implementation:

  1. known-answer reproduction — the two-extension record from the SEP's
     Conformance section, canonicalized per its own §2.3 rule, must hash to the
     SEP's own published digest f733fed9... Reproduced here with a runner
     independent of the SEP's reference implementation (GIF) and of Interlock's
     runtime-security implementation.
  2. action_ref join — action_ref (docs/spec/action-ref.md) computed from the
     same tool-call event the audit record describes, showing a cross-producer
     identity field the SEP's protected core does not define (it has event_id,
     an opaque id scoped to one chain; action_ref is content-addressed and
     recomputable by a party with no access to that chain). Positive: the same
     four preimage fields the audit record's own core fields determine collapse
     to one action_ref. Negative: a one-millisecond timestamp drift (occurred_at)
     changes action_ref even though the SEP's own event_hash construction is
     agnostic to whether the drifted timestamp is "the same event" or not for
     any purpose beyond bytes-in-chain.
  3. boundary anchoring — the SEP's hash chain (§2.4-2.6) proves the chain is
     internally consistent (operator-held integrity), not existence-in-time or
     precedence relative to an external outcome (SEP §2.8 reserves and
     explicitly defers this — "External Anchoring... orthogonal to the
     within-system chain construction"). Applying anchoring-precedence-ref-v1
     semantics (../anchoring-precedence-ref/) to a chain head: existence_only
     (an external anchor exists) is a strictly weaker property than precedence
     (the anchor is strictly before the outcome it attests to).

Zero-dependency, offline. Run: python3 verify.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

KNOWN_ANSWER_DIGEST = "f733fed9cc757165f810b778e4baba1f51a45504988e937707aaab4361b2f064"


def canonical_json(obj) -> str:
    """SEP-3004 §2.3: sorted-key canonical JSON at every level, no insignificant
    whitespace. Python's json.dumps(sort_keys=True) sorts recursively, which
    covers 'every level' including the extensions object and each extension's
    nested data."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def event_hash(record: dict) -> str:
    """§2.4: event_hash = H(canonical_form(protected_body)), protected_body =
    core (less event_hash) + full extensions object."""
    protected_body = {k: v for k, v in record.items() if k != "event_hash"}
    return sha256hex(canonical_json(protected_body))


def action_ref(agent_id: str, action_type: str, scope: str, timestamp: str) -> str:
    """docs/spec/action-ref.md — JCS over the four preimage fields."""
    payload = {
        "agent_id": agent_id,
        "action_type": action_type,
        "scope": scope,
        "timestamp": timestamp,
    }
    canonical = json.dumps(dict(sorted(payload.items())), separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def vector_1_known_answer() -> bool:
    """SEP-3004 Conformance section, C-REC-3 two-extension known-answer test."""
    record = {
        "event_id": "99999999-9999-9999-9999-999999999999",
        "event_type": "tool_call",
        "occurred_at": "2026-06-06T12:00:00.000Z",
        "outcome": "deferred",
        "previous_hash": None,
        "principal_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "tool_name": "export",
        "extensions": {
            "caller-governance": {
                "flagged": False,
                "invoked_by_principal_id": None,
                "purpose_declared": "reconcile June invoices",
                "session_id": "55555555-5555-5555-5555-555555555555",
            },
            "runtime-security": {
                "drift_status": "confirmed",
                "evidence_hash": "sha256:b2c547e2c8f17eafc72ef5c2d4d7b6b4d0f7437ab52bae573a9af14ff5e2d9be",
                "policy_id": "example.org/runtime-drift@3",
                "quarantine_decision": "quarantine",
                "severity": "high",
            },
        },
    }
    computed = event_hash(record)
    ok = computed == KNOWN_ANSWER_DIGEST
    print("=" * 78)
    print("VECTOR 1 — known-answer reproduction (SEP-3004 §Conformance, C-REC-3)")
    print("=" * 78)
    print(f"  computed:  {computed}")
    print(f"  published: {KNOWN_ANSWER_DIGEST}")
    print(f"  match: {ok}")
    return ok


def vector_2_action_ref_join() -> bool:
    """action_ref binds cross-producer identity for the same event the audit
    record describes; the SEP's core does not define this (event_id is an
    opaque id, unique 'within the chain' per §2.1 — not independently
    recomputable by a party outside the chain)."""
    print("\n" + "=" * 78)
    print("VECTOR 2 — action_ref join (positive + preimage-drift negative)")
    print("=" * 78)

    principal_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    tool_name = "export"
    occurred_at = "2026-06-06T12:00:00.000Z"
    scope = "caller-governance:reconcile June invoices"

    base_record = {
        "event_id": "99999999-9999-9999-9999-999999999999",
        "event_type": "tool_call",
        "occurred_at": occurred_at,
        "outcome": "deferred",
        "previous_hash": None,
        "principal_id": principal_id,
        "tool_name": tool_name,
        "extensions": {
            "caller-governance": {
                "flagged": False,
                "invoked_by_principal_id": None,
                "purpose_declared": "reconcile June invoices",
                "session_id": "55555555-5555-5555-5555-555555555555",
            }
        },
    }
    base_event_hash = event_hash(base_record)
    base_action_ref = action_ref(
        agent_id=principal_id, action_type=tool_name, scope=scope, timestamp=occurred_at
    )
    print(f"  positive — same event, both identifiers computed from its own fields:")
    print(f"    event_hash (SEP-3004, chain-scoped) : {base_event_hash}")
    print(f"    action_ref  (cross-producer, recomputable with no chain access): {base_action_ref}")

    drifted_record = dict(base_record)
    drifted_record["occurred_at"] = "2026-06-06T12:00:00.001Z"  # 1ms drift
    drifted_event_hash = event_hash(drifted_record)
    drifted_action_ref = action_ref(
        agent_id=principal_id, action_type=tool_name, scope=scope, timestamp="2026-06-06T12:00:00.001Z"
    )
    print(f"\n  negative — 1ms occurred_at drift (same principal, tool, outcome):")
    print(f"    event_hash changes  : {base_event_hash != drifted_event_hash}")
    print(f"    action_ref changes  : {base_action_ref != drifted_action_ref}")
    print(f"    both digests move together — action_ref carries the same preimage")
    print(f"    sensitivity SEP-3004's own chain has, expressed as a value a second")
    print(f"    producer can compute without ever seeing this chain.")

    ok = (
        base_event_hash != drifted_event_hash
        and base_action_ref != drifted_action_ref
        and base_event_hash != base_action_ref
    )
    return ok


def vector_3_boundary_anchoring() -> bool:
    """SEP-3004 §2.8 explicitly reserves and defers external anchoring: the hash
    chain (§2.4-2.6) is operator-held integrity, not existence-in-time or
    precedence. Apply anchoring-precedence-ref-v1's existence vs. precedence
    split (../anchoring-precedence-ref/) to a chain head."""
    print("\n" + "=" * 78)
    print("VECTOR 3 — boundary anchoring: existence_only vs. precedence on chain head")
    print("=" * 78)

    chain_head_hash = "f733fed9cc757165f810b778e4baba1f51a45504988e937707aaab4361b2f064"
    outcome_ts_ms = 1749211200000  # 2026-06-06T12:00:00.000Z, from the record's occurred_at

    # existence_only: an external anchor for this chain head exists, but arrives
    # AFTER the outcome it would need to attest to. SEP §2.8: "addresses a
    # distinct, weaker-priority threat... orthogonal to the within-system chain
    # construction" -- existence alone does not establish WHEN relative to the
    # outcome.
    existence_only = {
        "anchor_block_time": 1749211500,  # 300s AFTER outcome_ts_ms/1000
        "outcome_ts_ms": outcome_ts_ms,
        "chain_head": chain_head_hash,
    }
    anchor_ms_1 = existence_only["anchor_block_time"] * 1000
    exists_1 = existence_only["anchor_block_time"] is not None
    precedes_1 = anchor_ms_1 < outcome_ts_ms

    print(f"  existence_only — anchor present, arrives AFTER outcome:")
    print(f"    anchoring_existence  : {exists_1}")
    print(f"    anchoring_precedence : {precedes_1}  (anchor is {(anchor_ms_1 - outcome_ts_ms)//1000}s after)")
    print(f"    a verifier checking only chain integrity (§2.4-2.6) cannot see this")
    print(f"    gap — the chain is internally valid either way.")

    # precedence: anchor strictly before the outcome.
    precedence = {
        "anchor_block_time": 1749211100,  # 100s BEFORE outcome_ts_ms/1000
        "outcome_ts_ms": outcome_ts_ms,
        "chain_head": chain_head_hash,
    }
    anchor_ms_2 = precedence["anchor_block_time"] * 1000
    exists_2 = precedence["anchor_block_time"] is not None
    precedes_2 = anchor_ms_2 < outcome_ts_ms

    print(f"\n  precedence — anchor present, strictly BEFORE outcome:")
    print(f"    anchoring_existence  : {exists_2}")
    print(f"    anchoring_precedence : {precedes_2}  (anchor is {(outcome_ts_ms - anchor_ms_2)//1000}s before)")

    ok = exists_1 and (not precedes_1) and exists_2 and precedes_2
    return ok


def main() -> int:
    r1 = vector_1_known_answer()
    r2 = vector_2_action_ref_join()
    r3 = vector_3_boundary_anchoring()

    print("\n" + "-" * 78)
    print(f"Vector 1 (known-answer)     : {'PASS' if r1 else 'FAIL'}")
    print(f"Vector 2 (action_ref join)  : {'PASS' if r2 else 'FAIL'}")
    print(f"Vector 3 (boundary anchor)  : {'PASS' if r3 else 'FAIL'}")

    ok = r1 and r2 and r3
    print()
    if ok:
        print("PASS — SEP-3004's own known-answer digest reproduces byte-for-byte;")
        print("       action_ref supplies the cross-producer identity field its")
        print("       protected core does not define; its own §2.8 boundary (chain")
        print("       integrity != existence-in-time) is demonstrable with the same")
        print("       existence/precedence split used elsewhere in this repo.")
        return 0
    print("FAIL — one or more vectors did not hold.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
