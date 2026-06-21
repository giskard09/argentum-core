# counterparty-ref-v1 — Specification

**Stable tag:** `counterparty-ref-v1.0`
**Status:** stable
**Canonical fixture:** [`examples/conformance/counterparty-ref/`](../../examples/conformance/counterparty-ref/)

---

## What is counterparty-ref

`counterparty_ref` is a SHA-256 hex pointer to a counterparty reputation snapshot
captured at the moment an action was admitted. It enables a verifier to establish
the reputation context under which a transaction occurred — without embedding the
full reputation record in the trail.

**Two distinct layers:**

| Layer | What it records |
|-------|----------------|
| Wallet reputation | On-chain history, balances, slashing events — persistent, cross-provider |
| Action recording | What the agent did in this interaction — Mycelium trails |

`counterparty_ref` lives at the wallet-reputation layer. It is not a trail of
actions — it is a snapshot of standing. This distinction matters for verifiability:
wallet reputation survives provider churn; action trails require provider continuity.

**Anchor requirement:** for long-term verifiability, the preimage SHOULD be anchored
on-chain (e.g. via `GiskardPayments.markUsed(bytes32)` or equivalent) at the time of
snapshot. A `counterparty_ref` without an anchor degrades to a locally-trusted hash —
a verifier cannot confirm the snapshot was not post-dated.

---

## Preimage schema

```json
{
  "provider_id":     "<string — identity of the reputation provider>",
  "rubric_version":  "<string — rubric used to compute the score, e.g. mycelium.rubric.v1>",
  "timestamp":       "<ISO 8601 UTC, e.g. 2026-06-21T00:00:00.000Z>",
  "trailing_days":   <integer — lookback window used for the snapshot>,
  "wallet":          "<EVM address, checksummed>"
}
```

Field order in the source object is irrelevant — JCS canonicalization normalizes it.

### Why timestamp is required

A preimage without `timestamp` is a floating hash: it cannot be placed in time,
cannot be confirmed as pre-dating the action it gates, and cannot be compared against
an on-chain anchor. `timestamp` converts a content hash into a commitment.

Implementations that omit `timestamp` (e.g. `sha256(wallet || provider_id ||
rubric_version || days)`) produce non-comparable hashes across invocations and cannot
satisfy the anchor requirement.

---

## Derivation

```
counterparty_ref = SHA-256(JCS(preimage))
```

JCS: RFC 8785 canonical JSON (`json.dumps` with `sort_keys=True,
separators=(',',':'), ensure_ascii=False`).

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

preimage = {
    "provider_id":    "mycelium.argentum.v1",
    "rubric_version": "mycelium.rubric.v1",
    "timestamp":      "2026-06-21T00:00:00.000Z",
    "trailing_days":  30,
    "wallet":         "0xDcc84E9798E8eB1b1b48A31B8f35e5AA7b83DBF4",
}

counterparty_ref = hashlib.sha256(jcs(preimage).encode()).hexdigest()
```

---

## Usage in TrailRecord

`counterparty_ref` is an optional field in `TrailRecord`. When present, it asserts
that the action was admitted after evaluating the counterparty's reputation snapshot.

```json
{
  "action_type":      "token_transfer",
  "agent_id":         "pioneer-agent-001",
  "counterparty_ref": "<sha256 hex>",
  "scope":            "mycelium.safeagent"
}
```

---

## counterparty_ref_anchor (optional extension field)

`counterparty_ref_anchor` is an optional companion field to `counterparty_ref`.
When present, it provides a verifiable on-chain pointer to the `markUsed(bytes32)`
transaction that anchored the preimage hash at snapshot time.

### Purpose

A `counterparty_ref` without an anchor is locally-trusted: a verifier cannot confirm
the snapshot was not post-dated. `counterparty_ref_anchor` resolves this by pointing
to the chain transaction that made the commitment immutable and timestamped.

### Schema

```json
"counterparty_ref_anchor": {
  "chain_id": 8453,
  "contract": "0x90Fa32a9568c6aE6BEa915DF8737acfd7EEA97De",
  "tx_hash":  "<markUsed tx hash>"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `chain_id` | integer | EVM chain ID where the anchor tx was submitted. Base = 8453, Arbitrum One = 42161. |
| `contract` | string | Checksummed address of the `GiskardPayments` contract on that chain. |
| `tx_hash` | string | Hash of the `markUsed(bytes32)` transaction that anchored `counterparty_ref`. |

### Verification

A verifier who holds `counterparty_ref` and `counterparty_ref_anchor` can:

1. Recompute `counterparty_ref` from the preimage fields (JCS + SHA-256).
2. Query `chain_id` for `tx_hash`.
3. Confirm the transaction called `markUsed(bytes32(counterparty_ref))` on `contract`.
4. Read the block timestamp — this is the commitment time, independent of the provider.

No operator cooperation required after step 1. The anchor is verifiable by any party
with access to a public RPC for the declared `chain_id`.

### GiskardPayments deployments

| Chain | chain_id | Contract |
|-------|----------|----------|
| Base mainnet | 8453 | `0x90Fa32a9568c6aE6BEa915DF8737acfd7EEA97De` |
| Arbitrum One | 42161 | `0xe40E376cD32b03E3084F9E0d646155D0Ba0A63ae` |

### Usage example

```json
{
  "action_type":      "token_transfer",
  "agent_id":         "pioneer-agent-001",
  "counterparty_ref": "f969b8828e9c23a07cce4b1e2f10e7771ceca6ef9d924b2461819f548227fee0",
  "counterparty_ref_anchor": {
    "chain_id": 8453,
    "contract": "0x90Fa32a9568c6aE6BEa915DF8737acfd7EEA97De",
    "tx_hash":  "0x3b24cfcef0a9ea0843c2d4d684cfb9b85e71e0ee153d5563acea439ebbd5330e"
  },
  "scope": "mycelium.safeagent"
}
```

---

## Relationship to other primitives

| Primitive | What it points to |
|-----------|------------------|
| `action_ref` | the action itself |
| `negotiation_ref` | prior agreement that admitted the action |
| `signing_trust_ref` | key model of the signer |
| `counterparty_ref` | reputation snapshot of the counterparty at admission time |

These fields are orthogonal and composable — a single trail entry may carry all four.
