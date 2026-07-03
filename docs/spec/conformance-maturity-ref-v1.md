# conformance-maturity-ref-v1

Names the ladder a conformance claim climbs before it can be treated as
normative, so "two repos agree" and "an independent implementation verified
the spec text" stop being the same sentence.

## Problem

Conformance work in this repo has always followed one rule in practice:
CI byte-identity plus an implementation independent of the spec author,
before a vector counts as conformant. That rule was never written down as a
taxonomy — it lived as a habit applied per PR. Without an explicit enum, two
failure modes are indistinguishable from the outside: a harness that reached
consensus with itself (same author, related repos, no independent check) and
a harness that a second party actually verified from spec text alone. A
reader comparing conformance claims across profile docs has no field to
tell them apart.

## The ladder

```
DRAFT_VECTOR                 — spec text exists; a vector has been proposed,
                                not yet checked in or reproducible.
MUTUAL_CONSISTENCY           — two implementations agree, but they share an
                                author or a common description/harness. This
                                rules out a typo, not a misreading of the
                                spec. It is not independent verification.
PINNED_CONFORMANCE_VECTOR    — a vector digest is checked in and reproducible
                                from the repo alone (byte-for-byte, no network,
                                no author-supplied fixture at runtime).
INDEPENDENTLY_VERIFIED       — an implementation built from the spec text by
                                a party with no access to the reference
                                implementation's internals matches the pinned
                                vectors.
ACCEPTED_CONFORMANCE_PROFILE — the profile has been adopted as normative by a
                                verifier that did not author it: cited,
                                depended on, or referenced in that verifier's
                                own conformance surface.
```

Each level is a strict prerequisite for the next. A claim cannot skip a
rung — `ACCEPTED_CONFORMANCE_PROFILE` implies the profile already holds
`INDEPENDENTLY_VERIFIED`, which implies `PINNED_CONFORMANCE_VECTOR`, and so
on down.

## Field shape

`conformance_maturity` is a string field carrying one of the five enum
values above. It is optional metadata on a profile doc or a conformance
report — it does not change how `profile_id` is computed
(`SHA-256(JCS(profile_doc))` — see `profiles/profile_registry.py`) and does
not participate in digest recomputation for any other primitive. Adding or
correcting `conformance_maturity` on an existing profile mints a new
profile_id, following the same immutability rule as any other schema change
(see `profile_registry.py` docstring): old docs stay resolvable, they are
never edited in place.

```json
{
  "conformance_maturity": "INDEPENDENTLY_VERIFIED",
  "profile_id": "<sha256-hex, unaffected by this field>",
  "verified_by": "<string, optional — who ran the independent check>"
}
```

## Why this matters

`MUTUAL_CONSISTENCY` and `INDEPENDENTLY_VERIFIED` look identical from a
distance — both produce "two implementations match." The difference is
whether the second implementation could have made the same mistake the
first one did. Two repos from the same author agreeing is one opinion
checked twice. A harness becoming a de facto standard because nobody
distinguished those two cases is the failure this taxonomy exists to name.

## Relationship to existing primitives

- Applies to any profile doc resolved through `profiles/profile_registry.py`
  (e.g. `jcs-rfc8785-v1`, `jcs-rfc8785-action-ref-v1`) and to conformance
  vector sets under `examples/conformance/`.
- Complementary to `evidence-mode-disclosure-ref-v2` — disclosure-ref answers
  "is this evidence hint or anchor"; `conformance_maturity` answers "how far
  up the verification ladder has this specific conformance claim climbed."
