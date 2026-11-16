# ERC-8274 proofProfile first-seen anchor (DRAFT v0)

Concrete answer to the open point in the ERC-8274 review thread (ethereum/ERCs#1771): the spec now derives the
profile from components a consumer can recompute (e.g. the runtime bytecode hash), and leaves "when did this
profile first exist, and did it rotate silently" to a registry-layer mechanism. This is that mechanism, built on
the AnchorRegistry already deployed at the same address on Base, Arbitrum and Ink:
`0x49fEcA52bC634a9Ab773226D16619deC547794aa` (permissionless, no owner, `anchor(bytes32 ref)` emits
`Anchored(ref, anchoredBy, timestamp)`).

Status: draft. **Nothing from this directory has been anchored on-chain.** The example verifier, profile and
metadata in the tests are synthetic.

## Preimage

```
agentProofProfile = keccak256(abi.encode(address verifier, bytes32 proofProfile(), keccak256(metadata)))
                    // the single-backend formula already in the ERC-8274 draft (commit 50e1e120)
DOMAIN            = keccak256("erc8274.profile-anchor.v1")
ref               = keccak256(abi.encode(bytes32 DOMAIN, uint256 chainId, bytes32 agentProofProfile))
```

All words are static 32-byte words (the address left-padded), so a consumer can rebuild `ref` from values it
reads itself: the verifier address, `proofProfile()` and the `metadata` bytes it was given.

## Read rule (consumer side)

1. Recompute `ref` for the verifier configuration being used (chain id included).
2. Find the `Anchored` event(s) for that `ref` (topic1) on the registry. Two ways:
   - `confirm`: whoever holds a tx hash (the verifier's operator, an indexer, the PR) hands it over; the consumer
     confirms with one `eth_getTransactionReceipt` that the registry emitted `Anchored(ref, ...)`. Works on any
     RPC. Proves the configuration existed no later than that block; does not prove it is the earliest.
   - `first-seen`: scan the registry's `Anchored` logs for `ref` over a window the consumer picks (from the block
     it first relied on, or from the registry deploy block 47696524 on Base) and take the earliest. Needs an
     archive-capable RPC: free public RPCs cap or refuse historical `eth_getLogs` (checked 16/11: one caps at a
     recent window, one at 50 blocks, one does not support it, one rate-limits). An empty window means "no event
     in that window", not "never anchored".
   The timestamp is the one the registry emitted, read from the chain, never from the backend (the live test
   checks it equals the block's own timestamp).
   Which chain: the `chainId` inside `ref` names the verifier's chain; it does not stop anyone from anchoring that
   `ref` on another chain where the registry has the same address. Read the logs on the chain whose registry you
   trust (normally the same one) and pass `expected_chain_id` to `confirm_anchor` so the RPC's `eth_chainId` is
   checked.
3. Policy, chosen by the consumer: refuse a configuration with no event (unanchored); refuse one whose first
   event is later than the consumer's own pin; accept only events by anchorers the consumer lists
   (`anchoredBy` is in the log).

A rotation is a new `ref` (any change to the verifier address, `proofProfile()` or `metadata`). A silent
rotation is a configuration that is in use but has no earlier `Anchored` event: the consumer can see it and refuse.

## What it proves, and what it does not

- Proves existence of the configuration no later than block B. Not authorship, not correct behavior: anyone can
  anchor any `ref`, so the first event shows the configuration existed, not who operates it or that the verifier
  does what it says.
- Does not force a backend to anchor or to avoid rotating. It makes an un-anchored or late rotation detectable
  under the consumer's own policy.
- No revocation and no per-anchorer namespace in AnchorRegistry. Those are added by ModelCommitmentAnchor
  (trustless-ai/flashprove-onchain-verifier#2); the two are complementary, and the consumer chooses which
  anchorers to trust by reading `anchoredBy`.
- Subject to the chain's finality and reorg rules; read at the finality your policy needs. `removed` logs are
  ignored.
- Single-backend formula only (as in the ERC draft). Multi-verifier composition and the pre-selection sentinel
  profile are not covered.

## Limits of this example

- The `first-seen` mode (log scan) is implemented but has NO test against a real RPC: no free public RPC answered
  historical logs (tried 16/11: drpc, publicnode, 1rpc, meowrpc, mainnet.base.org with rate limit). Its window,
  ordering and filtering logic is exercised only against a simulated RPC in the tests. If you have an archive RPC,
  run it and add the test.
- The comparison with Foundry `cast` is a cross-check of the primitive (keccak and ABI encoding), not an
  implementation of the spec by someone else. Both sides were written from the same formula.
- **No on-chain anchor was made for ERC-8274 and no gas was spent.** The example is synthetic. The one real
  receipt used by the live test is an existing anchor from this repo (`PROVENANCE.md`, Base block 50824409), used
  only to exercise `confirm`.

## Files and how to check it

- `profile_anchor.py`: `ref` computation and a log reader (stdlib + pycryptodome, which `web3` already pulls in).
- `tests/test_erc8274_profile_anchor.py` (run from the repo root, `pytest -q`):
  - pinned `ref` for a synthetic configuration, computed with Foundry `cast`; recomputed with `cast` when it is
    installed (skipped otherwise);
  - negative controls: other chain, other verifier, rotated profile, any metadata change, domain separation, bad
    input (short, whitespace, trailing newline, bad chain ids);
  - `confirm` and `first-seen` logic against a simulated RPC (earliest by block then logIndex, windows, range
    errors, rate limits, a node ignoring the filter, removed logs, wrong chain);
  - with `ERC8274_LIVE=1`, a receipt confirmation of a real anchor on Base plus two negative controls.

```
python3 profile_anchor.py ref 8453 0x<verifier> 0x<proofProfile> 0x<metadataHex>
python3 profile_anchor.py confirm 0x<ref> 0x<txHash>
python3 profile_anchor.py first-seen 0x<ref> [fromBlock] [toBlock]
```

Registry deploy block on Base (first block with code, by bisection): 47696524, 2026-06-23 02:39:55 UTC.
