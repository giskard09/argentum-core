"""delegation-chain-ref/SHA256SUMS must describe the files of the set as they are.

The file is published for third-party grading (`sha256sum -c SHA256SUMS`). It went stale once
(see CHANGELOG): five files changed after it was last written and nothing failed. These tests
regenerate it from the tracked files and fail if any file of the set changed, was added, or was
removed without regenerating (`python3 build_sha256sums.py` in that directory).
"""
import importlib.util
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "examples" / "conformance" / "delegation-chain-ref"


def _load():
    spec = importlib.util.spec_from_file_location("dcr_build_sha256sums", HERE / "build_sha256sums.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build = _load()


def test_committed_sums_match_the_files():
    assert build.differences((HERE / "SHA256SUMS").read_text()) == []


def test_committed_sums_are_what_the_script_writes():
    assert (HERE / "SHA256SUMS").read_text() == build.render()


def test_sha256sum_itself_agrees():
    r = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=HERE, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_tracked_file_is_listed_including_subdirectories():
    listed = {line.partition("  ")[2] for line in (HERE / "SHA256SUMS").read_text().splitlines()}
    names = set(build.tracked_files())
    assert listed == names
    assert any("/" in n for n in names), "subdirectories must be covered"
    assert "small-order-key-vectors.json" in listed and "verify.py" in listed


def test_a_changed_added_or_removed_file_is_reported(tmp_path):
    root = tmp_path / "set"
    root.mkdir()
    (root / "a.json").write_text("{}")
    (root / "sub").mkdir()
    (root / "sub" / "b.py").write_text("x = 1\n")
    names = ["a.json", "sub/b.py"]
    sums = build.render(root, names)
    assert build.differences(sums, root, names) == []
    (root / "a.json").write_text('{"a": 1}')
    assert build.differences(sums, root, names) == ["changed since SHA256SUMS: a.json"]
    (root / "a.json").write_text("{}")
    assert build.differences(sums, root, names + ["c.json"]) == ["tracked but not listed: c.json"]
    (root / "sub" / "b.py").unlink()
    assert build.differences(sums, root, names) == ["listed but missing: sub/b.py"]


def test_stale_sums_fail_check_mode(tmp_path):
    # A copy of the set with one byte changed: the script's own --check must exit non-zero.
    work = tmp_path / "w"
    shutil.copytree(HERE, work, ignore=shutil.ignore_patterns("__pycache__"))
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    subprocess.run(["git", "add", "."], cwd=work, check=True)
    ok = subprocess.run(["python3", "-B", "-I", "build_sha256sums.py", "--check"], cwd=work)
    assert ok.returncode == 0
    (work / "vectors.json").write_text((work / "vectors.json").read_text() + " ")
    bad = subprocess.run(["python3", "-B", "-I", "build_sha256sums.py", "--check"], cwd=work,
                         capture_output=True, text=True)
    assert bad.returncode == 1 and "changed since SHA256SUMS: vectors.json" in bad.stdout
