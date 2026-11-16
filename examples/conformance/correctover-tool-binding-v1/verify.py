#!/usr/bin/env python3
"""Correctover independent tool-binding verifier (dependency-free).

Written from draft-etcheverry-action-ref-05 alone; intentionally does not read
or call any other author-set implementation. Reproduces every expected verdict
in correctover-tool-binding-v1-vectors.json.

Every anchor carries a real SHA-256(JCS(effective_args)) digest, so the digest
comparison is live on all seven of them. For each record this verifier also
prints what a digest-only pipeline would have concluded from the same bytes.
That column is the point of the suite: on the five REFUSES anchors a digest-only
pipeline sees a valid receipt and passes the record, while binding rejects it.

Scope note: the JCS implementation here is exact for the ASCII-only preimages in
this suite (sorted keys, no whitespace, minimal escaping). Byte-level RFC 8785
conformance for non-ASCII inputs belongs to the three JCS comparison-semantics
author-sets and is deliberately not duplicated here.
"""
import json
import hashlib
import sys
import os

FRESHNESS_WINDOW_DEFAULT_MS = 3600000


def jcs(obj):
    """RFC 8785 canonical JSON, exact for the ASCII-only preimages in this suite."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def digest_of(args):
    return hashlib.sha256(jcs(args)).hexdigest()


def digest_only_verdict(anchor):
    """What a pipeline that only checks the receipt digest would conclude.

    Returns None when the anchor asserts no digest: such a pipeline has nothing
    to say about the record, which is itself a way to pass it.
    """
    declared = anchor.get("effective_args_digest")
    if declared is None:
        return None
    return "BINDS" if declared == digest_of(anchor["effective_args"]) else "REFUSES"


def verdict_for(anchor):
    a = anchor

    # 1. label integrity: action_type is exact-match per the -05 preimage table
    approved_label = a.get("approved_action_type", a.get("action_type"))
    if a["action_type"] != approved_label:
        return ("REFUSES", "label-integrity")

    # 2. tool identity: dispatched tool must be the approved tool
    if a["dispatched_tool"] != a["authorized_tool"]:
        return ("REFUSES", "tool-identity")

    # 3. params binding against the approved declaration
    approved = a.get("approved_params")
    if approved:
        dispatched = a["effective_args"]
        if dispatched.get("to") != approved.get("to"):
            return ("REFUSES", "param-widening")
        if dispatched.get("currency") != approved.get("currency"):
            return ("REFUSES", "param-widening")
        # keys present in the dispatch but never approved: widening by addition
        extra = set(dispatched) - set(approved) - {"amount"}
        if extra:
            return ("REFUSES", "param-widening")
        # both ceilings bind, so the effective ceiling is the tighter one
        ceiling = approved.get("amount_max")
        scope = a.get("policy_scope_max")
        if scope is not None:
            ceiling = scope if ceiling is None else min(ceiling, scope)
        if ceiling is not None and dispatched.get("amount", 0) > ceiling:
            return ("REFUSES", "param-widening")

    # 4. freshness at settlement: authority and revocation are both settlement-time MUSTs
    window = a.get("freshness_window_ms", FRESHNESS_WINDOW_DEFAULT_MS)
    settled = a.get("settlement_at_ms")
    if settled is not None:
        for field in ("authority_verified_at_ms", "revocation_check_at_ms"):
            stamped = a.get(field)
            if stamped is not None and settled - stamped > window:
                return ("REFUSES", "stale-authority")

    # 5. delegation resolution: the preimage agent_id must be the chain tail
    chain = a.get("delegation_chain")
    if chain and a.get("agent_id_preimage") != chain[-1]:
        return ("REFUSES", "delegation-unresolved")

    # 6. integrity last: recompute the digest over the dispatched args
    declared = a.get("effective_args_digest")
    if declared is not None and declared != digest_of(a["effective_args"]):
        return ("REFUSES", "integrity")

    reason = "tool-identity + params-bound + fresh"
    if chain:
        reason = "delegation-resolved + " + reason
    return ("BINDS", reason)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    suite = json.load(open(os.path.join(here, "correctover-tool-binding-v1-vectors.json"),
                           encoding="utf-8"))

    agree = 0
    undecided = 0
    for anchor in suite["anchors"]:
        got = verdict_for(anchor)
        expected = (anchor["expected_verdict"], anchor["expected_reason"])
        ok = got == expected
        agree += ok

        only = digest_only_verdict(anchor)
        if only is not None and only != got[0]:
            undecided += 1
            marker = "  <- digest-only passes, binding refuses"
        elif only is None:
            marker = "  <- no digest asserted"
        else:
            marker = ""

        print(f"{'PASS' if ok else 'FAIL'}  {anchor['name']:34s} "
              f"expected={expected[0]}/{expected[1]}  "
              f"got={got[0]}/{got[1]}  digest-only={only or 'n/a'}{marker}")

    total = len(suite["anchors"])
    print()
    print(f"{agree}/{total} verdicts agree. Zero-disagreement is the author-set requirement.")
    print(f"{undecided} of {total} anchors are decided by binding alone: a digest-only "
          f"pipeline passes them and this verifier refuses them.")
    return 0 if agree == total else 1


if __name__ == "__main__":
    sys.exit(main())
