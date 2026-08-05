#!/usr/bin/env python3
"""Independent verifier for art12-log-integrity-notes vectors.

Recomputes every digest from the raw record in vectors.json and compares it to
the anchored digest. Never trusts a stored hash value. Zero dependencies, no
network in the trust path.

Run: python3 verify.py     (exit 0 = all vectors behaved as declared)
"""
import hashlib
import json
import sys
from pathlib import Path

# Profile domain, per docs/spec/action-ref.md: ASCII field values, RFC 3339
# timestamps in YYYY-MM-DDTHH:MM:SS.mmmZ form, no surrogate pairs, no -0.0.
TIMESTAMP_FIELDS = ("use_start", "use_end")


def jcs(obj: dict) -> str:
    return json.dumps(dict(sorted(obj.items())), separators=(",", ":"), ensure_ascii=False)


def digest(obj: dict) -> str:
    return "sha256:" + hashlib.sha256(jcs(obj).encode("utf-8")).hexdigest()


def in_profile_domain(record: dict) -> bool:
    """Domain check. Runs BEFORE any digest comparison and stops on failure."""
    for key, value in record.items():
        if not isinstance(key, str) or not key.isascii():
            return False
        if isinstance(value, str) and not value.isascii():
            return False
    for field in TIMESTAMP_FIELDS:
        value = record.get(field)
        if value is None:
            continue
        # YYYY-MM-DDTHH:MM:SS.mmmZ -- exactly 24 chars, 3-digit ms, trailing Z
        if len(value) != 24 or value[10] != "T" or value[19] != "." or value[-1] != "Z":
            return False
        if not value[20:23].isdigit():
            return False
    return True


def main() -> int:
    data = json.loads((Path(__file__).parent / "vectors.json").read_text())
    ok = True

    print(f"fixture: {data['fixture_id']} ({data['preimage_format']})\n")

    for v in data["vectors"]:
        vid, name = v["id"], v["name"]
        record = v["record"]
        anchored = v["anchored_digest"]
        expected = v["expected_result"]
        expected_code = v.get("expected_error_code")

        # 1. Domain check first, always -- never canonicalise out-of-domain input.
        if not in_profile_domain(record):
            actual, code = "FAIL", "OUT_OF_PROFILE_DOMAIN"
            detail = "rejected before digest comparison"
        else:
            # 2. Recompute from the record itself. The stored digest is never read
            #    as an input to this decision.
            computed = digest(record)
            if computed == anchored:
                actual, code, detail = "PASS", None, computed
            else:
                actual, code = "FAIL", "RECORD_MODIFIED_AFTER_ANCHOR"
                detail = f"computed {computed} != anchored {anchored}"

        # 3. A valid operator signature must NOT change the verdict.
        if v.get("operator_signature_validates") and actual == "FAIL":
            detail += " | operator signature validates and is disregarded"

        matched = (actual == expected) and (code == expected_code)
        if not matched:
            ok = False
        print(f"[{'OK ' if matched else 'BAD'}] {vid} ({name})")
        print(f"       expected {expected}{'/' + expected_code if expected_code else ''}"
              f" -> got {actual}{'/' + code if code else ''}")
        print(f"       {detail}")

    print()
    if ok:
        print("All vectors behaved as declared.")
    else:
        print("DIVERGENCE -- a vector did not behave as declared.")
    print("\nScope: this exercises the verification path Art. 12 leaves unspecified.")
    print("It is not an Article 12 conformance check. See README.md.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
