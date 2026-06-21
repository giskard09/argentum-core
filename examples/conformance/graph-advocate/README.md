# Graph Advocate independent conformance set for counterparty-ref-v1

An independent implementation of the `counterparty-ref-v1` wire format from
[`argentum-core/docs/spec/counterparty-ref.md`](../../../docs/spec/counterparty-ref.md),
shipped as a working provider on Base.

`counterparty_ref = SHA-256(JCS(preimage))` over the five-field preimage
`{provider_id, rubric_version, timestamp, trailing_days, wallet}`, with JCS
per RFC 8785 and the timestamp pinned to ISO 8601 UTC with millisecond
precision and a `Z` suffix (`YYYY-MM-DDTHH:MM:SS.mmmZ`).

## Provider

Graph Advocate is an x402-paid ERC-8004 agent on Base that scores wallets
0–100 along three independently-verifiable axes:

- **identity** (30 pts) — ERC-8004 registration on Base + IPFS metadata validity
- **activity** (40 pts) — USDC settlement velocity (Base RPC Transfer-event scan)
- **reputation** (30 pts) — ERC-8004 feedback + validation registry events,
  aggregated across all agents owned by the wallet

Hard 8004 gate: unregistered wallets score 0 regardless of activity. Filters
burn addresses, the USDC contract itself, and CEX hot wallets — none of
which should be returning a "this is a real agent" signal regardless of how
much USDC flows through them.

| Field | Value |
|---|---|
| Provider ID | `graph-advocate.agent-score.v1` |
| Rubric version | `graph-advocate.rubric.v1` |
| Endpoint | `POST https://graphadvocate.com/agent/score` |
| Price | $0.02 USDC on Base via x402 |
| Docs | [docs.graphadvocate.com/agent-score](https://docs.graphadvocate.com/agent-score) |

## Counterparty-ref binding

The `/agent/score` response includes the preimage and the computed ref so
verifiers can re-derive without calling back:

```json
{
  "wallet": "0xE69F9cC5e073B4a41D9e888A91159D0706161F18",
  "score": 40,
  "tier": "registered_or_settling",
  "verdict": "...",
  "provider_id": "graph-advocate.agent-score.v1",
  "rubric_version": "graph-advocate.rubric.v1",
  "trailing_days": 30,
  "timestamp": "2026-06-21T00:00:00.000Z",
  "counterparty_ref": "<sha256 hex>",
  "counterparty_ref_preimage": { ... },
  "counterparty_ref_jcs": "<canonical string>"
}
```

A consuming agent embeds `counterparty_ref` in its Trust Receipt envelope
to assert that it admitted the action after evaluating the counterparty's
reputation snapshot at `timestamp`. A third-party verifier reproduces
`SHA-256(JCS(counterparty_ref_preimage))` and confirms byte-exact match
against `counterparty_ref` — confirming the snapshot's content and time.

## Why timestamp is required

Per
[`docs/spec/counterparty-ref.md`](../../../docs/spec/counterparty-ref.md),
a preimage without `timestamp` is a floating hash: it cannot be placed in
time, cannot be confirmed as pre-dating the action it gates, and cannot be
compared against an on-chain anchor. Graph Advocate's earlier ad-hoc
construction (`sha256(wallet || provider_id || rubric_version || days)`,
proposed in
[coinbase/agentkit#1168 comment-4762465506](https://github.com/coinbase/agentkit/issues/1168#issuecomment-4762465506))
was exactly the reject pattern in
[`reject-missing-timestamp.json`](../counterparty-ref/reject-missing-timestamp.json).
After the spec landed, the provider was updated and now emits a complete
preimage on every score call.

## Files

- [`vectors.json`](./vectors.json) — the vector set. PASS vectors carry the
  five-field preimage, the canonical JCS string, and the lowercase-hex
  SHA-256. The reject vector carries `reject: true` and exercises the
  timestamp-omission failure mode from the provider side.
- [`verify.py`](./verify.py) — standalone runner, Python 3 stdlib only.
  Vendored JCS serializer, independent recomputation.
- [`verify.mjs`](./verify.mjs) — standalone runner, Node.js built-ins only
  (`node:crypto`, `node:fs`, `node:path`). Independent recomputation in a
  second language.

Neither runner imports any Graph Advocate library. Each recomputes from
the preimage, so a pass cross-checks the hashes against two independent
implementations alongside the provider's own.

## Run

```sh
python3 verify.py
node verify.mjs
```

Both exit 0 on a full pass and print:

```
PASS: 3 vectors (provider: graph-advocate.agent-score.v1)
```
