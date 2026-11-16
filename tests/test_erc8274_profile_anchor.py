"""examples/erc8274-profile-anchor: preimage, negative controls, and the read logic.

Three layers, kept apart on purpose:
  - always run: pinned values (computed once with Foundry `cast`), negative controls, and the
    confirm/first-seen LOGIC against a simulated RPC (not a real node);
  - skipped without `cast` on PATH: recompute with Foundry. A cross-check of the primitive,
    NOT an independent implementation of the spec;
  - skipped unless ERC8274_LIVE=1: confirm a real anchor receipt on Base mainnet.
The first-seen scan has NO test against a real RPC (no free public RPC answered historical logs).
"""
import importlib.util
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "examples", "erc8274-profile-anchor", "profile_anchor.py")
spec = importlib.util.spec_from_file_location("profile_anchor", PATH)
pa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pa)

V = "0x000102030405060708090a0b0c0d0e0f10111213"        # SYNTHETIC verifier address (not deployed); not a palindrome, so byte order matters
P = "0x" + pa.k(b"example/sp1-v1").hex()                 # SYNTHETIC proofProfile
M = b'{"programVKey":"0xabc"}'                          # SYNTHETIC metadata
CH = 8453

# PIN_REF was computed once with `cast keccak` / `cast abi-encode`; test_cross_check_with_foundry_cast recomputes it.
PIN_DOMAIN = "0xba2ad195991c76176527450aa466667c3ad8b7f3a4f54f1463d45889691e41bc"   # cast keccak erc8274.profile-anchor.v1
PIN_REF = "0xffe3e2249affa5fb83532248d302abad20f15beaf788d4da0a3232e219887011"   # `cast` output for the synthetic V, P, M, CH below


def test_pinned_values():
    assert "0x" + pa.anchor_ref(CH, V, P, M).hex() == PIN_REF


def test_negative_controls():
    base = pa.anchor_ref(CH, V, P, M)
    assert pa.anchor_ref(1, V, P, M) != base                                    # other chain
    assert pa.anchor_ref(CH, "0x" + "22" * 20, P, M) != base                    # other verifier address
    assert pa.anchor_ref(CH, V, "0x" + pa.k(b"example/sp1-v2").hex(), M) != base   # rotated profile
    assert pa.anchor_ref(CH, V, P, M + b" ") != base                            # any metadata change
    assert base != pa.agent_proof_profile(V, P, M)                              # domain separation
    assert pa.anchor_ref(CH, V, P, M) == base                                   # deterministic


@pytest.mark.parametrize("bad", [
    lambda: pa.anchor_ref(CH, "0x11", P, M),                       # short address
    lambda: pa.anchor_ref(CH, V, "0x1234", M),                     # short profile
    lambda: pa.anchor_ref(CH, V[:10] + " " + V[10:], P, M),        # whitespace inside (bytes.fromhex would skip it)
    lambda: pa.anchor_ref(CH, V + "\n", P, M),                     # trailing newline
    lambda: pa.anchor_ref(CH, "0X" + V[2:], P, M),                 # uppercase prefix
    lambda: pa.anchor_ref(0, V, P, M),
    lambda: pa.anchor_ref(-1, V, P, M),
    lambda: pa.anchor_ref(2**256, V, P, M),
    lambda: pa.anchor_ref(True, V, P, M),
])
def test_bad_input_rejected(bad):
    with pytest.raises(ValueError):
        bad()


@pytest.mark.skipif(shutil.which("cast") is None, reason="Foundry cast not installed")
def test_cross_check_with_foundry_cast():
    def cast(*args):
        return subprocess.run(["cast", *args], capture_output=True, text=True, check=True).stdout.strip()
    assert PIN_DOMAIN == cast("keccak", "erc8274.profile-anchor.v1")
    app = cast("keccak", cast("abi-encode", "f(address,bytes32,bytes32)", V, P, cast("keccak", "0x" + M.hex())))
    assert "0x" + pa.agent_proof_profile(V, P, M).hex() == app
    ref = cast("keccak", cast("abi-encode", "f(bytes32,uint256,bytes32)", PIN_DOMAIN, str(CH), app))
    assert "0x" + pa.anchor_ref(CH, V, P, M).hex() == ref == PIN_REF


# ---- read logic against a SIMULATED rpc (not a node) -------------------------------------------------

REF = pa.anchor_ref(CH, V, P, M)
OTHER = pa.anchor_ref(CH, V, P, M + b"x")


def _log(block, idx, ref=REF, by="aa" * 20, ts=1000, address=pa.REGISTRY, removed=False, topic0=None):
    return {"address": address, "blockNumber": hex(block), "logIndex": hex(idx), "transactionHash": f"0x{block:064x}",
            "topics": [topic0 or "0x" + pa.TOPIC0.hex(), "0x" + ref.hex(), "0x" + "00" * 12 + by],
            "data": hex(ts), "removed": removed}


class Sim:
    """eth_getLogs over a fixed log list; `max_range` makes wider windows fail like a capped public RPC."""
    def __init__(self, logs, head=1000, max_range=None, chain="0x2105"):
        self.logs, self.head, self.max_range, self.chain, self.calls = logs, head, max_range, chain, []

    def __call__(self, url, method, params):
        self.calls.append((method, params))
        if method == "eth_blockNumber":
            return hex(self.head)
        if method == "eth_chainId":
            return self.chain
        f = params[0]
        lo, hi = int(f["fromBlock"], 16), int(f["toBlock"], 16)
        if self.max_range and hi - lo + 1 > self.max_range:
            raise pa.RpcError({"code": -32602, "message": "range too large"})
        return [l for l in self.logs if lo <= int(l["blockNumber"], 16) <= hi]   # simulates the node's filter loosely


def test_first_seen_takes_earliest(monkeypatch):
    sim = Sim([_log(500, 3, ts=5), _log(500, 1, ts=4), _log(700, 0, ts=9)])
    monkeypatch.setattr(pa, "_rpc", sim)
    r = pa.first_seen(REF, from_block=0, to_block=1000, step=10_000)
    assert (r["block"], r["timestamp"]) == (500, 4)          # same block: lower logIndex wins


def test_first_seen_empty_window_is_none(monkeypatch):
    monkeypatch.setattr(pa, "_rpc", Sim([_log(500, 0)]))
    assert pa.first_seen(REF, from_block=0, to_block=499, step=10_000) is None


def test_first_seen_spans_windows_and_shrinks_on_range_error(monkeypatch):
    sim = Sim([_log(900, 0)], max_range=2_000)
    monkeypatch.setattr(pa, "_rpc", sim)
    assert pa.first_seen(REF, from_block=0, to_block=1000, step=9_999)["block"] == 900


def test_first_seen_window_boundary_is_not_skipped(monkeypatch):
    monkeypatch.setattr(pa, "_rpc", Sim([_log(100, 0)]))     # first block of the second window
    assert pa.first_seen(REF, from_block=0, to_block=1000, step=100)["block"] == 100


def test_first_seen_range_error_at_floor_raises(monkeypatch):
    monkeypatch.setattr(pa, "_rpc", Sim([_log(900, 0)], max_range=10))
    with pytest.raises(pa.RpcError):
        pa.first_seen(REF, from_block=0, to_block=1000, step=9_999)


def test_first_seen_rate_limit_is_not_a_range_error(monkeypatch):
    calls = []

    def limited(url, method, params):
        calls.append(params)
        raise pa.RateLimited(method)
    monkeypatch.setattr(pa, "_rpc", limited)
    with pytest.raises(pa.RateLimited):
        pa.first_seen(REF, from_block=0, to_block=1000, step=9_999)
    assert len(calls) == 1                                    # no shrink-and-retry on a rate limit


@pytest.mark.parametrize("bad", [
    _log(500, 0, ref=OTHER),                 # a node that ignores the topic filter
    _log(500, 0, address="0x" + "99" * 20),  # wrong contract
    _log(500, 0, removed=True),              # reorged out
    _log(500, 0, topic0="0x" + "00" * 32),   # other event
])
def test_first_seen_rechecks_returned_logs(monkeypatch, bad):
    monkeypatch.setattr(pa, "_rpc", Sim([bad]))
    assert pa.first_seen(REF, from_block=0, to_block=1000, step=10_000) is None


def _receipt(logs, status="0x1", block=77):
    return {"status": status, "blockNumber": hex(block), "logs": logs}


def test_confirm_anchor(monkeypatch):
    rc = _receipt([_log(77, 0, ts=42)])
    monkeypatch.setattr(pa, "_rpc", lambda u, m, p: rc if m == "eth_getTransactionReceipt" else "0x2105")
    assert pa.confirm_anchor(REF, "0xaa")["block"] == 77
    assert pa.confirm_anchor(OTHER, "0xaa") is None                                           # another ref
    assert pa.confirm_anchor(bytes([REF[0] ^ 1]) + REF[1:], "0xaa") is None                   # one bit off
    assert pa.confirm_anchor(REF, "0xaa", registry="0x" + "99" * 20) is None                  # another registry


@pytest.mark.parametrize("rc", [_receipt([_log(77, 0)], status="0x0"), _receipt([_log(77, 0, removed=True)]), None])
def test_confirm_anchor_rejects_failed_removed_or_missing(monkeypatch, rc):
    monkeypatch.setattr(pa, "_rpc", lambda u, m, p: rc)
    assert pa.confirm_anchor(REF, "0xaa") is None


def test_confirm_anchor_chain_check(monkeypatch):
    monkeypatch.setattr(pa, "_rpc", Sim([], chain="0xa4b1"))      # Arbitrum answering
    with pytest.raises(ValueError):
        pa.confirm_anchor(REF, "0xaa", expected_chain_id=8453)


# ---- live: a real anchor receipt on Base --------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("ERC8274_LIVE") != "1", reason="set ERC8274_LIVE=1 to read mainnet.base.org")
def test_live_receipt_confirmation():
    real_ref = bytes.fromhex("d2d342d8221ac56cca286173b875d08a4723b8467565adc43ef76f149120a1dc")
    real_tx = "0x9caa800651433db570a8ac58085b834107640d1df6088386f9086ecbdb78a86f"   # PROVENANCE.md, block 50824409
    r = pa.confirm_anchor(real_ref, real_tx, expected_chain_id=8453)
    assert r and r["block"] == 50824409, r
    blk = pa._rpc(pa.RPC_BASE, "eth_getBlockByNumber", [hex(r["block"]), False])
    assert r["timestamp"] == int(blk["timestamp"], 16)           # the event timestamp is the block's
    assert pa.confirm_anchor(REF, real_tx) is None               # another ref
    assert pa.confirm_anchor(bytes([real_ref[0] ^ 1]) + real_ref[1:], real_tx) is None
