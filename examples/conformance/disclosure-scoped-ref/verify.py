#!/usr/bin/env python3
"""verify.py — disclosure-scoped-ref-v0 conformance vectors.

Field-level selective disclosure: per-field salted commitments, a canonical
commitment vector, and a root digest (disclosure_ref). See
docs/spec/disclosure-scoped-ref.md for the full construction.

Does NOT touch action_ref -- this is a sibling primitive, same pattern as
screen_ref alongside a settlement action_ref (../presidio/).

Zero-dependency, offline. Run: python3 verify.py
Cross-checked byte-identical against verify.mjs.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def jcs(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def sha256hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def field_digest(field: str, value, salt: str) -> str:
    return sha256hex(jcs({"field": field, "salt": salt, "value": value}))


def commitment_vector(record: dict, salts: dict) -> list[dict]:
    return sorted(
        [{"field": f, "digest": field_digest(f, v, salts[f])} for f, v in record.items()],
        key=lambda e: e["field"],
    )


def disclosure_ref(vector: list[dict]) -> str:
    return sha256hex(jcs(vector))


def verify_pos(fixture: dict, vector_data: dict) -> bool:
    record = fixture["record"]
    salts = fixture["salts"]
    published_vector = fixture["commitment_vector"]
    published_root = fixture["disclosure_ref"]

    # recompute the full commitment vector from the source record + salts
    computed_vector = commitment_vector(record, salts)
    vector_ok = computed_vector == published_vector
    root_ok = disclosure_ref(published_vector) == published_root

    opened = vector_data["opened"]
    opened_ok = True
    for field, o in opened.items():
        recomputed = field_digest(field, o["value"], o["salt"])
        stored = next(e["digest"] for e in published_vector if e["field"] == field)
        if recomputed != stored:
            opened_ok = False

    print(f"  [{vector_data['id']}]")
    print(f"    commitment_vector recomputes from record+salts: {vector_ok}")
    print(f"    root recomputes to published disclosure_ref:    {root_ok}")
    print(f"    all opened fields match their committed digest: {opened_ok}")
    return vector_ok and root_ok and opened_ok


def verify_neg_hidden_altered(fixture: dict, vector_data: dict) -> bool:
    published_vector = fixture["commitment_vector"]
    published_root = fixture["disclosure_ref"]

    tampered_vector = [dict(e) for e in published_vector]
    for e in tampered_vector:
        if e["field"] == vector_data["tampered_field"]:
            e["digest"] = vector_data["tampered_digest"]

    tampered_root = disclosure_ref(tampered_vector)
    root_breaks = tampered_root != published_root
    matches_expected_tampered_root = tampered_root == vector_data["tampered_root"]

    print(f"  [{vector_data['id']}]")
    print(f"    tampered root: {tampered_root}")
    print(f"    tampered root != published disclosure_ref: {root_breaks}")
    print(f"    matches fixture's expected tampered root:   {matches_expected_tampered_root}")
    # expected FAIL -- correctly detected means root_breaks is True
    return root_breaks and matches_expected_tampered_root


def verify_neg_salt_reuse_and_substitution(fixture: dict, vector_data: dict) -> bool:
    record = fixture["record"]
    salts = fixture["salts"]
    published_vector = fixture["commitment_vector"]
    published_root = fixture["disclosure_ref"]

    sub = vector_data["sub_vectors"]

    # (a) salt reuse
    reuse = sub["salt_reuse"]
    salts_reused = dict(salts)
    for f in reuse["reused_by_fields"]:
        salts_reused[f] = reuse["reused_salt"]
    salt_set = list(salts_reused.values())
    salts_unique = len(salt_set) == len(set(salt_set))
    vector_with_reuse = commitment_vector(record, salts_reused)
    root_with_reuse = disclosure_ref(vector_with_reuse)
    matches_expected_reuse_root = root_with_reuse == reuse["recomputed_root_with_reused_salt"]

    print(f"  [{vector_data['id']}] (a) salt reuse")
    print(f"    salts unique across fields: {salts_unique} (must be False -- structural violation)")
    print(f"    root with reused salt still hashes 'correctly': {matches_expected_reuse_root}")
    a_ok = (not salts_unique) and matches_expected_reuse_root

    # (b) digest substitution
    subst = sub["digest_substitution"]
    substituted_vector = [dict(e) for e in published_vector]
    for e in substituted_vector:
        if e["field"] == subst["substituted_field"]:
            e["digest"] = subst["substituted_digest"]
    substituted_root = disclosure_ref(substituted_vector)
    root_breaks = substituted_root != published_root
    matches_expected_subst_root = substituted_root == subst["substituted_root"]

    true_field = subst["substituted_field"]
    true_value = record[true_field]
    true_salt = salts[true_field]
    recomputed_true_digest = field_digest(true_field, true_value, true_salt)
    stored_after_swap = next(e["digest"] for e in substituted_vector if e["field"] == true_field)
    later_open_fails = recomputed_true_digest != stored_after_swap

    print(f"  [{vector_data['id']}] (b) digest substitution")
    print(f"    root breaks immediately: {root_breaks}")
    print(f"    matches fixture's expected substituted root: {matches_expected_subst_root}")
    print(f"    later disclosure of true value also fails to match: {later_open_fails}")
    b_ok = root_breaks and matches_expected_subst_root and later_open_fails

    return a_ok and b_ok


def main() -> int:
    fixture = json.loads((HERE / "vectors.json").read_text())
    by_id = {v["id"]: v for v in fixture["vectors"]}

    print("=" * 78)
    print("disclosure-scoped-ref-v0 conformance")
    print("=" * 78)

    r1 = verify_pos(fixture, by_id["pos-subset-disclosure"])
    print()
    r2 = verify_neg_hidden_altered(fixture, by_id["neg-hidden-field-altered"])
    print()
    r3 = verify_neg_salt_reuse_and_substitution(fixture, by_id["neg-salt-reuse-and-digest-substitution"])

    print("\n" + "-" * 78)
    print(f"pos-subset-disclosure                     : {'PASS' if r1 else 'FAIL'}")
    print(f"neg-hidden-field-altered (correctly caught): {'PASS' if r2 else 'FAIL'}")
    print(f"neg-salt-reuse-and-digest-substitution     : {'PASS' if r3 else 'FAIL'}")

    ok = r1 and r2 and r3
    print()
    if ok:
        print("PASS -- subset disclosure verifies against the root; a tampered closed")
        print("        field breaks the root; salt reuse is caught structurally and digest")
        print("        substitution breaks both the root and any later disclosure.")
        return 0
    print("FAIL -- one or more vectors did not hold.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
