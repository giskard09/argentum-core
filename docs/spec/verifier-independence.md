# Verifier Independence: Two Models of Execution Record Trust

This document distinguishes two verification models that address complementary
questions about agent execution records. Both are useful; they answer different
questions and compose without conflict.

## The two models

### Model A — Server-asserted (operator-signed)

The enforcement point signs a decision record (before execution) and an outcome
record (after). A verifier holds two signed artifacts and can confirm:

- The signing key belongs to the declared enforcement point
- The decision and outcome are paired to the same call instance
- The records have not been tampered with since signing

**What a verifier must trust:** the operator's signing key management. The
signing key is generated, stored, and rotated by the operator. A verifier who
does not trust the operator must accept the operator's public key on the
operator's word. Key revocation and rotation are operator-controlled events
invisible to the verifier.

**Regulatory surface:** an external auditor can verify the cryptographic
integrity of the record. They cannot verify, without trusting the operator,
that the signing key corresponds to the system that actually executed the
action, that the key was not compromised between signing and audit time, or
that the record was not produced retrospectively by a key the operator still
controls.

### Model B — Operator-independent (content-addressed anchor)

The `action_ref` is derived from the intent tuple alone:

```
action_ref = SHA-256(JCS({
  "agent_id":    "<string>",
  "action_type": "<string>",
  "scope":       "<string>",
  "timestamp_ms": <uint64>
}))
```

The same four fields that describe the action produce the same hash on any
machine, by any party, without access to operator infrastructure. The hash
is anchored on a public chain via `markUsed(action_ref)`. A verifier can:

1. Recompute `action_ref` from the intent tuple
2. Query the chain for that hash directly
3. Confirm the anchor without contacting the operator

**What a verifier must trust:** the public chain's finality — the same trust
model as verifying a payment transaction. No operator key, no operator
endpoint, no operator cooperation required.

**Regulatory surface:** an external auditor, a counterparty, or a smart
contract can verify independently. The anchor predates the audit — it cannot
be produced retrospectively without a blockchain reorganization.

## What each model proves and does not prove

| Property | Model A (server-signed) | Model B (content-addressed) |
|---|---|---|
| Record integrity since signing | ✅ | ✅ |
| Verifiable without operator cooperation | ❌ | ✅ |
| Verifiable without trusting operator key management | ❌ | ✅ |
| Binding to a specific call instance | ✅ (via backLink) | ✅ (via `action_ref` preimage) |
| Independent recomputation from intent | ❌ key-dependent | ✅ four fields only |
| Retrospective forgery resistance | Operator-bounded | Chain-bounded |
| Audit cost | Signature verification | Chain query |

## Composition

The two models are not alternatives — they address different questions and
compose naturally.

A deployment that uses server-signed records for decision/outcome lifecycle
tracking (Model A) and `action_ref` anchoring for independent verifiability
(Model B) satisfies both:

- An internal compliance system can verify the signed lifecycle
- An external regulator or auditor can verify independently

The `action_ref` field can be included in a server-signed record's payload.
When it is, the signed record binds the operator's decision to a hash that
any third party can verify on-chain without the operator's involvement.

```json
{
  "record_type": "execution_outcome",
  "action_ref": "a3f4e2...c1d9",
  "outcome": "executed",
  "outcome_digest": "b7c3a1...f4e2",
  "issuer_signature": "...",
  "anchor": {
    "chain": "arbitrum-one",
    "tx_hash": "0xf39d6d...",
    "block": 469035040
  }
}
```

The `issuer_signature` covers the operator's decision. The `anchor.tx_hash`
is independently verifiable. A verifier who trusts neither party can check
both: the signature proves internal consistency; the anchor proves the
`action_ref` existed at block 469035040.

## Conformance fixtures

Fixtures demonstrating the distinction are in
[`examples/conformance/near-miss-v1/`](../../examples/conformance/near-miss-v1/)
under failure mode `OPERATOR_SIGNED_ONLY` — a record with a valid operator
signature but no on-chain anchor. A conformant Mycelium verifier rejects
this as incomplete for the independent-verifiability requirement.

The full fixture set (53 vectors, 5 languages) is at
[`examples/conformance/`](../../examples/conformance/).

## References

- `action-ref.md` — canonical field set and derivation
- `signing-trust-ref.md` — layer above `action_ref`: makes signer identity and key model part of the verifiable record, enabling verifier assessment of signing trust independently of the operator assertion
- `cross-system-verification.md` — verifier that requires no operator endpoint
- `guarantee-model.md` — composability with pre-execution enforcement layers
- Regulatory mapping: `docs/compliance/regulatory-compliance.md`
  (Art. 12 EU AI Act, FCA SYSC 9.1, DORA)

## Preimage honesty boundary

The content-addressed guarantee covers two properties: recomputability and
anchor immutability.

**Recomputability:** any party who holds the four preimage fields can derive
the same `action_ref` independently, without operator infrastructure.

**Anchor immutability:** once `markUsed(action_ref)` is on-chain, the hash
cannot be retroactively removed or altered. A verifier can confirm the hash
existed at a specific block without contacting the operator.

**What neither property covers:** the spec defines the hash surface and the
anchor layer. Preimage honesty — whether the fields accurately reflect what
the agent executed — is a property of the signing trust model, which is
intentionally out of scope. An operator who controls the fields — `agent_id`,
`action_type`, `scope`, `timestamp_ms` — can produce any `action_ref` they
choose and anchor it. The anchor makes that record immutable; it does not make
it honest.

This is a deliberate design boundary. Three approaches address the preimage
honesty question at the signing layer, in increasing order of
verifier-independence:

| Approach | What it adds | What a verifier trusts |
|---|---|---|
| Operator-held key (Model A above) | Signature over the record | Operator's key custody |
| Agent-held keypair | Agent signs with a key it controls; operator never touches the private key | Agent's key custody |
| TEE attestation | Hardware-bound key signs the preimage inside a trusted execution environment | TEE manufacturer + attestation report |

The spec is compatible with all three. Conformance fixtures do not prescribe
a signing trust model — `issuer_signature` is an opaque field. Implementations
that require stronger preimage honesty guarantees should document their signing
trust model alongside their conformance vectors.

**Note on agent-held keypairs:** using a wallet address as the `agent_id`
field in the preimage is valid and enables on-chain verification of the
signer's identity. The wallet address should be a named field in the JCS
object, not concatenated into the hash directly — concatenation breaks the
exactly-once and idempotency properties if the agent rotates its wallet
between calls.
