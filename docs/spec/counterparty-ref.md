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
on-chain at the time of snapshot via a permissionless anchor (see
[counterparty_ref_anchor](#counterparty_ref_anchor-optional-extension-field) below).
A `counterparty_ref` without an anchor degrades to a locally-trusted hash —
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

> **Status: under specification.** The anchoring mechanism below is being finalized.
> The companion contract is a dedicated, permissionless anchor registry — not
> `GiskardPayments` and not the karma/identity registry. Concrete contract addresses
> and a worked example will be published here once the registry is deployed and a real
> anchoring transaction exists on-chain. Until then, treat `counterparty_ref` as a
> locally-trusted hash.

`counterparty_ref_anchor` is an optional companion field to `counterparty_ref`.
When present, it provides a verifiable on-chain pointer to the transaction that
anchored the preimage hash at snapshot time.

### Purpose

A `counterparty_ref` without an anchor is locally-trusted: a verifier cannot confirm
the snapshot was not post-dated. `counterparty_ref_anchor` resolves this by pointing
to the chain transaction that made the commitment immutable and timestamped.

### Mechanism (permissionless anchor)

The anchor is recorded by calling `anchor(bytes32 ref)` on a dedicated anchor registry
contract. The call is **permissionless** — any party can anchor any hash — and emits an
`Anchored(bytes32 indexed ref, address indexed anchoredBy, uint256 timestamp)` event.
Permissionlessness is deliberate: the anchor's verifiability must not depend on the
operator that produced the snapshot. This is what separates an operator-independent
anchor from an operator-gated one.

### Schema

```json
"counterparty_ref_anchor": {
  "chain_id": "<integer — EVM chain ID where the anchor tx was submitted>",
  "contract": "<checksummed address of the anchor registry on that chain>",
  "tx_hash":  "<hash of the anchor(bytes32) transaction>"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `chain_id` | integer | EVM chain ID where the anchor tx was submitted. |
| `contract` | string | Checksummed address of the anchor registry on that chain. |
| `tx_hash` | string | Hash of the `anchor(bytes32)` transaction that anchored `counterparty_ref`. |

### Verification

A verifier who holds `counterparty_ref` and `counterparty_ref_anchor` can:

1. Recompute `counterparty_ref` from the preimage fields (JCS + SHA-256).
2. Query `chain_id` for `tx_hash`.
3. Confirm the transaction called `anchor(bytes32(counterparty_ref))` on `contract`,
   or read the `Anchored` event with `ref == counterparty_ref`.
4. Read the block timestamp — this is the commitment time, independent of the provider.

No operator cooperation required after step 1. The anchor is verifiable by any party
with access to a public RPC for the declared `chain_id`.

---

## Relationship to other primitives

| Primitive | What it points to |
|-----------|------------------|
| `action_ref` | the action itself |
| `negotiation_ref` | prior agreement that admitted the action |
| `signing_trust_ref` | key model of the signer |
| `counterparty_ref` | reputation snapshot of the counterparty at admission time |

These fields are orthogonal and composable — a single trail entry may carry all four.
