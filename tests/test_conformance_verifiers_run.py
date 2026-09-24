"""CI gate for examples/conformance: every reference verifier runs and exits 0.

Most corpora had no test of their own, so CI never ran them. Verifiers are
discovered by glob, so a new corpus is covered without editing this file.

The crewai-unguarded-retry verifiers need crewai installed and run in their own
job (see DEUDA: pinned crewai CI job); they are skipped here, not silently passed.

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
    for p in glob.glob(os.path.join(CONF, "*", "verify*.py")) + glob.glob(os.path.join(CONF, "*", "*", "verify*.py"))
    if "venv" not in p
)


def _run(directory, script):
    return subprocess.run([sys.executable, script], cwd=directory, capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("rel", VERIFIERS)
def test_verifier_exits_zero(rel):
    if rel.startswith(NEEDS_CREWAI):
        pytest.skip("needs crewai; runs in its own job")
    r = _run(os.path.join(CONF, os.path.dirname(rel)), os.path.basename(rel))
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]


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
