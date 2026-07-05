"""
governance-block-join-ref-v1 conformance verifier
Recomputes governance_block_digest and checks the single-authority-path invariant.
"""
import hashlib, json, sys
from pathlib import Path

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

def ref(obj):
    return hashlib.sha256(jcs(obj).encode()).hexdigest()

vectors_path = Path(__file__).parent / "vectors.json"
data = json.loads(vectors_path.read_text())

passed = 0
failed = 0

for v in data["vectors"]:
    vid = v["id"]
    gb = v["governance_block"]
    te = v["terminal_envelope"]

    computed_gb_digest = ref(gb)
    if computed_gb_digest != v["governance_block_digest"]:
        print(f"FAIL [{vid}] governance_block_digest mismatch")
        failed += 1
        continue

    if te["governance_block_digest"] != computed_gb_digest:
        print(f"FAIL [{vid}] terminal_envelope does not name the recomputed governance_block_digest")
        failed += 1
        continue

    print(f"PASS [{vid}] {v['expected']} — gb_digest={computed_gb_digest[:16]}…")
    passed += 1

for v in data.get("negative_vectors", []):
    vid = v["id"]

    if vid == "governance-block-digest-mismatch":
        computed = ref(v["governance_block"])
        if computed == v["claimed_governance_block_digest"]:
            print(f"FAIL [{vid}] expected digest mismatch but digests matched")
            failed += 1
        else:
            print(f"PASS [{vid}] GOVERNANCE_BLOCK_DIGEST_MISMATCH confirmed (claimed={v['claimed_governance_block_digest'][:16]}… != recomputed={computed[:16]}…)")
            passed += 1
        continue

    if vid == "split-authority-divergent-bucket":
        a, b = v["terminal_envelope_a"], v["terminal_envelope_b"]
        same_gb = a["governance_block_digest"] == b["governance_block_digest"]
        same_call_pair = (a["proposed_call_digest"], a["effective_call_digest"]) == (b["proposed_call_digest"], b["effective_call_digest"])
        divergent_bucket = a["terminal_bucket"] != b["terminal_bucket"]
        if same_gb and same_call_pair and divergent_bucket:
            print(f"PASS [{vid}] SPLIT_AUTHORITY confirmed (bucket_a={a['terminal_bucket']} != bucket_b={b['terminal_bucket']} despite identical gb_digest + call pair)")
            passed += 1
        else:
            print(f"FAIL [{vid}] expected split-authority conditions not met")
            failed += 1
        continue

    if vid == "divergent-call-envelope-legitimate-divergence":
        a, b = v["terminal_envelope_a"], v["terminal_envelope_b"]
        same_gb = a["governance_block_digest"] == b["governance_block_digest"]
        different_call_pair = (a["proposed_call_digest"], a["effective_call_digest"]) != (b["proposed_call_digest"], b["effective_call_digest"])
        divergent_bucket = a["terminal_bucket"] != b["terminal_bucket"]
        if same_gb and different_call_pair and divergent_bucket:
            print(f"PASS [{vid}] JOINED_AND_CONSISTENT confirmed (bucket_a={a['terminal_bucket']} != bucket_b={b['terminal_bucket']} — legitimate, call pair differs, not split authority)")
            passed += 1
        else:
            print(f"FAIL [{vid}] expected legitimate divergence conditions not met")
            failed += 1
        continue

    if vid == "orphan-terminal-envelope":
        if v["governance_block"] is None:
            print(f"PASS [{vid}] ORPHAN_TERMINAL_ENVELOPE confirmed (no governance_block available for governance_block_digest={v['terminal_envelope']['governance_block_digest'][:16]}…)")
            passed += 1
        else:
            print(f"FAIL [{vid}] governance_block unexpectedly present")
            failed += 1
        continue

    if vid == "dispatch-binding-mismatch":
        gb, te = v["governance_block"], v["terminal_envelope"]
        computed_gb_digest = ref(gb)
        gb_recomputes = computed_gb_digest == v["governance_block_digest"] == te["governance_block_digest"]
        dispatch_mismatch = te["effective_call_digest"] != v["dispatched_effective_call_digest"]
        if gb_recomputes and dispatch_mismatch:
            print(f"PASS [{vid}] DISPATCH_BINDING_MISMATCH confirmed (envelope names {te['effective_call_digest'][:16]}… but runtime dispatched {v['dispatched_effective_call_digest'][:16]}… — governance_block itself recomputes fine)")
            passed += 1
        else:
            print(f"FAIL [{vid}] expected dispatch-binding-mismatch conditions not met")
            failed += 1
        continue

print(f"\n{passed}/{passed+failed} vectors passed")
sys.exit(0 if failed == 0 else 1)
