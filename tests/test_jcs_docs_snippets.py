"""Every jcs() recipe published in docs/spec must be RFC 8785, not code-point order.

Until 2026-09-22 ~20 docs/spec files (and 4 fixtures' reproduce_in_python)
showed json.dumps(sort_keys=True) / dict(sorted(obj.items())) as "the" JCS
implementation. Production used jcs.py (UTF-16 order) and was correct, but
the recipe an external implementer would copy diverged from RFC 8785 §3.2.3
for keys outside the BMP. This test extracts every `def jcs` from docs/spec
and runs it against examples/conformance/jcs-utf16-key-order-v1, so the
docs cannot silently drift back to the code-point recipe.
"""
import json
import os
import re
import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jcs import jcs_dumps

SET_DIR = ROOT / "examples/conformance/jcs-utf16-key-order-v1"
VECTORS = json.loads((SET_DIR / "vectors.json").read_text())["vectors"]
POSITIVES = [v for v in VECTORS if v["kind"] == "positive"]


def _doc_helpers():
    """(source, code) for every `def jcs` in docs/spec markdown and fixtures."""
    out = []
    spec = ROOT / "docs/spec"
    for md in sorted(spec.glob("*.md")):
        for block in re.findall(r"```python\n(.*?)```", md.read_text(), re.S):
            m = re.search(r"^def jcs\(obj\):\n(?:(?:    .*|)\n)+", block + "\n", re.M)
            if m:
                out.append((md.name, "import json\n" + m.group(0)))
    for fx in sorted((spec / "fixtures").glob("*.json")):
        code = json.loads(fx.read_text()).get("reproduce_in_python", "")
        m = re.search(r"^def jcs\(obj\).*(?:\n    .*)*", code, re.M)
        if m:
            out.append((fx.name, "import json\n" + m.group(0) + "\n"))
    return out


HELPERS = _doc_helpers()


def test_found_the_published_helpers():
    # 17 markdown files (cross-system-verification.md has two) + 4 fixtures
    # carried a jcs() recipe when this test was written.
    assert len(HELPERS) >= 21


def test_verifier_passes():
    assert runpy.run_path(str(SET_DIR / "verify.py"), run_name="not_main")["main"]()


@pytest.mark.parametrize("vector", POSITIVES, ids=[v["id"] for v in POSITIVES])
def test_reference_jcs_matches_vectors(vector):
    assert jcs_dumps(vector["input"]) == vector["expected_canonical"]


@pytest.mark.parametrize("source,code", HELPERS, ids=[s for s, _ in HELPERS])
def test_doc_helper_is_rfc8785(source, code):
    ns = {}
    exec(code, ns)
    for v in POSITIVES:
        assert ns["jcs"](v["input"]) == v["expected_canonical"], f"{source}: {v['id']}"
