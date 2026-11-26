"""delegation-chain-ref coverage vectors, RFC 8785 canonicalization, and mutants.

Needs PyNaCl, like the verifier. Covers: coverage-vectors.json is what its builder writes; the two
canonicalization vectors really differ from json.dumps(sort_keys=True), so a verifier that went
back to it would fail them; every negative vector names a failure_mode; every mutant of verify.py
is caught.
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "examples" / "conformance" / "delegation-chain-ref"


def _vectors():
    return json.loads((HERE / "coverage-vectors.json").read_text())["vectors"]


def test_coverage_vectors_are_what_the_builder_writes():
    r = subprocess.run([sys.executable, "-B", "-I", str(HERE / "build_coverage_vectors.py"), "--check"])
    assert r.returncode == 0


def test_canonicalization_vectors_differ_from_sort_keys():
    seen = 0
    for v in _vectors():
        if not v["id"].startswith("cov-jcs-"):
            continue
        seen += 1
        old_style = json.dumps(v["chain_artifact"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert hashlib.sha256(old_style.encode("utf-8")).hexdigest() != v["delegation_chain_ref"], v["id"]
    assert seen == 2


def test_every_negative_vector_names_a_failure_mode():
    for v in _vectors():
        if v["expected"] == "FAIL":
            assert v.get("failure_mode"), v["id"]


def test_verifier_passes_every_vector_file():
    r = subprocess.run([sys.executable, "-B", "-I", str(HERE / "verify.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:]
    assert "coverage-vectors.json" in r.stdout


def test_every_mutant_is_caught():
    r = subprocess.run([sys.executable, "-B", "-I", str(HERE / "mutants.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "32/32 caught" in r.stdout
