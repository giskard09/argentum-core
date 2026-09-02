# offer-identity-ref-v1 — Specification

**Stable tag:** `offer-identity-ref-v1.0`
**Status:** stable
**Canonical fixture:** [`examples/conformance/offer-identity-ref/vectors.json`](../../examples/conformance/offer-identity-ref/vectors.json)
**Reference verifier:** [`examples/conformance/offer-identity-ref/verify.py`](../../examples/conformance/offer-identity-ref/verify.py)

---

## What is offer-identity-ref

`offer_identity_ref` is a SHA-256 hex pointer to the complete terms a Seller advertised at
S1 (the `402` challenge) — the x402 `x402Response` envelope, including every
`PaymentRequirements` entry in `accepts`. It gives the terms of an offer a single,
recomputable identity that every later stage of the transaction can reference or recompute,
instead of each artifact restating (or omitting) the parts of the offer it depends on.

**Why this exists:** x402's baseline receipt (Signed Offers & Receipts, PR #2811) commits
only the resource, the payer and a time — never which specific offer, at which price, was
paid. A Seller who publishes two offers for the same resource at different prices (T1, offer
substitution) can pair a cheap-offer receipt with the expensive offer after the fact, because
nothing in the chain names which offer was accepted. `offer_identity_ref` closes that gap the
same way `action_ref` closes it for an executed action: content-address the thing once, at
the moment it existed, and let every later artifact point back to that specific hash instead
of to a description of it.

**What it points to:** the x402 `x402Response` object exactly as advertised — not a
paraphrase, not a subset. If the Seller advertises three accepted payment mechanisms, all
three are in the preimage; a later artifact that references `offer_identity_ref` is
committing to the whole advertised offer, not to whichever single `PaymentRequirements` entry
the Buyer happened to pick.

**What it does not do:** `offer_identity_ref` does not decide which `PaymentRequirements`
entry in `accepts` a Buyer selected — that is `PaymentPayload.scheme` /
`PaymentPayload.network` at S3, carried alongside `offer_identity_ref` in whatever envelope a
later spec defines, the same pattern `negotiation_ref` uses next to `action_ref`
([`negotiation-ref.md`](./negotiation-ref.md)). It does not fetch, re-serve or archive the
offer — the hash is a pointer a verifier who already holds a copy of the advertised terms can
recompute; retaining the terms themselves is the implementer's concern.

---

## Derivation

`offer_identity_ref` is `SHA-256(JCS(x402_response))` where:

- **JCS** is RFC 8785 canonical JSON: `json.dumps(obj, separators=(',',':'), sort_keys=True, ensure_ascii=False)`
- **SHA-256** lowercase hex
- `x402_response` is the exact `x402Response` object served at S1, per the x402 protocol's
  own schema (`x402Specs.ts`, `x402ResponseSchema` / `PaymentRequirementsSchema`) — this
  profile imposes no schema of its own, it content-addresses the protocol's own wire shape

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

x402_response = {
    "x402Version": 1,
    "accepts": [
        {
            "scheme":            "exact",
            "network":           "base-sepolia",
            "maxAmountRequired": "10000",
            "resource":          "https://api.example.com/weather",
            "description":       "Current weather data for a given location",
            "mimeType":          "application/json",
            "payTo":             "0x209693Bc6afc0C5328bA36FaF03C514EF312287C",
            "maxTimeoutSeconds": 60,
            "asset":             "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        },
    ],
}
offer_identity_ref = hashlib.sha256(jcs(x402_response).encode()).hexdigest()
# 8f3e0b6a2d1c9f4e7a5b8c6d3f2e1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f
```

Field names, types and required-vs-optional status are taken verbatim from
`x402-foundation/x402`'s `PaymentRequirementsSchema` and `x402ResponseSchema`
(`typescript/packages/legacy/x402/src/types/verify/x402Specs.ts`) — `scheme`, `network`,
`maxAmountRequired`, `resource`, `description`, `mimeType`, `payTo`, `maxTimeoutSeconds`,
`asset` are required per `PaymentRequirements`; `outputSchema` and `extra` are optional per
`PaymentRequirements`; `x402Version` is required and `error`/`payer` are optional per
`x402Response`. This profile does not add, rename or drop a field — it hashes the wire object
as x402 itself defines it.

---

## Invariants

**1. commits to the complete advertised offer, not a selected mechanism**

The preimage is the full `x402Response`, `accepts` array included in full. Referencing
`offer_identity_ref` commits to every accepted payment mechanism the Seller advertised at that
moment — not to the one mechanism a given Buyer went on to select. Selecting one entry from
`accepts` is a fact about S3 (`PaymentPayload.scheme`/`.network`), not about S1.

**2. envelope-only — does not enter action_ref preimage**

Same treatment as `negotiation_ref`: `offer_identity_ref` is carried alongside `action_ref` in
whatever envelope a later spec defines for the executed action. It is never folded into
`action_ref`'s four-field preimage (`action_type`, `agent_id`, `scope`, `timestamp`, see
[`action-ref.md`](./action-ref.md)). Changing or removing `offer_identity_ref` does not change
`action_ref`.

**3. hash is over the wire object, not a description of it**

`offer_identity_ref = SHA-256(JCS(x402_response))` — the hash commits to the exact bytes of
the advertised offer. A verifier holding an independent copy of the same `402` response (e.g.
one it received directly as the Buyer, or one archived by a witness) recomputes the same hash
without trusting whoever cites the reference.

**4. optional, and its absence makes no claim**

`offer_identity_ref` is absent when a later artifact chooses not to carry it (e.g. a spec that
predates this profile, or an out-of-band offer never delivered via a `402` challenge).
Absence is not evidence that no offer existed — same treatment `negotiation_ref` invariant 4
gives absence versus non-existence.

**5. two distinct offers produce two distinct references — by construction**

Because the hash is over the complete `accepts` array, any difference in advertised terms
(a different `maxAmountRequired`, a different `payTo`, even a different `description`) that a
Seller might use to later substitute one offer for another (T1) produces a different
`offer_identity_ref`. A verifier comparing the reference cited by a later artifact against the
reference of the offer the Buyer actually holds catches a substituted offer directly — no
separate substitution check is needed once the reference is compared.

---

## Threat coverage (traceability)

Per the x402 Evidence Chain RFP (R1; UC2, UC3; T1, T2):

- **T1 (offer substitution):** a Seller who signs two offers for the same resource at
  different prices cannot pair a cheap-offer transaction record with the expensive offer,
  because the transaction record's `offer_identity_ref` recomputes only from the offer that
  was actually served — a mismatched substitution is a hash mismatch, not a matter of
  interpretation.
- **T2 (economic mismatch):** because `maxAmountRequired`, `asset` and `payTo` are inside the
  hashed `accepts` entries, a later artifact that carries `offer_identity_ref` cannot be
  paired with a claim about amount/asset/payee that the referenced offer did not actually
  state — the terms travel with the reference, not as a separately-assertable field a
  producer could misstate.

---

## Position in the envelope

```json
{
  "packet_version":     "1.0",
  "action_ref":          "<sha256 hex — derived from preimage>",
  "offer_identity_ref":  "<sha256 hex — derived from x402_response>",
  "hash_algo":           "sha256",
  "preimage_format":     "jcs-rfc8785-v1",
  "preimage": {
    "action_type": "x402.payment.execute",
    "agent_id":    "buyer-agent-001",
    "scope":       "x402:payment",
    "timestamp":   "2026-09-02T09:00:00.000Z"
  }
}
```

`offer_identity_ref` sits alongside `action_ref`, as a sibling field — not nested inside
`preimage`. Same position `negotiation_ref` takes; both MAY be present on the same envelope
(one points to what preceded the action as a prior agreement, the other to the specific
advertised terms the action paid under).

---

## Cross-references

- `action_ref` derivation: [`action-ref.md`](./action-ref.md)
- `negotiation_ref` — same envelope-only, hash-of-artifact pattern for a general prior
  agreement: [`negotiation-ref.md`](./negotiation-ref.md)
- x402 wire schema (source of truth for field names):
  `x402-foundation/x402`, `typescript/packages/legacy/x402/src/types/verify/x402Specs.ts`
- Conformance fixtures: [`examples/conformance/offer-identity-ref/`](../../examples/conformance/offer-identity-ref/)
