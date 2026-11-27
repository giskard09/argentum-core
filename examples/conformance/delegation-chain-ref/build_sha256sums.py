"""Regenerate SHA256SUMS for delegation-chain-ref.

SHA256SUMS lists every git-tracked file under this directory except itself, subdirectories
included (vectors, verifiers, the frozen verifier copies, interop sources, this script), as
`sha256sum` lines: `<hex>  <path relative to this directory>`, sorted by path. A third party
can grade a checkout with `sha256sum -c SHA256SUMS` from this directory.

    python3 build_sha256sums.py           # rewrite SHA256SUMS
    python3 build_sha256sums.py --check   # exit 1 and list what differs, write nothing

tests/test_delegation_chain_sha256sums.py runs the check, so a file of this set that changes
without regenerating the sums fails CI. Only tracked files are listed: an untracked local file
is neither listed nor checked.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUMS = "SHA256SUMS"


def tracked_files(root: Path = HERE) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "."], cwd=root, check=True,
                         capture_output=True).stdout.decode()
    names = [f for f in out.split("\0") if f and f != SUMS]
    return sorted(names, key=lambda n: n.encode("utf-8"))


def render(root: Path = HERE, names=None) -> str:
    names = tracked_files(root) if names is None else names
    return "".join(f"{hashlib.sha256((root / n).read_bytes()).hexdigest()}  {n}\n" for n in names)


def differences(sums_text: str, root: Path = HERE, names=None) -> list[str]:
    """What `sha256sum -c` plus a completeness check would report: files whose bytes differ from
    their line, listed files that are missing, tracked files that have no line."""
    names = tracked_files(root) if names is None else names
    listed = {}
    for line in sums_text.splitlines():
        digest, _, name = line.partition("  ")
        listed[name] = digest
    problems = []
    for name, digest in listed.items():
        path = root / name
        if not path.is_file():
            problems.append(f"listed but missing: {name}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            problems.append(f"changed since SHA256SUMS: {name}")
    problems += [f"tracked but not listed: {n}" for n in names if n not in listed]
    return problems


def main(argv) -> int:
    if "--check" in argv:
        problems = differences((HERE / SUMS).read_text())
        for p in problems:
            print(p)
        return 1 if problems else 0
    (HERE / SUMS).write_text(render())
    print(f"{len(tracked_files())} files -> {SUMS}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
