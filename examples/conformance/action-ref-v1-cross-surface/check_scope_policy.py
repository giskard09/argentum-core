#!/usr/bin/env python3
"""Cross-surface scope-policy consistency check for action-ref.md.

Institutionalizes the method aeoess (Pidlisnyi) used by hand in
draft-etcheverry-action-ref#6 (2026-08-25) to find bug #1 of PR#62:
docs/spec/action-ref.md's field table and its "Scope conventions" section
stated CONTRADICTORY policies on whether `scope` may be `""` -- and had for
10 days (commit 66df348, #48, 2026-08-15) before anyone noticed, because
nothing checked the two locations against each other.

This script extracts both locations' stated policy from docs/spec/action-ref.md
at each of a fixed set of git refs (git tags for released versions, plus a
working-tree/HEAD check for main) and flags any ref where they disagree.

It does NOT re-execute historical code. The pre-2026-07-29 refs (e.g. the
action-ref-v1.0 tag, 2026-05-23) predate plugins/agt_evidence_anchor/action_ref.py
entirely -- there is no reference implementation there to run. What DID exist
at every ref, and what actually diverged in practice, is the spec TEXT. This
tool checks that text is self-consistent at each ref; it complements (does not
replace) the runtime conformance vectors in ../action-ref-v1-domain-negative/,
which check the CURRENT implementation's behavior, not the document's wording
history.

Exit code 0 if every checked ref is internally consistent, 1 otherwise.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SPEC_PATH = "docs/spec/action-ref.md"

# Refs to check. "HEAD" always resolves to the current working tree's committed
# state (or index/worktree if run with --worktree); tags are the two spec
# versions that have ever been declared stable and citable externally.
DEFAULT_REFS = ["action-ref-v1.0", "action-ref-v2.0", "HEAD"]

STRICT = "STRICT (non-empty, no exception)"
PERMISSIVE = "PERMISSIVE (\"\" allowed as an explicit exception)"
UNKNOWN = "UNKNOWN (heuristic did not match known phrasing -- needs a human read)"
ABSENT = "ABSENT (no Scope conventions section / no scope field row at this ref)"


def get_spec_text(ref: str, use_worktree: bool = False) -> str | None:
    if use_worktree and ref == "HEAD":
        p = REPO / SPEC_PATH
        return p.read_text() if p.exists() else None
    result = subprocess.run(
        ["git", "show", f"{ref}:{SPEC_PATH}"],
        cwd=REPO, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def extract_field_table_row(text: str) -> str | None:
    for line in text.splitlines():
        if line.strip().startswith("| `scope` |") or line.strip().startswith("| scope |"):
            return line.strip()
    return None


def extract_scope_conventions_para(text: str) -> str | None:
    m = re.search(r"^## Scope conventions\s*$", text, re.MULTILINE)
    if not m:
        return None
    rest = text[m.end():]
    # First non-empty paragraph after the heading.
    para_match = re.search(r"\n\s*\n?(.+?)(?:\n\s*\n|\Z)", rest, re.DOTALL)
    if not para_match:
        return None
    return " ".join(para_match.group(1).split())


def classify_field_row(row: str | None) -> str:
    if row is None:
        return ABSENT
    lower = row.lower()
    permissive_markers = ('pass `""`' in lower or 'pass ""' in lower or "exception" in lower)
    if permissive_markers:
        return PERMISSIVE
    if "non-empty" in lower:
        return STRICT
    return UNKNOWN


def classify_conventions_para(para: str | None) -> str:
    if para is None:
        return ABSENT
    lower = para.lower()
    if "there is no" in lower and "exception" in lower:
        return STRICT
    if "no `\"\"`" in lower and "exception" in lower:
        return STRICT
    if "see the field table above for the" in lower and "exception" in lower:
        return PERMISSIVE
    if "non-empty" in lower and "exception" not in lower:
        return STRICT
    return UNKNOWN


def check_ref(ref: str, use_worktree: bool = False) -> tuple[bool, str]:
    text = get_spec_text(ref, use_worktree=use_worktree)
    if text is None:
        return True, f"{ref}: SKIPPED -- {SPEC_PATH} does not exist at this ref " \
                      "(pre-dates the spec file, or the ref itself doesn't resolve)"

    row = extract_field_table_row(text)
    para = extract_scope_conventions_para(text)
    field_verdict = classify_field_row(row)
    conv_verdict = classify_conventions_para(para)

    if field_verdict == ABSENT and conv_verdict == ABSENT:
        return True, f"{ref}: SKIPPED -- no scope field table or Scope conventions section yet"

    consistent = (
        field_verdict not in (UNKNOWN,)
        and conv_verdict not in (UNKNOWN,)
        and field_verdict.split()[0] == conv_verdict.split()[0]  # "STRICT"/"PERMISSIVE" prefix match
    )

    lines = [f"{ref}:"]
    lines.append(f"  field table row:      {field_verdict}")
    lines.append(f"    {row!r}" if row else "    (not found)")
    lines.append(f"  Scope conventions:    {conv_verdict}")
    lines.append(f"    {para!r}" if para else "    (not found)")
    lines.append(f"  -> {'CONSISTENT' if consistent else 'CONTRADICTION -- same document, two different scope policies'}")
    return consistent, "\n".join(lines)


def main() -> int:
    use_worktree = "--worktree" in sys.argv
    refs = [a for a in sys.argv[1:] if not a.startswith("--")] or DEFAULT_REFS

    all_ok = True
    for ref in refs:
        ok, report = check_ref(ref, use_worktree=use_worktree)
        print(report)
        print()
        all_ok = all_ok and ok

    if all_ok:
        print(f"All {len(refs)} ref(s) internally consistent.")
        return 0
    print("FAILED -- at least one ref has a scope-policy contradiction between "
          "the field table and Scope conventions section. This is exactly the "
          "bug class from PR#62 (aeoess/Pidlisnyi, draft-etcheverry-action-ref#6).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
