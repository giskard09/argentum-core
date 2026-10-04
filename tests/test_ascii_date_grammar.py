"""Guard: date/timestamp regexes must use [0-9], never \\d.

In Python 3 `\\d` matches Unicode digits (e.g. Arabic-Indic), so a regex built on it
accepts timestamps that are not ASCII. This was found in five example verifiers
(PR #115) and in the month gate of argentum.py.

The example verifiers under examples/conformance/ are standalone on purpose
(independent implementations, no shared module), so the grammar is copied there.
This test guards the copies instead of centralizing them.
"""
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files that define date/timestamp grammars.
SOURCES = sorted(
    set(glob.glob(os.path.join(ROOT, "examples", "conformance", "**", "*.py"), recursive=True))
    | {os.path.join(ROOT, "argentum.py")}
    | set(glob.glob(os.path.join(ROOT, "plugins", "**", "*.py"), recursive=True))
)

# A regex call whose pattern uses \d together with a date/time shape: YYYY, MM, HH, or a T separator.
REGEX_CALL = re.compile(r"(re\.compile|fullmatch|re\.match|re\.search|_re\.fullmatch)\(")
DATE_SHAPE = re.compile(r"\\d\{4\}|\\d\{2\}")


def _offending_lines():
    hits = []
    for path in SOURCES:
        if "/tests/" in path or path.endswith("test_ascii_date_grammar.py"):
            continue
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                code = line.split("#", 1)[0]
                if REGEX_CALL.search(code) and DATE_SHAPE.search(code):
                    hits.append(f"{os.path.relpath(path, ROOT)}:{lineno}: {line.strip()}")
    return hits


def test_date_regexes_use_ascii_digits():
    hits = _offending_lines()
    assert not hits, "\\d used in a date/timestamp regex (use [0-9]):\n" + "\n".join(hits)


def test_guard_detects_the_bug_it_is_meant_to_catch():
    # The guard itself must flag the pattern it exists for, so it cannot pass vacuously.
    sample = 'TS = re.compile(r"^\\d{4}-\\d{2}-\\d{2}T")'
    code = sample.split("#", 1)[0]
    assert REGEX_CALL.search(code) and DATE_SHAPE.search(code)
