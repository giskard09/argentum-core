"""The two frozen verifier copies under delegation-chain-ref/ (leaf-screen-halt, revoked-ancestor).

Each copy canonicalizes with json.dumps(sort_keys=True), which is not RFC 8785 (the spec requires it). The
copies are left as they are and their READMEs say so. These tests keep the READMEs and the code honest:
  - the copy still uses sort_keys (if someone changes it to RFC 8785, the README text must change too);
  - every JSON subtree of the directory canonicalizes to the same bytes under the copy and under jcs.py, so
    no vector depends on the difference. Adding one with a key outside the BMP or a number such as 1.0 fails
    here and forces a decision (change the copy, or keep it and declare it).
Needs PyNaCl, like the copies.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jcs import jcs_bytes  # noqa: E402

BASE = ROOT / "examples" / "conformance" / "delegation-chain-ref"
COPIES = ("revoked-ancestor", "leaf-screen-halt")


def _load(d):
    spec = importlib.util.spec_from_file_location("frozen_" + d.replace("-", "_"), BASE / d / "verify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _subtrees(o):
    yield o
    if isinstance(o, dict):
        for v in o.values():
            yield from _subtrees(v)
    elif isinstance(o, list):
        for v in o:
            yield from _subtrees(v)


@pytest.mark.parametrize("d", COPIES)
def test_copy_still_uses_sort_keys_and_readme_says_so(d):
    src = (BASE / d / "verify.py").read_text()
    readme = (BASE / d / "README.md").read_text()
    assert "sort_keys=True" in src
    assert "Canonicalization of this copy (declared limit)" in readme
    assert "not an RFC 8785 implementation" in readme


@pytest.mark.parametrize("d", COPIES)
def test_no_json_subtree_of_the_directory_depends_on_the_difference(d):
    mod = _load(d)
    files = sorted((BASE / d).glob("*.json"))
    assert files
    n = 0
    for f in files:
        for sub in _subtrees(json.loads(f.read_text())):
            n += 1
            assert mod.jcs(sub).encode("utf-8") == jcs_bytes(sub), (f.name, str(sub)[:80])
    assert n > 20


@pytest.mark.parametrize("d", COPIES)
def test_the_difference_is_real(d):
    # The copy and RFC 8785 do differ on the data the READMEs describe; if this stops being true the
    # READMEs are out of date.
    mod = _load(d)
    assert mod.jcs({"￿": 2, "\U0001F600": 1}).encode("utf-8") != jcs_bytes({"￿": 2, "\U0001F600": 1})
    assert mod.jcs({"n": 1.0}).encode("utf-8") != jcs_bytes({"n": 1.0})
