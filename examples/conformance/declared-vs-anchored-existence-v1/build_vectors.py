"""Regenerate vectors.json. Run: python3 build_vectors.py

Real data: the positive anchor evidence below was read from Base mainnet
(eth_getTransactionReceipt + eth_getBlockByNumber, https://mainnet.base.org,
2026-11-11). It is the anchor of the preimage published in
giskard09/delivery-receipt-anchor (artifacts/manifest.json). Run
`python3 verify.py --live` to re-read it from the chain.

Synthetic data: everything under binding_vectors, and the two tampered
captures N3/N4/N5. They are labelled as such in each vector.
"""
import copy
import json
from pathlib import Path

from verify import compute_action_ref, iso

PREIMAGE = {
    "action_type": "commerce.delivery_receipt_confirmed",
    "agent_id": "worked-example.delivery-receipt-anchor",
    "scope": "x402:order:worked-order-0001:settlement:worked-settlement-0001",
    "timestamp": "2026-09-15T12:00:00.000Z",
}
REF = compute_action_ref(PREIMAGE)
assert REF == "c78eb8513c6f43a19d15e6cb22f9b939131026f08de3441fb3f25b244f4aa9ce"

EVIDENCE = {
    "chain": "eip155:8453",
    "captured_from": "eth_getTransactionReceipt + eth_getBlockByNumber on https://mainnet.base.org, 2026-11-11",
    "tx": "0xb1144ee8777262b0d3ac2cd6ea342f14daa300cb5a4401f082e070ae18aed125",
    "status": "0x1",
    "block_number": 51345144,
    "block_hash": "0xda301bf6664819ad8f8be2b296de2f47b6dbacadd8557026d142fbe42f6a855b",
    "block_timestamp": 1789479635,
    "log": {
        "log_index": 259,
        "address": "0x49feca52bc634a9ab773226d16619dec547794aa",
        "topics": [
            "0xfe2289542f7a0110ac112c3a4d712afdcaaf2900a1326f4e6f340b563a0e8734",
            "0x" + REF,
            "0x000000000000000000000000dcc84e9798e8eb1b1b48a31b8f35e5aa7b83dbf4",
        ],
        "data": "0x000000000000000000000000000000000000000000000000000000006aa94ad3",
    },
}


def existence(vid, kind, desc, preimage, claimed, evidence, verdict, extra=None):
    exp = {"verdict": verdict}
    exp.update(extra or {})
    return {"id": vid, "kind": kind, "description": desc,
            "input": {"preimage": preimage, "claimed_action_ref": claimed, "anchor_evidence": evidence},
            "expected": exp}


altered = dict(PREIMAGE, timestamp="2026-09-15T11:59:59.999Z")  # one millisecond earlier
after = dict(PREIMAGE, timestamp="2026-09-15T14:00:00.000Z")     # later than the block time

ev_wrong_registry = copy.deepcopy(EVIDENCE)
ev_wrong_registry["log"]["address"] = "0x0000000000000000000000000000000000000001"
ev_wrong_event = copy.deepcopy(EVIDENCE)
ev_wrong_event["log"]["topics"][0] = "0x" + "11" * 32
ev_failed = copy.deepcopy(EVIDENCE)
ev_failed["status"] = "0x0"
ev_internal = copy.deepcopy(EVIDENCE)
ev_internal["block_timestamp"] = EVIDENCE["block_timestamp"] + 1  # log data no longer equals block time

# Evidence tampered so that it is INTERNALLY consistent but false: a block time
# earlier than the declared one, with the log data changed to match. Offline
# verification cannot tell; only a chain read can (verify.py --live).
early = EVIDENCE["block_timestamp"] - 3600  # still after the declared time
ev_fabricated = copy.deepcopy(EVIDENCE)
ev_fabricated["block_timestamp"] = early
ev_fabricated["log"]["data"] = "0x" + format(early, "064x")

existence_vectors = [
    existence("P1-declared-only-no-anchor", "positive",
              "Valid action_ref, no anchor. The timestamp is a signer-declared claim; there is no existence bound.",
              PREIMAGE, REF, None, "DECLARED_ONLY"),
    existence("P2-anchored-existence-established", "positive",
              "REAL anchor (Base mainnet). The digest existed by block time 2026-09-15T13:40:35Z. The declared "
              "timestamp (12:00:00.000Z) is 6035 s earlier than that bound; nothing in this evidence says whether "
              "the declared time is true. Key validity at the bound is not established.",
              PREIMAGE, REF, EVIDENCE, "EXISTENCE_BOUND_ESTABLISHED",
              {"existed_by_utc": iso(EVIDENCE["block_timestamp"])}),
    existence("N1-declared-time-changed-breaks-digest-link", "negative",
              "Changing the declared timestamp by one millisecond gives a different action_ref, so the real anchor "
              "no longer matches. The anchor binds the timestamp AS DECLARED, it does not verify it.",
              altered, compute_action_ref(altered), EVIDENCE, "ANCHOR_DIGEST_MISMATCH"),
    existence("N2-claimed-ref-does-not-match-preimage", "negative",
              "Claimed action_ref is the real one but the preimage was altered: recomputation fails before any anchor is read.",
              altered, REF, EVIDENCE, "ACTION_REF_MISMATCH"),
    existence("N3-wrong-registry-address", "negative",
              "SYNTHETIC tamper of the capture: log emitted by an address that is not the AnchorRegistry.",
              PREIMAGE, REF, ev_wrong_registry, "ANCHOR_WRONG_REGISTRY"),
    existence("N4-wrong-event-topic", "negative",
              "SYNTHETIC tamper of the capture: topic0 is not the Anchored event.",
              PREIMAGE, REF, ev_wrong_event, "ANCHOR_WRONG_EVENT"),
    existence("N5-anchor-tx-not-successful", "negative",
              "SYNTHETIC tamper of the capture: receipt status 0x0.",
              PREIMAGE, REF, ev_failed, "ANCHOR_TX_NOT_SUCCESSFUL"),
    existence("N6-evidence-internal-mismatch", "negative",
              "SYNTHETIC tamper of the capture: the event timestamp and the block timestamp disagree.",
              PREIMAGE, REF, ev_internal, "EVIDENCE_INTERNAL_MISMATCH"),
    existence("N7-declared-after-existence-bound", "negative",
              "Declared timestamp is later than the anchor's block time: the digest cannot have existed before it "
              "was declared. Uses a SYNTHETIC preimage and a SYNTHETIC capture whose block time was set earlier "
              "than the declared time, with the log data changed to match (internally consistent, false).",
              after, compute_action_ref(after),
              {**ev_fabricated, "log": {**ev_fabricated["log"], "topics": [EVIDENCE["log"]["topics"][0],
                                                                          "0x" + compute_action_ref(after),
                                                                          EVIDENCE["log"]["topics"][2]]}},
              "DECLARED_AFTER_EXISTENCE_BOUND"),
    existence("K1-fabricated-capture-passes-offline", "known_limit",
              "KNOWN LIMIT. A capture whose block time was moved earlier and whose log data was changed to match is "
              "internally consistent, so offline verification of the capture alone accepts it as an existence bound. "
              "Only a chain read of {tx, block hash} detects it. This is why anchor checking cannot be 'bytes plus a "
              "standard-library verifier' and must be an optional layer or a carve-out. SYNTHETIC tamper.",
              PREIMAGE, REF, ev_fabricated, "EXISTENCE_BOUND_ESTABLISHED",
              {"existed_by_utc": iso(early)}),
]

# ---- binding (all SYNTHETIC) --------------------------------------------------
PAYTO = "0x00000000000000000000000000000000000000aa"


def rec(rid, binding, amount="10.00"):
    r = {"record_id": rid, "payment": {"amount": amount, "asset": "USDC", "pay_to": PAYTO}}
    if binding is not None:
        r["binding"] = binding
    return r


N1_ = "0x" + "a1" * 32
N2_ = "0x" + "a2" * 32
T1_ = "0x" + "b1" * 32
T2_ = "0x" + "b2" * 32


def bvec(vid, kind, desc, a, b, expected):
    return {"id": vid, "kind": kind, "description": desc, "synthetic": True,
            "input": {"record_a": a, "record_b": b}, "expected": expected}


binding_vectors = [
    bvec("B1-amount-payto-cannot-tell-two-same-price-calls-apart", "negative",
         "Two separate calls, same amount, same asset, same payTo. Declared binding is amount+payTo, so the two "
         "records are not distinguishable: the binding is not unique.",
         rec("call-1", {"kind": "amount_payto"}), rec("call-2", {"kind": "amount_payto"}),
         {"verdict": "BINDING_NOT_UNIQUE", "distinguishable": False, "binding_strength": "amount_payto"}),
    bvec("B2-authorization-nonce-distinguishes-same-price-calls", "positive",
         "Same two calls, same amount and payTo. Declared binding is the authorization's one-time nonce "
         "(bytes32); distinct values distinguish them.",
         rec("call-1", {"kind": "authorization_nonce", "value": N1_}),
         rec("call-2", {"kind": "authorization_nonce", "value": N2_}),
         {"verdict": "DISTINGUISHED", "distinguishable": True, "binding_strength": "authorization_nonce"}),
    bvec("B3-tx-hash-distinguishes-but-is-declared-weaker", "positive",
         "Same two calls bound by transaction hash. Distinguishable, and the declared strength is tx_hash, which "
         "is weaker than authorization_nonce in this vector set's ordering.",
         rec("call-1", {"kind": "tx_hash", "value": T1_}), rec("call-2", {"kind": "tx_hash", "value": T2_}),
         {"verdict": "DISTINGUISHED", "distinguishable": True, "binding_strength": "tx_hash"}),
    bvec("B4-same-nonce-is-same-binding", "negative",
         "Two records declare the same authorization nonce: same binding, not two distinct calls.",
         rec("call-1", {"kind": "authorization_nonce", "value": N1_}),
         rec("call-2", {"kind": "authorization_nonce", "value": N1_}),
         {"verdict": "SAME_BINDING", "distinguishable": False, "binding_strength": "authorization_nonce"}),
    bvec("B5-undeclared-binding-is-not-inferred", "negative",
         "Record carries payment fields but declares no binding kind. The verifier does not infer one.",
         rec("call-1", None), rec("call-2", {"kind": "authorization_nonce", "value": N2_}),
         {"verdict": "BINDING_UNDECLARED", "distinguishable": False, "binding_strength": None}),
    bvec("B6-declared-nonce-with-invalid-value", "negative",
         "Declared kind authorization_nonce but the value is not a 0x + 64 hex bytes32.",
         rec("call-1", {"kind": "authorization_nonce", "value": "0x1234"}),
         rec("call-2", {"kind": "authorization_nonce", "value": N2_}),
         {"verdict": "BINDING_VALUE_INVALID", "distinguishable": False, "binding_strength": None}),
    bvec("B7-different-declared-kinds-are-not-comparable", "negative",
         "One record binds by nonce, the other by tx hash: strengths differ, the pair is not compared.",
         rec("call-1", {"kind": "authorization_nonce", "value": N1_}), rec("call-2", {"kind": "tx_hash", "value": T2_}),
         {"verdict": "BINDING_KINDS_DIFFER", "distinguishable": False, "binding_strength": None}),
]

doc = {
    "spec_version": "declared-vs-anchored-existence-v1",
    "license": "CC0-1.0",
    "description": "Vector pairs that keep a signer-declared timestamp separate from an existence bound that the "
                   "emitter does not control, and that make the binding identifier a DECLARED field with a stated "
                   "strength. Consistency under the evidence given here; no claim of independence, adoption or "
                   "endorsement by any third party.",
    "constants": {
        "registry": "0x49fEcA52bC634a9Ab773226D16619deC547794aa (same CREATE2 address on Base, Arbitrum One, Ink)",
        "event": "Anchored(bytes32 indexed ref, address indexed anchoredBy, uint256 timestamp)",
        "event_topic0": "0xfe2289542f7a0110ac112c3a4d712afdcaaf2900a1326f4e6f340b563a0e8734",
        "not_established": ["declared_time_is_true", "key_uncompromised_at_bound", "set_of_actions_complete"],
    },
    "real_vs_synthetic": {
        "real": ["P1 preimage and P2 anchor evidence (Base mainnet block 51345144, tx 0xb1144ee8...d125)"],
        "synthetic": ["N3-N7 and K1 tampered captures", "every binding vector and its nonces/tx hashes/addresses"],
    },
    "tension_declared": "Verifying an anchor needs a chain read. verify.py's offline mode only checks the captured "
                        "evidence for internal consistency (see K1); `verify.py --live` re-reads the chain. Anchor "
                        "checking is therefore an optional layer or an explicit carve-out from a 'bytes plus "
                        "standard library' bar, not part of it.",
    "existence_vectors": existence_vectors,
    "binding_vectors": binding_vectors,
}
Path(__file__).with_name("vectors.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
print("wrote", len(existence_vectors), "existence +", len(binding_vectors), "binding vectors")
