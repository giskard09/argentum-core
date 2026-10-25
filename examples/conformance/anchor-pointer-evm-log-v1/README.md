# anchor-pointer-evm-log-v1

CC0-1.0. Conformance vectors for the EVM-log anchor-pointer mechanism, built at
Tetsurohhori's (aos-standard/catalog) request in
[aeoess/agent-governance-vocabulary#217](https://github.com/aeoess/agent-governance-vocabulary/issues/217),
in the same spirit as their own `anchor-pointer` draft-0 (14 vectors: one real
positive plus negative variants, each with an expected result) -- adapted here
for the EVM shape:

```json
{"chain": "eip155:8453", "contract": "0x49fEcA52bC634a9Ab773226D16619deC547794aa",
 "tx": "<hash>", "log_index": 59, "height": 52987624}
```

For EVM there is no blob to pin and verify offline -- the proof *is* the live
chain query. A conformant reader resolves `{chain, tx}` to a transaction
receipt, finds the log at `log_index`, and checks `log.address == contract`,
`log.blockNumber == height`, and `log.topics[1] == anchored_digest` against
the `Anchored(bytes32 indexed ref, address indexed anchoredBy, uint256
timestamp)` event. See `vectors.json`'s `mechanism` block for the exact
resolution rule and the event's topic0.

This file carries data only, no verification code. Tetsurohhori asked to
write their own EVM-log reader from the event signature and run these vectors
independently, without reading ours.

The positive vector is a real anchor: the gt-v2.1 release-statement custody
record AXES (magentixai) requested in
[axes#3](https://github.com/magentixai/axes/issues/3), sent 2026-10-23,
re-verified independently against `eth_getTransactionReceipt` on
`https://mainnet.base.org` while building this file (not taken from any
script printout). Every field in every vector -- including which real,
unrelated contracts/transactions appear in the negative cases -- was checked
live against a public RPC before being written down; none are invented.

See `vectors.json` for the full set and the `omitted_by_design` note on why
no reorg/finality vector is included in this draft.
