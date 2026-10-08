"""
Runner for the partial-chain-recovery set.

This file is not a copy of the reference verifier. It loads
examples/conformance/delegation-chain-ref/verify.py (the reference verifier
at the commit being run) and calls its evaluate_vector() on every vector, in
file order, against ONE SeenRegistry created empty at the start. Registry
state carries across vectors: that is the property under test.

What is checked, in order:
  1. fixture integrity (not chain invariants): every vector carries the same
     fixed delegation_chain_ref, which recomputes from original_chain_artifact;
     the missing-hop vector's hops are the original hops minus
     missing_hop_index; the misplaced-hop control holds exactly the original
     hop objects in another order; the substituted-hop control differs from the
     original only in hops[missing_hop_index].delegation_ref, which recomputes
     from substitute_delegation_artifact; the restoration vector's
     chain_artifact is byte-identical to original_chain_artifact; the
     resubmission is byte-identical to the restoration.
  2. every vector's verdict matches `expected`; `failure_mode` and each of
     `additional_failure_modes` must appear among the failures; nothing in
     `must_not_fail_with` may appear.
  3. after every vector, the registry holds exactly
     `expected_registry_after` (chain_ids, delegation_refs): failed attempts
     are not recorded, the first accepted submission is.

Exit status is 0 only if all three hold. Flipping any `expected` in a copy
of vectors.json makes this runner exit non-zero.

Dependency: PyNaCl, via the reference verifier (`pip install -r ../requirements.txt`).
"""

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_reference_verifier():
    spec = importlib.util.spec_from_file_location("reference_verify", HERE.parent / "verify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def integrity_problems(data, ref):
    problems = []
    by_id = {v["id"]: v for v in data["vectors"]}
    original = data["original_chain_artifact"]
    fixed = data["delegation_chain_ref"]
    idx = data["missing_hop_index"]
    if ref.sha256hex(ref.jcs(original)) != fixed:
        problems.append("delegation_chain_ref does not recompute from original_chain_artifact")
    for v in data["vectors"]:
        if v["delegation_chain_ref"] != fixed:
            problems.append(f"{v['id']}: delegation_chain_ref is not the fixed reference")
        if v["chain_artifact"]["chain_id"] != original["chain_id"]:
            problems.append(f"{v['id']}: chain_id differs from the original")
    orig_hops = original["hops"]
    key = lambda h: ref.jcs(h)  # noqa: E731

    missing = by_id["recovery-001-missing-hop"]["chain_artifact"]["hops"]
    if [key(h) for h in missing] != [key(h) for i, h in enumerate(orig_hops) if i != idx]:
        problems.append("recovery-001: hops are not the original hops minus the missing one")

    sub_v = by_id["recovery-002-substituted-hop-control"]
    sub_hops = sub_v["chain_artifact"]["hops"]
    if len(sub_hops) != len(orig_hops) or any(key(sub_hops[i]) != key(orig_hops[i]) for i in range(len(orig_hops)) if i != idx):
        problems.append("recovery-002: a hop other than the substituted one differs from the original")
    s, o = sub_hops[idx], orig_hops[idx]
    if {k: s[k] for k in ("delegatee", "delegator", "scope")} != {k: o[k] for k in ("delegatee", "delegator", "scope")}:
        problems.append("recovery-002: substituted hop differs in more than delegation_ref")
    if s["delegation_ref"] == o["delegation_ref"]:
        problems.append("recovery-002: substituted hop has the original delegation_ref")
    if ref.sha256hex(ref.jcs(sub_v["substitute_delegation_artifact"])) != s["delegation_ref"]:
        problems.append("recovery-002: substituted delegation_ref does not recompute from substitute_delegation_artifact")

    mis = by_id["recovery-003-misplaced-hop-control"]["chain_artifact"]["hops"]
    if sorted(key(h) for h in mis) != sorted(key(h) for h in orig_hops) or [key(h) for h in mis] == [key(h) for h in orig_hops]:
        problems.append("recovery-003: hops are not the original hop objects in a different order")

    restored = by_id["recovery-004-exact-restoration"]["chain_artifact"]
    if ref.jcs(restored) != ref.jcs(original):
        problems.append("recovery-004: chain_artifact is not byte-identical to original_chain_artifact")
    resub = by_id["recovery-005-resubmission-after-restoration"]["chain_artifact"]
    if ref.jcs(resub) != ref.jcs(restored):
        problems.append("recovery-005: chain_artifact is not byte-identical to recovery-004")
    return problems


def main():
    ref = load_reference_verifier()
    data = json.loads((HERE / "vectors.json").read_text(encoding="utf-8"))
    vectors = data["vectors"]
    print(f"vectors.json — {len(vectors)} vectors, run in order against one empty replay registry")
    print(f"reference verifier: {HERE.parent / 'verify.py'}")
    print(f"fixed delegation_chain_ref: {data['delegation_chain_ref']}\n")

    problems = integrity_problems(data, ref)
    for p in problems:
        print(f"  ✗ [INTEGRITY] {p}")
    print(f"fixture integrity: {'ok' if not problems else f'{len(problems)} problem(s)'}\n")

    registry = ref.SeenRegistry()
    passed = failed = 0
    for v in vectors:
        verdict, failures, not_assessed = ref.evaluate_vector(v, seen_registry=registry)
        ok = verdict == v["expected"]
        required = ([v["failure_mode"]] if v.get("failure_mode") else []) + v.get("additional_failure_modes", [])
        for mode in required:
            ok = ok and any(f.startswith(mode) for f in failures)
        for mode in v.get("must_not_fail_with", []):
            ok = ok and not any(f.startswith(mode) for f in failures)
        state = {"chain_ids": len(registry.chain_ids), "delegation_refs": len(registry.delegation_refs)}
        registry_ok = state == v["expected_registry_after"]
        ok = ok and registry_ok
        marker = "✓" if ok else "✗"
        print(f"  {marker} [{'PASS' if ok else 'FAIL'}] {v['id']}  -> {verdict}")
        if not ok:
            print(f"         expected {v['expected']}"
                  + (f" with {required}" if required else "")
                  + (f", never {v['must_not_fail_with']}" if v.get("must_not_fail_with") else ""))
        for f in failures + not_assessed:
            print(f"         {f}")
        print(f"         registry after: {state}" + ("" if registry_ok else f"  (expected {v['expected_registry_after']})"))
        passed += ok
        failed += not ok
    print(f"\n{passed}/{len(vectors)} passed" + (f", {failed} failed" if failed else ""))
    print("Byte restoration under the original reference and failed-attempt replay handling "
          "only. Nothing here recovers authority, retrieves missing artifacts, or resolves "
          "parent_delegation_ref.")

    if problems or failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
