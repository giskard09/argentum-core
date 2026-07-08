# disclosure-scoped-ref-v0

Field-level selective disclosure: a per-field salted commitment vector and a
root digest (`disclosure_ref`). A discloser opens a chosen subset of a
record's fields; a verifier confirms the opened values against the vector and
the vector against the published root, without the closed fields' values ever
being revealed or derivable from their digests alone (given the salting rule
below).

Full construction: [`docs/spec/disclosure-scoped-ref.md`](../../../docs/spec/disclosure-scoped-ref.md).

## Construction, in short

```
field_digest(field, value, salt) = SHA256(JCS({"field": field, "salt": salt, "value": value}))
commitment_vector = sorted([{field, digest} for each field], by field name)
disclosure_ref = SHA256(JCS(commitment_vector))
```

Salt is **per-field**, not shared. A shared salt across two fields — especially
two low-entropy fields (small integers, bounded amounts) — collapses both
fields' dictionary-attack resistance to that of one guess.

## Relationship to `action_ref`

Sibling, not a replacement. `action_ref` ([`docs/spec/action-ref.md`](../../../docs/spec/action-ref.md))
keeps hashing the full, unredacted four-field preimage exactly as already
specified — this primitive does not touch it. A record may carry both: the
existing `action_ref` for its own identity, and `disclosure_ref` for a
use case that needs field-level redaction on a different field set. Same
pattern as `screen_ref` alongside a settlement `action_ref`
([`../presidio/`](../presidio/)) — a second ref for a second purpose.

## Vectors

- **`pos-subset-disclosure`** — three of six fields opened, three stay closed.
  Opened fields recompute to their committed digests; the full vector
  recomputes to the published root (unchanged by which fields were chosen).
- **`neg-hidden-field-altered`** — a closed field's digest is swapped for a
  different value's digest under the same salt. The root breaks immediately —
  caught without the field ever being opened.
- **`neg-salt-reuse-and-digest-substitution`** — two distinct failure modes on
  the same field: (a) salt reuse across two fields, a structural conformance
  violation caught by a uniqueness scan over the salt set, independent of any
  hash recomputation; (b) a valid digest from one field's commitment
  substituted verbatim into another field's slot — breaks the root
  immediately, and independently fails a later disclosure of the true value
  because the field-name binding inside the original commitment doesn't
  match.

## Run

```
python3 verify.py      # zero-dependency, offline
node verify.mjs         # zero-dependency, offline
```

Both recompute independently from [`vectors.json`](./vectors.json) and land on
byte-identical digests.
