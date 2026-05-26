# cross-system-verification-v1 — Specification

**Stable tag:** `cross-system-verification-v1.0`  
**Status:** stable  
**Canonical fixture:** [`examples/conformance/cross-system-verification-v1.fixture.json`](../../examples/conformance/cross-system-verification-v1.fixture.json)

---

## What is cross-system-verification

`verification_ref` is a SHA-256 hex pointer to a verification artifact — a structured document that records the result of independent, trustless verification of a Mycelium Trail by an external stack. The verifier needs only three inputs: the four preimage fields (or the `action_ref` already computed), the public trail record, and the `tx_hash` on-chain. No API calls to Giskard. No trust in the trail emitter.

**What it enables:** any stack — a competing accountability layer, an enterprise compliance tool, a smart contract, a regulator's auditor — can verify a Mycelium Trail and produce a `verification_ref` that is itself a tamper-evident record of that verification. Two independent verifiers who run the same four steps on the same trail MUST produce the same `verification_ref` for the same `verifier_id`. If they don't, one of them has a non-conformant implementation.

**What it does not do:** `verification_ref` does not assert that the action was authorized (that is `delegation_ref`'s job) or that the authorization is still in force (that is `revocation_ref`'s job). It asserts only that the trail record is internally consistent and that the `action_ref` is anchored on-chain at the stated `tx_hash`.

---

## Verification steps

A conformant cross-system verifier executes these four steps in order:

### Step 1 — recompute_action_ref

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

preimage = {
    "action_type": trail_record["preimage"]["action_type"],
    "agent_id":    trail_record["preimage"]["agent_id"],
    "scope":       trail_record["preimage"]["scope"],
    "timestamp":   trail_record["preimage"]["timestamp"],
}
computed_action_ref = hashlib.sha256(jcs(preimage).encode()).hexdigest()
assert computed_action_ref == trail_record["action_ref"], "FAIL: action_ref mismatch"
```

The verifier does not trust the `action_ref` in the trail record. They recompute it from the four preimage fields and assert equality.

### Step 2 — match_trail_record

```python
assert trail_record["action_ref"] == action_ref_under_verification, \
    "FAIL: trail record does not correspond to the action_ref being verified"
```

The trail record provided is confirmed to contain the `action_ref` being verified.

### Step 3 — fetch_chain_anchor

```python
# Fetch tx from public RPC — no Giskard node required
tx = rpc.eth_getTransactionByHash(trail_record["tx_hash"])
anchor_payload = decode_op_return(tx)   # extracts OP_RETURN data bytes
```

The verifier fetches the on-chain transaction from any public RPC endpoint for the relevant chain. No Giskard infrastructure is required.

### Step 4 — match_anchor_payload

```python
assert anchor_payload == bytes.fromhex(trail_record["action_ref"]), \
    "FAIL: on-chain anchor does not match action_ref"
```

The OP_RETURN payload MUST be the raw bytes of the `action_ref` hex string (32 bytes). A verifier who finds any other value MUST reject the trail as non-conformant.

---

## Derivation

`verification_ref` is `SHA-256(JCS(verification_artifact))` where:

- **JCS** is RFC 8785 canonical JSON: `json.dumps(obj, separators=(',',':'), sort_keys=True, ensure_ascii=False)`
- **SHA-256** lowercase hex
- `verification_artifact` must contain: `action_ref`, `chain_anchor`, `verification_steps`, `verified_at`, `verifier_id`, `version`

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

verification_artifact = {
    "action_ref": "584bc79bb11ce3af5058b3da84d03f85e4aa464a175bd4f913aeb82a22cef60f",
    "chain_anchor": {
        "anchor_type":  "op_return",
        "block_number": 21847293,
        "chain_id":     8453,
        "payload_hex":  "584bc79bb11ce3af5058b3da84d03f85e4aa464a175bd4f913aeb82a22cef60f",
        "tx_hash":      "0x7fd0a8ededd1feb65ab37b3324218a0386dbf124174cf122bffc40717c057b84",
    },
    "verification_steps": [
        "recompute_action_ref",
        "match_trail_record",
        "fetch_chain_anchor",
        "match_anchor_payload",
    ],
    "verified_at": "2026-05-26T20:30:00.000Z",
    "verifier_id": "external-verifier-001",
    "version":     "cross-system-verification-v1",
}
verification_ref = hashlib.sha256(jcs(verification_artifact).encode()).hexdigest()
# ca602e8726617b0e0491bbe2b7593f44b99591be2952193c9a3e414e784cec7d
```

---

## Fields

### verification_artifact

| Field | Type | Description |
|-------|------|-------------|
| `action_ref` | SHA-256 hex | The `action_ref` being verified. Must match the trail record. |
| `chain_anchor` | object | The on-chain anchor found at `tx_hash`. See chain_anchor fields below. |
| `verification_steps` | array of strings | Ordered list of steps executed. All four canonical steps MUST be present for a conformant verification. |
| `verified_at` | RFC 3339 string | Timestamp when verification was performed by the external verifier. |
| `verifier_id` | string | Stable identifier for the external verifier. Differentiates `verification_ref` values across independent verifiers running the same verification. |
| `version` | string | Always `"cross-system-verification-v1"` for this spec version. |

### chain_anchor

| Field | Type | Description |
|-------|------|-------------|
| `anchor_type` | string | Anchor mechanism. Currently `"op_return"` for EVM OP_RETURN anchors. |
| `block_number` | integer | Block number where the anchoring transaction was included. |
| `chain_id` | integer | EIP-155 chain ID. `8453` = Base mainnet; `42161` = Arbitrum One; `11155111` = Ethereum Sepolia. |
| `payload_hex` | string | Hex-encoded bytes found in the anchor. For `op_return` type, this MUST equal the `action_ref` hex string. |
| `tx_hash` | string | The on-chain transaction hash containing the anchor. |

---

## Invariants

**1. verification_ref is deterministic for a given verifier**

Two runs of the same four steps by the same `verifier_id` on the same trail MUST produce identical `verification_ref` values. Non-determinism indicates a non-conformant implementation.

**2. verification_ref differs across verifiers**

Two different verifiers running the same steps on the same trail produce different `verification_ref` values because `verifier_id` differs. This is intentional: the artifact records who verified, not only what was verified.

**3. all four steps are required**

A `verification_artifact` that omits any of the four canonical `verification_steps` is non-conformant. A verifier MAY add steps beyond the four (e.g. `verify_delegation_ref`, `verify_revocation_ref`) but MUST include all four canonical steps.

**4. payload_hex must equal action_ref for op_return anchors**

For `anchor_type: "op_return"`, the `payload_hex` in the `chain_anchor` MUST equal `action_ref`. Any other value in `payload_hex` means the on-chain anchor does not correspond to this trail record.

**5. no Giskard endpoint required**

A conformant implementation MUST NOT require any call to a Giskard-operated endpoint to complete the four verification steps. The verifier uses only: the trail record (provided externally or fetched from a public endpoint), the four preimage fields, and a public RPC endpoint for the relevant chain.

**6. verification_ref does not enter action_ref preimage**

`verification_ref` is a post-hoc artifact. It never enters the trail record's action_ref preimage. Verification of a trail does not mutate the trail.

---

## Position in a verification workflow

`verification_ref` is not carried in the original trail record. It is produced by the external verifier after completing the four steps and may be:

- Stored in the verifier's own audit log
- Published alongside the original trail record as an independent attestation
- Submitted to a third-party compliance system
- Used as the `delegation_ref` in a subsequent trail record (`action_type: trail.verified`)

```json
{
  "trail_record": { "...original trail record..." },
  "independent_verification": {
    "verification_ref": "ca602e8726617b0e0491bbe2b7593f44b99591be2952193c9a3e414e784cec7d",
    "verifier_id":      "external-verifier-001",
    "verified_at":      "2026-05-26T20:30:00.000Z"
  }
}
```

---

## The Visa model — emit once, verify anywhere

Mycelium emits trail records. Any external stack verifies them. The verifier does not need a relationship with Mycelium — just access to public blockchain data and the trail record. This is structurally equivalent to a Visa network: the card issuer (Mycelium) and the merchant verifier (any external stack) operate independently. The shared substrate is the on-chain anchor, which neither party controls.

---

## Cross-references

- `action_ref` derivation: [`docs/spec/action-ref.md`](./action-ref.md)
- `delegation_ref` (authorization verification, separate concern): [`docs/spec/delegation-ref.md`](./delegation-ref.md)
- `composition_ref` (lifecycle composition): [`docs/spec/composition-ref.md`](./composition-ref.md)
- `delegation_chain_ref` (multi-hop chain verification): [`docs/spec/delegation-chain-ref.md`](./delegation-chain-ref.md)
- TrailRecord schema: [`docs/MYCELIUM_TRAILS_REFERENCE.md`](../MYCELIUM_TRAILS_REFERENCE.md)
