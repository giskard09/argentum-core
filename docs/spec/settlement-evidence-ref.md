# settlement-evidence-ref-v1 — Specification

**Stable tag:** `settlement-evidence-ref-v1.0`
**Status:** stable
**Canonical fixture:** [`examples/conformance/settlement-evidence-ref/vectors.json`](../../examples/conformance/settlement-evidence-ref/vectors.json)
**Reference verifier:** [`examples/conformance/settlement-evidence-ref/verify.py`](../../examples/conformance/settlement-evidence-ref/verify.py)

---

## What is settlement-evidence-ref

`settlement_evidence_ref` is a SHA-256 hex pointer to a settlement artifact that names both
sides of a payment's value movement — payer debit and payee credit — as independently
recomputed from the payment rail's own ledger, not as declared by the facilitator that
brokered the payment.

**Why this exists:** x402's `SettleResponse` (S5, per the x402 wire schema —
`typescript/packages/legacy/x402/src/types/verify/x402Specs.ts`,
`SettleResponseSchema`) carries `{success, errorReason?, payer?, transaction, network}` — a
boolean success flag, an optional payer, a transaction reference, and a network. It names
**no amount and no payee**, and `success: true` is the facilitator's own assertion about its
own settlement, not a fact a third party has confirmed against the ledger. An Evaluator
reviewing the transaction without the Buyer present (UC3) holds exactly this response and
cannot confirm from it alone that anything settled for the amount or party the offer named.

**What it points to:** a settlement artifact that separately names `payer_debit` and
`payee_credit` — each an `{address, amount, asset}` triple — recomputed from the rail's own
transaction receipt (e.g. an ERC-20 `Transfer` event's `from`/`to`/`value`, or the
rail-equivalent), not copied from the facilitator's `SettleResponse`. The artifact also
carries the `network` and `transaction` reference that both sides were read from, and MAY
carry `offer_identity_ref` ([`offer-identity-ref.md`](./offer-identity-ref.md)) to bind the
settled amount back to what the offer actually required.

**What it does not do:** `settlement_evidence_ref` does not perform the ledger lookup itself
— like `chain_invariant` in [`anchoring-precedence-ref-v1.md`](./anchoring-precedence-ref-v1.md#5-chain_invariant)
and `resolved_by` in [`peer-reconciliation-ref-v1.md`](./peer-reconciliation-ref-v1.md#5-supersedes_chain_integrity),
this is declared-in-vector, external resolution not performed live by this reference
verifier. What it does enforce is that the declaration says *how* it was obtained
(`ledger_recomputed: true | false`) and treats the two cases as distinguishable, never
silently defaulting the unverified case to "settled."

---

## Derivation

`settlement_evidence_ref` is `SHA-256(JCS(settlement_artifact))` where:

- **JCS** is RFC 8785 canonical JSON: `json.dumps(obj, separators=(',',':'), sort_keys=True, ensure_ascii=False)`
- **SHA-256** lowercase hex
- `settlement_artifact` must contain at minimum: `network`, `transaction`, `payer_debit`,
  `payee_credit`, `version`. `offer_identity_ref` is optional.

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

settlement_artifact = {
    "network":            "base-sepolia",
    "transaction":        "0x7c8692c003b80a48bb8123ae6965e26464d271ee2041404cc025e0f15e5fcaba",
    "offer_identity_ref": "0df1f6792f5aa482568ff3b6cb39568d5fe0b5f29b7dc7148b5dba400451d4c4",
    "payer_debit":  {"address": "0xA11ce00000000000000000000000000000000001", "amount": "10000", "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e"},
    "payee_credit": {"address": "0x209693Bc6afc0C5328bA36FaF03C514EF312287C", "amount": "10000", "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e"},
    "version": "settlement-evidence-ref-v1",
}
settlement_evidence_ref = hashlib.sha256(jcs(settlement_artifact).encode()).hexdigest()
```

`payer_debit.address`/`payee_credit.address`, `.amount` and `.asset` are the fields a party
reads directly off the rail's transaction receipt for a value-transfer event (an ERC-20
`Transfer(from, to, value)` log, or the rail-equivalent) — not fields a facilitator supplies
in its response object.

---

## Invariants

**1. both sides, not one**

A conformant `settlement_artifact` names both `payer_debit` and `payee_credit`. A settlement
artifact that names only one side (e.g. only that the payer's balance decreased, without
confirming the payee's balance increased by the matching amount on the matching asset) does
not satisfy this profile — see `checks.debit_credit_paired` in the reference vectors.

**2. ledger-recomputed, not facilitator-declared**

Every settlement artifact carries `checks.ledger_recomputed: true | false` in the vector,
naming whether `payer_debit`/`payee_credit` were read from an independent verifier's own
lookup against the rail (`true`) or merely copied from the facilitator's `SettleResponse`
(`false` — which, per x402's own schema, could not even supply these fields, since
`SettleResponse` carries no amount or payee). **A vector with `ledger_recomputed: false` MUST
be rejected by a conformant verifier** — `success: true` from a facilitator is not, by
itself, ledger proof. This is R5's central prohibition, enforced structurally rather than
left as a caveat in prose.

**3. non-payer recomputability**

Because the artifact is built from the rail's own public transaction data (a network + a
transaction reference readable by anyone with RPC access) and, optionally, a publicly
recomputable `offer_identity_ref`, any party — payer, payee, or an Evaluator who was neither
— can reproduce `settlement_evidence_ref` independently. The construction does not depend on
records held only by the payer.

**4. envelope-only — does not enter action_ref preimage**

Same treatment as `negotiation_ref` and `offer_identity_ref`: `settlement_evidence_ref` sits
alongside `action_ref` in whatever envelope a later spec defines. It is never folded into
`action_ref`'s four-field preimage (`action_type`, `agent_id`, `scope`, `timestamp`; see
[`action-ref.md`](./action-ref.md)).

**5. amount/asset mismatch against the offer is a distinguishable failure**

When `offer_identity_ref` is present, a conformant verifier compares
`payer_debit.amount`/`.asset` against the `maxAmountRequired`/`asset` of the referenced offer.
A settlement that recomputes cleanly from the ledger but for a different amount or asset than
what was offered is `checks.debit_credit_paired: true` (both sides are internally consistent
with each other) but `checks.matches_offer: false` — a distinguishable state, not collapsed
into either a hash-mismatch or a pass.

---

## Position in the envelope

```json
{
  "packet_version":         "1.0",
  "action_ref":              "<sha256 hex — derived from preimage>",
  "offer_identity_ref":      "<sha256 hex — derived from x402_response, optional>",
  "settlement_evidence_ref": "<sha256 hex — derived from settlement_artifact>",
  "hash_algo":               "sha256",
  "preimage_format":         "jcs-rfc8785-v1",
  "preimage": {
    "action_type": "x402.payment.execute",
    "agent_id":    "buyer-agent-001",
    "scope":       "x402:payment",
    "timestamp":   "2026-09-02T09:00:00.000Z"
  }
}
```

`settlement_evidence_ref` is a sibling field to `action_ref`, `negotiation_ref` and
`offer_identity_ref` — not nested inside `preimage`. All four MAY be present on the same
envelope: `offer_identity_ref` names what was owed, `settlement_evidence_ref` names what
actually moved, and a verifier compares the two per invariant 5.

---

## Threat coverage (traceability)

Per the x402 Evidence Chain RFP (R5; UC3, UC6; T2, T4):

- **T2 (economic mismatch):** because `payer_debit`/`payee_credit` name amount and asset
  explicitly and are compared against `offer_identity_ref`, a Buyer or Principal reviewing
  what was actually charged is not limited to a receipt that "confirms only that some payer
  transacted for that resource."
- **T4 (unanchored settlement):** `network` + `transaction` are required fields, not optional
  ones — a settlement artifact with no transaction reference cannot be constructed under this
  profile, closing the gap left by x402's own `SettleResponse.transaction` being present but
  the wire response otherwise carrying no amount to match it against.

---

## Cross-references

- `action_ref` derivation: [`action-ref.md`](./action-ref.md)
- `offer_identity_ref` — what the settlement is checked against: [`offer-identity-ref.md`](./offer-identity-ref.md)
- Same "declared, external resolution not performed live" treatment:
  [`anchoring-precedence-ref-v1.md`](./anchoring-precedence-ref-v1.md#5-chain_invariant),
  [`peer-reconciliation-ref-v1.md`](./peer-reconciliation-ref-v1.md#5-supersedes_chain_integrity)
- x402 wire schema (source of truth for what `SettleResponse` does and does not carry):
  `x402-foundation/x402`, `typescript/packages/legacy/x402/src/types/verify/x402Specs.ts`
- Conformance fixtures: [`examples/conformance/settlement-evidence-ref/`](../../examples/conformance/settlement-evidence-ref/)
