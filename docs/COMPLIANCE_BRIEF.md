# Mycelium Trails — Compliance Brief

**Version:** 1.0 — 2026-05-15 — Approved for due diligence  
**Audience:** Compliance officers — banking, insurance, regulated enterprise  
**Prepared by:** Mycelium Trails

---

## What is Mycelium Trails

Mycelium Trails is an immutable registry for AI agent activity. Each action executed by an agent produces a signed record anchored on an external surface outside the operator's infrastructure — preventing the record from being modified or deleted after the fact. The result is an evidence trail that third parties can audit without depending on the operator's infrastructure.

## What problem it solves

AI systems operating in regulated environments generate internal logs. The problem: those logs live inside the operator's own infrastructure — they can be rewritten, deleted, or reconstructed before an audit. Mycelium Trails closes that gap: the hash of each evidence record is written to an external append-only system at execution time. After that point, any modification to the record is detectable by an independent auditor — without access to the operator's runtime or prior trust in it.

## Technical guarantee — scope and limit

**What Mycelium Trails proves:** that the evidence record existed, unmodified, at the time of anchoring. An external verifier can confirm this without accessing the operator's systems.

**What Mycelium Trails does not prove:** that the content of the record was correct at the time of writing. The guarantee is tamper-evidence, not content correctness. This distinction matters in contexts where the regulator evaluates both log integrity and the veracity of what was recorded.

---

## Regulatory mapping

| Framework | Relevant requirement | How Mycelium Trails addresses it | Legal status |
|-----------|---------------------|----------------------------------|--------------|
| **EU AI Act Art. 12** (enforcement: 2 August 2026) | Automatic logging of high-risk AI system operation, retained to allow supervision by competent authority. | Each agent action produces a signed record anchored externally. The record is auditable by the competent national authority without operator access. Note: Art. 12 requires automatic logging; tamper-evidence is a necessary but not sufficient condition for full compliance. See note (1). | **[LEGAL-OK]** Mycelium "supports" Art. 12 — does not "satisfy" it alone. |
| **SOC 2 CC7.x** (Change Management / Incident Response) | Detection of unauthorized changes to system components and integrity evidence in audit reviews. | External anchoring allows detection of any post-write modification to the evidence record. The auditor runs independent verification without depending on the operator. | **[LEGAL-OK]** |
| **ISO 27001 A.12.4** (Logging and Monitoring) | Protection of event logs against modification or unauthorized access. | The record cannot be altered without the system detecting the discrepancy at verification time. Protection is structural, not dependent on the operator's internal access controls. | **[LEGAL-OK]** |
| **FCA SYSC 9.1** (Recordkeeping — UK financial services) | Retention of sufficient records for the FCA to supervise compliance during the applicable period. | Mycelium generates records the FCA can verify independently. However, "sufficiency" under SYSC 9.1 also includes content and retention period. The system covers integrity but does not define retention policy: must be configured by the operator per the financial instrument. See note (2). | **[REVIEW]** |
| **Basel III / BCBS 239** (Risk Data Aggregation) | Auditable data lineage by the regulator, independent of the reporting firm. | The evidence trail covers who executed what action, when, and with what result. External anchoring allows the regulator to verify lineage without depending on the bank's infrastructure. | **[LEGAL-OK]** |

---

## Current status

The Mycelium Trails architecture is under review in the Microsoft agent-governance-toolkit repository (EvidenceAnchor proposal, v3 under active review by maintainers). The plugin interface is specified; integration as the on-chain anchoring backend follows the community contribution process.

---

## Legal notes

### (1) EU AI Act Art. 12 — "supports" vs "satisfies"

Art. 12.1 requires the system to "automatically record events" and for those records to be "sufficient to identify the reasons for the system's outputs." Mycelium Trails guarantees that existing records cannot be altered — but does not determine what gets recorded or at what granularity. Full Art. 12 compliance also requires: (a) that the operator configures logging at adequate granularity, and (b) that the records contain the fields the article enumerates.

Mycelium Trails "supports" Art. 12 on the integrity and independent auditability component. It does not "satisfy" the article on its own.

**Recommendation:** in any external communication, use "supports compliance with" or "supports adherence to" — never "satisfies" or "ensures compliance." The difference is material before a regulator.

### (2) FCA SYSC 9.1 — retention policy

SYSC 9.1 establishes retention periods that vary by financial instrument type (e.g., 5 years for most MiFID II instruments). Mycelium Trails guarantees record integrity but does not define or manage retention policy. The operator must configure explicitly how long anchored records are retained and in which backend.

Without a documented retention policy, an FCA audit may question compliance even if records are intact. Mycelium Trails is to retention policy what a database is to backup policy: the system enables configuration; the operator owns the decision.

For UK financial services clients: retention policy is an implementation conversation, not a product gap. The system supports any retention period the operator configures.

---

## Executive summary for joint review

- 4 of 5 rows: **[LEGAL-OK]**
- 1 row: **[REVIEW]** — FCA SYSC 9.1, retention policy is operator responsibility. Known gap, documented, non-blocking.
- EU AI Act: approved with precision note on "supports" vs "satisfies"
- Brief approved for due diligence. For UK financial services clients: retention policy is resolved at implementation, not at the product level.
