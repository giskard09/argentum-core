#!/usr/bin/env python3
"""Stdlib-only validator for axes-exchange vectors.

Derivation vectors (class action_ref-derivation): recomputes SHA-256 over the
JCS-RFC8785 canonical form of `input` and checks it matches `expect.digest`
and `expected_canonical_bytes`.

Confirmation vectors (class confirmation_predicate): structural check only —
confirms the required fields (correlation_field, confirmation_predicate,
freshness_window, worked_example) are present. There is no cross-checkable
digest for these; they document a predicate, not a derivation.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def jcs(obj):
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def check_derivation(vec: dict) -> list[str]:
    errors = []
    canonical = jcs(vec["input"])
    if canonical != vec["expected_canonical_bytes"]:
        errors.append(
            f"canonical bytes mismatch: computed {canonical!r} != "
            f"expected {vec['expected_canonical_bytes']!r}"
        )
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    if digest != vec["expect"]["digest"]:
        errors.append(f"digest mismatch: computed {digest} != expected {vec['expect']['digest']}")
    return errors


def check_confirmation(vec: dict) -> list[str]:
    errors = []
    for field in ("correlation_field", "confirmation_predicate", "freshness_window", "worked_example"):
        if field not in vec:
            errors.append(f"missing required field: {field}")
    return errors


def main() -> int:
    manifest = json.loads((HERE / "MANIFEST.json").read_text())
    failures = 0
    for entry in manifest["vectors"]:
        vec = json.loads((HERE / entry["file"]).read_text())
        if vec["class"] == "action_ref-derivation":
            errors = check_derivation(vec)
        elif vec["class"] == "confirmation_predicate":
            errors = check_confirmation(vec)
        else:
            errors = [f"unknown class: {vec['class']}"]

        if errors:
            failures += 1
            print(f"FAIL {entry['id']}:")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"PASS {entry['id']}")

    print()
    if failures:
        print(f"{failures} of {len(manifest['vectors'])} vectors FAILED")
        return 1
    print(f"All {len(manifest['vectors'])} vectors PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
