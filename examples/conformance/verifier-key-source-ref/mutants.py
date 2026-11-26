"""Mutants for verifier-key-source-ref: each one removes one rule of verify.py and
must fail at least one vector. A corpus that a mutant passes does not show that
the rule is checked.

    python3 mutants.py    # exit 0 iff every mutant is caught
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "verify.py").read_text()

# Not listed: dropping the end anchor of _TS (fullmatch -> match). No vector can
# catch it: parse_instant also rejects trailing text through datetime.fromisoformat,
# so the verdict is the same either way. The anchor is still there because the
# repo's regex ratchet requires it.
MUTANTS = {
    "timestamps-compared-as-strings":
        ("if parse_instant(krt) > parse_instant(fixture_certification_time):", "if krt > fixture_certification_time:"),
    "absent-key-resolution-time-passes":
        ("if _absent(krt):", "if False:"),
    "absent-certification-time-passes":
        ('if records and _absent(cert_time):', 'if False:'),
    "unknown-key-source-accepted":
        ("elif ks not in KEY_SOURCES:", "elif False:"),
    "evidence-hash-stands-in-for-public-key-hash":
        ("has_key = not _absent(pkh)\n    else:", "has_key = not _absent(pkh) or not _absent(evh)\n    else:"),
    "hash-format-not-checked":
        ("if not _absent(val) and not (isinstance(val, str) and _HEX64.fullmatch(val)):", "if False:"),
    "role-registry-ignored":
        ("    if role_registry is None:\n        if sid in UNBOUND_SIGNER_IDS:", "    if True:\n        if sid in UNBOUND_SIGNER_IDS:"),
    "out-of-scope-satisfies":
        ('elif vr != "pass":', 'elif vr not in ("pass", "out_of_scope"):'),
    "unknown-verification-result-accepted":
        ("if vr not in VERIFICATION_RESULTS:", "if False:"),
    "hash-regex-not-anchored-at-end":
        ("_HEX64.fullmatch(val)", "_HEX64.match(val)"),
    "sentinel-not-rejected":
        ("if sid in UNBOUND_SIGNER_IDS:", "if False:"),
}


def caught_by(src):
    ns = {"__file__": str(HERE / "verify.py"), "__name__": "mutant"}
    exec(compile(src, "verify_mutant.py", "exec"), ns)
    canon, vectors = ns["load_vectors"]()
    return [v["id"] for v in vectors if not ns["score"](v, canon)[0]]


def main() -> int:
    bad = 0
    base = caught_by(SRC)
    print(f"unmutated verifier fails {len(base)} vector(s)")
    bad += bool(base)
    for name, (old, new) in MUTANTS.items():
        if SRC.count(old) != 1:
            print(f"BAD  {name}: mutation site not found exactly once")
            bad += 1
            continue
        hit = caught_by(SRC.replace(old, new, 1))
        print(f"{'OK ' if hit else 'BAD'}  {name}: fails {len(hit)} vector(s) {hit[:3]}")
        bad += not hit
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
