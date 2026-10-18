# peer-reconciliation-ref-v1 — Specification

**Status:** stable
**Version:** 1.2
**Canonical fixture:** [`examples/conformance/peer-reconciliation-ref/vectors.json`](../../examples/conformance/peer-reconciliation-ref/vectors.json)
**Reference verifier:** [`examples/conformance/peer-reconciliation-ref/verify.py`](../../examples/conformance/peer-reconciliation-ref/verify.py)

**v1.2 (2026-10-18, closes a signature-binding gap — NOT additive, see below):** found in a
self-audit of this spec prompted by narko4u/Empire Labs flagging the same class of bug in a
different design — zhaoxinghua09-cell's verdict evidence records, in the same thread where
`peer-reconciliation-ref-v1` itself has standing
(`GenAI-Security-Project/agent-control-standard#33`, comment `6246290138`, 2026-10-18): *"the
peer_artifact proves that the peer checked vector V, but not that it checked THIS verdict — a
genuine statement is reusable to mint a second record of the same vector with the opposite
result."* This spec had the same gap, unflagged by anyone yet: §"Observation block" required
`co_signer` to be structurally complete (`issuer`/`kid`/`pubkey`/`jws_signature` all present)
but never said what the JWS payload must actually *cover*. A `co_signer` that is cryptographically
valid and signs only the party's identity — never the specific `action_ref` it is presented
alongside — can be paired with a *different* `action_ref` in a different envelope without
re-signing anything, exactly the reuse narko4u described for the other design. **Fix:** a new
required field, `co_signer.signed_fields` (list of field names the JWS payload actually binds),
and a MUST that it cover `party_id`, `action_ref`, and `interaction_id` — checked by the new
`signature_binding` invariant (§4 below), independent of and in addition to `signature_validity`.
**This is deliberately not framed as additive the way v1.1's fields were:** a `co_signer` that
omits `signed_fields`, or whose `signed_fields` omits `action_ref`, was always insecure against
this replay — grandfathering it as still-valid would defeat the point of closing the gap. All
nine v1.0/v1.1 fixtures in `vectors.json` were updated in place to declare `signed_fields`,
which changed their declared `peer_reconciliation_ref` (the field sits inside the hashed
envelope). A new negative vector, `replay-001`, exercises the exact shape above.

**v1.1 (2026-08-31, additive, no compatibility break):** three optional fields —
`supersedes`, `requested_at`, `as_of` — added after a cross-check against
`trustless-ai/cross-reference-console`'s `CELL-v1.md` found the same tri-state
comparator problem solved with more rigor on three points: correction vs.
rewrite, timestamped non-suppression, and an explicit per-observation time
field. All three fields are absent-by-default and change nothing about how an
envelope without them hashes or evaluates — the five v1.0 fixtures remain
valid v1.1 vectors unmodified. Same gradual-addition pattern this repo already
uses for `hop_signature` in [`delegation-chain-ref.md`](./delegation-chain-ref.md).

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

- **JCS** is RFC 8785 canonical JSON: object keys sorted recursively by UTF-16 code units (§3.2.3), no whitespace, literal UTF-8 — **not** `json.dumps(sort_keys=True)`, which sorts by code point and diverges for keys outside the BMP. Reference implementation: [`jcs.py`](../../jcs.py)
- **SHA-256** lowercase hex
- `envelope` must contain at minimum: `interaction_id`, `party_a`, `party_b`, `version`

```python
import hashlib, json

def jcs(obj):
    # RFC 8785 §3.2.3: object keys sorted recursively by UTF-16 code units.
    # Not json.dumps(sort_keys=True): that sorts by code point and diverges
    # from RFC 8785 for keys outside the BMP. Floats additionally need
    # ECMA-262 Number::toString formatting -- see jcs.py.
    def canon(o):
        if isinstance(o, dict):
            return {k: canon(o[k]) for k in sorted(o, key=lambda k: k.encode("utf-16-be", "surrogatepass"))}
        if isinstance(o, list):
            return [canon(v) for v in o]
        return o
    return json.dumps(canon(obj), separators=(',', ':'), ensure_ascii=False)

envelope = {
    "interaction_id": "3f9c9e2e-6b5a-4b7e-8f3e-1a2b3c4d5e6f",
    "party_a": {
        "party_id": "safeagent-guardian",
        "observed": True,
        "action_ref": "a2f1...b8e9",
        "co_signer": {"issuer": "safeagent-guardian", "kid": "sg-key-01",
                       "pubkey": "MCowBQYDK2VwAyEA...", "jws_signature": "eyJhbGciOi...",
                       "signed_fields": ["party_id", "action_ref", "interaction_id"]},
    },
    "party_b": {
        "party_id": "counterparty-guardian",
        "observed": True,
        "action_ref": "a2f1...b8e9",
        "co_signer": {"issuer": "counterparty-guardian", "kid": "cg-key-01",
                       "pubkey": "MCowBQYDK2VwAyEA...", "jws_signature": "eyJhbGciOi...",
                       "signed_fields": ["party_id", "action_ref", "interaction_id"]},
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
| `supersedes` | string \| absent | **v1.1, optional.** `peer_reconciliation_ref` of the prior envelope this one corrects. See "Corrections (v1.1)" below. Absent means this is a root record, not a correction. |

### Observation block (`party_a` / `party_b`)

| Field | Type | Description |
|-------|------|--------------|
| `party_id` | string | Stable identifier of the Guardian producing this observation. |
| `observed` | boolean | `true` if this party produced its half of the reconciliation. `false` means this party's Guardian did not (yet) supply an observation — the envelope still hashes deterministically, but the comparator MUST treat this as `UNRESOLVED`, never as agreement or disagreement by default. |
| `action_ref` | string \| null | The `action_ref` (per [`action-ref.md`](./action-ref.md)) this party independently derived for the interaction. `null` when `observed` is `false`. |
| `co_signer` | object \| null | Present when `observed` is `true`. Same shape as the co-signer block in [`anchoring-precedence-ref-v1.md`](./anchoring-precedence-ref-v1.md#2-admission_invariant) plus one addition (`signed_fields`, v1.2, see below): `issuer`, `kid`, `pubkey`, `jws_signature`, `signed_fields`, all recomputable from the fixture alone — no out-of-band lookup required. `null` when `observed` is `false`. |
| `co_signer.signed_fields` | list of strings | **v1.2, REQUIRED when `co_signer` is present.** Declares which fields of this observation the JWS payload actually binds. MUST include `party_id`, `action_ref`, and `interaction_id` — see "Signature scope, honestly declared" below and invariant §4 (`signature_binding`). |
| `requested_at` | integer (epoch ms) \| absent | **v1.1, optional, RECOMMENDED when `observed` is `false`.** See "Timestamped non-suppression (v1.1)" below. |
| `as_of` | integer (epoch ms) \| absent | **v1.1, optional.** When this specific party's Guardian made its observation. See "Explicit per-observation time (v1.1)" below. |

**Signature scope, honestly declared:** this profile is a stdlib-only Python reference
(hashlib + json, per the pattern set by every verifier in this repo's `examples/conformance/`
tree that does not carry a PyNaCl dependency, e.g. `anchoring-precedence-ref`). It checks the
canonical hash and the structural shape of `co_signer` — issuer/kid/pubkey/jws_signature/
signed_fields are all present and internally consistent — the same treatment `chain_invariant`
receives in `anchoring-precedence-ref-v1`. It does **not** perform live Ed25519/JWS
cryptographic verification; a fixture's `checks.signature_valid` per party is a declared,
externally-audited fact the reference verifier trusts, exactly as `chain_invariant` is trusted
in `anchoring-precedence-ref-v1`'s reference verifier. An implementer building a production
Guardian SHOULD perform real signature verification over `co_signer` — this profile does not
forbid it, it just does not ship a crypto dependency to demonstrate it (see
[`delegation-chain-ref.md`](./delegation-chain-ref.md) for this repo's PyNaCl-based reference
if a live-verification example is needed).

**But `signature_valid` alone is not enough, which is why `signed_fields` is not just another
item on this trust list (v1.2).** A real JWS can be fully valid and still only cover the
signer's identity — never the `action_ref` it happens to sit next to in the envelope. That
makes the co_signer *reusable*: the same valid signature, obtained once, can be paired with a
different `action_ref` in a different envelope, because nothing about the signature itself
changes when the surrounding `action_ref` does. `signed_fields` names what the payload actually
binds, and unlike `signature_valid` — which this stdlib-only profile cannot check live and must
trust as declared — whether `signed_fields` *covers* `action_ref`/`interaction_id`/`party_id` is
something the verifier can and does check for itself, directly from the fixture, with no crypto
dependency and no external trust. This is why `signature_binding` is its own invariant (§4)
rather than folded into `signature_validity`: one is a declared fact, the other is a computed
one, and conflating them would hide exactly the gap this version closes.

---

## The six invariants

Each invariant is separately recomputable. A verifier MUST check all six independently.

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

### 4. signature_binding (v1.2)

Unlike `signature_validity`, this is **computed**, not externally trusted: for each party with
`observed=true`, `co_signer.signed_fields` MUST be a superset of `{party_id, action_ref,
interaction_id}`. A verifier reads `signed_fields` directly from the fixture — no crypto
dependency, no declared external fact to trust.

**Fails when:** an `observed=true` party's `signed_fields` omits `party_id`, `action_ref`, or
`interaction_id` — the signature does not provably bind the value it is presented alongside,
so the co_signer could in principle be paired with a different `action_ref` without
re-signing. See `replay-001` in the fixture set for the exact shape.

### 5. comparator_state

The three-state comparator, computed from `structural_validity` + `signature_validity` +
`signature_binding` + the two `action_ref` values. **Never collapse "could not be checked" into
either "agreed" or "disagreed"** — the same principle
[`verify-failure-mode-ref.md`](./verify-failure-mode-ref.md) applies to distinguishing
`verify_unreachable` from `verify_invalid`.

| State | Condition |
|-------|-----------|
| `AGREED` | Both parties `observed=true`, both signatures declared valid, both signatures' `signed_fields` cover `{party_id, action_ref, interaction_id}`, `party_a.action_ref == party_b.action_ref`. |
| `DISAGREED` | Same readiness conditions as `AGREED`, but `party_a.action_ref != party_b.action_ref`. The mismatched values are carried in the output, not discarded — this is a named conflict, not an error. |
| `UNRESOLVED` | Either party has `observed=false`, either declared `signature_valid_*` is `false` for a party that claims `observed=true`, or either party's `signed_fields` fails `signature_binding`. Applies regardless of what the other party observed or signed — one missing, invalid, or unbound half is enough to make the pair `UNRESOLVED`, never a default `AGREED`. |

**Fails when:** the declared `comparator_state` in a vector does not match what the inputs
above compute.

### 6. supersedes_chain_integrity (v1.1)

Present only when the envelope carries a `supersedes` field. The referenced
`peer_reconciliation_ref` MUST resolve to a real, previously known envelope — the
same "declared in vector, external resolution not performed live" treatment
`chain_invariant` receives in [`anchoring-precedence-ref-v1.md`](./anchoring-precedence-ref-v1.md#5-chain_invariant).
A vector without `supersedes` is exempt from this check (it is a root record).

Each `known_envelopes` entry MUST also declare `resolved_by`: the identifier of
the source that supplied this record. `resolved_by` MUST NOT equal either
`party_a.party_id` or `party_b.party_id` of the envelope carrying the
`supersedes` pointer. Without this, the same party that emits a correction
could also fabricate the "prior" envelope it claims to correct — the two
values being compared (the pointer and what it resolves to) could never
diverge, because one party controls both sides. `resolved_by` names an
independent source (an index, an auditor, the counterparty's own Guardian —
anything other than the party doing the pointing); it is not itself
cryptographically verified by this reference verifier, the same "declared,
externally-audited fact" treatment `signature_valid_*` receives above.

**Fails when:** `supersedes` is present but does not resolve to a known prior
envelope, resolves to an envelope whose own `interaction_id` differs (a
correction MUST correct the same interaction, not a different one), the
`known_envelopes` entry has no `resolved_by`, or `resolved_by` is one of the
current envelope's own two parties.

---

## Corrections (v1.1)

`trustless-ai/cross-reference-console`'s `CELL-v1.md` states the append-only rule
this profile was missing: *"a correcting cell anchors, the original stays
preserved-marked-disputed."* Before v1.1, nothing in this spec said what
happens when `party_a` needs to correct an `action_ref` it already signed —
an implementer could silently overwrite the original observation, destroying
the record of what was actually agreed or disagreed at the time.

**The rule:** a correction is a **new envelope**, never a mutation of the old
one. The new envelope sets `supersedes` to the `peer_reconciliation_ref` of the
envelope it corrects. The original envelope is never deleted or rewritten — it
remains resolvable by its own hash, and any consumer indexing this profile
SHOULD mark it disputed/superseded rather than removing it from view. A chain
of corrections is a chain of `supersedes` pointers; a consumer resolving
"the current state" of an `interaction_id` follows the chain to its tip.

This profile does not define how a consumer discovers the tip of a
`supersedes` chain (out-of-band index, latest-by-`as_of`, or an explicit
pointer maintained by the reconciling parties) — it only guarantees the chain
itself is honest: nothing is destroyed, and each correction names exactly
what it corrects.

## Timestamped non-suppression (v1.1)

`CELL-v1.md` treats a missing observation as *"itself a derivable, falsifiable
fact"*, not passive silence: *"non-suppression: a missing cell is itself a
derivable, falsifiable fact."* This profile's `UNRESOLVED` state already
refuses to default a missing half into `AGREED`, but before v1.1 it had no way
to prove *when* the missing half was asked for — a party could claim
`observed=false` without any record that an observation was ever solicited.

**The field:** `requested_at` (epoch ms) on an observation block declares when
that party's Guardian was asked to produce its half. It is **RECOMMENDED, not
required**, when `observed` is `false` — this profile does not make it a hard
requirement in v1.1 because doing so would invalidate `unresolved-001` (the
v1.0 fixture), which predates the field and has no way to retroactively supply
it. A future `peer-reconciliation-ref-v2` MAY require `requested_at` on every
`UNRESOLVED` observation; this version does not, in keeping with the same
gradual-tightening posture `hop_signature` took in `delegation-chain-ref.md`.

**What this does not prove:** `requested_at` is a declared value from the
requesting side, not independently attested — a party can still misstate when
it asked. It converts "no proof a request was ever made" into "a specific,
falsifiable claim about when," which is the improvement `CELL-v1.md` names;
it does not add cryptographic non-repudiation to the request itself.

## Explicit per-observation time (v1.1)

`CELL-v1.md` requires `as_of` on both `claim` and `cell`, with an explicit
rule that a late transition cannot rewrite an earlier snapshot. This profile's
envelope had no notion of time before v1.1.

**The field:** `as_of` (epoch ms) on an observation block is the declared time
at which that specific Guardian made its observation. It requires no shared
clock between the two parties — each party declares its own `as_of`
independently, the same treatment `anchor_block_time` receives in
[`anchoring-precedence-ref-v1.md`](./anchoring-precedence-ref-v1.md): a
value asserted by the party producing it, not independently proven by this
profile. `as_of` is informational in v1.1 — the tri-state comparator does not
consume it to decide `AGREED` / `DISAGREED` / `UNRESOLVED`; it exists so an
auditor reading a reconciliation (or a chain of corrections via `supersedes`)
can reconstruct the declared sequence of events. `CELL-v1.md`'s
"late transition can't rewrite an earlier snapshot" rule is achieved in this
profile structurally, via the append-only `supersedes` chain above, rather
than by `as_of` enforcing an ordering rule of its own.

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
- **`signature_binding` (v1.2) does not prove the JWS payload actually contains what
  `signed_fields` claims it does.** It checks that `signed_fields` declares the right field
  names; it does not decode the JWS and compare its claims against the envelope. That stronger
  check requires the same live verification this profile already declares out of scope. A
  production Guardian performing real signature verification MUST also recompute the JWS
  payload and confirm it matches `signed_fields`'s claim, not just that the list contains the
  right names — otherwise `signed_fields` itself becomes a second value that can be asserted
  independently of what was actually signed.
- **It does not assign fault for `UNRESOLVED`.** A missing observation may mean the other
  party's Guardian has not run yet, is offline, or is deliberately withholding — this profile
  makes no claim about which, and a verifier MUST NOT infer intent from `UNRESOLVED` alone.
- **It does not require `requested_at` on every `UNRESOLVED` observation (v1.1).** It is
  RECOMMENDED, not enforced — see "Timestamped non-suppression (v1.1)" above for why, and the
  declared limitation this leaves for a future v2.
- **It does not use `as_of` to order or arbitrate anything (v1.1).** It is transported for
  audit legibility only; the ordering guarantee this profile actually makes comes from the
  append-only `supersedes` chain, not from comparing `as_of` values across parties.

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
- v1.1 correction/non-suppression/as_of source: `trustless-ai/cross-reference-console`, `CELL-v1.md` ("a correcting cell anchors, the original stays preserved-marked-disputed"; "a missing cell is itself a derivable, falsifiable fact"; `as_of` required on claim and cell)
- v1.2 `signature_binding` source: self-audit prompted by narko4u/Empire Labs flagging the same
  reusable-statement class of bug in a different design, same thread — `agent-control-standard#33`
  comment `6246290138` (zhaoxinghua09-cell's verdict evidence records, 2026-10-18)
