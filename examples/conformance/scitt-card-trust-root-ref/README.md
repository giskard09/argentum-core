# scitt-card-trust-root-ref — adversarial conformance vectors — v1

Adversarial conformance vectors built against the Cedulon/emiliaprotocol SCITT thread
(`scitt@ietf.org`, Nicholas/Doğru). Both vectors are **self-consistent** claims — nothing
internally malformed — that a lenient verifier can pass by checking only internal
consistency, without an independent check against ground truth. Both MUST fail closed
with a **named** `failure_mode`, and the two failure modes MUST NOT collapse into one
shared boolean.

## Vectors

| Vector | Class | Failure mode | What it tests |
|--------|-------|--------------|----------------|
| `self-issued-card-fresh-key` | `card_authenticity` | `TRUST_ANCHOR_UNRESOLVED` | Card signature verifies against its own embedded key (self-consistent), but that key was generated for the occasion and does not chain to any registry-known trust anchor. Distinguishes **self-consistency** from **authenticity**. |
| `legitimate-card-known-root` | `card_authenticity` | — (`PASS`) | Control — same shape, key chains to a known trust anchor. |
| `preimage-field-holds-rule-text` | `envelope_preimage` | `PREIMAGE_NOT_RECOMPUTABLE` | Envelope's `preimage` field holds the literal text of the canonicalization rule instead of the `{agent_id,action_type,scope,timestamp}` object it's supposed to reduce to `canonical_envelope_ref` under SHA-256(JCS(·)). |
| `preimage-field-recomputes-correctly` | `envelope_preimage` | — (`PASS`) | Control — real preimage object, recomputes byte-identical. |

## Why these two, together

Both vectors follow the same adversarial shape as three bugs already found and fixed in
this repo (referenced in the thread as reference shape):

- **Vernon boolean** — signature-valid treated as authenticity-proven, no separate check
  against a trust root.
- **Joel ABSENT collapse** — distinct "no linkage" states folded into a single value
  (see `infra_servicios.md` — `negotiation_linkage: unreached vs absent`, fixed PR#55).
- **Emek tailPinned** — pinned/anchored state not independently distinguished from the
  claimed state.

Both new vectors reproduce that same class of bug from a different angle: a verifier that
checks the wrong invariant (internal consistency) instead of the right one (independent
recomputability / independent trust anchor) will silently accept a forged claim.

Both map to the `action-ref.md#Domain` (line 88) `OUT_OF_PROFILE_DOMAIN` pattern: when an
input is outside what the profile actually proves, the verifier MUST stop and name the
boundary — never coerce it into a permissive default or a single collapsed boolean.

## Verification

```bash
python3 verify.py
```

A conformant verifier MUST:
1. For `card_authenticity`: check `self_consistency` (signature validity) AND
   `trust_anchor_ref` membership in an independent trust anchor registry, as two
   separate checks — never accept on signature validity alone.
2. For `envelope_preimage`: attempt real `SHA-256(JCS(preimage))` recomputation; if
   `preimage` is not the required 4-field object, reject `PREIMAGE_NOT_RECOMPUTABLE`
   before any digest comparison — do not attempt to coerce or partially hash it.
3. Never emit the same `failure_mode` for both classes — a caller must be able to tell
   *which* boundary failed from the result alone (the `MUST-surface` clause agreed with
   Nicholas/Doğru: rejection exposed in a named field, not swallowed).

Status: built for dept-estrategia (2026-08-27), not yet shown to Nicholas — pending
estrategia sign-off before it's run as second-verifier material.
