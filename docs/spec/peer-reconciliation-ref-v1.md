# peer-reconciliation-ref-v1 — Specification

**Status:** stable
**Version:** 1.3
**Canonical fixture:** [`examples/conformance/peer-reconciliation-ref/vectors.json`](../../examples/conformance/peer-reconciliation-ref/vectors.json)
**Reference verifier:** [`examples/conformance/peer-reconciliation-ref/verify.py`](../../examples/conformance/peer-reconciliation-ref/verify.py)

**v1.3 (2026-11-24, party distinctness — NOT additive, see below):** a self-audit found that
nothing in the envelope or the verifier checked that `party_a` and `party_b` are different: the
same `party_id` on both sides, or two `party_id` values behind one `co_signer.pubkey`, still
produced `AGREED` (reproduced with the reference verifier, hash recomputed). A new computed
invariant, §7 `party_distinctness`, requires different `party_id` values (compared ignoring ASCII case)
and, when both parties are `observed=true`, different `co_signer.pubkey` KEYS, compared as the
32 decoded key bytes and never as text: the same key written without padding, with whitespace, or
with different unused trailing bits must not pass as a second key. **This changes which envelopes can be
`AGREED`:** an envelope that was `AGREED` under v1.2 with a repeated `party_id` or a repeated
`pubkey` is now `UNRESOLVED`. It is not additive, for the same reason v1.2 was not: grandfathering
the old shape would keep the check unable to fail. No existing fixture changes result and no
declared hash changes (the 11 v1.2 vectors are untouched, byte for byte); ten negative vectors
exercise the new rules, one per way of writing the same party or key differently. `party_id` and
`pubkey` now have format rules (§2 and §7). What it still
cannot see: one operator holding two different keys under two different `party_id` values (see
"What this profile does not do"). `verify.py` now canonicalizes with the repo's `jcs.py` (RFC
8785) instead of `json.dumps(sort_keys=True)`, which this spec says not to use; all 11 existing
hashes are identical under both.

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
`witness_scope=PEER`: two Guardians, each assumed to be controlled by a different party within the
same agreement (an assumption of this profile, not something the verifier checks; see "What this
profile does not do"), each producing its own record of what happened.

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
| `action_ref` | string \| null | The `action_ref` (per [`action-ref.md`](./action-ref.md)) this party reports having derived for the interaction. The profile does not check how it was derived. `null` when `observed` is `false`. |
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

## The seven invariants

Each invariant is separately recomputable. A verifier MUST check all seven independently.

### 1. canonical_envelope

The bytes produced by `JCS(envelope)` hash to the declared `peer_reconciliation_ref`. Any
party with both observation blocks can recompute and compare.

**Fails when:** the declared hash does not match `SHA-256(JCS(envelope))` — envelope was
mutated after either party signed.

### 2. structural_validity

Both `party_a` and `party_b` blocks are present and internally consistent: `observed=true`
requires a non-null `action_ref` and a complete `co_signer` block (`issuer`, `kid`, `jws_signature`
all present, and a `pubkey` that is a strict base64 SPKI Ed25519 key, see §7); every block, observed or
not, needs a valid `party_id` (§7); `observed=false` requires `action_ref` and `co_signer` to both
be `null`.

**Fails when:** a block claims `observed=true` with a missing `action_ref` or an incomplete
`co_signer`, a `pubkey` that is not a strict base64 SPKI Ed25519 key, or an invalid `party_id` (v1.3), or claims `observed=false` while still carrying a non-null `action_ref` —
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
| `AGREED` | `party_distinctness` holds (v1.3), both parties `observed=true`, both signatures declared valid, both signatures' `signed_fields` cover `{party_id, action_ref, interaction_id}`, `party_a.action_ref == party_b.action_ref`. |
| `DISAGREED` | Same readiness conditions as `AGREED`, but `party_a.action_ref != party_b.action_ref`. The mismatched values are carried in the output, not discarded — this is a named conflict, not an error. |
| `UNRESOLVED` | Either party has `observed=false`, either declared `signature_valid_*` is `false` for a party that claims `observed=true`, either party's `signed_fields` fails `signature_binding`, or `party_distinctness` fails (v1.3). Applies regardless of what the other party observed or signed — one missing, invalid, or unbound half is enough to make the pair `UNRESOLVED`, never a default `AGREED`. |

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

### 7. party_distinctness (v1.3)

Computed from the envelope, like `signature_binding`. `party_a.party_id` and `party_b.party_id`
MUST differ, compared without regard to ASCII case. When both parties are `observed=true`,
`party_a.co_signer.pubkey` and `party_b.co_signer.pubkey` MUST be different keys.

**Keys are compared as bytes, not as text.** A `pubkey` is read as strict base64 (no whitespace,
no character outside the alphabet, padding present), must decode to exactly 44 bytes, and must
start with the SPKI Ed25519 prefix (`MCowBQYDK2VwAyEA`); the comparison is on the remaining 32
key bytes. A `pubkey` that is not such a key makes its block `structural_validity` false, not
"a different key": the same key without its `=`, with a trailing newline or a leading space, or
as the 32 raw bytes cannot be used to pass as a second key.

**The canonical re-encoding is not required.** A key whose last base64 character carries
non-zero unused bits decodes to the same bytes as the canonical spelling; eight keys in the
existing fixtures are written that way, and rejecting them would change the result of six
existing vectors. They are accepted, and because the comparison is on bytes, the same key written
with different trailing bits is still caught as the same key
(`distinct-pubkey-trailing-bits-001`).

**`party_id` format (also part of `structural_validity`):** a non-empty string of printable
ASCII with no space or control character. `null`, a non-string, an empty string, or a value with
a space or a newline makes the block structurally invalid.

**Fails when:** the two `party_id` values are equal ignoring ASCII case, or both parties are
`observed=true` and decode to the same 32 key bytes. The comparator state is then `UNRESOLVED`,
never `AGREED` or `DISAGREED`: two signed observations from one identity or one key are one
observation. A shared `issuer` is not checked: a hosting platform can legitimately issue for two
parties.

**Declared versus computed.** The result is always computed; a vector's
`checks.party_distinctness` is only a cross-check. The 11 vectors that predate v1.3 do not declare
it and keep their bytes, so for them an absent value means "nothing declared", not "declared
true"; the vectors added in v1.3 all declare it.

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
- **It does not show that a record exists behind each observation.** The envelope neither
  requires nor carries a reference to either party's own record: `interaction_id` MAY be linked
  back to a party's trail, and that is out of scope here. An `AGREED` state therefore shows two
  signed observations that carry the same `action_ref`, not that each party holds a record of the
  interaction. Without a reference to the party's own record, naming a peer is the producer's
  claim about who was watching, not that party's account (the rule
  [narko4u/evidence-record-spec](https://github.com/narko4u/evidence-record-spec) applies in its
  `VERIFIABILITY-OVERVIEW.md`, "What makes a party independent", commit
  [`6c899c5`](https://github.com/narko4u/evidence-record-spec/commit/6c899c582193643031216c8f26897bb507e61e05),
  credit narko4u / Empire Labs, who also defined `witness_scope`). An optional reference field is
  a possible future addition, not part of v1.x.
- **It does not show that the two parties are controlled by different operators.** Since v1.3 the
  envelope must carry two different `party_id` values and, when both are observed, two different
  `co_signer.pubkey` values (§7). Nothing stops one operator from holding both keys under both
  ids. "Each controlled by a different party" stays an assumption the consumer must establish out
  of band, for example through custody of the keys (see [custody-ref.md](./custody-ref.md));
  "same custody named twice" is not independence.

---

## Relationship to other refs

| Ref | What it answers |
|-----|----------------|
| `action_ref` | What did the agent do, exactly? |
| `cross-system-verification` | Does my trail match one external anchor I don't control (`witness_scope=EXTERNAL`)? |
| `counterparty-ref` | What is the counterparty's reputation snapshot? |
| `anchoring-precedence-ref` | Did an independent external commitment precede the outcome? |
| `peer-reconciliation-ref` | Do two signed observations agree on the same interaction (`witness_scope=PEER`), on the assumption that two different parties produced them? |

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
