# anchoring-precedence-ref-v1 — Specification

**Status:** stable  
**Version:** 1.0  
**Canonical fixture:** [`examples/conformance/anchoring-precedence-ref/vectors.json`](../../examples/conformance/anchoring-precedence-ref/vectors.json)

---

## What is anchoring-precedence-ref

`anchoring-precedence-ref` answers a question that existence proofs alone cannot: did an external, independently verifiable commitment to the proposed action precede the terminal outcome?

A system that only confirms an anchor exists can be manipulated by a participant who anchors after learning the outcome. `anchoring-precedence-ref` separates these two properties — existence and temporal ordering — into separately recomputable invariants, so each can be verified or falsified independently without trusting any party in the action pipeline.

**Principle of mechanism-neutrality:** the board does not bless a mechanism — it publishes which invariant each mechanism satisfies (Bitcoin OTS, on-chain Arbitrum, any external clock). A verifier checks invariants, not named mechanisms.

---

## Derivation

`anchoring_precedence_ref` is `SHA-256(JCS(envelope))` where:

- **JCS** is RFC 8785 canonical JSON: `json.dumps(obj, separators=(',',':'), sort_keys=True, ensure_ascii=False)`
- **SHA-256** lowercase hex
- `envelope` must contain at minimum: `trail_id`, `anchor_block_time`, `mechanism`, `outcome_ts_ms`, `version`

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

envelope = {
    "anchor_block_time": 1782677381,
    "mechanism":         "on-chain",
    "outcome_ts_ms":     1782677980000,
    "trail_id":          "b4377bcd-7342-4f7d-bdb3-daf41201bd47",
    "version":           "anchoring-precedence-ref-v1",
}
anchoring_precedence_ref = hashlib.sha256(jcs(envelope).encode()).hexdigest()
# 906a51a3be93e9ab5c4911080b2e1dc4ad07bbbc9711aa997f212ea95257008c
```

---

## Envelope fields

| Field | Type | Description |
|-------|------|-------------|
| `trail_id` | string | Stable identifier linking this record to the Mycelium trail. |
| `anchor_block_time` | integer \| null | Unix seconds of the externally confirmed anchor point. `null` means no external commitment exists — `anchoring_existence` fails. |
| `mechanism` | string | Mechanism that produced the anchor (e.g. `"on-chain"`, `"bitcoin-ots"`, `"trusted-timestamp"`). Informational — the verifier checks invariants, not the mechanism label. |
| `outcome_ts_ms` | integer | Millisecond epoch timestamp of the terminal outcome. |
| `version` | string | Always `"anchoring-precedence-ref-v1"`. |

---

## The five invariants

Each invariant is separately recomputable. A verifier MUST check all five independently — passing four while skipping one is not conformant.

### 1. canonical_envelope

The bytes produced by `JCS(envelope)` hash to the declared `anchoring_precedence_ref`. Any party with the envelope fields can recompute and compare.

**Fails when:** the declared hash does not match `SHA-256(JCS(envelope))` — envelope was mutated after commitment.

### 2. admission_invariant

An independent signer — outside the control of the actor and the executor — verifies the same canonical hash. The signer identity must not resolve to the actor or executor controller.

**Fails when:** the admitting signer is the actor, the executor, or an entity they control. Independence is the property; the identity of the signer is the evidence.

### 3. anchoring_existence

`anchor_block_time` is non-null and the commitment is confirmed by the declared mechanism's external record (block explorer, OTS file, timestamp authority). The anchor must be independently retrievable without querying the actor.

**Fails when:** `anchor_block_time` is `null`, or the external record cannot be retrieved, or the record does not match the commitment.

### 4. anchoring_precedence

The anchor point strictly precedes the terminal outcome:

```
anchor_block_time * 1000 < outcome_ts_ms
```

Equality is not conformant — strict ordering is required. The multiplication converts Unix seconds to milliseconds for comparison with `outcome_ts_ms`.

**Fails when:** `anchor_block_time * 1000 >= outcome_ts_ms`. This includes anchors created at the same millisecond as the outcome.

### 5. chain_invariant

The terminal record traces back to the proposed action that originated the trail. The `trail_id` in the envelope must resolve to a trail whose root action is the proposed action under governance.

**Fails when:** the `trail_id` resolves to a different proposed action, or cannot be resolved, or the resolution path is broken.

---

## Mechanism examples (non-normative)

| Mechanism | Satisfies existence | Satisfies precedence | Notes |
|-----------|--------------------|--------------------|-------|
| On-chain Arbitrum | ✓ if tx confirmed | ✓ if block precedes outcome | `anchor_block_time` = block timestamp from chain |
| Bitcoin OTS | ✓ if OTS file verifiable | ✓ if Bitcoin block precedes outcome | OTS upgrade path to Bitcoin block |
| Trusted timestamp authority (RFC 3161) | ✓ | ✓ if TSA timestamp precedes outcome | Requires TSA to be independent of actor |
| Internal ordering log | ✗ | ✗ | No external confirmation — fails `anchoring_existence` |

---

## Relationship to other refs

| Ref | What it answers |
|-----|----------------|
| `action_ref` | What did the agent do, exactly? |
| `delegation_chain_ref` | Was the authorization chain valid end-to-end? |
| `anchoring-precedence-ref` | Did an independent external commitment precede the outcome? |

---

## Cross-references

- `action_ref` derivation: [`docs/spec/action-ref.md`](./action-ref.md)
- `delegation_chain_ref`: [`docs/spec/delegation-chain-ref.md`](./delegation-chain-ref.md)
- TrailRecord schema: [`docs/MYCELIUM_TRAILS_REFERENCE.md`](../MYCELIUM_TRAILS_REFERENCE.md)
