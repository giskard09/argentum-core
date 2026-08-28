"""
Aggregates every conformance vector set under examples/conformance/ into one
self-contained export file (conformance-export.json), ready to publish.

Each set keeps its original JSON bytes verbatim under "files" — this script
does not rename fields, does not pick a schema, and does not choose the
public route. Those three decisions are deliberately deferred until the
discovery-pattern convention converges with Kenneives/CTEF
(agentgraph.co/.well-known/cte-test-vectors.json, A2A#1628) — see the
"note" field in the generated export and the dept-codigo/dept-estrategia
handoff (2026-08-27/28) for why.

A "set" is one top-level entry directly under examples/conformance/:
  - a standalone *.json file (its own set, id = filename minus extension)
  - a directory (all *.json files under it, recursively, become that set's
    "files" map — keyed by path relative to the directory)

Excluded, deliberately: README.md, verify.py / *.py, __pycache__/,
node_modules/, package.json, package-lock.json (npm tooling noise, not
conformance data — present only in agenttrust-v1 today) and this script's
own output file, so re-running is idempotent.

Usage: python3 build_export.py [--out conformance-export.json]
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
EXCLUDE_DIRS = {"__pycache__", "node_modules"}
EXCLUDE_FILENAMES = {"package.json", "package-lock.json"}


def collect_dir_files(d: Path) -> dict:
    files = {}
    for p in sorted(d.rglob("*.json")):
        if p.name in EXCLUDE_FILENAMES:
            continue
        if any(part in EXCLUDE_DIRS for part in p.relative_to(d).parts):
            continue
        rel = str(p.relative_to(d))
        files[rel] = json.loads(p.read_text())
    return files


def build(out_name: str) -> dict:
    sets = {}
    skipped = []

    for entry in sorted(HERE.iterdir()):
        if entry.name in (out_name, "README.md", "build_export.py"):
            continue
        if entry.name.startswith("."):
            continue

        if entry.is_file() and entry.suffix == ".json":
            set_id = entry.stem
            sets[set_id] = {
                "path": f"examples/conformance/{entry.name}",
                "files": {entry.name: json.loads(entry.read_text())},
            }
        elif entry.is_dir():
            files = collect_dir_files(entry)
            if not files:
                skipped.append(entry.name)
                continue
            sets[entry.name] = {
                "path": f"examples/conformance/{entry.name}/",
                "files": files,
            }
        # else: not a set (e.g. loose .py, .md at top level) — ignored silently

    if skipped:
        print(f"skipped (no .json found): {', '.join(skipped)}", file=sys.stderr)

    return {
        "export_version": "conformance-export-v0-draft",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        ),
        "generated_by": "examples/conformance/build_export.py",
        "source_repo": "giskard09/argentum-core",
        "note": (
            "Draft aggregation of every conformance vector set in this repo. "
            "Public discovery route and final field-naming convention are deliberately "
            "NOT decided here — pending convergence with Kenneives/CTEF "
            "(agentgraph.co/.well-known/cte-test-vectors.json pattern, A2A#1628) so the "
            "ecosystem doesn't end up with two competing conventions. Each set's `files` "
            "map preserves the original vectors.json/fixture.json bytes unmodified."
        ),
        "set_count": len(sets),
        "sets": sets,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="conformance-export.json")
    args = ap.parse_args()

    export = build(args.out)
    out_path = HERE / args.out
    out_path.write_text(json.dumps(export, indent=2, ensure_ascii=False, sort_keys=False) + "\n")

    print(f"{export['set_count']} sets aggregated -> {out_path}")


if __name__ == "__main__":
    main()
