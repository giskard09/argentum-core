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
conformance data — present only in agenttrust-v1 today), this script's
own output file and conformance-vectors.json (built FROM this export by
build_conformance_vectors.py), so re-running is idempotent.

Only files tracked by git are exported. The script used to walk the disk,
so an untracked local virtualenv (crewai-unguarded-retry/venv/) put 59
site-packages JSON files into the export.

Usage: python3 build_export.py [--out conformance-export.json]
"""

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXCLUDE_DIRS = {"__pycache__", "node_modules"}
EXCLUDE_FILENAMES = {"package.json", "package-lock.json"}
# Built from this export; aggregating it would nest the export inside itself.
DERIVED_OUTPUTS = {"conformance-vectors.json"}


def tracked_files() -> set:
    out = subprocess.run(["git", "ls-files", "-z", "."], cwd=HERE, check=True,
                         capture_output=True).stdout.decode()
    return {(HERE / f).resolve() for f in out.split("\0") if f}


TRACKED = tracked_files()


def collect_dir_files(d: Path) -> dict:
    files = {}
    for p in sorted(d.rglob("*.json")):
        if p.resolve() not in TRACKED:
            continue
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
        if entry.name in (out_name, "README.md", "build_export.py") or entry.name in DERIVED_OUTPUTS:
            continue
        if entry.is_file() and entry.resolve() not in TRACKED:
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
