"""CI gate for examples/conformance/delegation-chain-ref.

1. Every vector file scores clean against the reference verifier (an expected
   FAIL has to fail for its failure_mode).
2. build_key_completeness.py regenerates key-completeness-vectors.json byte for byte.
3. Each key-completeness vector is turned red by at least one mutant of the
   verifier. changed_cases records every case a mutant moves, not only the one
   it targets.
"""
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VEC = os.path.join(ROOT, "examples", "conformance", "delegation-chain-ref")
FILES = ("vectors.json", "cross-org-vectors.json", "replay-vectors.json", "key-completeness-vectors.json")


def _load(name):
    spec = importlib.util.spec_from_file_location("dcr_" + name, os.path.join(VEC, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


verify = _load("verify")
build = _load("build_key_completeness")


def _red_cases(v):
    """Ids of vectors that score red in any file under verifier module v."""
    red = set()
    for fname in FILES:
        data = json.loads(Path(VEC, fname).read_text())
        seen = v.SeenRegistry()
        for vec in data["vectors"]:
            expected = vec["expected"] if isinstance(vec["expected"], list) else [vec["expected"]]
            pubkeys = vec.get("pubkeys", data.get("pubkeys", {}))
            complete = vec.get("keys_are_complete", data.get("keys_are_complete", False))
            verdict, failures, _ = v.evaluate_vector(vec, pubkeys, seen, complete)
            ok = verdict in expected
            if ok and verdict == "FAIL" and vec.get("failure_mode"):
                ok = any(f.startswith(vec["failure_mode"]) for f in failures)
            if not ok:
                red.add(vec["id"])
    return red


@pytest.mark.parametrize("fname", FILES)
def test_vector_file_scores_clean(fname, capsys):
    passed, failed = verify.run_file(Path(VEC, fname))
    assert failed == 0 and passed > 0


def test_build_is_deterministic():
    assert Path(VEC, "key-completeness-vectors.json").read_text() == (
        json.dumps(build.build(), indent=2, ensure_ascii=False) + "\n"
    )


def _mutant_collapse(orig):
    """Unresolved key reported as a bad signature (the AC-11 collapse)."""
    def f(*a):
        r = orig(*a)
        return verify.HOP_SIG_INVALID if r == verify.HOP_SIG_KEY_UNRESOLVED else r
    return f


def _mutant_fail_open(orig):
    """Unresolved key treated as a verified signature."""
    def f(*a):
        r = orig(*a)
        return verify.HOP_SIG_VALID if r == verify.HOP_SIG_KEY_UNRESOLVED else r
    return f


def _mutant_ignore_declaration(orig):
    """keys_are_complete dropped: the caller's declaration never reaches the check."""
    def f(vector, pubkeys=None, seen_registry=None, keys_are_complete=False):
        return orig(vector, pubkeys, seen_registry, False)
    return f


def _mutant_not_assessed_masks_fail(orig):
    """Verdict precedence swapped: anything not assessed hides an adverse finding."""
    def f(*a, **kw):
        verdict, failures, not_assessed = orig(*a, **kw)
        if not_assessed:
            return "NOT_ASSESSED", failures, not_assessed
        return verdict, failures, not_assessed
    return f


def _mutant_preimage_drops_chain_id(orig):
    """Hop preimage recomputed without chain_id: every validly signed hop stops verifying."""
    def f(chain_id, hop):
        return orig("", hop)
    return f


MUTANTS = {
    "preimage_drops_chain_id": ("hop_signing_preimage", _mutant_preimage_drops_chain_id,
                                {"kc-001-all-keys-present",
                                 "kc-002-key-absent-not-declared-complete",
                                 "cross-org-001-independent-signers",
                                 "replay-001-first-submission",
                                 "replay-002-resubmission-same-chain-id",
                                 "replay-004-valid-retry-after-invalid-attempt"}),
    "collapse_unresolved_to_invalid": ("verify_hop_signature", _mutant_collapse,
                                       {"kc-002-key-absent-not-declared-complete",
                                        "kc-003-key-absent-declared-complete"}),
    "unresolved_fails_open": ("verify_hop_signature", _mutant_fail_open,
                              {"kc-002-key-absent-not-declared-complete",
                               "kc-003-key-absent-declared-complete"}),
    "ignore_completeness_declaration": ("evaluate_vector", _mutant_ignore_declaration,
                                        {"kc-003-key-absent-declared-complete"}),
    "not_assessed_masks_fail": ("evaluate_vector", _mutant_not_assessed_masks_fail,
                                {"kc-004-mixed-forged-and-key-absent"}),
}


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_mutant_turns_vectors_red(name, monkeypatch):
    attr, make, changed_cases = MUTANTS[name]
    monkeypatch.setattr(verify, attr, make(getattr(verify, attr)))
    assert _red_cases(verify) == changed_cases


def test_every_key_completeness_vector_has_a_mutant():
    ids = {v["id"] for v in build.build()["vectors"]}
    covered = set().union(*(c for _, _, c in MUTANTS.values()))
    assert ids <= covered, ids - covered
