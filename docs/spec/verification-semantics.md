# verification-semantics — Specification

**Status:** stable  
**Applies to:** all conformance vectors in `examples/conformance/`

---

## Purpose

This document defines the normative values of the `verification_mode` field used
in conformance vectors. The field classifies how a verifier can confirm the
property that a given vector demonstrates — without runtime state, oracle access,
or operator cooperation.

See `verifier-independence.md` for the conceptual model (Model A / Model B) that
motivates this distinction.

---

## Values

### `asserted`

The property is **structurally decidable** from the vector fields alone.

A verifier:

1. Reads the `preimage` fields from the vector.
2. Applies JCS canonicalization (RFC 8785): `json.dumps(obj, separators=(',',':'), sort_keys=True, ensure_ascii=False)`.
3. Computes `SHA-256` over the canonical bytes.
4. Compares the digest byte-exact against the declared reference field (`action_ref`, `counterparty_ref`, etc.).

No runtime state is required. No oracle is required. No operator cooperation is
required. Any two conformant implementations MUST produce the same result given the
same preimage fields.

This corresponds to **Model B** in `verifier-independence.md`: content-addressed,
operator-independent.

### `enforced`

The property depends on **runtime state** that is not present in the vector fields.

Examples of runtime state: a policy engine decision, an oracle response, an
on-chain query at execution time, a time-window check against a live clock, or
any external system whose output is not embedded in the preimage.

A verifier cannot fully reconstruct the enforcement outcome from the vector alone.
The vector demonstrates the schema and hash derivation, but verification of the
full property requires access to the runtime environment.

This corresponds to **Model A** in `verifier-independence.md`: server-asserted,
operator-dependent.

---

## Field definition

`verification_mode` is an optional string field in conformance vectors.

```json
{
  "verification_mode": "asserted" | "enforced"
}
```

**Default when omitted:** `enforced`.

The default is conservative: a vector that does not declare `asserted` MUST NOT be
assumed to be structurally decidable. Implementations that tally `asserted` vectors
for coverage reporting MUST NOT count vectors with absent `verification_mode`.

---

## Normative requirements

- A vector that declares `verification_mode: "asserted"` MUST be byte-reproducible
  by any conformant implementation from the stated preimage fields alone.
- A vector that declares `verification_mode: "enforced"` SHOULD document in its
  `notes` field which runtime dependency prevents structural decidability.
- Test runners SHOULD emit a tally of `asserted` vs `enforced` vectors at
  completion to surface the ratio of operator-independent verifiability.

---

## Relationship to verifier-independence.md

| `verification_mode` | `verifier-independence.md` model | Verifier trust requirement |
|---------------------|----------------------------------|---------------------------|
| `asserted` | Model B (content-addressed) | Public chain finality only |
| `enforced` | Model A (server-asserted) | Operator key management |

---

## References

- `verifier-independence.md` — Model A / Model B conceptual foundation
- `action-ref.md` — canonical preimage and derivation for `action_ref`
- `examples/conformance/action-ref-v1-baseline.fixture.json` — first vectors
  carrying `verification_mode: "asserted"`
