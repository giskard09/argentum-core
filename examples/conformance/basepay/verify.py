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
pending = 0

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

for v in data.get("negative_vectors", []):
    vid = v["id"]
    if v.get("verification_mode") == "pending":
        print(f"SKIP [{vid}] pending — {v.get('status', '')}")
        pending += 1
        continue

    if vid == "basepay-permit-batch-negative":
        claim_hash = v["claim"]["recipient_set_hash"]
        calldata_hash = v["calldata"]["computed_set_hash"]
        if claim_hash == calldata_hash:
            print(f"FAIL [{vid}] expected RECIPIENT_SET_MISMATCH but hashes match")
            failed += 1
        else:
            print(f"PASS [{vid}] RECIPIENT_SET_MISMATCH confirmed (claim={claim_hash[:16]}… != calldata={calldata_hash[:16]}…)")
            passed += 1

    elif vid == "basepay-x402-relay-negative":
        relay_ref = v["relay_response"]["action_ref"]
        # verify relay_response action_ref matches its own preimage
        relay_preimage = v["relay_response"]["preimage"]
        ok_hex, actual_hex = verify_bytes_hex(relay_preimage, v["relay_response"]["preimage_canonical_bytes_hex"])
        if not ok_hex:
            print(f"FAIL [{vid}] relay_response preimage bytes mismatch")
            failed += 1
            continue
        computed_real = compute_action_ref(relay_preimage)
        if computed_real != relay_ref:
            print(f"FAIL [{vid}] relay_response.action_ref doesn't match its own preimage")
            failed += 1
            continue
        # verify stale produces different hash
        stale_preimage = v["verifier_attempt"]["stale_preimage"]
        ok_hex2, actual_hex2 = verify_bytes_hex(stale_preimage, v["verifier_attempt"]["stale_canonical_bytes_hex"])
        if not ok_hex2:
            print(f"FAIL [{vid}] stale preimage bytes mismatch")
            failed += 1
            continue
        stale_ref = compute_action_ref(stale_preimage)
        if stale_ref != v["verifier_attempt"]["recomputed_action_ref"]:
            print(f"FAIL [{vid}] stale action_ref doesn't match expected")
            failed += 1
            continue
        if stale_ref == relay_ref:
            print(f"FAIL [{vid}] expected ACTION_REF_MISMATCH but hashes match")
            failed += 1
        else:
            print(f"PASS [{vid}] ACTION_REF_MISMATCH confirmed (relay={relay_ref[:16]}… != stale={stale_ref[:16]}…)")
            passed += 1

    elif vid == "basepay-dispatch-binding-negative":
        approved = v["approved_envelope"]
        executed = v["executed_envelope"]
        # verify approved action_ref matches its preimage
        ok_hex, actual_hex = verify_bytes_hex(approved["preimage"], approved["preimage_canonical_bytes_hex"])
        if not ok_hex:
            print(f"FAIL [{vid}] approved preimage bytes mismatch")
            failed += 1
            continue
        computed_approved = compute_action_ref(approved["preimage"])
        if computed_approved != approved["action_ref"]:
            print(f"FAIL [{vid}] approved action_ref doesn't match its own preimage")
            failed += 1
            continue
        # verify executed recomputed_action_ref matches its preimage
        ok_hex2, actual_hex2 = verify_bytes_hex(executed["preimage"], executed["preimage_canonical_bytes_hex"])
        if not ok_hex2:
            print(f"FAIL [{vid}] executed preimage bytes mismatch")
            failed += 1
            continue
        computed_executed = compute_action_ref(executed["preimage"])
        if computed_executed != executed["recomputed_action_ref"]:
            print(f"FAIL [{vid}] executed recomputed_action_ref doesn't match preimage")
            failed += 1
            continue
        if computed_approved == computed_executed:
            print(f"FAIL [{vid}] expected DISPATCH_BINDING_VIOLATION but hashes match")
            failed += 1
        else:
            print(f"PASS [{vid}] DISPATCH_BINDING_VIOLATION confirmed (approved={computed_approved[:16]}… != executed={computed_executed[:16]}…)")
            passed += 1

print(f"\n{passed}/{passed+failed} vectors passed, {pending} pending")
sys.exit(0 if failed == 0 else 1)
