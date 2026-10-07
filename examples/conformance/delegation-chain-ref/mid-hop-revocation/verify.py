"""
Runner for the mid-hop-revocation differential set.

This file is not a copy of the reference verifier. It loads
examples/conformance/delegation-chain-ref/verify.py (the reference verifier
at the commit being run) and calls its evaluate_vector() on every vector, so
the structural verdict reported here is the reference verifier's own. Each
vector is evaluated against a fresh SeenRegistry: the two vectors of a pair
are independent submissions of the same chain, not a resubmission.

What is checked, in order:
  1. fixture integrity (not chain invariants): the two vectors of each pair
     carry byte-identical chain_artifact and leaf_preimage; the baseline
     carries no revocation fields; revocation_ref recomputes from
     revocation_artifact; revoked_delegation_ref equals the targeted hop's
     delegation_ref; the artifact carries no revoked_action_ref;
     revocation_action_ref recomputes from its preimage.
  2. every vector's verdict matches `expected` (and `failure_mode`, which
     must be the only failure reported).
  3. the differential: for each pair, (verdict, failures, not_assessed) are
     identical with and without the revocation artifact.

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


REVOCATION_FIELDS = ("revocation_artifact", "revocation_ref",
                     "revocation_action_preimage", "revocation_action_ref")


def integrity_problems(data, ref):
    problems = []
    by_id = {v["id"]: v for v in data["vectors"]}
    hop_index = data["revoked_hop_index"]
    for pair in data["pairs"]:
        b, w = by_id[pair["baseline"]], by_id[pair["with_revocation"]]
        label = f"{pair['baseline']} / {pair['with_revocation']}"
        if ref.jcs(b["chain_artifact"]) != ref.jcs(w["chain_artifact"]):
            problems.append(f"{label}: chain_artifact differs between the pair")
        if ref.jcs(b["leaf_preimage"]) != ref.jcs(w["leaf_preimage"]):
            problems.append(f"{label}: leaf_preimage differs between the pair")
        if b["delegation_chain_ref"] != w["delegation_chain_ref"]:
            problems.append(f"{label}: delegation_chain_ref differs between the pair")
        present_in_baseline = [f for f in REVOCATION_FIELDS if f in b]
        if present_in_baseline:
            problems.append(f"{pair['baseline']}: baseline carries {present_in_baseline}")
        missing = [f for f in REVOCATION_FIELDS if f not in w]
        if missing:
            problems.append(f"{pair['with_revocation']}: missing {missing}")
            continue
        art = w["revocation_artifact"]
        if ref.sha256hex(ref.jcs(art)) != w["revocation_ref"]:
            problems.append(f"{pair['with_revocation']}: revocation_ref does not recompute")
        if "revoked_action_ref" in art:
            problems.append(f"{pair['with_revocation']}: revocation_artifact carries revoked_action_ref "
                            "(the stand-in this set deliberately does not use)")
        target = w["chain_artifact"]["hops"][hop_index]["delegation_ref"]
        if art.get("revoked_delegation_ref") != target:
            problems.append(f"{pair['with_revocation']}: revoked_delegation_ref != hops[{hop_index}].delegation_ref")
        if ref.compute_action_ref(w["revocation_action_preimage"]) != w["revocation_action_ref"]:
            problems.append(f"{pair['with_revocation']}: revocation_action_ref does not recompute")
    return problems


def main():
    ref = load_reference_verifier()
    data = json.loads((HERE / "vectors.json").read_text(encoding="utf-8"))
    vectors = data["vectors"]
    print(f"vectors.json — {len(vectors)} vectors, {len(data['pairs'])} pairs")
    print(f"reference verifier: {HERE.parent / 'verify.py'}\n")

    problems = integrity_problems(data, ref)
    for p in problems:
        print(f"  ✗ [INTEGRITY] {p}")
    print(f"fixture integrity: {'ok' if not problems else f'{len(problems)} problem(s)'}\n")

    results = {}
    passed = failed = 0
    for v in vectors:
        verdict, failures, not_assessed = ref.evaluate_vector(v, seen_registry=ref.SeenRegistry())
        results[v["id"]] = (verdict, failures, not_assessed)
        ok = verdict == v["expected"]
        mode = v.get("failure_mode")
        if ok and verdict == "FAIL" and mode:
            ok = len(failures) == 1 and failures[0].startswith(mode)
        marker = "✓" if ok else "✗"
        print(f"  {marker} [{'PASS' if ok else 'FAIL'}] {v['id']}  -> {verdict}")
        if not ok:
            print(f"         expected {v['expected']}" + (f" (only: {mode})" if mode else ""))
        for f in failures + not_assessed:
            print(f"         {f}")
        passed += ok
        failed += not ok
    print(f"\n{passed}/{len(vectors)} passed" + (f", {failed} failed" if failed else ""))

    differential_ok = True
    print("\nDIFFERENTIAL CHECK (fresh replay registry per vector):")
    for pair in data["pairs"]:
        same = results[pair["baseline"]] == results[pair["with_revocation"]]
        differential_ok &= same
        verdict = results[pair["baseline"]][0]
        print(f"  {pair['baseline']} == {pair['with_revocation']} -> {same} (both {verdict}, expected {pair['expected']})")
    print("Revocation metadata for hops[1] changed neither the passing verdict nor the failing "
          "one. This is the structural verdict only: it says nothing about whether the chain "
          "still authorizes the leaf, about cascade rejection, or about future-use blocking.")

    if problems or failed or not differential_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
