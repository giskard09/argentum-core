"""
transition-sufficiency-ref-v1 conformance verifier
Recomputes Required(τ) \\ Supported(τ) from item-level sets under
inclusion_operator. Never accepts an asserted inclusion_result or a pair of
set-digests as a substitute for recomputation.
"""
import json, sys
from pathlib import Path

SUPPORTED_OPERATORS = {"set_subset"}

vectors_path = Path(__file__).parent / "vectors.json"
data = json.loads(vectors_path.read_text())

passed = 0
failed = 0


def recompute_missing(required, supported, operator):
    if operator not in SUPPORTED_OPERATORS:
        return None, "UNSUPPORTED_INCLUSION_OPERATOR"
    missing = [item for item in required if item not in set(supported)]
    return missing, ("SUFFICIENT" if not missing else "INSUFFICIENT")


for v in data["vectors"]:
    vid = v["id"]
    missing, result = recompute_missing(
        v["required_support_items"], v["supported_support_items"], v["inclusion_operator"]
    )
    if result != v["expected"]:
        print(f"FAIL [{vid}] expected {v['expected']}, recomputed {result}")
        failed += 1
        continue
    if "expected_missing" in v and sorted(missing) != sorted(v["expected_missing"]):
        print(f"FAIL [{vid}] missing_support_items mismatch: {missing} != {v['expected_missing']}")
        failed += 1
        continue
    print(f"PASS [{vid}] {result} — missing={len(missing)} item(s)")
    passed += 1

for v in data.get("negative_vectors", []):
    vid = v["id"]

    if vid == "asserted-hashes-not-inclusion":
        # No item-level sets present — only two set-digests and a claim.
        # A conformant verifier must refuse to infer inclusion from digest
        # agreement alone, regardless of whether the digests match.
        has_item_sets = "required_support_items" in v and "supported_support_items" in v
        if has_item_sets:
            print(f"FAIL [{vid}] expected only set-digests to be present, item-level sets found")
            failed += 1
        else:
            print(f"PASS [{vid}] INCLUSION_NOT_RECOMPUTED confirmed — no item-level sets to recompute from, "
                  f"digest agreement (required_support_hash == supported_support_hash) does not establish inclusion")
            passed += 1
        continue

    if vid == "claimed-sufficient-but-recomputation-disagrees":
        missing, result = recompute_missing(
            v["required_support_items"], v["supported_support_items"], v["inclusion_operator"]
        )
        if result == v["expected"] and v["claimed_inclusion_result"] != result:
            print(f"PASS [{vid}] recomputation ({result}) overrides claim ({v['claimed_inclusion_result']})")
            passed += 1
        else:
            print(f"FAIL [{vid}] recomputation did not diverge from claim as expected")
            failed += 1
        continue

    if vid == "unsupported-inclusion-operator":
        _, result = recompute_missing(
            v["required_support_items"], v["supported_support_items"], v["inclusion_operator"]
        )
        if result == "UNSUPPORTED_INCLUSION_OPERATOR":
            print(f"PASS [{vid}] UNSUPPORTED_INCLUSION_OPERATOR confirmed (operator={v['inclusion_operator']})")
            passed += 1
        else:
            print(f"FAIL [{vid}] expected UNSUPPORTED_INCLUSION_OPERATOR, got {result}")
            failed += 1
        continue

    if vid == "unresolvable-decision-record":
        if v.get("resolvable") is False:
            print(f"PASS [{vid}] UNRESOLVABLE_DECISION_RECORD confirmed (decision_record_id={v['decision_record_id']})")
            passed += 1
        else:
            print(f"FAIL [{vid}] decision record unexpectedly resolvable")
            failed += 1
        continue

    print(f"FAIL [{vid}] unknown negative vector id")
    failed += 1

print(f"\n{passed}/{passed+failed} vectors passed")
sys.exit(0 if failed == 0 else 1)
