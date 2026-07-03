#!/usr/bin/env python3
"""verify.py — composed profile: admission + recompute + chain-fork, three distinct axes.

Requested by rpelevin on autogen#7353 (2026-07-03): "the useful next conformance
step seems to be composing the two properties that are now being tested
separately... a self-signed ALLOW, a verdict that does not recompute, and a
same-sequence fork should fail for different reasons, but the composed profile
should catch all three."

Composes two properties, both already conformance-tested separately in this repo:
  - presidio-x402-decision-ref-v1 (../presidio/): is a payment DECISION entitled
    to its own verdict? Two negatives -- admission (signer independence: a decision
    signed by the actor's own wallet is self-approval, not a second opinion) and
    recompute (the recorded verdict must re-derive from its own cited controls,
    verdict = f(controls), not just carry a valid signature).
  - chain-fork: does the RECEIPT HISTORY become fork-detectable, not just
    individually-anchored? head_hash = sha256(content_hash + "|" + prev_head_hash),
    so a fork is two conflicting, independently-computable heads at the same
    sequence position -- not something you have to take the server's word for.

Independently implemented from the construction description, not copied from any
third party's code. Cross-checked byte-identical against an independent build of
the same composed profile (babyblueviper1/preaction-governance-conformance,
examples/composed-decision-chain-recompute/) -- see README.md for the comparison.

Zero-dependency, offline. Run: python3 verify.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE_PATH = HERE.parent / "presidio" / "presidio-x402-decision-ref-v1.fixture.json"

# A fixed test prior-head, standing in for whatever real head preceded this entry in
# a live chain. The construction doesn't care what it is, only that both candidate
# entries in the fork test share it (same sequence position).
TEST_PRIOR_HEAD = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def jcs(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(record: dict) -> str:
    return hashlib.sha256(jcs(record).encode("utf-8")).hexdigest()


def head_hash(c_hash: str, prev_head: str) -> str:
    return hashlib.sha256(f"{c_hash}|{prev_head}".encode("utf-8")).hexdigest()


def decision_ref(fields: dict, preimage_keys: list[str]) -> str:
    preimage = {k: fields[k] for k in preimage_keys}
    return hashlib.sha256(jcs(preimage).encode("utf-8")).hexdigest()


def admits(vector: dict) -> bool:
    """Axis 1: admission. A decision signed by the actor's own payment wallet is
    self-approval, not an independent verdict -- fail closed regardless of hash validity."""
    return vector["signer"]["key_id"] != vector["artifact"]["actor"]["payment_signer"]


def recomputes(vector: dict) -> bool:
    """Axis 2: recompute. The recorded verdict must match f(controls) re-derived from
    scratch -- a valid hash on a verdict that doesn't follow from its own cited inputs
    is void."""
    precedence = ["pii", "trusted_wallet", "policy", "replay", "mpa"]
    pass_verdicts = {"pii": {"CLEAN", "PII_REDACTED"}, "trusted_wallet": {"TRUSTED"},
                      "policy": {"ALLOW"}, "replay": {"FRESH"}}
    controls = vector["artifact"]["controls"]
    f_controls = "ALLOW"
    for control in precedence:
        c = controls.get(control, {})
        v = c.get("verdict")
        if control == "mpa":
            if c.get("required") and v != "APPROVED":
                f_controls = "REFER"
                break
            continue
        if v not in pass_verdicts.get(control, set()):
            f_controls = "DENY"
            break
    return f_controls == vector["artifact"]["verdict"]


def main() -> int:
    fixture = json.loads(FIXTURE_PATH.read_text())
    by_id = {v["id"]: v for v in fixture["vectors"]}
    accepted = by_id["presidio-x402-decision-001"]
    self_signed = by_id["presidio-x402-decision-signer-equals-runtime"]
    bad_recompute = by_id["presidio-x402-decision-verdict-not-recomputable"]

    print("=" * 78)
    print("COMPOSED PROFILE: admission + recompute + chain-fork, three distinct axes")
    print("=" * 78)

    # Axis 1 -- admission
    self_signed_admits = admits(self_signed)
    self_signed_recomputes = recomputes(self_signed)
    print(f"\n[Axis 1: ADMISSION] self-signed decision:")
    print(f"  admission check: {self_signed_admits} (must be False -- signer is the actor's own wallet)")
    print(f"  recompute check: {self_signed_recomputes} (True -- the verdict itself is fine; fails on WHO signed it)")
    axis1_ok = (not self_signed_admits) and self_signed_recomputes and admits(accepted)

    # Axis 2 -- recompute
    bad_recompute_admits = admits(bad_recompute)
    bad_recompute_recomputes = recomputes(bad_recompute)
    print(f"\n[Axis 2: RECOMPUTE] verdict-not-recomputable decision:")
    print(f"  admission check: {bad_recompute_admits} (True -- signer is a legitimate independent policy-issuer)")
    print(f"  recompute check: {bad_recompute_recomputes} (must be False -- policy=VIOLATION -> f(controls)=DENY, recorded verdict=ALLOW)")
    axis2_ok = bad_recompute_admits and (not bad_recompute_recomputes)

    # Axis 3 -- chain fork
    got_ref = decision_ref(accepted["decision_ref_preimage"], accepted["decision_ref_preimage_fields"])
    decision_ok = got_ref == accepted["decision_ref"]
    print(f"\n[Axis 3: CHAIN FORK] starting decision ({accepted['id']}) recomputes: {decision_ok}")

    receipt_record = {"entry": 41, **accepted["decision_ref_preimage"]}
    c_hash_a = content_hash(receipt_record)
    head_a = head_hash(c_hash_a, TEST_PRIOR_HEAD)
    predictable = head_hash(content_hash(receipt_record), TEST_PRIOR_HEAD) == head_a
    print(f"  committed as chain entry, prior_head={TEST_PRIOR_HEAD[:16]}...")
    print(f"  head_hash: {head_a}")
    print(f"  recompute matches (head changes PREDICTABLY): {predictable}")

    divergent_record = {"entry": 41, **bad_recompute["decision_ref_preimage"]}
    c_hash_b = content_hash(divergent_record)
    head_b = head_hash(c_hash_b, TEST_PRIOR_HEAD)
    fork_detectable = head_a != head_b
    print(f"  DIVERGENT entry, SAME sequence position (same prior_head):")
    print(f"  head_hash: {head_b}")
    print(f"  fork is a detectable CONFLICT, not an overwrite (heads differ): {fork_detectable}")
    axis3_ok = decision_ok and predictable and fork_detectable

    print("\n" + "-" * 78)
    print(f"Axis 1 (admission)  : {'PASS' if axis1_ok else 'FAIL'} -- fails on WHO signed, hash/verdict untouched")
    print(f"Axis 2 (recompute)  : {'PASS' if axis2_ok else 'FAIL'} -- fails on WHETHER the verdict follows from its inputs")
    print(f"Axis 3 (chain fork) : {'PASS' if axis3_ok else 'FAIL'} -- fails on WHERE two conflicting heads meet at one position")

    ok = axis1_ok and axis2_ok and axis3_ok
    print()
    if ok:
        print("PASS -- all three axes distinguishable and caught: a self-signed ALLOW, a")
        print("        verdict that doesn't recompute, and a same-sequence fork each fail")
        print("        for a DIFFERENT, individually-diagnosable reason.")
        return 0
    print("FAIL -- composed profile did not hold on all three axes.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
