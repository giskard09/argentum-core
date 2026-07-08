# disclosure-scoped-ref-v0 — Specification

**Status:** draft (v0)
**Canonical fixture:** [`examples/conformance/disclosure-scoped-ref/vectors.json`](../../examples/conformance/disclosure-scoped-ref/vectors.json)

---

## What is `disclosure_ref`

`disclosure_ref` is a root digest over a **per-field commitment vector**. It lets a
verifier confirm that a rule was evaluated against a specific, committed record while
the discloser reveals only a chosen subset of that record's fields — the undisclosed
fields stay as opaque digests, never as values or as anything derivable from the
digest alone.

This is a **field-level selective disclosure** primitive: given a record with fields
`{f1, f2, ..., fn}`, a discloser can open `{f2, f5}` and prove they belong to the same
committed record as `{f1, f3, f4, ...fn}` without revealing the latter's values — and
without the verifier being able to brute-force a closed low-entropy field (an amount,
a small integer, a short code) from its digest alone, provided the salting rule below
is followed.

**What it does not do.** `disclosure_ref` does not evaluate the rule itself ("does
this record satisfy policy X") — that is external business logic operating on
whichever fields are opened. It does not replace `action_ref`
([`action-ref.md`](./action-ref.md)): the two are **siblings**, not layers. `action_ref`
continues to hash the full, unredacted four-field preimage exactly as specified —
disclosure-scoped-ref does not touch it, wrap it, or make it optional. A record MAY
carry both: `action_ref` as the primitive's own unblinded identity, `disclosure_ref` as
an additional, independently-computed pointer for a use case that needs field-level
redaction. This mirrors the existing `screen_ref` pattern (`action_ref` applied to a
screening decision as a sibling pointer alongside the settlement action, see
[`examples/conformance/presidio/`](../../examples/conformance/presidio/)) — a second
ref for a second purpose, not a modification of the first.

## Derivation

### Field commitment

Each field of the source record is committed independently:

```
field_digest(field_name, value, salt) = SHA256(JCS({
    "field": field_name,
    "salt":  salt,      # hex string, >=16 bytes / 128 bits of randomness
    "value": value,
}))
```

- **`salt` is per-field.** Every field gets its own independently-generated salt.
  This is not a convenience choice — it is REQUIRED. A shared or reused salt across
  two fields (especially two low-entropy fields, e.g. two small integers or amounts
  from a bounded range) collapses the dictionary-attack cost of both fields to that
  of one: an attacker who guesses the salt for field A by brute-forcing its digest
  gets field B's digest "for free" if the salt is shared. Distinct salts are what
  make each field's digest independently hard to invert.
- **`value` is the field's native JSON value** (string, number, boolean, or null) —
  no pre-hashing, no truncation.
- **JCS** is RFC 8785 canonical JSON (`json.dumps(obj, separators=(',',':'),
  sort_keys=True, ensure_ascii=False)` in Python; the minimal recursive sorted-key
  serializer in JS — see the reference verifiers).

### Commitment vector and root

```
commitment_vector = sorted(
    [{"field": name, "digest": field_digest(name, value, salt)} for each field],
    by field name, ascending
)

disclosure_ref = SHA256(JCS(commitment_vector))
```

The vector is a JSON **array**, not an object keyed by field name — this makes field
order canonical (sorted by name) without relying on JSON object key-order, which
some parsers do not preserve reliably for arrays-of-objects the way JCS's key-sort
does for objects. Each array entry is itself a JCS-canonicalized object
(`{"digest":..., "field":...}`, keys sorted).

### Disclosure

A disclosure reveals a subset of fields:

```
disclosure = {
    "disclosure_ref": "<root digest>",
    "opened": {
        "<field_name>": {"value": <value>, "salt": "<hex>"},
        ...
    }
}
```

The **closed** fields are represented only by their entries already present in the
published `commitment_vector` (field name + digest, no value, no salt).

## Verification

Given `commitment_vector`, `disclosure_ref`, and a `disclosure`:

1. **Root check.** Recompute `SHA256(JCS(commitment_vector))` and confirm it equals
   `disclosure_ref`. This is the same check regardless of which fields are opened —
   the root does not change when different fields are chosen for disclosure, because
   the vector always carries all fields' digests, opened or not.
2. **Opened-field check.** For each `(field_name, {value, salt})` in `opened`,
   recompute `field_digest(field_name, value, salt)` and confirm it equals the
   digest recorded for `field_name` in `commitment_vector`. A mismatch means either
   the revealed value/salt does not correspond to the committed field, or the
   commitment vector's entry for that field was substituted from a different
   field's commitment (§ Security below).
3. **Salt uniqueness (structural, MUST).** No two entries in a single disclosure
   (or, for a conforming record, no two fields in the full record) MAY share a
   salt. This is a structural conformance check on the *issuer's* construction,
   independent of whether the root or any opened-field digest verifies — a record
   can pass checks 1–2 while still being non-conformant if its salts collide,
   because the collision is a live security defect (§ Rationale) that recomputation
   alone does not surface for fields that stay closed.
4. **Rule evaluation** (external). Whatever policy the disclosure exists to prove
   ("amount is within an approved range", "counterparty is on an approved list") is
   evaluated by the verifier over the opened values only. This primitive does not
   define or constrain that policy — it only guarantees the opened values are the
   ones that were committed, and that nothing else about the record was revealed.

## Security

- **Field-name binding.** `field_digest` includes `"field": field_name` in its own
  preimage. A commitment computed for field `"jurisdiction"` cannot be silently
  relabeled as field `"amount"` in the vector without detection **once that field
  is opened**: recomputing `field_digest("amount", value, salt)` from the disclosed
  value/salt will not match a digest that was actually produced with
  `"field":"jurisdiction"` baked in. Undisclosed fields carry this risk latently —
  substitution of a closed field's digest is not detectable until (if ever) that
  field is later opened, which is a known limitation of any pure-digest commitment
  scheme and not specific to this primitive; it is the reason § Verification's step
  3 (salt uniqueness) is a structural, issuer-side conformance requirement rather
  than something a downstream verifier can always catch on its own.
- **Low-entropy fields require the per-field salt.** A field like a boolean flag or
  a small bounded integer has few possible values; without a salt, its digest is
  trivially invertible by brute-forcing the value space. The salt raises the
  effective search space to the salt's own entropy (>=128 bits), independent of the
  field's native entropy — but only if that salt is not shared with any other
  field (see § Derivation).
- **Root digest reveals field count and names, not values.** `commitment_vector`
  is published in full (all field names + digests) even before any disclosure — a
  verifier always knows the record's field names and count, just not their values.
  Applications requiring field-name confidentiality need a different construction;
  this v0 does not provide it.

## Relationship to `action_ref`

`disclosure_ref` is **not** derived from `action_ref`'s preimage and does not alter
it. The two may co-occur on the same record (an `action_ref` computed over
`{agent_id, action_type, scope, timestamp}` exactly as specified in
[`action-ref.md`](./action-ref.md), plus a `disclosure_ref` computed independently
over whatever field set the disclosure use case requires), the same way a
`screen_ref` and a settlement `action_ref` coexist as two independently-computed
pointers for two different purposes on related events. This is a deliberate
scoping decision for v0: the alternative — a ref computed *over* the field-digest
vector in place of the raw preimage, changing what `action_ref` itself means — is
recorded as an open question below rather than implemented, because no design
pressure surfaced during this draft that required touching the existing,
already-relied-upon `action_ref` construction.

## Open Questions

- **Alternative profile: `action_ref` over the field-digest vector.** Rather than a
  sibling ref, a future profile could define `action_ref` itself as
  `SHA256(JCS(commitment_vector))` for records that want selective disclosure as
  their primary mode, making disclosure-scoping the default rather than an add-on.
  Not pursued in v0 — no concrete use case surfaced requiring `action_ref`'s
  existing semantics to change, and changing them would affect every existing
  consumer of the four-field preimage. Left open for a v1 if that pressure
  materializes.
- **Partial-vector proofs (Merkle-tree, not flat vector).** v0 uses a flat
  commitment vector — verifying the root requires recomputing over *all* field
  digests, not just the opened ones' path to a root. A Merkle-tree construction
  would let a verifier check an opened field against the root with a
  logarithmic-size proof instead of the full vector, at the cost of a more complex
  construction. Not pursued in v0: typical record field counts (tens, not
  thousands) make the flat-vector cost negligible, and the simpler construction is
  preferable until a use case demonstrates the tree's cost is justified.
- **Revocation / re-disclosure.** Not addressed — a `disclosure_ref` is a static
  commitment to one record; whether or how a field can be *closed* again after
  being opened, or a new commitment vector issued superseding an old one, is out of
  scope for v0.
