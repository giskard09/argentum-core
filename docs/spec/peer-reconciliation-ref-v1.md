# peer-reconciliation-ref-v1 — Specification

**Status:** stable
**Version:** 1.0
**Canonical fixture:** [`examples/conformance/peer-reconciliation-ref/vectors.json`](../../examples/conformance/peer-reconciliation-ref/vectors.json)
**Reference verifier:** [`examples/conformance/peer-reconciliation-ref/verify.py`](../../examples/conformance/peer-reconciliation-ref/verify.py)

---

## What is peer-reconciliation-ref

`peer-reconciliation-ref` answers a question none of this repo's existing specs cover: when
two parties to the same interaction each run their own Guardian (policy enforcement point),
and neither trusts the other's, did they independently observe the same action?

[`cross-system-verification.md`](./cross-system-verification.md) verifies one trail against
one external anchor (`witness_scope=EXTERNAL`) — a single party checking itself against an
outside record. [`counterparty-ref.md`](./counterparty-ref.md) is a reputation snapshot of
the counterparty, not a reconciliation of two independently produced chains. Neither answers
`witness_scope=PEER`: two Guardians, each controlled by a different party within the same
agreement, each with an equally valid but independently derived record of what happened.

The requirement comes from the field, not a hypothetical: `agent-control-standard#33`
(narko4u/Empire Labs, addendum witness-scope SELF/PEER/EXTERNAL) defines `PEER` as *"another
party within an agreement — a counterparty, a peer Guardian mediating the same interaction, or
a tenant. Evidence comes from: artifacts exchanged within the agreement."* The row is `SELF`
unless a verifiable artifact exists from the named witness, produced without depending on that
witness's own enforcement point.

`peer-reconciliation-ref-v1` does not decide who is right when two Guardians disagree. It
gives both observations a canonical, independently recomputable shape and names the
disagreement explicitly, so a third party — an auditor, an arbitrator, a human — can resolve
it with evidence. The construction proves *that* two records diverge or match; it does not
adjudicate *why*.

---

## Derivation

`peer_reconciliation_ref` is `SHA-256(JCS(envelope))` where:

- **JCS** is RFC 8785 canonical JSON: `json.dumps(obj, separators=(',',':'), sort_keys=True, ensure_ascii=False)`
- **SHA-256** lowercase hex
- `envelope` must contain at minimum: `interaction_id`, `party_a`, `party_b`, `version`

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

envelope = {
    "interaction_id": "3f9c9e2e-6b5a-4b7e-8f3e-1a2b3c4d5e6f",
    "party_a": {
        "party_id": "safeagent-guardian",
        "observed": True,
        "action_ref": "a2f1...b8e9",
        "co_signer": {"issuer": "safeagent-guardian", "kid": "sg-key-01",
                       "pubkey": "MCowBQYDK2VwAyEA...", "jws_signature": "eyJhbGciOi..."},
    },
    "party_b": {
        "party_id": "counterparty-guardian",
        "observed": True,
        "action_ref": "a2f1...b8e9",
        "co_signer": {"issuer": "counterparty-guardian", "kid": "cg-key-01",
                       "pubkey": "MCowBQYDK2VwAyEA...", "jws_signature": "eyJhbGciOi..."},
    },
    "version": "peer-reconciliation-ref-v1",
}
peer_reconciliation_ref = hashlib.sha256(jcs(envelope).encode()).hexdigest()
```

---

## Envelope fields

| Field | Type | Description |
|-------|------|--------------|
| `interaction_id` | string | Stable identifier for the interaction both parties are reconciling. Not itself a `trail_id` — either party's `action_ref` MAY link back to their own Mycelium trail via [`action-ref.md`](./action-ref.md), out of scope for this envelope. |
| `party_a`, `party_b` | object | One observation block per party, shape below. Order is not significant — `party_a`/`party_b` are labels, not a priority ranking. |
| `version` | string | Always `"peer-reconciliation-ref-v1"`. |

### Observation block (`party_a` / `party_b`)

| Field | Type | Description |
|-------|------|--------------|
| `party_id` | string | Stable identifier of the Guardian producing this observation. |
| `observed` | boolean | `true` if this party produced its half of the reconciliation. `false` means this party's Guardian did not (yet) supply an observation — the envelope still hashes deterministically, but the comparator MUST treat this as `UNRESOLVED`, never as agreement or disagreement by default. |
| `action_ref` | string \| null | The `action_ref` (per [`action-ref.md`](./action-ref.md)) this party independently derived for the interaction. `null` when `observed` is `false`. |
| `co_signer` | object \| null | Present when `observed` is `true`. Same shape as the co-signer block in [`anchoring-precedence-ref-v1.md`](./anchoring-precedence-ref-v1.md#2-admission_invariant): `issuer`, `kid`, `pubkey`, `jws_signature`, all recomputable from the fixture alone — no out-of-band lookup required. `null` when `observed` is `false`. |

**Signature scope, honestly declared:** this profile is a stdlib-only Python reference
(hashlib + json, per the pattern set by every verifier in this repo's `examples/conformance/`
tree that does not carry a PyNaCl dependency, e.g. `anchoring-precedence-ref`). It checks the
canonical hash and the structural shape of `co_signer` — issuer/kid/pubkey/jws_signature are
all present and internally consistent — the same treatment `chain_invariant` receives in
`anchoring-precedence-ref-v1`. It does **not** perform live Ed25519/JWS cryptographic
verification; a fixture's `checks.signature_valid` per party is a declared, externally-audited
fact the reference verifier trusts, exactly as `chain_invariant` is trusted in
`anchoring-precedence-ref-v1`'s reference verifier. An implementer building a production
Guardian SHOULD perform real signature verification over `co_signer` — this profile does not
forbid it, it just does not ship a crypto dependency to demonstrate it (see
[`delegation-chain-ref.md`](./delegation-chain-ref.md) for this repo's PyNaCl-based reference
if a live-verification example is needed).

---

## The four invariants

Each invariant is separately recomputable. A verifier MUST check all four independently.

### 1. canonical_envelope

The bytes produced by `JCS(envelope)` hash to the declared `peer_reconciliation_ref`. Any
party with both observation blocks can recompute and compare.

**Fails when:** the declared hash does not match `SHA-256(JCS(envelope))` — envelope was
mutated after either party signed.

### 2. structural_validity

Both `party_a` and `party_b` blocks are present and internally consistent: `observed=true`
requires a non-null `action_ref` and a complete `co_signer` block (`issuer`, `kid`, `pubkey`,
`jws_signature` all present); `observed=false` requires `action_ref` and `co_signer` to both
be `null`.

**Fails when:** a block claims `observed=true` with a missing `action_ref` or an incomplete
`co_signer`, or claims `observed=false` while still carrying a non-null `action_ref` —
either shape decouples the observation from its signature and is malformed by construction.

### 3. signature_validity

Declared per party in `checks.signature_valid_a` / `checks.signature_valid_b` — external
resolution, not performed live by this reference verifier (see the honesty note above).

**Fails when:** either declared `signature_valid_*` is `false` for a party with
`observed=true`.

### 4. comparator_state

The three-state comparator, computed from `structural_validity` + `signature_validity` +
the two `action_ref` values. **Never collapse "could not be checked" into either "agreed" or
"disagreed"** — the same principle [`verify-failure-mode-ref.md`](./verify-failure-mode-ref.md)
applies to distinguishing `verify_unreachable` from `verify_invalid`.

| State | Condition |
|-------|-----------|
| `AGREED` | Both parties `observed=true`, both signatures declared valid, `party_a.action_ref == party_b.action_ref`. |
| `DISAGREED` | Both parties `observed=true`, both signatures declared valid, `party_a.action_ref != party_b.action_ref`. The mismatched values are carried in the output, not discarded — this is a named conflict, not an error. |
| `UNRESOLVED` | Either party has `observed=false`, or either declared `signature_valid_*` is `false` for a party that claims `observed=true`. Applies regardless of what the other party observed — one missing or invalid half is enough to make the pair `UNRESOLVED`, never a default `AGREED`. |

**Fails when:** the declared `comparator_state` in a vector does not match what the four
inputs above compute.

---

## What this profile does not do

Declared explicitly, matching the honesty convention this repo applies elsewhere (see
`anchoring-precedence-ref-v1`'s miner-timestamp caveat and `action-ref.md`'s
`OUT_OF_PROFILE_DOMAIN`):

- **It does not resolve a `DISAGREED` state.** A `DISAGREED` output names that `party_a` and
  `party_b` derived different `action_ref` values for the same `interaction_id` — it does not
  determine which one, if either, is correct. Resolving that requires evidence outside this
  envelope (raw artifacts exchanged within the agreement, a third-party arbitrator, an
  out-of-band audit) — the same posture `anchoring-precedence-ref-v1` takes toward what its
  own construction cannot prove.
- **It does not perform live cryptographic signature verification** in the reference
  Python implementation, as declared under "Signature scope" above.
- **It does not assign fault for `UNRESOLVED`.** A missing observation may mean the other
  party's Guardian has not run yet, is offline, or is deliberately withholding — this profile
  makes no claim about which, and a verifier MUST NOT infer intent from `UNRESOLVED` alone.

---

## Relationship to other refs

| Ref | What it answers |
|-----|----------------|
| `action_ref` | What did the agent do, exactly? |
| `cross-system-verification` | Does my trail match one external anchor I don't control (`witness_scope=EXTERNAL`)? |
| `counterparty-ref` | What is the counterparty's reputation snapshot? |
| `anchoring-precedence-ref` | Did an independent external commitment precede the outcome? |
| `peer-reconciliation-ref` | Do two independently controlled Guardians agree on the same interaction (`witness_scope=PEER`)? |

---

## Cross-references

- `action_ref` derivation: [`docs/spec/action-ref.md`](./action-ref.md)
- Co-signer block shape precedent: [`docs/spec/anchoring-precedence-ref-v1.md`](./anchoring-precedence-ref-v1.md#2-admission_invariant)
- Tri-state "don't collapse unknown into known" precedent: [`docs/spec/verify-failure-mode-ref.md`](./verify-failure-mode-ref.md)
- `witness_scope` requirement source: `agent-control-standard#33` (narko4u/Empire Labs)
