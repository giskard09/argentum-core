"""
verify-failure-mode-ref-v1 conformance verifier
Recomputes classify_verify_attempt() from stated inputs and checks the
declared reason code + policy action against the fixture's expected values.
"""
import json
import sys
from pathlib import Path


def classify_verify_attempt(fetch_ok, sig_valid, digest_match, issued_at_ms,
                             expires_at_ms, ttl_seconds, now_ms):
    if not fetch_ok:
        return "verify_unreachable"
    if expires_at_ms is not None and now_ms > expires_at_ms:
        return "verify_stale"
    if ttl_seconds is not None and (now_ms - issued_at_ms) > ttl_seconds * 1000:
        return "verify_stale"
    if not (sig_valid and digest_match):
        return "verify_invalid"
    return "verify_ok"


def policy_action(reason, verify_mode):
    if reason == "verify_ok":
        return "PROCEED_TO_GATE_POLICY"
    if reason == "verify_unreachable":
        return "SKIP" if verify_mode == "fail_open" else "DENY"
    return "DENY"


vectors_path = Path(__file__).parent / "vectors.json"
data = json.loads(vectors_path.read_text())

passed = 0
failed = 0

for v in data["vectors"]:
    vid = v["id"]
    inp = v["input"]
    verify_mode = inp.get("verify_mode", "fail_closed")

    reason = classify_verify_attempt(
        inp["fetch_ok"], inp["sig_valid"], inp["digest_match"],
        inp["issued_at_ms"], inp["expires_at_ms"], inp["ttl_seconds"], inp["now_ms"]
    )
    action = policy_action(reason, verify_mode)

    if reason != v["expected_reason"]:
        print(f"FAIL [{vid}] expected reason {v['expected_reason']}, got {reason}")
        failed += 1
        continue
    if action != v["expected_policy_action"]:
        print(f"FAIL [{vid}] expected action {v['expected_policy_action']}, got {action}")
        failed += 1
        continue

    print(f"PASS [{vid}] reason={reason} action={action}")
    passed += 1

for v in data.get("negative_vectors", []):
    vid = v["id"]
    if vid == "collapsed-unreachable-and-invalid":
        lenient = v["lenient_output"]
        conformant = v["conformant_output"]
        collapsed = (lenient["unreachable_case"]["reason"]
                     == lenient["invalid_signature_case"]["reason"])
        distinguishable = (conformant["unreachable_case"]["reason"]
                            != conformant["invalid_signature_case"]["reason"])
        if collapsed and distinguishable:
            print(f"PASS [{vid}] REASON_CODES_MUST_REMAIN_DISTINGUISHABLE confirmed "
                  f"(lenient collapses both to '{lenient['unreachable_case']['reason']}', "
                  f"conformant keeps '{conformant['unreachable_case']['reason']}' != "
                  f"'{conformant['invalid_signature_case']['reason']}')")
            passed += 1
        else:
            print(f"FAIL [{vid}] expected collapse-vs-distinguishable conditions not met")
            failed += 1
        continue

print(f"\n{passed}/{passed+failed} vectors passed")
sys.exit(0 if failed == 0 else 1)
