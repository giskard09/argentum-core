"""CI gate for examples/conformance: every reference verifier runs and exits 0.

Most corpora had no test of their own, so CI never ran them. Verifiers are
discovered by glob, so a new corpus is covered without editing this file.

The crewai-unguarded-retry verifiers need crewai installed. TODAY THEY RUN IN NO CI:
no workflow installs crewai (`grep -r crewai .github` is empty). They are reported as
skipped here, which means not run, not passed. Open debt: a pinned crewai CI job
(DEUDA_INTERNA 24/09), not built yet.

test_flipped_expected_turns_red: for corpora whose verifier used to ignore the
declared `expected`, flipping it in a copy of the corpus must make the verifier
exit non-zero. tools/probe_expected_flip.py runs the same probe over every corpus.
"""
import glob
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(ROOT, "examples", "conformance")
NEEDS_CREWAI = "crewai-unguarded-retry"

VERIFIERS = sorted(
    os.path.relpath(p, CONF)
    for p in (glob.glob(os.path.join(CONF, "*", "verify*.py")) + glob.glob(os.path.join(CONF, "*", "*", "verify*.py"))
              + glob.glob(os.path.join(CONF, "*", "validate.py")) + glob.glob(os.path.join(CONF, "*", "*", "validate.py")))
    if "venv" not in p
)

# An empty glob parametrizes to ONE skipped test and the run stays green. Floor measured 2026-11-16: 49 verify*.py
# (4 of them crewai) + 4 validate.py = 53. Raise it when a corpus is added; never lower it without saying why.
MIN_VERIFIERS = 53


def test_verifier_discovery_floor():
    assert len(VERIFIERS) >= MIN_VERIFIERS, f"found {len(VERIFIERS)} verifiers, expected >= {MIN_VERIFIERS}"


def _run(directory, script):
    return subprocess.run([sys.executable, script], cwd=directory, capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("rel", VERIFIERS)
def test_verifier_exits_zero(rel):
    if rel.startswith(NEEDS_CREWAI):
        pytest.skip("needs crewai; NOT run in any CI today (DEUDA_INTERNA 24/09)")
    r = _run(os.path.join(CONF, os.path.dirname(rel)), os.path.basename(rel))
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]


# Scripts the glob above does not pick up (names are check_*/run_*). Explicit list on purpose: a new script is a decision, not an
# accident. Each exits 0 on the real corpus, takes < 0.1 s, needs no network and no dependency CI lacks (PyNaCl is in requirements.txt;
# measured 2026-11-16 with -X importtime: only `nacl` is third-party).
EXTRA_SCRIPTS = [
    "delegation-chain-ref/ed25519-hardening/check_hardening.py",   # 12 vectors from ed25519-speccheck vs the pinned PyNaCl
    "settlement-retry-safety/run_battery.py",                       # 7 x402#3208 modes settle exactly once
    "delegation-chain-ref/moltycel-interop/run_interop.py",         # 2 MoltyCel-derived vectors, report hash stable across 2 runs
]


def test_extra_scripts_exist_and_floor():
    assert len(EXTRA_SCRIPTS) >= 3
    for rel in EXTRA_SCRIPTS:
        assert os.path.isfile(os.path.join(CONF, rel)), f"{rel} moved or deleted: update EXTRA_SCRIPTS on purpose"


@pytest.mark.parametrize("rel", EXTRA_SCRIPTS)
def test_extra_script_exits_zero(rel):
    r = _run(os.path.join(CONF, os.path.dirname(rel)), os.path.basename(rel))
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]


def test_scope_policy_is_consistent_at_head():
    """check_scope_policy.py exits 1 by design WITHOUT arguments: the immutable tag action-ref-v1.0 has a REAL, historical
    contradiction (field table permissive vs Scope conventions strict) that cannot be fixed. CI only checks HEAD, read from the
    working tree (--worktree) so the check cannot become a vacuous SKIPPED when git history is unavailable."""
    d = os.path.join(CONF, "action-ref-v1-cross-surface")
    r = subprocess.run([sys.executable, "check_scope_policy.py", "--worktree", "HEAD"], cwd=d, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "CONSISTENT" in r.stdout and "SKIPPED" not in r.stdout and "CONTRADICTION" not in r.stdout, r.stdout[-1500:]


FLIP = {"PASS": "FAIL", "FAIL": "PASS"}
FLIP_CASES = [
    ("audit-record-contract-compat", "expected", "boundary-anchoring-existence-only"),
    ("audit-record-contract-compat", "expected", "boundary-anchoring-precedence"),
    ("decision-binding-context-digest-v1", "expected_result", "cd-001"),
    ("decision-binding-context-digest-v1", "expected_result", "cd-002"),
    ("decision-binding-context-digest-v1", "expected_result", "cd-003"),
    ("decision-binding-context-digest-v1", "expected_result", "cd-004"),
    ("disclosure-scoped-ref", "expected", "pos-subset-disclosure"),
    ("disclosure-scoped-ref", "expected", "neg-hidden-field-altered"),
    ("disclosure-scoped-ref", "expected", "neg-salt-reuse-and-digest-substitution"),
]


@pytest.mark.parametrize("corpus,key,vid", FLIP_CASES)
def test_flipped_expected_turns_red(corpus, key, vid, tmp_path):
    work = tmp_path / corpus
    shutil.copytree(os.path.join(CONF, corpus), work, ignore=shutil.ignore_patterns("__pycache__"))
    path = work / "vectors.json"
    data = json.loads(path.read_text())
    (v,) = [v for v in data["vectors"] if v["id"] == vid]
    v[key] = FLIP[v[key]]
    path.write_text(json.dumps(data, indent=2))
    assert _run(work, "verify.py").returncode != 0
