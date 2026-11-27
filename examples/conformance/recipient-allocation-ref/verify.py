"""
recipient-allocation-ref-v1 conformance verifier
Reproduces recipient_allocation_ref from preimage fields and validates all invariants.
"""
import hashlib, json, sys
from pathlib import Path

# RFC 8785 JCS from the repo's jcs.py. Until 2026-11-26 jcs() was json.dumps(sort_keys=True), which the
# spec says not to use (code-point key order; Python number forms). Run from a checkout of the repository.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from jcs import jcs_bytes  # noqa: E402


def jcs(obj):
    """Raises ValueError for an integer outside +/-(2^53-1) or a non-finite float (out of the JCS profile):
    this script has no per-vector error path, so such a preimage ends the run with a traceback."""
    return jcs_bytes(obj).decode("utf-8")

def compute_ref(preimage):
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

    # 2. recipient_allocation_ref
    computed = compute_ref(preimage)
    if computed != v["recipient_allocation_ref"]:
        print(f"FAIL [{vid}] recipient_allocation_ref mismatch")
        print(f"  expected: {v['recipient_allocation_ref']}")
        print(f"  got:      {computed}")
        failed += 1
        continue

    # 3. aggregate == sum of allocations
    allocs = preimage["recipient_allocations"]
    total = sum(int(a["amount_usdc"]) for a in allocs)
    if str(total) != preimage["aggregate_usdc"]:
        print(f"FAIL [{vid}] aggregate_usdc mismatch: sum={total} != {preimage['aggregate_usdc']}")
        failed += 1
        continue

    # 4. allocations sorted by address
    sorted_allocs = sorted(allocs, key=lambda a: a["address"].lower())
    if allocs != sorted_allocs:
        print(f"FAIL [{vid}] recipient_allocations not sorted by address")
        failed += 1
        continue

    print(f"PASS [{vid}] recipient_allocation_ref={computed[:16]}…")
    passed += 1

for v in data.get("negative_vectors", []):
    vid = v["id"]

    if vid == "allocation-redistribution-negative":
        committed = v["committed"]
        executed = v["executed"]

        # verify committed ref matches its preimage
        ok_hex, actual_hex = verify_bytes_hex(committed["preimage"], committed["preimage_canonical_bytes_hex"])
        if not ok_hex:
            print(f"FAIL [{vid}] committed preimage bytes mismatch")
            failed += 1
            continue
        computed_committed = compute_ref(committed["preimage"])
        if computed_committed != committed["recipient_allocation_ref"]:
            print(f"FAIL [{vid}] committed ref doesn't match preimage")
            failed += 1
            continue

        # verify executed recomputed_ref matches its preimage
        ok_hex2, actual_hex2 = verify_bytes_hex(executed["preimage"], executed["preimage_canonical_bytes_hex"])
        if not ok_hex2:
            print(f"FAIL [{vid}] executed preimage bytes mismatch")
            failed += 1
            continue
        computed_executed = compute_ref(executed["preimage"])
        if computed_executed != executed["recomputed_ref"]:
            print(f"FAIL [{vid}] executed recomputed_ref doesn't match preimage")
            failed += 1
            continue

        # verify redistribution is detectable (refs differ, aggregates match)
        committed_agg = committed["preimage"]["aggregate_usdc"]
        executed_agg = executed["preimage"]["aggregate_usdc"]
        if committed_agg != executed_agg:
            print(f"FAIL [{vid}] aggregates differ — not a redistribution scenario")
            failed += 1
            continue
        if computed_committed == computed_executed:
            print(f"FAIL [{vid}] expected ALLOCATION_REDISTRIBUTION but refs match")
            failed += 1
        else:
            print(f"PASS [{vid}] ALLOCATION_REDISTRIBUTION confirmed (committed={computed_committed[:16]}… != executed={computed_executed[:16]}…, aggregate={committed_agg} unchanged)")
            passed += 1

print(f"\n{passed}/{passed+failed} vectors passed")
sys.exit(0 if failed == 0 else 1)
