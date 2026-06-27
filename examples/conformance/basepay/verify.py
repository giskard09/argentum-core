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

    print(f"PASS [{vid}] action_ref={computed[:16]}\u2026")
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
            print(f"PASS [{vid}] RECIPIENT_SET_MISMATCH confirmed (claim={claim_hash[:16]}\u2026 != calldata={calldata_hash[:16]}\u2026)")
            passed += 1

    elif vid == "basepay-x402-relay-negative":
        relay_ref = v["relay_response"]["action_ref"]
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
            print(f"PASS [{vid}] ACTION_REF_MISMATCH confirmed (relay={relay_ref[:16]}\u2026 != stale={stale_ref[:16]}\u2026)")
            passed += 1

    elif vid == "basepay-dispatch-binding-negative":
        approved = v["approved_envelope"]
        executed = v["executed_envelope"]
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
            print(f"PASS [{vid}] DISPATCH_BINDING_VIOLATION confirmed (approved={computed_approved[:16]}\u2026 != executed={computed_executed[:16]}\u2026)")
            passed += 1

    elif vid in ("basepay-eip3009-expired", "basepay-eip3009-nonce-spent"):
        preimage = v["action_ref_preimage"]
        ok_hex, actual_hex = verify_bytes_hex(preimage, v["action_ref_preimage_canonical_bytes_hex"])
        if not ok_hex:
            print(f"FAIL [{vid}] action_ref preimage bytes mismatch")
            failed += 1
            continue
        computed = compute_action_ref(preimage)
        if computed != v["action_ref"]:
            print(f"FAIL [{vid}] action_ref doesn't match preimage")
            failed += 1
            continue
        if vid == "basepay-eip3009-expired":
            ctx = v["submission_context"]
            claim = v["claim"]
            expired = ctx["block_timestamp"] >= claim["valid_before"]
            if not expired:
                print(f"FAIL [{vid}] expected block_timestamp >= valid_before but condition not met")
                failed += 1
                continue
            print(f"PASS [{vid}] AUTHORIZATION_EXPIRED confirmed (block_ts={ctx['block_timestamp']} >= valid_before={claim['valid_before']}, action_ref={computed[:16]}\u2026)")
            passed += 1
        elif vid == "basepay-eip3009-nonce-spent":
            on_chain = v["on_chain_state"]
            if not on_chain["authorizationState"]:
                print(f"FAIL [{vid}] expected authorizationState==true but got false")
                failed += 1
                continue
            print(f"PASS [{vid}] NONCE_SPENT confirmed (authorizationState=true, action_ref={computed[:16]}\u2026)")
            passed += 1

    elif vid == "basepay-mechanism-scope-mismatch":
        claim = v["claim"]
        exec_path = v["execution_path"]
        # verify claim action_ref matches its own preimage
        ok_hex, actual_hex = verify_bytes_hex(claim["preimage"], claim["preimage_canonical_bytes_hex"])
        if not ok_hex:
            print(f"FAIL [{vid}] claim preimage bytes mismatch")
            failed += 1
            continue
        computed_claim = compute_action_ref(claim["preimage"])
        if computed_claim != claim["action_ref"]:
            print(f"FAIL [{vid}] claim action_ref doesn't match its own preimage")
            failed += 1
            continue
        # verify execution_path expected_action_ref matches its preimage
        ok_hex2, actual_hex2 = verify_bytes_hex(exec_path["expected_preimage"], exec_path["expected_preimage_canonical_bytes_hex"])
        if not ok_hex2:
            print(f"FAIL [{vid}] execution_path preimage bytes mismatch")
            failed += 1
            continue
        computed_expected = compute_action_ref(exec_path["expected_preimage"])
        if computed_expected != exec_path["expected_action_ref"]:
            print(f"FAIL [{vid}] execution_path expected_action_ref doesn't match preimage")
            failed += 1
            continue
        # confirm the mismatch
        if computed_claim == computed_expected:
            print(f"FAIL [{vid}] expected MECHANISM_SCOPE_MISMATCH but action_refs match")
            failed += 1
        else:
            print(f"PASS [{vid}] MECHANISM_SCOPE_MISMATCH confirmed (claim={computed_claim[:16]}\u2026 != expected={computed_expected[:16]}\u2026)")
            passed += 1

    elif vid == "basepay-permit-batch-redistribution":
          claim = v["claim"]
          calldata = v["calldata"]

          # --- invariant 1: recipient_set_hash identical on both sides ---
          if claim["recipient_set_hash"] != calldata["computed_set_hash"]:
              print(f"FAIL [{vid}] expected recipient_set_hash to be identical for both allocations")
              failed += 1
              continue

          # --- invariant 2: aggregate_usdc identical ---
          if claim["aggregate_usdc"] != calldata["aggregate_usdc"]:
              print(f"FAIL [{vid}] expected aggregate_usdc to be identical for both allocations")
              failed += 1
              continue

          # --- claim allocation: verify stored jcs hex is byte-identical to normalizing approved_allocation ---
          # uses top-level jcs() (RFC 8785, sort_keys=True) — same contract as the rest of the fixture
          approved_norm = sorted(
              [{"amount_atomic": str(p["amount_atomic"]), "to": p["to"].lower()} for p in claim["approved_allocation"]],
              key=lambda x: (x["to"], x["amount_atomic"])
          )
          approved_jcs_bytes = jcs(approved_norm).encode()
          if approved_jcs_bytes.hex() != v["claim_allocation_jcs_hex"]:
              print(f"FAIL [{vid}] claim approved_allocation jcs hex mismatch")
              print(f"  expected: {v['claim_allocation_jcs_hex'][:32]}...")
              print(f"  got:      {approved_jcs_bytes.hex()[:32]}...")
              failed += 1
              continue
          computed_claim_hash = hashlib.sha256(approved_jcs_bytes).hexdigest()
          if computed_claim_hash != claim["recipient_allocation_hash"]:
              print(f"FAIL [{vid}] claim recipient_allocation_hash doesn't match normalized approved_allocation")
              failed += 1
              continue

          # --- calldata allocation: verify stored jcs hex + hash ---
          executed_norm = sorted(
              [{"amount_atomic": str(p["amount_atomic"]), "to": p["to"].lower()} for p in calldata["executed_allocation"]],
              key=lambda x: (x["to"], x["amount_atomic"])
          )
          executed_jcs_bytes = jcs(executed_norm).encode()
          if executed_jcs_bytes.hex() != v["calldata_allocation_jcs_hex"]:
              print(f"FAIL [{vid}] calldata executed_allocation jcs hex mismatch")
              failed += 1
              continue
          computed_calldata_hash = hashlib.sha256(executed_jcs_bytes).hexdigest()
          if computed_calldata_hash != calldata["computed_allocation_hash"]:
              print(f"FAIL [{vid}] calldata computed_allocation_hash doesn't match normalized executed_allocation")
              failed += 1
              continue

          # --- invariant 3: allocation hashes must differ ---
          if computed_claim_hash == computed_calldata_hash:
              print(f"FAIL [{vid}] expected RECIPIENT_ALLOCATION_MISMATCH but allocation hashes match")
              failed += 1
              continue

          # --- invariant 4 (asserted, not executable here): rejection before permit signing ---

          # --- invariant 5: decision_ref recomputable from persisted timestamps + allocation hash ---
          dr_ex = v.get("decision_ref_example", {})
          if dr_ex:
              computed_dr = compute_action_ref(dr_ex["preimage"])
              if computed_dr != dr_ex["decision_ref"]:
                  print(f"FAIL [{vid}] decision_ref_example doesn't match its preimage")
                  failed += 1
                  continue

          print(f"PASS [{vid}] RECIPIENT_ALLOCATION_MISMATCH confirmed")
          print(f"  claim_alloc={computed_claim_hash[:16]}\u2026 != calldata_alloc={computed_calldata_hash[:16]}\u2026")
          print(f"  set_hash identical: {claim['recipient_set_hash'][:16]}\u2026 (proving set_hash insufficient)")
          if dr_ex:
              print(f"  decision_ref recomputable: {computed_dr[:16]}\u2026")
          passed += 1

  
print(f"\n{passed}/{passed+failed} vectors passed, {pending} pending")
sys.exit(0 if failed == 0 else 1)
