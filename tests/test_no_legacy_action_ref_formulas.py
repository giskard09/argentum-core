"""Regression guard: the two superseded action_ref constructions must not reappear in docs/ or examples/.

action_ref v1 is SHA-256(JCS({agent_id, action_type, scope, timestamp})) -- see docs/spec/action-ref.md.
Two earlier constructions circulated in docs and example code and do not produce v1 values:

  1. byte concatenation of the fields with an int64 big-endian timestamp_ms;
  2. a colon-joined string "agent_id:action_type:scope:timestamp" with an integer (seconds) timestamp.

This test fails if the text of either construction appears in a scanned file. Lines that carry the
word FINDING (self-audit comments that describe the removed scheme) are skipped, and historical
reports at the repository root (AUDIT_REPORT_*) are outside the scanned trees.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCANNED = ("docs", "examples")
SUFFIXES = {".md", ".py", ".ts", ".js", ".mjs", ".txt", ".json", ".yaml", ".yml"}
SKIP_DIRS = {"node_modules", "venv", ".venv", "__pycache__", "dist"}

LEGACY = {
    "concatenation + int64 big-endian timestamp": [
        re.compile(r"to_bytes\(\s*8\s*,\s*['\"]big['\"]\s*\)"),
        re.compile(r"agent_id\.encode\([^)]*\)\s*\|\|"),
    ],
    "colon-joined fields": [
        re.compile(r"\{agent_id\}\s*:\s*\{action_type\}"),
        re.compile(r"agent_id:action_type:scope"),
        re.compile(r"agent:type:scope"),
        re.compile(r"\$\{[^}]*agent_id[^}]*\}:\$\{"),
        re.compile(r"timestamp_seconds"),
    ],
}


def _scanned_files():
    for top in SCANNED:
        for path in (ROOT / top).rglob("*"):
            if path.is_file() and path.suffix in SUFFIXES and not (SKIP_DIRS & set(path.parts)):
                yield path


def _hits():
    for path in _scanned_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, 1):
            if "FINDING" in line:
                continue
            for name, patterns in LEGACY.items():
                if any(p.search(line) for p in patterns):
                    yield f"{path.relative_to(ROOT)}:{number}: {name}: {line.strip()[:100]}"


def test_legacy_action_ref_formulas_absent():
    hits = list(_hits())
    assert not hits, "superseded action_ref construction found:\n" + "\n".join(hits)


def test_guard_detects_both_constructions(tmp_path):
    """The guard is not vacuous: each pattern family fires on a sample of its construction."""
    samples = {
        "concatenation + int64 big-endian timestamp": "x = timestamp_ms.to_bytes(8, 'big')",
        "colon-joined fields": 'payload = f"{agent_id}:{action_type}:{scope}:{int(timestamp)}"',
    }
    for name, text in samples.items():
        assert any(p.search(text) for p in LEGACY[name]), name
