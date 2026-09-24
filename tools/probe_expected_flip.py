"""Audit probe: is each vector's declared outcome actually scored?

For every vector that carries a flippable outcome (PASS/FAIL, ACCEPT/REJECT, or a
boolean under one of KEYS), flip it in a temporary copy of its corpus, run that
corpus's verifier, and record whether the exit code goes non-zero. A vector that
stays green was not scored: its declared outcome is decorative.

Only JSON files a verifier names in its own source are flipped for that verifier.
Vectors whose outcome is not a flippable scalar are listed as not probed; they
need a corpus-specific check (a mutant of the verifier), not this one.

    python3 tools/probe_expected_flip.py            # summary + every non-RED case
    python3 tools/probe_expected_flip.py --json out.json
"""
import collections
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(ROOT, "examples", "conformance")
KEYS = ("expected", "expected_result", "expected_outcome", "verdict")
FLIP = {"PASS": "FAIL", "FAIL": "PASS", "ACCEPT": "REJECT", "REJECT": "ACCEPT",
        "pass": "fail", "fail": "pass", "accept": "reject", "reject": "accept"}


def flipped(value):
    if isinstance(value, bool):
        return not value
    if isinstance(value, str) and value in FLIP:
        return FLIP[value]
    return None


def run(directory, script):
    try:
        return subprocess.run([sys.executable, script], cwd=directory,
                              capture_output=True, timeout=120).returncode
    except subprocess.TimeoutExpired:
        return "timeout"


def verifiers():
    paths = glob.glob(os.path.join(CONF, "*", "verify*.py")) + glob.glob(os.path.join(CONF, "*", "*", "verify*.py"))
    return sorted(p for p in paths if "venv" not in p and "crewai-unguarded-retry" not in p)


def probe():
    rows = []
    for script_path in verifiers():
        d, script = os.path.dirname(script_path), os.path.basename(script_path)
        source = open(script_path).read()
        for p in sorted(glob.glob(os.path.join(d, "*.json"))):
            name = os.path.basename(p)
            if name not in source:
                continue
            try:
                data = json.load(open(p))
            except ValueError:
                continue
            vectors = data.get("vectors") if isinstance(data, dict) else None
            if not isinstance(vectors, list):
                continue
            for i, v in enumerate(vectors):
                if not isinstance(v, dict):
                    continue
                vid = v.get("id") or v.get("name") or f"#{i}"
                key = next((k for k in KEYS if k in v and flipped(v[k]) is not None), None)
                row = {"verifier": os.path.relpath(script_path, CONF), "file": name, "id": vid}
                if key is None:
                    rows.append({**row, "result": "not-probed"})
                    continue
                tmp = tempfile.mkdtemp()
                try:
                    work = os.path.join(tmp, os.path.basename(d))
                    shutil.copytree(d, work, ignore=shutil.ignore_patterns("__pycache__", "venv"))
                    copy = json.loads(json.dumps(data))
                    copy["vectors"][i][key] = flipped(v[key])
                    with open(os.path.join(work, name), "w") as f:
                        json.dump(copy, f, indent=2)
                    rc = run(work, script)
                finally:
                    shutil.rmtree(tmp)
                rows.append({**row, "key": key, "result": "RED" if rc != 0 else "STAYS-GREEN"})
    return rows


if __name__ == "__main__":
    rows = probe()
    for r in rows:
        if r["result"] != "RED":
            print(r["result"], r["verifier"], r["file"], r["id"])
    print(dict(collections.Counter(r["result"] for r in rows)))
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as f:
            json.dump(rows, f, indent=1)
    sys.exit(1 if any(r["result"] == "STAYS-GREEN" for r in rows) else 0)
