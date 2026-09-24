"""CI gate for examples/conformance/host-capability-ref.

1. Every vector scores as declared on both hosts (with and without the algorithm).
2. build.py regenerates vectors.json byte for byte.
3. Each vector is turned red by at least one mutant of the verifier; changed_cases
   records every case a mutant moves, as (vector id, host).
"""
import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VEC = os.path.join(ROOT, "examples", "conformance", "host-capability-ref")


def _load(name):
    spec = importlib.util.spec_from_file_location("hcr_" + name, os.path.join(VEC, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


verify = _load("verify")
sys.modules["verify"] = verify  # build.py does `from verify import ...`
build = _load("build")
del sys.modules["verify"]


def _red(v):
    return {(vid, host) for vid, host, _, ok in v.run() if not ok}


def test_every_vector_scores_as_declared():
    results = verify.run()
    assert len(results) == 6 and all(ok for *_, ok in results), results


def test_build_is_deterministic():
    with open(os.path.join(VEC, "vectors.json")) as f:
        assert f.read() == json.dumps(build.build(), indent=2, ensure_ascii=False) + "\n"


def _collapse(orig, artifact, capabilities):
    verdict, failures, not_assessed = orig(artifact, capabilities)
    if not_assessed:
        return "FAIL", failures + ["signature_invalid: collapsed"], []
    return verdict, failures, not_assessed


def _mutant_collapse(orig):
    """Missing capability reported as a bad signature."""
    return lambda artifact, capabilities: _collapse(orig, artifact, capabilities)


def _mutant_fail_open(orig):
    """Missing capability treated as a verified signature."""
    def f(artifact, capabilities):
        verdict, failures, not_assessed = orig(artifact, capabilities)
        return ("FAIL" if failures else "PASS"), failures, []
    return f


def _mutant_not_assessed_masks_fail(orig):
    """NOT_ASSESSED outranks an adverse finding."""
    def f(artifact, capabilities):
        verdict, failures, not_assessed = orig(artifact, capabilities)
        return ("NOT_ASSESSED" if not_assessed else verdict), failures, not_assessed
    return f


def _mutant_skip_preimage_check(orig):
    """Declared preimage_jcs trusted instead of recomputed."""
    def f(artifact, capabilities):
        a = dict(artifact, preimage=json.loads(artifact["preimage_jcs"]))
        return orig(a, capabilities)
    return f


def _mutant_signature_always_valid(orig):
    """Capable host never actually checks the signature."""
    return lambda msg, pubkey, sig: True


MUTANTS = {
    "missing_capability_is_bad_signature": ("evaluate", _mutant_collapse, {
        ("hc-001-valid-signature", "incapable"), ("hc-002-invalid-signature", "incapable")}),
    "missing_capability_fails_open": ("evaluate", _mutant_fail_open, {
        ("hc-001-valid-signature", "incapable"), ("hc-002-invalid-signature", "incapable")}),
    "not_assessed_masks_fail": ("evaluate", _mutant_not_assessed_masks_fail, {
        ("hc-003-mixed-preimage-mismatch", "incapable")}),
    "trust_declared_preimage_jcs": ("evaluate", _mutant_skip_preimage_check, {
        ("hc-003-mixed-preimage-mismatch", "capable"), ("hc-003-mixed-preimage-mismatch", "incapable")}),
    "signature_always_valid": ("schnorr_verify", _mutant_signature_always_valid, {
        ("hc-002-invalid-signature", "capable")}),
}


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_mutant_turns_vectors_red(name, monkeypatch):
    attr, make, changed_cases = MUTANTS[name]
    monkeypatch.setattr(verify, attr, make(getattr(verify, attr)))
    assert _red(verify) == changed_cases


def test_every_vector_has_a_mutant():
    ids = {v["id"] for v in build.build()["vectors"]}
    covered = {vid for _, _, cases in MUTANTS.values() for vid, _ in cases}
    assert ids <= covered, ids - covered
