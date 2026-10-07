"""
Revocation enforcement layer for delegation-chain-ref (AAE-02 §7.5).

Two verdict models over the same chain:

  default  — structural verdict only (verify.py). Revocations are not read.
             This is the default model documented in docs/spec/delegation-chain-ref.md.
  7.5      — structural verdict AND enforcement. A relying party that knows a
             hop is revoked treats every descendant hop, and the leaf action
             executed under it, as invalid (AAE-02 §7.5).

The enforcement layer is a separate function (enforce_7_5). It does not change
verify_vector, so the structural verdict is identical under both models. The
runner checks that explicitly for every case.

Open modeling point, carried from revoked-ancestor/README.md: revoked_action_ref
is matched against hops[i].delegation_ref, the same convention the existing
vector uses. A revocation_ref schema that targets delegation_ref directly
(revoked_delegation_ref) is not implemented here.

Reproducible output: the report is deterministic and its sha256 is printed last.
Exit code is 0 only if every case matches its declared expectation.
"""

import hashlib
import json
import sys
from pathlib import Path

from verify import SeenRegistry, verify_vector

BASE = Path(__file__).parent
MODELS = ("default", "7.5")


def revoked_ancestor_indices(hops: list[dict], revocations: list[dict]) -> list[int]:
    revoked_refs = {
        r["revoked_action_ref"]
        for r in revocations
        if r.get("version") == "revocation-ref-v1" and "revoked_action_ref" in r
    }
    return [i for i, hop in enumerate(hops) if hop["delegation_ref"] in revoked_refs]


def enforce_7_5(chain: dict, revocations: list[dict]) -> tuple[bool, list[str]]:
    """AAE-02 §7.5: descendants of a known-revoked hop are invalid.

    Judged only on revocations the relying party already knows. No time test is
    applied: §7.5 says "already knows", not "revoked before action".
    """
    hops = chain["hops"]
    ancestors = revoked_ancestor_indices(hops, revocations)
    if not ancestors:
        return True, []
    first = ancestors[0]
    failures = []
    for i in range(first + 1, len(hops)):
        failures.append(
            f"descendant_of_revoked_ancestor at hop {i}: hops[{first}] "
            f"(delegation_ref={hops[first]['delegation_ref']}) is known revoked; "
            f"hops[{i}] ({hops[i]['delegator']!r} -> {hops[i]['delegatee']!r}) is a descendant "
            f"and is invalid per AAE-02 §7.5"
        )
    if first < len(hops) - 1:
        failures.append(
            f"leaf_action_under_revoked_ancestor: the leaf action executes under hops[-1] "
            f"({hops[-1]['delegatee']!r}), a descendant of revoked hops[{first}]; invalid per AAE-02 §7.5"
        )
    return len(failures) == 0, failures


def verdict(vector: dict, revocations: list[dict], model: str) -> tuple[bool, list[str], bool]:
    """Returns (valid, failures, structural_ok). The structural verdict never reads revocations."""
    structural_ok, structural_failures = verify_vector(vector, seen_registry=SeenRegistry())
    if model == "default":
        return structural_ok, structural_failures, structural_ok
    if model == "7.5":
        enforced_ok, enforced_failures = enforce_7_5(vector["chain_artifact"], revocations)
        return structural_ok and enforced_ok, structural_failures + enforced_failures, structural_ok
    raise ValueError(f"unknown model {model!r}")


def resolve_revocations(spec, top_level: list[dict]) -> list[dict]:
    if spec == "revocation_artifact":
        return [top_level]
    if spec == "none":
        return []
    return spec  # inline list of revocation objects


def run(vectors_path: Path, enforcement_path: Path) -> int:
    source = json.loads(vectors_path.read_text())
    by_id = {v["id"]: v for v in source["vectors"]}
    top_rev = source["revocation_artifact"]
    cases = json.loads(enforcement_path.read_text())["cases"]

    lines = []
    failed = 0
    structural_seen: dict[str, bool] = {}
    for case in cases:
        vector = by_id[case["source"]]
        revocations = resolve_revocations(case["known_revocations"], top_rev)
        valid, failures, structural_ok = verdict(vector, revocations, case["model"])
        got = "PASS" if valid else "FAIL"
        ok = got == case["expected"]
        if not ok:
            failed += 1
        status = "ok" if ok else "MISMATCH"
        lines.append(f"[{status}] {case['id']} model={case['model']} source={case['source']} "
                     f"known_revocations={len(revocations)} verdict={got} expected={case['expected']}")
        for f in failures:
            lines.append(f"    {f}")
        # Separation check: the structural verdict must not depend on the model or on revocations.
        key = case["source"]
        structural_seen.setdefault(key, structural_ok)
        if structural_seen[key] != structural_ok:
            failed += 1
            lines.append(f"    STRUCTURAL VERDICT CHANGED for {key} across models/revocations")

    body = "\n".join(lines)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    print(body)
    print(f"\n{sum(1 for c in cases)} cases, {failed} failed")
    print(f"REPORT_SHA256 {digest}")
    return failed


def main():
    failed = run(BASE / "vectors.json", BASE / "enforcement-vectors.json")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
