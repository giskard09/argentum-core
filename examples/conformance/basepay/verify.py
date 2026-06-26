"""
BasePay conformance verifier — action-ref-basepay-v1
Reproduces action_refs from preimage fields and validates all invariants.
"""
import hashlib, json, sys
from pathlib import Path

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

def compute_action_ref(preimage):
    return hashlib.sha256(jcs(preimage).encode()).hexdigest()

def verify_bytes_hex(preimage, expected_hex):
    actual = jcs(preimage).encode().hex()
    return actual == expected_hex, actual

vectors_path = Path(__file__).parent / "vectors.json"
data = json.loads(vectors_path.read_text())

passed = 0
failed = 0

for v in data["vectors"]:
    vid = v["id"]
    preimage = v["preimage"]

    # 1. byte-identical JCS
    ok_hex, actual_hex = verify_bytes_hex(preimage, v["preimage_canonical_bytes_hex"])
    if not ok_hex:
        print(f"FAIL [{vid}] canonical bytes mismatch")
        print(f"  expected: {v['preimage_canonical_bytes_hex']}")
        print(f"  got:      {actual_hex}")
        failed += 1
        continue

    # 2. action_ref
    computed = compute_action_ref(preimage)
    if computed != v["action_ref"]:
        print(f"FAIL [{vid}] action_ref mismatch")
        print(f"  expected: {v['action_ref']}")
        print(f"  got:      {computed}")
        failed += 1
        continue

    print(f"PASS [{vid}] action_ref={computed[:16]}…")
    passed += 1

print(f"\n{passed}/{passed+failed} vectors passed")
sys.exit(0 if failed == 0 else 1)
