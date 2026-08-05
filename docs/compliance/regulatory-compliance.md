# Mycelium Trails — Regulatory Compliance Mapping

**Version:** 1.2 — 2026-08-05 — Corrects citation error in Note (1) (v1.1, 2026-05-19)  
**Prepared by:** Legal, Rama (v1.1 approved for due diligence 2026-05-16, published to main 2026-05-19)

**Changelog:** v1.1 Note (1) misquoted Art. 12.1 as requiring records "sufficient to
identify the reasons for the outputs of the system." That language does not appear
in the enacted text. Corrected to reflect the actual three-paragraph structure
(automatic event logging / linkage to Art. 79(1), 72, 26(5) oversight / minimum
content fields limited to Annex III(1)(a) remote biometric identification).

**Other changes in v1.2**, none of which widen any assertion made in v1.1:
(1) EU AI Act Art. 12 is now **in force** (2 August 2026) — v1.1 described it prospectively;
(2) a new Note (3) records that **no harmonised technical standard for Art. 12 has been
finalised**;
(3) Current Status corrected — AGT PR #2415 was closed without merge.
The "supports, not satisfies" constraint from v1.1 is unchanged and governs this revision.

---

## Legal Notice

This document is informational. It does not constitute legal advice or a guarantee
of regulatory compliance. Recipients should obtain independent legal advice regarding
requirements applicable to their jurisdiction and activities. Rama assumes no
liability for decisions made based on this document without independent verification.

## Trademark Notice

"Mycelium Trails" and "Rama" are descriptive service and company names. Neither is
currently registered as a trademark with USPTO, EUIPO, or UKIPO.

---

## What Mycelium Trails Is

Mycelium Trails is an immutable audit-trail system for AI agent activity. Every
action executed by an agent produces a signed record anchored to an external surface
outside the operator's control — making the record tamper-evident after the fact.
The result is an evidence trail auditable by third parties without depending on the
operator's infrastructure.

## What Problem It Solves

AI systems operating in regulated environments produce internal logs. The problem
is that those logs live in the operator's own infrastructure: they can be rewritten,
deleted, or reconstructed before an audit. Mycelium Trails closes that gap: the hash
of each evidence record is written to an external append-only surface at execution
time. After that point, any modification to the record is detectable by an
independent auditor — without access to the operator's runtime or any prior trust in it.

## Why Operator-Signed Receipts Are Not Enough

Several audit-trail systems for AI agents generate receipts that are signed by the operating platform itself. This is the structural gap: if the signer and the operator are the same entity, a receipt proves that *someone with the operator's key* attested to an event — not that the event occurred, not that the record has not been rewritten, and not that the operator is telling the truth. Offline verification means trusting the operator.

EU AI Act Art. 12 requires that logs be available to the *competent national authority*, which implies independent verification — the authority cannot depend on the operator's infrastructure or key material to assess whether a high-risk system behaved as documented. FCA SYSC 9.1 similarly requires records "sufficient for the FCA to supervise compliance," which presupposes that the FCA can verify record integrity without relying on the firm's own attestation.

Mycelium Trails separates the verifier from the operator by design: the action_ref is derived client-side (SHA-256 over a JCS-canonical preimage), and the hash is anchored on a public blockchain before the record is submitted. A regulator, counterparty, or auditor verifies by recomputing the hash from the preimage fields and confirming the on-chain anchor — no operator key, no operator infrastructure, no operator trust required.

## Technical Guarantee — Scope and Limits

**What Mycelium Trails proves:** that the evidence record existed, unmodified, at
the time of anchoring. An external verifier can confirm this without accessing the
operator's systems.

**What Mycelium Trails does not prove:** that the record's content was accurate at
the time of writing. The guarantee is tamper-evidence, not content correctness. This
distinction matters in contexts where the regulator evaluates both log integrity and
the truthfulness of what was recorded.

---

## Regulatory Mapping

| Framework | Relevant Requirement | How Mycelium Trails Addresses It | Legal Status |
|-----------|---------------------|----------------------------------|-------------|
| **EU AI Act Art. 12** (**in force since 2 Aug 2026**) | Automatic recording of events (logs) over the system lifetime, enabling traceability appropriate to the intended purpose — specifically for risk identification (Art. 79(1)), post-market monitoring (Art. 72), and deployer monitoring (Art. 26(5)). | Each agent action produces a record with a signed, externally-anchored hash. The record is auditable by a party that did not produce it, without operator access. *Note: Art. 12 mandates that logs exist and be relevant; it does not prescribe tamper-evidence or any verification mechanism. See Note (1) for what the article does and does not say, and Note (3) on the absence of a harmonised standard.* | **[LEGAL-OK]** Mycelium "supports" Art. 12 — does not "satisfy" it alone. |
| **SOC 2 CC7.x** (Change Management / Incident Response) | Detection of unauthorized changes to system components and integrity evidence in audit reviews. | External anchoring enables detection of any post-write modification to the evidence record. The auditor runs independent verification without relying on the operator. | **[LEGAL-OK]** |
| **ISO 27001 A.12.4** (Logging and Monitoring) | Protection of event logs against modification or unauthorized access. | Records cannot be altered without the system detecting a discrepancy on verification. Protection is structural — does not depend on the operator's internal access controls. | **[LEGAL-OK]** |
| **FCA SYSC 9.1** (Recordkeeping — UK financial services) | Retention of records sufficient for the FCA to supervise compliance, for the applicable period. | Mycelium generates records the FCA can verify independently. However, "sufficiency" under SYSC 9.1 also encompasses content and retention period. The system covers integrity but does not define retention policy — that must be configured by the operator per the financial instrument. See Note (2). | **[REVIEW]** Retention policy is operator responsibility. |
| **Basel III / BCBS 239** (Risk Data Aggregation) | Auditable data lineage, verifiable by the regulator independently of the reporting firm. | The evidence trail covers who executed what action, when, and with what outcome. External anchoring allows the regulator to verify lineage without depending on the reporting bank's infrastructure. | **[LEGAL-OK]** |

---

## Notes

### (1) EU AI Act Art. 12 — what it says, what it does not, and "supports" vs "satisfies"

**Correction (v1.2).** v1.1 of this document attributed to Article 12.1 a requirement that
records be *"sufficient to identify the reasons for the outputs of the system."* **That
phrase does not appear in the enacted Article 12.** It was carried over from earlier
drafting and should not be relied upon. Corrected against the enacted text:

- **Art. 12(1)** — high-risk AI systems "shall technically allow for the automatic recording
  of events (logs) over the lifetime of the system."
- **Art. 12(2)** — logging capabilities shall enable recording of events relevant for
  (a) identifying situations that may result in a risk within the meaning of Art. 79(1) or in
  a substantial modification; (b) facilitating post-market monitoring under Art. 72;
  (c) monitoring the operation referred to in Art. 26(5).
- **Art. 12(3)** — enumerates minimum log contents (period of each use, reference database,
  matched input data, identification of the natural persons involved in verification per
  Art. 14(5)) **only for systems under Annex III point 1(a)** — remote biometric
  identification. These minimums are not general obligations for all high-risk systems.

**What the article does not say.** Article 12 does not require tamper-evidence, cryptographic
integrity, external anchoring, third-party recomputability, or any specific verification
mechanism. Any claim that it does is unsupported by the text. Overstating this is a
material risk: a mapping that inflates the legal hook is discredited by the first lawyer
who reads the Official Journal alongside it.

**Where the structural gap actually is — and it is real without exaggeration.** All three
limbs of Art. 12(2) describe logs consumed by a party that did not produce them: a market
surveillance authority acting on risk (Art. 79(1)), post-market monitoring reaching the
provider (Art. 72), and a deployer monitoring operation (Art. 26(5)). Art. 12(3)(d) goes
further and requires identifying the natural persons who verified results. The Regulation
therefore creates demand for logs read by third parties **and specifies no mechanism by
which such a reader gains assurance that the log was not rewritten before they saw it.**
That silence is the gap this system addresses. The gap is in the verification path, not in
the text of the obligation — and it should always be stated that way.

*This observation describes a structural feature of the enacted text, not a legal opinion on
enforcement risk or regulatory intent.*

Mycelium Trails guarantees that existing records cannot be altered undetectably — but it
does not determine what is recorded or at what granularity. Full Art. 12 adherence also
requires that the operator configure logging at adequate granularity and that records carry
whatever fields apply to the system's Annex III classification.

Mycelium Trails **supports** Art. 12 on the integrity and independent-audit component.
It does not **satisfy** the article alone.

**Recommendation:** In all external communications, use "supports compliance with" or
"supports adherence to" — never "satisfies" or "ensures compliance." Do not characterise
tamper-evidence as an Art. 12 requirement. The difference is material before a regulator.

### (2) FCA SYSC 9.1 — Retention Policy

SYSC 9.1 establishes retention periods that vary by financial instrument type
(e.g. 5 years for most MiFID II instruments). Mycelium Trails guarantees record
integrity but does not define or manage retention policy. The operator must explicitly
configure how long anchored records are retained and in which backend. Without a
documented retention policy, an FCA audit may question compliance even if records
are intact.

This is an operator configuration gap, not an architecture gap. For UK financial
services clients, retention policy is an implementation conversation, not a product
limitation.

### (3) No harmonised technical standard exists for Art. 12 (as at 2026-08-05)

Article 12 has been in force since 2 August 2026, but the technical standards intended to
give it operational shape are **not yet published**. ISO/IEC 24970 (AI system logging)
reached **FDIS** — the final approval stage — in June 2026; it is close to publication, not
early-stage. prEN 18229-1 (AI logging and human oversight) remains at prEN stage.

That distinction matters and cuts against us: the gap described here is narrowing, not open
indefinitely. Verify the current stage before relying on this note — it is a statement about
a third party's process, which changes without notice to us.

Two consequences, and they pull in opposite directions:

- **For an operator today**, there is a binding obligation with no settled specification to
  implement against. Anything adopted now is a good-faith interpretation, and should be
  documented as such rather than presented as conformity.
- **For this project**, the absence of a settled standard is not a licence to position
  `action_ref` as *the* answer to Art. 12. It is not, and no artefact of ours should imply
  it. What can be stated accurately is narrower and still useful: the assurance path
  described in Note (1) is unaddressed by the Regulation and unresolved by the draft
  standards, and a content-addressed, externally-anchored record is one way to close it that
  does not require the reader to trust the operator.

Absence of a harmonised standard does not transfer regulatory risk from the operator to Rama.

When either standard is finalised, this note and the Art. 12 row must be re-reviewed —
including the possibility that the settled approach diverges from ours.

*This observation describes a structural feature of the enacted text, not a legal opinion on
enforcement risk or regulatory intent.*

---

## Current Status

*Verified against primary sources on 2026-08-05.*

- [argentum-core](https://github.com/giskard09/argentum-core) specification published, with conformance fixtures under `examples/conformance/` verifiable at `https://argentum-api.rgiskard.xyz/trails/verify`
- Mycelium Providers in production (see [PROVIDERS.md](../../PROVIDERS.md)): azender1 / SafeAgent (Verified Provider, since 2026-06) and TKCollective / AgentOracle + AgentTrust (Declared Provider, since 2026-06)
- Conformance tooling published as a pinned GitHub Action: [giskard09/action-ref-conformance](https://github.com/giskard09/action-ref-conformance) — the claim is a green run against the frozen `action-ref-v1-jcs-sha256` profile, not a badge
- action_ref derivation (JCS RFC 8785 + SHA-256) cross-validated by independent implementations built without reference to ours
- **Correction to v1.1:** AGT PR [microsoft/agent-governance-toolkit#2415](https://github.com/microsoft/agent-governance-toolkit/pull/2415) was listed as "open for review". It is **closed without merge**. It should not be cited as an integration in progress.

---

## Executive Summary

| | |
|---|---|
| Frameworks reviewed | 5 |
| **[LEGAL-OK]** | 4 |
| **[REVIEW]** | 1 (FCA SYSC 9.1 — retention policy is operator configuration, not a product gap) |
| EU AI Act language | Approved with precision note: "supports" not "satisfies" — and, as of v1.2, never "Art. 12 requires tamper-evidence" |
| Art. 12 status | In force since 2026-08-02. No harmonised technical standard finalised (Note 3) |
| Approved for | Due diligence with compliance officers (banking, insurance, regulated enterprise) |
| Pending | Legal re-review of the corrected Note (1) and the new Note (3) |

---

*For questions about this mapping, open an issue in [argentum-core](https://github.com/giskard09/argentum-core/issues).*
