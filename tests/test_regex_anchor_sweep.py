"""Guard against '$' in regexes used with re.match.

'$' matches at end-of-string OR immediately before a trailing newline. With
re.match that lets a value with '\\n' appended pass a grammar check and then be
hashed or compared as a different string. Anchor with '\\Z' (or use fullmatch).

This test scans tracked Python files for compiled patterns that end in '$' and
are applied with .match(). Patterns compiled with re.MULTILINE are skipped,
because there '$' is meant to match at line ends.
"""
import os
import re
import subprocess

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSIGN = re.compile(r"""^\s*(\w+)\s*=\s*re\.compile\(\s*r(['"])(.*)\2\s*(,[^)]*)?\)""")


def _tracked_py_files():
    out = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    return [f for f in out if not f.startswith("tests/")]


def _violations():
    found = []
    for rel in _tracked_py_files():
        path = os.path.join(ROOT, rel)
        try:
            src = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        for line in src.splitlines():
            m = ASSIGN.match(line)
            if not m:
                continue
            name, pattern, flags = m.group(1), m.group(3), m.group(4) or ""
            if "MULTILINE" in flags or not pattern.endswith("$"):
                continue
            if re.search(rf"\b{re.escape(name)}\.match\(", src):
                found.append(f"{rel}: {name} = r'{pattern}'")
    return found


def test_no_dollar_anchored_pattern_used_with_match():
    assert _violations() == [], (
        "use \\Z (or fullmatch) instead of $ for these patterns:\n" + "\n".join(_violations())
    )


def test_guard_catches_the_original_defect():
    """Sanity check that the scanner flags the pattern that caused the bug."""
    bad = re.compile(r"^[0-9]+$")
    assert bad.match("123\n")  # the defect: $ matches before a trailing newline
    assert ASSIGN.match('_EPOCH_MS_RE = re.compile(r"^[0-9]+$")')
