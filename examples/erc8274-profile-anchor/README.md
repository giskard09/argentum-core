# ERC-8274 proofProfile first-seen anchor (DRAFT v0)

Concrete answer to the open point in the ERC-8274 review thread (ethereum/ERCs#1771): the spec now derives the
profile from components a consumer can recompute (e.g. the runtime bytecode hash), and leaves "when was this
profile first committed to, and did it rotate silently" to a registry-layer mechanism. This is that mechanism, built on
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
     RPC. Proves that someone committed to this configuration no later than that block; does not prove it is the earliest.
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
rotation is a configuration that is in use but has no `Anchored` event (or none earlier than the consumer's own pin): the consumer can see it and refuse.

## What it proves, and what it does not

- Proves that someone committed to this exact configuration no later than block B. The `ref` is computable in
  advance (predictable CREATE/CREATE2 address, public bytecode hash), so an anchor does not show the verifier was
  deployed or live at B; check its deployment separately (creation block, `eth_getCode`). Not authorship, not
  correct behavior: anyone can anchor any `ref`. A configuration in use with NO anchor is still detectable.
- Threat model: pre-anchoring of a predicted configuration is possible and is why first-seen is a lower bound on
  commitment, not on deployment.
- Does not force a backend to anchor or to avoid rotating. It makes an un-anchored or late rotation detectable
  under the consumer's own policy.
- No revocation and no per-anchorer namespace in AnchorRegistry. ModelCommitmentAnchor
  (trustless-ai/flashprove-onchain-verifier#2) adds them for model commitments (commitment ID -> digest of static
  artifacts), not for verifier profiles; the two are complementary, and the consumer chooses which
  anchorers to trust by reading `anchoredBy`.
- Subject to the chain's finality and reorg rules; read at the finality your policy needs. `removed` logs are
  ignored.
- Single-backend formula only (as in the ERC draft). Multi-verifier composition and the pre-selection sentinel
  profile are not covered.

## Composition control: anchor + retirement + consumer policy (SIMULATED)

Negative control proposed by Pavlo in the trustless-ai group (Telegram, 2026-11-16): anchoring a `proofProfile`
is not the same as authorizing that verifier to accept NEW submissions. The control, end to end and without
touching the ERC interface: (1) anchor verifier A; (2) retire A at block B and activate verifier B; (3) a NEW
submission by A after B is rejected although A still has a valid anchor; (4) an OLD submission by A before B stays
verifiable historically; (5) a configuration with no anchor is rejected when the consumer's policy requires one.

`composition_policy.py` is a pure function `evaluate(verifier_ref, submission_block, anchor_block, retirements,
trusted_emitters, require_anchor) -> (accept, reason)`; reasons: `UNANCHORED`, `ANCHOR_AFTER_SUBMISSION`,
`RETIRED_AT_OR_BEFORE_SUBMISSION`, `HISTORICAL_OK`, `ANCHORED_OK`, `ANCHORED_LATE`, `ANCHOR_NOT_REQUIRED`. Tests:
`tests/test_erc8274_composition_policy.py` (a positive and a negative case per step, plus the edges).

Block conventions (chosen here, tested on both sides): a retirement at block B takes effect AT B, so a submission
in block B is REJECTED and one in B-1 is accepted as historical; an anchor in the same block as the submission
counts as covered, one block later does not. A block-level policy cannot order two events inside one block, so the
retirement edge fails closed. With `require_anchor=False` an anchor later than the submission is not rejected, but it is no longer labelled as if it had been there: the reason is `ANCHORED_LATE` (`ANCHORED_OK` is reserved for an anchor in the submission's block or earlier, so same block = `ANCHORED_OK`, one block later = `ANCHORED_LATE`). The timing is evaluated to label, not to reject. Precedence: a trusted retirement decides the reason first, so `ANCHORED_LATE` only applies on the branch without a retirement, and `HISTORICAL_OK` says nothing about anchor timing when `require_anchor=False`. The earliest retirement from a trusted emitter governs (a later duplicate does not
un-retire); retirements from emitters the consumer does not trust, or for another verifier, are ignored.

Non-claims:

- The retirement source is SIMULATED. AnchorRegistry has no retirement or revocation (no owner, no roles, a single
  `anchor(bytes32)`), and this example does not invent one. A "retirement" here is an event the consumer reads from
  a source it chooses to trust.
- This test does not prove that a verifier stops accepting anything in production. It proves that a consumer
  policy combining anchor + retirement + require-anchor gives the expected verdicts on explicit inputs.
- An anchor proves COMMITMENT, not existence or deployment (see "What it proves"); nothing here contradicts that.
- `docs/spec/revocation-ref.md` (revocation-ref-v1) has the same semantics Pavlo asks for in steps 3 and 4
  (append-only, applies to future use, does not rewrite the past), but it covers delegations
  (`revoked_action_ref` / `revoked_delegation_ref`), NOT the retirement of a verifier profile, and its `revoked_at`
  is an ISO timestamp declared by the revoker, not a block number. This is a gap; it is not covered by that spec.
- Reorgs and finality: block numbers are inputs already read at the finality the consumer's policy requires (see
  "What it proves").
- Not covered: who is a trustworthy retirement emitter, how a consumer discovers retirements, and multi-verifier
  composition.

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

- `composition_policy.py`: consumer policy over simulated anchor/retirement inputs (see the section above).
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
