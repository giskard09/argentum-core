#!/usr/bin/env python3
"""ERC-8274 proofProfile first-seen anchor on AnchorRegistry (DRAFT v0).

Computes the 32-byte `ref` that anchors a verifier configuration, and reads the
earliest `Anchored` event for it straight from the chain. Stdlib + pycryptodome.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request

from Crypto.Hash import keccak

REGISTRY = "0x49fEcA52bC634a9Ab773226D16619deC547794aa"   # Base 8453, Arbitrum 42161, Ink 57073
DEPLOY_BLOCK_BASE = 47696524                              # first block with code, by bisection (2026-06-23 02:39:55 UTC)
RPC_BASE = "https://mainnet.base.org"   # fine for eth_getTransactionReceipt; free public RPCs cap or refuse historical eth_getLogs


class RpcError(RuntimeError):
    """The node answered with a JSON-RPC error object (e.g. range too large)."""


class RateLimited(RuntimeError):
    """The node kept rate-limiting us. Not a range problem: shrinking the window will not help."""


def k(b: bytes) -> bytes:
    h = keccak.new(digest_bits=256)
    h.update(b)
    return h.digest()


DOMAIN = k(b"erc8274.profile-anchor.v1")
TOPIC0 = k(b"Anchored(bytes32,address,uint256)")

_HEX = re.compile(r"(?:0x)?([0-9a-fA-F]*)")


def _hex(x: str, n: int, what: str) -> bytes:
    # fullmatch, not bytes.fromhex: fromhex silently skips ASCII whitespace inside the string.
    m = _HEX.fullmatch(x) if isinstance(x, str) else None
    if m is None or len(m.group(1)) % 2:
        raise ValueError(f"{what}: not a hex string")
    b = bytes.fromhex(m.group(1))
    if len(b) != n:
        raise ValueError(f"{what}: expected {n} bytes, got {len(b)}")
    return b


def agent_proof_profile(verifier: str, proof_profile: str, metadata: bytes) -> bytes:
    """keccak256(abi.encode(address verifier, bytes32 proofProfile(), keccak256(metadata)))
    -- the single-backend formula in the ERC-8274 draft (commit 50e1e120)."""
    return k(_hex(verifier, 20, "verifier").rjust(32, b"\0") + _hex(proof_profile, 32, "proofProfile") + k(metadata))


def anchor_ref(chain_id: int, verifier: str, proof_profile: str, metadata: bytes) -> bytes:
    """keccak256(abi.encode(bytes32 DOMAIN, uint256 chainId, bytes32 agentProofProfile))"""
    if type(chain_id) is not int or not 0 < chain_id < 2**256:
        raise ValueError("chain_id: expected a positive integer below 2**256")
    app = agent_proof_profile(verifier, proof_profile, metadata)
    return k(DOMAIN + chain_id.to_bytes(32, "big") + app)


def _rpc(url, method, params):
    req = urllib.request.Request(url, json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                 {"Content-Type": "application/json", "User-Agent": "profile-anchor/0"})
    for wait in (0, 2, 5, 10, 20):
        time.sleep(wait)
        try:
            out = json.loads(urllib.request.urlopen(req, timeout=60).read())
        except urllib.error.HTTPError as e:            # public RPCs rate-limit: back off and retry
            if e.code != 429:
                raise
            continue
        if isinstance(out.get("error"), dict) and out["error"].get("code") == -32011:   # "request limit reached"
            continue
        break
    else:
        raise RateLimited(method)
    if "error" in out:
        raise RpcError(out["error"])
    return out["result"]


def confirm_anchor(ref: bytes, tx: str, rpc=RPC_BASE, registry=REGISTRY, expected_chain_id=None):
    """Confirm, from the chain's own receipt (not from whoever hands you the tx hash), that `tx` emitted
    Anchored(ref, ...) on the registry. Cheap: one eth_getTransactionReceipt, works on any RPC.
    Proves: the configuration existed no later than the returned block. Not "first": use first_seen for that.

    The registry has the same address on several chains and anyone can anchor any ref on any of them. Pass
    `expected_chain_id` (the chain whose registry you trust, normally the chainId inside the ref) and the
    RPC's eth_chainId is checked first; otherwise the chain of `rpc` is whatever you happened to point at."""
    if expected_chain_id is not None and int(_rpc(rpc, "eth_chainId", []), 16) != expected_chain_id:
        raise ValueError("rpc is on a different chain than expected_chain_id")
    r = _rpc(rpc, "eth_getTransactionReceipt", [tx])
    if not r or r.get("status") != "0x1":
        return None
    for l in r["logs"]:
        if _is_anchored(l, ref, registry) and not l.get("removed"):
            return {"block": int(r["blockNumber"], 16), "tx": tx, "anchored_by": "0x" + l["topics"][2][-40:],
                    "timestamp": int(l["data"], 16)}
    return None


def _is_anchored(l, ref, registry):
    return (l["address"].lower() == registry.lower() and len(l["topics"]) == 3
            and l["topics"][0].lower() == "0x" + TOPIC0.hex() and l["topics"][1].lower() == "0x" + ref.hex())


def first_seen(ref: bytes, rpc=RPC_BASE, registry=REGISTRY, from_block=DEPLOY_BLOCK_BASE, to_block=None, step=9_999):
    """Earliest Anchored(ref, anchoredBy, timestamp) event in [from_block, to_block], or None.
    None means "no event in that window", not "never anchored": the consumer picks the window (pin it to the
    block at which the configuration was first relied on) and, for completeness from the registry deploy block,
    passes an archive-capable RPC and a wide step. Returned logs are re-checked locally (address, topics),
    not trusted to match the node's filter."""
    head = to_block if to_block is not None else int(_rpc(rpc, "eth_blockNumber", []), 16)
    lo = from_block
    while lo <= head:
        hi = min(lo + step - 1, head)
        try:
            logs = _rpc(rpc, "eth_getLogs", [{"address": registry, "fromBlock": hex(lo), "toBlock": hex(hi),
                                              "topics": ["0x" + TOPIC0.hex(), "0x" + ref.hex()]}])
        except RpcError:                        # only a JSON-RPC error means "range too large"; rate limits propagate
            if step <= 5_000:
                raise
            step //= 4
            continue
        logs = [l for l in logs if _is_anchored(l, ref, registry) and not l.get("removed")]
        if logs:
            e = min(logs, key=lambda l: (int(l["blockNumber"], 16), int(l["logIndex"], 16)))
            return {"block": int(e["blockNumber"], 16), "tx": e["transactionHash"],
                    "anchored_by": "0x" + e["topics"][2][-40:], "timestamp": int(e["data"], 16)}
        lo = hi + 1
    return None


def main(a):
    if a and a[0] == "ref" and len(a) == 5:
        print("0x" + anchor_ref(int(a[1]), a[2], a[3], _bytes(a[4])).hex())
    elif a and a[0] == "confirm" and len(a) == 3:
        print(json.dumps(confirm_anchor(_hex(a[1], 32, "ref"), a[2]), indent=1))
    elif a and a[0] == "first-seen" and 2 <= len(a) <= 4:
        fb = int(a[2]) if len(a) > 2 else DEPLOY_BLOCK_BASE
        tb = int(a[3]) if len(a) > 3 else None
        print(json.dumps(first_seen(_hex(a[1], 32, "ref"), from_block=fb, to_block=tb), indent=1))
    else:
        print("usage: confirm <ref> <txHash> | ref <chainId> <verifier> <proofProfile> <metadataHex> | first-seen <ref> [fromBlock] [toBlock]")


def _bytes(s):
    m = _HEX.fullmatch(s)
    if m is None or len(m.group(1)) % 2:
        raise ValueError("metadata: not a hex string")
    return bytes.fromhex(m.group(1))


if __name__ == "__main__":
    main(sys.argv[1:])
