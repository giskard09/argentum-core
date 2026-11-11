"""Verifier for declared-vs-anchored-existence-v1 vectors.

Two things are kept apart on purpose:

  * DECLARED timestamp: the `timestamp` field inside the action_ref preimage
    is stated by whoever emitted the record. Nothing in the preimage proves it
    is true.
  * ANCHORED existence: an Anchored event for the same digest, emitted by a
    contract the emitter does not control, bounds when the digest existed
    ("existed by block time T"). It does NOT show that the declared time was
    true, that the signing key was uncompromised at that time, or that the set
    of anchored actions is complete.

Part 1 (existence): standard library only, no network. It checks the CAPTURED
evidence for internal consistency. Captured evidence is data somebody wrote
down; this offline mode does not authenticate it against the chain. Checking
the chain needs a chain read (see live_recheck(), optional, network).

Part 2 (binding): a record DECLARES which identifier binds it to a payment.
Strength is read from the declared kind, never inferred from which fields
happen to be present.

All binding data in vectors.json is synthetic. No payer-level or
transaction-linked request data is used.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

REGISTRY = "0x49feca52bc634a9ab773226d16619dec547794aa"
ANCHORED_TOPIC0 = "0xfe2289542f7a0110ac112c3a4d712afdcaaf2900a1326f4e6f340b563a0e8734"
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
HEX32_RE = re.compile(r"^0x[0-9a-f]{64}$")
PREIMAGE_KEYS = ("action_type", "agent_id", "scope", "timestamp")


# --------------------------------------------------------------------------
# action_ref (v1, bare SHA-256(JCS(preimage))) -- ASCII-only profile domain
# --------------------------------------------------------------------------
class OutOfProfileDomain(ValueError):
    pass


def compute_action_ref(preimage: dict) -> str:
    if not isinstance(preimage, dict) or set(preimage) != set(PREIMAGE_KEYS):
        raise OutOfProfileDomain("preimage must have exactly the four fields")
    for k in PREIMAGE_KEYS:
        v = preimage[k]
        if not isinstance(v, str) or not v or not v.isascii():
            raise OutOfProfileDomain(f"{k}: non-empty ASCII string required")
    if not TS_RE.match(preimage["timestamp"]):
        raise OutOfProfileDomain("timestamp grammar")
    try:
        parse_declared(preimage["timestamp"])
    except ValueError as exc:
        raise OutOfProfileDomain("timestamp is not a real instant") from exc
    canonical = json.dumps(dict(sorted(preimage.items())), separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def parse_declared(ts: str) -> int:
    dt = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp())


def iso(seconds: int) -> str:
    return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Part 1: declared timestamp vs anchored existence
# --------------------------------------------------------------------------
def verify_existence(inp: dict) -> dict:
    out = {
        "declared": {"claim_class": "signer_declared", "independently_bounded": False,
                     "timestamp": None},
        "existence": {"claim_class": "anchored_existence", "established": False,
                      "existed_by_utc": None,
                      "evidence_authenticity": "captured_not_chain_verified"},
        # Constant by design: an anchor never establishes these.
        "not_established": ["declared_time_is_true", "key_uncompromised_at_bound",
                            "set_of_actions_complete"],
        "verdict": None,
    }
    preimage = inp["preimage"]
    try:
        recomputed = compute_action_ref(preimage)
    except OutOfProfileDomain:
        out["verdict"] = "OUT_OF_PROFILE_DOMAIN"
        return out
    out["declared"]["timestamp"] = preimage["timestamp"]
    if inp["claimed_action_ref"] != recomputed:
        out["verdict"] = "ACTION_REF_MISMATCH"
        return out
    ev = inp.get("anchor_evidence")
    if ev is None:
        out["verdict"] = "DECLARED_ONLY"
        return out
    log = ev["log"]
    if ev.get("status") != "0x1":
        out["verdict"] = "ANCHOR_TX_NOT_SUCCESSFUL"
    elif str(log["address"]).lower() != REGISTRY:
        out["verdict"] = "ANCHOR_WRONG_REGISTRY"
    elif len(log["topics"]) < 2 or str(log["topics"][0]).lower() != ANCHORED_TOPIC0:
        out["verdict"] = "ANCHOR_WRONG_EVENT"
    elif str(log["topics"][1]).lower() != "0x" + recomputed:
        out["verdict"] = "ANCHOR_DIGEST_MISMATCH"
    elif int(log["data"], 16) != ev["block_timestamp"]:
        out["verdict"] = "EVIDENCE_INTERNAL_MISMATCH"
    elif parse_declared(preimage["timestamp"]) > ev["block_timestamp"]:
        out["verdict"] = "DECLARED_AFTER_EXISTENCE_BOUND"
    else:
        out["verdict"] = "EXISTENCE_BOUND_ESTABLISHED"
        out["existence"]["established"] = True
        out["existence"]["existed_by_utc"] = iso(ev["block_timestamp"])
        out["declared"]["seconds_before_bound"] = ev["block_timestamp"] - parse_declared(preimage["timestamp"])
    return out


def live_recheck(ev: dict, rpc_url: str) -> dict:
    """OPTIONAL chain read (network). Re-fetches the receipt and block and
    compares them with the captured evidence. This is the step that makes the
    evidence authenticated; it is not bytes + standard library only."""
    import urllib.request

    def call(method, params):
        req = urllib.request.Request(
            rpc_url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
            headers={"content-type": "application/json", "user-agent": "conformance-recheck/1"})
        return json.load(urllib.request.urlopen(req, timeout=20))["result"]

    rc = call("eth_getTransactionReceipt", [ev["tx"]])
    blk = call("eth_getBlockByNumber", [hex(ev["block_number"]), False])
    log = next(entry for entry in rc["logs"] if int(entry["logIndex"], 16) == ev["log"]["log_index"])
    checks = {
        "block_hash": rc["blockHash"].lower() == ev["block_hash"].lower() == blk["hash"].lower(),
        "block_timestamp": int(blk["timestamp"], 16) == ev["block_timestamp"],
        "log_topics": [t.lower() for t in log["topics"]] == [t.lower() for t in ev["log"]["topics"]],
        "log_data": log["data"].lower() == ev["log"]["data"].lower(),
        "status": rc["status"] == ev["status"],
    }
    return {"chain_read_confirmed": all(checks.values()), "checks": checks}


# --------------------------------------------------------------------------
# Part 2: declared binding kind and its strength
# --------------------------------------------------------------------------
# Strength is a property of the DECLARED kind. Order (our reading of why):
#   authorization_nonce : a one-time value inside what the payer signed
#   tx_hash             : exists only after submission; set by the submitter's
#                         transaction envelope, not by the payer's signature
#   amount_payto        : not unique across repeated same-price calls
STRENGTH = {"authorization_nonce": 3, "tx_hash": 2, "amount_payto": 0}


def _binding_value(rec: dict):
    b = rec.get("binding")
    if not isinstance(b, dict) or "kind" not in b:
        return "BINDING_UNDECLARED", None
    kind = b["kind"]
    if kind not in STRENGTH:
        return "BINDING_KIND_UNKNOWN", None
    if kind == "amount_payto":
        p = rec.get("payment", {})
        if not all(isinstance(p.get(k), str) and p.get(k) for k in ("amount", "asset", "pay_to")):
            return "BINDING_VALUE_INVALID", None
        return None, (p["amount"], p["asset"], p["pay_to"].lower())
    val = b.get("value")
    if not isinstance(val, str) or not HEX32_RE.match(val.lower()):
        return "BINDING_VALUE_INVALID", None
    return None, val.lower()


def verify_binding_pair(r1: dict, r2: dict) -> dict:
    e1, v1 = _binding_value(r1)
    e2, v2 = _binding_value(r2)
    res = {"binding_strength": None, "distinguishable": False, "verdict": None}
    err = e1 or e2
    if err:
        res["verdict"] = err
        return res
    k1, k2 = r1["binding"]["kind"], r2["binding"]["kind"]
    if k1 != k2:
        res["verdict"] = "BINDING_KINDS_DIFFER"
        return res
    res["binding_strength"] = k1
    if k1 == "amount_payto":
        # Equal tuple => the two calls cannot be told apart by this binding.
        res["verdict"] = "BINDING_NOT_UNIQUE" if v1 == v2 else "DISTINGUISHED"
        res["distinguishable"] = v1 != v2
        return res
    if v1 == v2:
        res["verdict"] = "SAME_BINDING"
        return res
    res["verdict"] = "DISTINGUISHED"
    res["distinguishable"] = True
    return res


# --------------------------------------------------------------------------
def run(path: Path) -> int:
    data = json.loads(path.read_text())
    failures = 0
    for v in data["existence_vectors"]:
        got = verify_existence(v["input"])
        ok = got["verdict"] == v["expected"]["verdict"]
        ok = ok and got["not_established"] == data["constants"]["not_established"]
        if "existed_by_utc" in v["expected"]:
            ok = ok and got["existence"]["existed_by_utc"] == v["expected"]["existed_by_utc"]
        print(("PASS " if ok else "FAIL ") + v["id"] + " -> " + str(got["verdict"]))
        failures += not ok
    for v in data["binding_vectors"]:
        got = verify_binding_pair(v["input"]["record_a"], v["input"]["record_b"])
        ok = all(got[k] == v["expected"][k] for k in v["expected"])
        print(("PASS " if ok else "FAIL ") + v["id"] + " -> " + str(got["verdict"]))
        failures += not ok
    return failures


if __name__ == "__main__":
    here = Path(__file__).parent / "vectors.json"
    if "--live" in sys.argv:
        d = json.loads(here.read_text())
        ev = next(v for v in d["existence_vectors"] if v["id"] == "P2-anchored-existence-established")["input"]["anchor_evidence"]
        print(json.dumps(live_recheck(ev, "https://mainnet.base.org"), indent=1))
        sys.exit(0)
    sys.exit(1 if run(here) else 0)
