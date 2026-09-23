"""
Vector key gate: every JSON key in a vector set must appear in the external
spec it claims to instantiate, as a field.

Catches fields no verifier checks: a fixture with an invented key ("tool"
where draft-farley-acta-signed-receipts-03 §3.1.1 requires "tool_name") can
pass a signature verifier, because the signature covers whatever bytes are
there. Found in argentum-core#96 by robertolocatelli81-dev (Noûs).

Opt-in per set via tools/vector_key_gate.json. It only applies to sets whose
fixtures declare to be payloads of an external schema; a set in our own
composite format carries metadata keys no external spec defines.

A key counts as backed by the spec when it appears:
  1. quoted: "key"
  2. as a field definition at line start: key (REQUIRED|OPTIONAL|...)
  3. in prose, only if it is identifier-shaped (snake_case or camelCase);
     a common word like "tool" or "type" in prose backs nothing.

Usage:
  python3 tools/check_vector_keys.py            # every set in the manifest
  python3 tools/check_vector_keys.py SPEC DIR [EXCLUDE ...]
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "tools/vector_key_gate.json"


def collect_keys(vector_dir: Path, exclude: set[str]) -> dict[str, set[str]]:
    keys: dict[str, set[str]] = {}

    def walk(o, fname):
        if isinstance(o, dict):
            for k, v in o.items():
                keys.setdefault(k, set()).add(fname)
                walk(v, fname)
        elif isinstance(o, list):
            for v in o:
                walk(v, fname)

    for p in sorted(vector_dir.glob("*.json")):
        if p.name not in exclude:
            walk(json.loads(p.read_text(encoding="utf-8")), p.name)
    return keys


def field_uses(spec: str, key: str) -> int:
    e = re.escape(key)
    n = len(re.findall(r'"' + e + r'"', spec)) + len(
        re.findall(r"(?m)^\s*" + e + r"\s*\((?:REQUIRED|OPTIONAL|RECOMMENDED|CONDITIONAL)", spec)
    )
    if not n and re.search(r"_|[a-z][A-Z]", key):
        n = len(re.findall(r"(?<![A-Za-z0-9_])" + e + r"(?![A-Za-z0-9_])", spec))
    return n


def unbacked_keys(spec: str, vector_dir: Path, exclude: set[str]) -> dict[str, set[str]]:
    keys = collect_keys(vector_dir, exclude)
    return {k: files for k, files in sorted(keys.items()) if not field_uses(spec, k)}


def check_manifest() -> list[str]:
    errors = []
    for entry in json.loads(MANIFEST.read_text(encoding="utf-8"))["sets"]:
        spec_path = ROOT / entry["spec"]
        raw = spec_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["spec_sha256"]:
            errors.append(f"{entry['vectors']}: {entry['spec']} does not match spec_sha256")
            continue
        bad = unbacked_keys(raw.decode("utf-8", "replace"), ROOT / entry["vectors"], set(entry.get("exclude", [])))
        for k, files in bad.items():
            errors.append(f"{entry['vectors']}: key {k!r} not defined as a field in {entry['spec']} ({', '.join(sorted(files))})")
    return errors


def main(argv: list[str]) -> int:
    if argv:
        spec = Path(argv[0]).read_text(encoding="utf-8", errors="replace")
        errors = [f"key {k!r} not defined as a field ({', '.join(sorted(f))})"
                  for k, f in unbacked_keys(spec, Path(argv[1]), set(argv[2:])).items()]
    else:
        errors = check_manifest()
    for e in errors:
        print("FAIL", e)
    if not errors:
        print("OK: every vector key is defined as a field in its spec")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
