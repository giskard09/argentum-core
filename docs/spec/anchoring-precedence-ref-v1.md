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

**Co-signer blocks MUST include the published pubkey alongside `issuer` / `kid` / `jws_signature`.** Without the pubkey in the fixture, a referee can only verify the primary admission leg without out-of-band lookup. Both JWS legs must be recomputable from the fixture alone.

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

**Normative caveat — `anchor_block_time` is a miner-claimed value, not an independently proven one.** For on-chain mechanisms, `anchor_block_time` is the block timestamp as declared by the miner within Bitcoin/Ethereum consensus bounds (for Bitcoin: Median Time Past of the 11 preceding blocks as the lower bound, ~2 hours of network-adjusted time as the upper bound — an asymmetric window). This check computes on that value directly (`anchor_block_time * 1000 < outcome_ts_ms`), not merely displays it, so the caveat carries more weight here than in a display-only context. A miner may declare a timestamp earlier than the block's true chronological position while remaining fully consensus-valid — real, non-monotonic Bitcoin blocks exist (e.g. block 156114, timestamped before its own parent by roughly 2 hours; block 790402, timestamped 2 minutes before its parent). **This means `anchoring_precedence` can false-pass**: a backdated-but-consensus-valid `anchor_block_time` will satisfy the strict-ordering check even when the anchor did not, in absolute wall-clock terms, actually precede the outcome. There is no fix available within this profile — closing this gap requires an independent time source outside the miner's declared value, which the profile does not have access to. This is a declared limitation, not a bug pending a fix, matching the same treatment `OUT_OF_PROFILE_DOMAIN` receives in [`action-ref.md`](./action-ref.md) for its own domain boundary. See [`examples/conformance/anchoring-precedence-ref/vectors.json`](../../examples/conformance/anchoring-precedence-ref/vectors.json) vector `known-limitation-miner-claimed-backdated` for a reproduction of this shape.

Credit: Jonna Fassbender (`draft-fassbender-scitt-time-anchor-05`), scitt@ietf.org, 2026-08-26, confirming this profile's invariant needs the same caveat her draft introduces for Bitcoin OTS.

**Non-normative reframing (for a future revision, not this one):** what this profile actually proves is not a *time* — it is that the artifact existed before block H was appended to the canonical chain. If the outcome can itself be located at a block height, precedence becomes a comparison of block heights, and the miner's declared clock drops out of the calculation entirely. Not adopted in this version; noted here for a future `anchoring-precedence-ref-v2`.

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
