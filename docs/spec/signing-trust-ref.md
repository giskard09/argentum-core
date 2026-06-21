# signing-trust-ref-v1

`signing-trust-ref` is a content-addressed pointer to a signing-trust assertion:
who signed a given `action_ref`, under what key model, and at what time.

`action_ref` guarantees that a record is immutable once committed. It does not
guarantee that the preimage is honest — an operator can compute a valid
`action_ref` over a fabricated record. `signing-trust-ref` makes the signer's
identity and key model part of the verifiable record, enabling a verifier to
assess the trust level of the signer independently of the operator's assertion.

See `verifier-independence.md` for the trust-model context that motivates this
primitive.

## Preimage schema

```json
{
  "signer_type":  "operator_key" | "agent_keypair" | "tee_attested" | "multi_party",
  "signer_id":    "<public key address or TEE report hash or threshold descriptor>",
  "action_ref":   "<action_ref this signing-trust assertion covers>",
  "timestamp_ms": <uint64, Unix epoch milliseconds>
}
```

## Derivation

```
signing_trust_ref = SHA-256(JCS(preimage))
```

JCS: RFC 8785 canonical JSON (keys sorted, no extra whitespace).

```python
import hashlib, json

def jcs(obj):
    return json.dumps(dict(sorted(obj.items())), separators=(',',':'), ensure_ascii=False)

signing_trust_ref = hashlib.sha256(jcs(preimage).encode()).hexdigest()
```

## `signer_type` values

| Value | Trust model |
|-------|-------------|
| `operator_key` | Operator-controlled key. Trust is bounded by operator key management. |
| `agent_keypair` | Key controlled by the agent instance (e.g. wallet address). Operator does not hold the private key. |
| `tee_attested` | Signing occurred inside a TEE; `signer_id` is the TEE report hash or measurement. |
| `multi_party` | Threshold M-of-N signing; `signer_id` encodes threshold and participant keys. |

## `signer_id` encoding

- `operator_key`: EVM address (`0x...`) or hex public key
- `agent_keypair`: EVM address (`0x...`) or Ed25519 public key (base64)
- `tee_attested`: TEE report hash or PCR composite
- `multi_party`: `<scheme>:<M>-of-<N>:<key1>;<key2>;...` — e.g. `tkc:2-of-3:0xaaa;0xbbb;0xccc`

## Relationship to `action_ref`

```
action_ref          → immutability of the record (what happened)
signing_trust_ref   → trust level of the signer (who attested it and how)
```

Both can coexist as sibling fields in a trail record or audit log entry:

```json
{
  "action_ref":         "25b9c32f...",
  "signing_trust_ref":  "1d1becb3..."
}
```

## Conformance fixtures

[`examples/conformance/signing-trust-ref/`](../../examples/conformance/signing-trust-ref/)

- `str-001` — `operator_key` (base case)
- `str-002` — `agent_keypair` with EVM wallet address as `signer_id`
- `str-003` — `multi_party` with 2-of-3 threshold (TKCollective pattern)

## References

- `action-ref.md` — canonical field derivation
- `verifier-independence.md` — trust-model context and motivation
- `guarantee-model.md` — composability with pre-execution enforcement layers
