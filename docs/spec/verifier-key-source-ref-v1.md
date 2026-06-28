# verifier-key-source-ref-v1 — Specification

**Status:** stable  
**Version:** 1.0  
**Canonical fixture:** [`examples/conformance/verifier-key-source-ref/vectors.json`](../../examples/conformance/verifier-key-source-ref/vectors.json)

---

## What is verifier-key-source-ref

A `signer_record` is the per-signer artifact that proves one leg of a multi-signer admission claim is independently recomputable from the fixture alone. Without this record, a verifier reading a two-signer admission row cannot determine whether both legs are actually recomputable — or whether one leg requires a live key fetch, a cache hit, or an out-of-band lookup.

**Central principle:** a claim of two independent signers is completely recomputable from the fixture only if both public keys, or pinned resolution records for both keys, are present in the fixture. A board that reports an admission pass without declaring key sources for all signers is making a claim that cannot be independently verified.

---

## signer_record schema

Each signer in a multi-signer admission block MUST include a `signer_record` with the following eight fields:

| Field | Type | Description |
|-------|------|-------------|
| `signer_id` | string | Stable identifier for the signer. Must be bound to the declared verifier role — a key that verifies cryptographically but whose `signer_id` is not linked to the declared role fails `signer_identity_unbound`. |
| `key_id` | string | Key identifier within the signer's key set (e.g. JWK `kid`). |
| `key_source` | enum | How the public key was obtained. One of: `embedded` / `published_jwks` / `pinned_registry` / `cached_prior`. See [key_source values](#key_source-values). |
| `public_key_hash` | SHA-256 hex | Hash of the raw public key bytes. Present when `key_source = embedded` or `pinned_registry`. Absent is valid for `published_jwks` or `cached_prior` only if `key_resolution_evidence_hash` is present. |
| `signature_input_hash` | SHA-256 hex | Hash of the exact bytes the signer signed. MUST equal the `canonical_envelope_hash` of the certified fixture. Divergence indicates `signature_input_drift`. |
| `verification_result` | enum | `pass` / `fail` / `unverifiable` / `out_of_scope`. A result of `unverifiable` MUST be accompanied by a `verification_note` explaining why. |
| `key_resolution_time` | ISO 8601 UTC | When the key was resolved, relative to the fixture certification time. A resolution time after the fixture certification time indicates a potentially stale or post-hoc key fetch. |
| `key_resolution_evidence_hash` | SHA-256 hex | Hash of the resolution record (JWKS response, registry entry snapshot, cached artifact). Enables a verifier to detect if the key source changed after certification. |

---

## key_source values

| Value | Meaning | Recomputable from fixture? |
|-------|---------|--------------------------|
| `embedded` | Public key bytes included directly in the fixture. | Yes — no external fetch required. |
| `published_jwks` | Key resolved from a live JWKS endpoint at certification time. `key_resolution_evidence_hash` pins the response. | Partially — verifier can check the hash but must trust the fetched response was authentic at that time. |
| `pinned_registry` | Key resolved from a registry entry whose content is pinned by hash. | Yes — verifier recomputes hash of pinned content. |
| `cached_prior` | Key reused from a prior resolution, not re-fetched. | Only if the cache hit is pinned by `key_resolution_evidence_hash`. |

---

## Invariants

**1. key_source_declared**  
Every `signer_record` MUST declare a `key_source`. A record without `key_source` makes the recomputability of that leg indeterminate.

**2. signature_input_bound**  
`signature_input_hash` MUST equal `SHA-256(JCS(canonical_envelope))`. Any deviation means the signer signed different bytes than the certified envelope — the admission does not bind to the certified artifact.

**3. signer_identity_bound**  
`signer_id` must be verifiably linked to the declared verifier role. A key that verifies cryptographically but belongs to an unlinked identity does not satisfy admission independence.

**4. key_resolution_not_stale**  
`key_resolution_time` MUST precede or equal the fixture certification time. A key resolved after the fixture was certified cannot be proven to have been used during the original admission.

**5. multisig_completeness**  
A multi-signer admission claim requires every signer leg to be independently recomputable. Reporting N signers when fewer than N legs are fully recomputable from the fixture is an overclaim.

---

## Relationship to other specs

| Spec | What it answers |
|------|----------------|
| `anchoring-precedence-ref-v1` | Did an external commitment precede the outcome? |
| `verifier-key-source-ref-v1` | Is each signer leg independently recomputable from the fixture? |
| `delegation-chain-ref-v1` | Is the authorization chain structurally valid end-to-end? |

---

## Conformance Column Split

A conformance board MUST report two distinct columns for multi-signer admission. Collapsing them into a single cell discards the distinction that makes the claim verifiable.

**`admission_independent`** — `admission_invariant` passes with at least one signer whose leg is fully recomputable from the fixture alone. A co-signer block may be present but is not required for this column to pass. A row passes `admission_independent` if any single `signer_record` has `verification_result: pass`, `key_source` declared, `signature_input_hash` equal to the canonical envelope hash, and either `public_key_hash` or `key_resolution_evidence_hash` present.

**`admission_multisig_recomputable`** — `admission_invariant` passes with every declared signer recomputable from the fixture alone. Requires that each co-signer block includes either an embedded `public_key_hash` or a `pinned_registry` entry. `published_jwks` without a pinned `key_resolution_evidence_hash` does not satisfy this column. `cached_prior` without a pinned hash does not satisfy this column.

A row may pass both columns simultaneously if the fixture is sufficiently complete — all signer blocks embedded or pinned, all `signature_input_hash` fields bound to the canonical envelope, all `verification_result` fields `pass`. The board MUST show both columns explicitly and MUST NOT collapse the distinction into a single green cell.

| Scenario | `admission_independent` | `admission_multisig_recomputable` |
|----------|------------------------|----------------------------------|
| One signer, embedded key, correct sig input | ✓ | ✓ (single signer = all signers recomputable) |
| Two signers, both embedded, both correct | ✓ | ✓ |
| Two signers, primary embedded, co-signer JWKS (no pinned hash) | ✓ | ✗ |
| Two signers, primary embedded, co-signer key absent | ✓ | ✗ |
| Two signers, both JWKS without pinned hash | ✗ | ✗ |

---

## Cross-references

- `anchoring-precedence-ref-v1`: [`docs/spec/anchoring-precedence-ref-v1.md`](./anchoring-precedence-ref-v1.md)
- TrailRecord schema: [`docs/MYCELIUM_TRAILS_REFERENCE.md`](../MYCELIUM_TRAILS_REFERENCE.md)
