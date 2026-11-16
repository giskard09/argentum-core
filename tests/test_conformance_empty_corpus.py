"""Ratchet: a conformance verifier must NOT report success on an empty corpus.

For each verifier in examples/conformance, the list-shaped corpus (every list of objects in every JSON file in the
verifier's own directory) is emptied IN A COPY of the repo and the verifier is run. It must exit non-zero with an
explicit message (not a traceback). A verifier that exits 0 on nothing proves nothing: "0/0 passed" is green.

EMPTY_OK_ALLOWLIST is the explicit, reasoned list of verifiers that still do (to be worked down, never grown):
  - test_allowlisted_verifier_still_needs_its_entry fails when an entry already turns red -> remove it;
  - test_verifier_turns_red_on_empty_corpus fails for any verifier that is not listed and does not turn red,
    so a NEW verifier without a guard cannot land silently;
  - test_allowlist_names_existing_verifiers fails on a stale entry.
The probe only empties JSON inside the verifier's own directory; fixtures it reads from a sibling directory are
not touched (that is declared, not hidden). It also does not check that specific vector IDs are present: it
tests "empty", not "incomplete".
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


def _discover():
    paths = (glob.glob(os.path.join(CONF, "*", "verify*.py")) + glob.glob(os.path.join(CONF, "*", "*", "verify*.py"))
             + glob.glob(os.path.join(CONF, "*", "validate.py")))
    return sorted(os.path.relpath(p, CONF) for p in paths if "venv" not in p and not os.path.relpath(p, CONF).startswith(NEEDS_CREWAI))


VERIFIERS = _discover()

# Verifiers that already failed closed on an empty corpus with their OWN message before the ZERO_CASES guards.
# Every other verifier that is not allowlisted must say ZERO_CASES, so a guard cannot be swapped for an incidental failure.
OWN_EMPTY_MESSAGE = {
    "evidence-anchor-static-analysis-v0/verify.py",
    "scitt-card-trust-root-ref/verify.py",
    "trail-head-window-ref/verify.py",
}

EMPTY_OK_ALLOWLIST = {
    "art12-log-integrity-notes/verify.py": "declares itself 'not an Article 12 conformance check' (notes, not a conformance verifier)",
    "axes-exchange/validate.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "basepay/verify.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "composed-attestation-bip340-cell/verify.py": "cell.json holds no list-of-objects corpus: the probe empties nothing (vacuous), needs its own check",
    "composed-decision-chain-recompute/verify.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "custody-ref/validate.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "delegation-chain-ref/mid-hop-revocation/verify.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "governance-block-join-ref-v1/verify.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "graph-advocate/verify.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "host-capability-ref/verify.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "offer-identity-ref/verify.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "peer-reconciliation-ref/verify.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "recipient-allocation-ref/verify.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "retrieval-provenance-v1/verify.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "settlement-retry-safety/verify.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "settlement-retry-safety/verify_generic.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "timestamp-grammar-negative-v1/verify.py": "declares 'no negative vectors present ... Positive control only' on its own output",
    "transition-sufficiency-ref-v1/verify.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
    "verifier-key-source-ref/verify.py": "no ZERO_CASES guard yet; this batch guards the externally-cited baselines first (ratchet: shrink, do not grow)",
}


def test_verifier_discovery_is_not_empty():
    assert len(VERIFIERS) >= 45, f"only {len(VERIFIERS)} verifiers found; discovery is broken"


def test_allowlist_names_existing_verifiers():
    assert set(EMPTY_OK_ALLOWLIST) <= set(VERIFIERS)


def _emptied(o):
    if isinstance(o, list):
        return [] if o and all(isinstance(x, dict) for x in o) else [_emptied(x) for x in o]
    if isinstance(o, dict):
        return {k: _emptied(v) for k, v in o.items()}
    return o


@pytest.fixture(scope="module")
def repo_copy(tmp_path_factory):
    dst = tmp_path_factory.mktemp("emptycorpus") / "repo"
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".venv", "venv", ".git", "__pycache__", "tests", "trails.db", "node_modules"))
    return dst


def _probe(repo_copy, rel):
    """Empty the corpus of `rel` inside the copy, run it, restore. Returns (files_emptied, returncode, stdout+stderr)."""
    d = repo_copy / "examples" / "conformance" / os.path.dirname(rel)
    saved = {}
    try:
        for j in sorted(d.rglob("*.json")):
            try:
                data = json.loads(j.read_text(encoding="utf-8"))
            except Exception:
                continue
            new = _emptied(data)
            if new != data:
                saved[j] = j.read_bytes()
                j.write_text(json.dumps(new), encoding="utf-8")
        r = subprocess.run([sys.executable, os.path.basename(rel)], cwd=d, capture_output=True, text=True, timeout=120)
        return len(saved), r.returncode, r.stdout + r.stderr
    finally:
        for j, b in saved.items():
            j.write_bytes(b)


@pytest.mark.parametrize("rel", VERIFIERS)
def test_verifier_turns_red_on_empty_corpus(rel, repo_copy):
    n, code, out = _probe(repo_copy, rel)
    if rel in EMPTY_OK_ALLOWLIST:
        return   # known gap, reason recorded in EMPTY_OK_ALLOWLIST; test_allowlisted_verifier_still_needs_its_entry keeps it honest
    assert n > 0, f"{rel}: nothing to empty in its directory; the probe is vacuous, allowlist it with a reason"
    assert code != 0, f"{rel}: exit 0 on an EMPTY corpus; add a ZERO_CASES guard or allowlist it with a reason\n{out[-400:]}"
    assert "Traceback" not in out, f"{rel}: fails by crash, not by an explicit message\n{out[-400:]}"
    if rel not in OWN_EMPTY_MESSAGE:
        assert "ZERO_CASES" in out, f"{rel}: exit != 0 but not through its ZERO_CASES guard (incidental failure?)\n{out[-400:]}"


@pytest.mark.parametrize("rel", sorted(EMPTY_OK_ALLOWLIST))
def test_allowlisted_verifier_still_needs_its_entry(rel, repo_copy):
    n, code, out = _probe(repo_copy, rel)
    assert n == 0 or code == 0, f"{rel}: now turns red on an empty corpus; remove it from EMPTY_OK_ALLOWLIST"
