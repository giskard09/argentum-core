# EU AI Act Art. 12 — notes on log integrity and the verification path the Article leaves unspecified

**These are not Article 12 conformance vectors.** Article 12 prescribes no technical
mechanism, so conformance vectors for it cannot exist, and any artefact claiming to be one
should be treated with suspicion — including ours.

What this fixture exercises is narrower and real: **can a party that did not produce a log
record determine that the record was not rewritten before they read it?**

## Why that question, and why it is not invented

Article 12 has been in force since 2 August 2026. Read against the enacted text:

- **Art. 12(1)** — high-risk AI systems "shall technically allow for the automatic recording
  of events (logs) over the lifetime of the system."
- **Art. 12(2)** — logging shall enable recording of events relevant for (a) identifying
  situations that may result in a risk within the meaning of **Art. 79(1)** or in a
  substantial modification; (b) facilitating post-market monitoring under **Art. 72**;
  (c) monitoring the operation referred to in **Art. 26(5)**.
- **Art. 12(3)** — enumerates minimum log contents, **only for Annex III point 1(a)** systems
  (remote biometric identification): period of each use, reference database, matched input
  data, and identification of the natural persons involved in verification per Art. 14(5).

All three limbs of 12(2) describe a log consumed by someone who did not produce it — a market
surveillance authority, a provider receiving post-market signals, a deployer monitoring
operation. Article 12(3)(d) goes further and names a human verifier who must be identifiable.

**The Regulation creates demand for logs read by third parties and specifies no mechanism by
which such a reader can confirm that the log was not rewritten.** That silence is the gap.
It is in the verification path, not in the text of the obligation, and it should always be stated
that way.

As at 2026-08-05 the harmonised standards intended to give Art. 12 operational shape —
**prEN 18229-1** (AI logging and human oversight, still at prEN stage) and **ISO/IEC 24970**
(AI system logging) — are not yet published. ISO/IEC 24970 reached **FDIS**, the final
approval stage, in June 2026: it is close to publication, not early-stage.

That cuts against the case for this fixture, so it is stated plainly: the gap is narrowing.
Publishing a concrete, checkable interpretation openly is still worthwhile; presenting one as
settled, or implying the vacuum is durable, is not. Both stages are third-party process
states that change without notice to us — verify before relying on this paragraph.

## What these vectors demonstrate

A synthetic log record shaped after Art. 12(3)(a)–(d). That shape is used because it is the
one place the Article is concrete — not as a claim that those fields are required of all
high-risk systems. The record digest is `SHA-256(JCS(record))`, recomputable by anyone
holding the record.

| id | what it checks | result |
|----|----------------|--------|
| `a12-001` | a reader who did not produce the record recomputes the digest and matches the externally anchored value, using no operator key and no operator infrastructure | PASS |
| `a12-002` | `human_verifier_ref` (Art. 12(3)(d)) is inside the hashed preimage, so substituting the verifier after the fact changes the digest | PASS |
| `a12-003` | `use_end` moved 6.8 s later to make a human verification window appear compliant; nothing else altered | FAIL (`RECORD_MODIFIED_AFTER_ANCHOR`) |
| `a12-004` | the operator re-signs the modified record with a key that genuinely validates — signature check accepts, recomputation against the anchor still rejects | FAIL (`RECORD_MODIFIED_AFTER_ANCHOR`) |
| `a12-005` | the verifier is denied the operator public key, API credentials and infrastructure access, and still reaches a determinate verdict | PASS |
| `a12-006` | non-ASCII verifier identifier — outside the profile domain of [`action-ref.md`](../../../docs/spec/action-ref.md); rejected before any digest comparison, never canonicalised on a best-effort basis | FAIL (`OUT_OF_PROFILE_DOMAIN`) |

`a12-004` is the one that matters most. A receipt signed by the operator proves that someone
holding the operator's key asserted the record — not that the record is the one that existed
at the time of the event. If the signer and the operator are the same entity, offline
verification means trusting the operator. That is the distinction the whole fixture exists to
make legible.

## What this does not prove

- **It does not make anything compliant.** Passing these vectors has no bearing on adherence
  to Art. 12 or any part of the AI Act. Article 12 adherence also requires that the operator
  log at adequate granularity and carry whatever fields apply to the system's Annex III
  classification — neither of which this mechanism determines.
- **Art. 12 does not require tamper-evidence**, anchoring, or third-party recomputability.
  Any claim that it does is unsupported by the text.
- **Binding is not identity assurance.** `a12-002` proves `human_verifier_ref` was not
  substituted. It says nothing about whether that identifier is truthful.
- **Integrity is not correctness.** These vectors show that a record was not altered after
  anchoring. They say nothing about whether its contents were accurate when written — the
  same restraint `action_ref` applies to content versus intent.
- **No transaction hash is asserted.** This fixture is anchor-agnostic and its records are
  synthetic. Live anchoring, with a real transaction, is shown in the worked-example
  repositories.

## Running it

```
python3 verify.py       # recomputes every digest from the raw record; exit 0 = all as declared
python3 build_vectors.py  # regenerates vectors.json; no digest is ever written by hand
```

Zero dependencies. No network in the trust path.

## Status

Published as one interpretation, offered for disagreement. If prEN 18229-1 or ISO/IEC DIS
24970 settle on a different approach, this fixture and the corresponding note in
[`docs/compliance/regulatory-compliance.md`](../../../docs/compliance/regulatory-compliance.md)
must be re-reviewed — including the possibility that the settled approach diverges from ours.

Independent cross-verification is welcome and wanted. The pattern we use for it is in
[`composed-decision-chain-recompute`](../composed-decision-chain-recompute/): a second
implementation built without reference to this one, compared on the negatives first.
