# draft-etcheverry-action-ref-02 — Self-Audit Report
**Date:** 2026-08-15
**Auditor:** Giskard (internal audit, session-based)
**Document audited:** draft-etcheverry-action-ref-02 (Etcheverry & Ives, IETF Independent Submission)
**Implementation audited:** giskard09/argentum-core (`argentum.py`, `mycelium_trails.py`, `jcs.py`, `agent_signing.py`, `plugins/agt_evidence_anchor/`, `examples/conformance/`)
**Method:** self-audit spec↔deploy in both directions + adversarial vectors, inspired by Tora Toraman's self-audit of draft-noa-scitt-ai-agent-receipt-01

---

## Executive Summary

Prompted by Tora Toraman (draft-noa-scitt-ai-agent-receipt), who audited his own 5 verifiers against his spec, found 2 real cases where they accepted things they shouldn't, and published it as-is — this is the same exercise applied to our own I-D before requesting external review from anyone else.

11 normative requirements (MUST/SHOULD) of -02 were checked against the real code serving the production endpoint (`POST /nexus/trail`, the actual entry point for integrators such as SafeAgent), and against the conformance suite.

**Initial pass (2026-08-14 night):** 4/11 enforced correctly, 5/11 documented but not enforced in the production endpoint, 2/11 not applicable / not verifiable with what exists today.

**Remediated same night (2026-08-15, commits `d951116`, `66df348`, `073d1e7`, all CI-green on `main`):** FINDING-001 and the three MEDIUM findings below. Root cause was structural — `/nexus/trail` reimplemented its own validation logic in parallel to the reference validator (`plugins/agt_evidence_anchor/action_ref.py`) instead of calling it, and that duplicate fell behind twice in one night. Fixed at the root by unifying the endpoint onto the shared `_validate_domain`.

**Still open, scope decision pending (not fixed today, documented honestly):** FINDING-002 (`authorization_ref` / three-record-trail, §5 of the draft, does not exist in any endpoint or table) and FINDING-003 (replay protection insufficient per §9.1 without it).

No case was found in the inverse direction — code being stricter than what the spec requires.

**A note on scope, for readers unfamiliar with this project:** FINDING-002 and FINDING-003 below are a **scope decision pending**, not a defect or a regression — the `authorization_ref` / three-record-trail feature they describe has never been built, so there is nothing that broke. Separately, `argentum-core#7` (the joint specification with azender1/SafeAgent referenced elsewhere in this project) is a **shared design document**, not a contractual delivery commitment with a date. Nothing signed with SafeAgent has been missed or breached; these findings describe a feature gap being tracked openly, not a failure to honor an agreement.

---

## Findings

### FINDING-001 — Two accepted `action_ref` derivations on `/nexus/trail`
**Severity:** HIGH
**Status:** REMEDIATED

**Spec:** §3.2 (JCS derivation), §9.4 Operator-Independence Guarantee — a verifier must be able to independently confirm any `action_ref` using one public, deterministic algorithm.

**Description:**
`/nexus/trail` accepted the official JCS-derived `action_ref` (§3.2) and a legacy "colon-separated" scheme (`f"{agent_id}:{action_type}:{scope}:{ts}"`) as interchangeably valid, kept "during transition" per an in-code comment. Two accepted derivations on the same endpoint means an external verifier following the published spec cannot always reproduce a trail the system accepted — the exact failure mode §9.4 exists to prevent.

Same commit also closed a related finding: the endpoint's local `json.dumps(sorted(...))` hashing (not RFC 8785-correct for non-BMP characters) was replaced with the repo's actual `jcs.py` module, which was already correctly implemented but not called from this path.

**Remediation:** `/nexus/trail` now accepts exactly one derivation (JCS via `jcs.py`). Any other `action_ref` is a 422, never a silent accept.

**Retroactive impact (checked against production `trails.db` before the fix):** 2449 trails with a recoverable preimage — 2448 JCS, 0 colon-separated, 1 anomaly (see "SafeAgent trail f07ee520" note below). 296 trails from the 18/5–30/6 window have no preimage saved and are not retroactively classifiable — a known gap in auditability for that window, not a hashing-scheme gap.

**Commit:** `d951116` — `fix(security): FINDING-001 single derivation path + timestamp semantic check (#47)`

---

### MEDIUM — Timestamp grammar-gate was purely lexical
**Severity:** MEDIUM
**Status:** REMEDIATED

**Spec:** §3.4, §9.3 Timestamp Manipulation — "Implementations MUST validate timestamp format at emission time, not only at verification time."

**Description (adversarial vector, Toraman-style):** the only timestamp check anywhere in the repo was a regex (`^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$`) in the reference verifier — it checks digit counts per position, not calendar validity. Confirmed live: `2026-02-30T25:99:99.000Z`, `9999-13-40T99:99:99.999Z`, and `0000-00-00T00:00:00.000Z` all passed. Separately, the production endpoint (`/nexus/trail`) had no timestamp check of any kind at emission time — `str(ts)` was hashed as-is regardless of format.

**Remediation:** part of the same root-cause fix as below — `_validate_domain` now performs real semantic validation (calendar-valid RFC 3339, plus epoch-ms for NEXUS `packet_version 1.0`) and `/nexus/trail` now calls it.

**Commit:** `d951116` (initial fix), `073d1e7` (unification, see root-cause item below)

---

### MEDIUM — Empty `scope` accepted, contradicting the published spec text
**Severity:** MEDIUM
**Status:** REMEDIATED

**Spec:** draft-etcheverry-action-ref-02 §6 (verified against the datatracker): "scope is a free-form non-empty string... Any value is valid as long as it is non-empty" — no exception.

**Description:** the local spec mirror (`action-ref.md`) documented `""` as an explicit "not applicable" exception, and `/nexus/trail` accepted it (default `scope = preimage.get("scope", "")`, no rejection). The repo's own conformance fixture (`recompute-drift-v1`, vector `0003-empty-scope`) certified this as a valid, conformant case — a documentation↔documentation contradiction inside the same project, independent of the spec↔code gap. Retroactive check: 3881 total trails, 4 with empty/null scope, none via `/nexus/trail` — zero existing production data affected by this specific fix.

**Remediation:** local `action-ref.md` corrected to match the published I-D (non-empty, no exception) since the public I-D is the document already committed to externally; fixture `av-007` reverted to reject empty scope.

**Known divergence, not acted on today:** the reverted `av-007` now diverges from a vector in aeoess's own vendorized APS corpus (`examples/conformance/aps/`, mirror not touched), which expects empty scope to be *accepted*. Logged in `IETF_ID_BACKLOG.txt` as a pending ask for next strategy session — not resolved, not ignored.

**Commit:** `66df348` — `fix(security): scope non-empty, align local spec to published I-D (#48)`

---

### Root cause — `/nexus/trail` reimplemented validation instead of calling the reference validator
**Severity:** MEDIUM (process/architecture finding)
**Status:** REMEDIATED

**Description:** the same pattern repeated twice in one night on the same endpoint. `/nexus/trail` never called `_validate_domain` (the reference implementation in `plugins/agt_evidence_anchor/action_ref.py`) for any field — not timestamp, not scope, not agent_id — it reimplemented its own checks in parallel, and that reimplementation fell behind the reference twice: first with the derivation scheme (FINDING-001), then again immediately after with the domain checks the same fixes were supposed to cover.

**Remediation:** fixed at the root instead of patching `/nexus/trail` a third time. `_validate_domain` extended to support both accepted timestamp formats (RFC 3339 and all-digit epoch-ms, per NEXUS `packet_version 1.0`, which the endpoint's own docstring already claimed to accept); `/nexus/trail` now calls the shared validator directly instead of maintaining its own copy.

**Retroactive impact:** of 2450 trails with a recoverable preimage, 2448 RFC 3339, 1 genuine epoch-ms (`nandana-design-partner-test`, within the new supported range), and 1 is the SafeAgent anomaly described below. No legitimate production timestamp breaks under the unified validator.

**Suite:** 130/130 (`tests/` + `plugins/agt_evidence_anchor/tests/`). Fixture `action-ref-v1-domain-negative`: 7/7.

**Commit:** `073d1e7` — `fix(security): unify /nexus/trail on the shared domain validator (#49)`

---

### FINDING-002 — `authorization_ref` / three-record-trail (§5) not implemented in runtime
**Severity:** HIGH
**Status:** OPEN — scope decision pending, not fixed today

**Spec:** §5 in full — Layer Model, `authorization_ref` derivation, the 4 checks in Table 2 (same call instance / same proposed payload / same dispatched payload / same authorization decision). MUST: "`authorization_ref` MUST appear in both the pre-execution record and the receipt"; "The signer of the Decision record MUST be independent of the actor/executor."

**Evidence:** `grep -rn "authorization_ref" argentum.py mycelium_trails.py` returns nothing. The only place `authorization_ref` exists in the repo is a static example fixture (`examples/conformance/guardrail-provider-v1.fixture.json`) with no directory of its own and no executable verifier, unlike the vectors that do have one (`recompute-drift-v1`, `action-ref-v1-domain-negative`).

**Consequence:** §5, which is what the anti-replay mechanism in §9.1 depends on ("a replayed action_ref with a different authorization decision will fail check 4"), is documentation only. No production trail passes through the 4 checks of Table 2 today.

---

### FINDING-003 — Replay protection insufficient on `/nexus/trail`
**Severity:** HIGH
**Status:** OPEN — scope decision pending, not fixed today

**Spec:** §9.1 Replay Attack Surface — "A verifier that checks action_ref alone (without authorization_ref and signature) cannot detect replay. This specification requires both fields for complete replay resistance."

**Evidence:** `/nexus/trail` authenticates solely by recomputing `action_ref` from the preimage. It never calls `_verify_agent_signature` (used elsewhere — `/entity`, `/attest`, `/report`, `/execute`, `/rate`, `/attest` — but not here). Combined with FINDING-002, the endpoint implements exactly the mode §9.1 identifies as insufficient.

**Not verified — marked OPEN, not assumed:** whether a `UNIQUE` constraint on `action_ref` exists at the DB layer, which would at least block exact reinsertion without resolving the underlying gap. Requires reading the `trails` table schema directly — not done in this pass.

---

### FINDING-004 — `scope`-as-hash anti-pattern not enforced (found via SafeAgent trail investigation)
**Severity:** MEDIUM
**Status:** OPEN — not fixed today, next round

**Spec:** `action-ref.md` line 170 (local spec mirror, consistent with draft-etcheverry-action-ref-02 §3.1 Table 1: "scope MUST NOT be a derived hash of the intent object") explicitly prohibits using a hash of the intent object as `scope` — it collapses the field's purpose and breaks recomputability guarantees the same way a colon-separated derivation does.

**Description:** discovered while investigating the SafeAgent trail anomaly below, not during the original 11-requirement sweep. Neither the 2026-08-15 non-empty-scope fix (`66df348`) nor the unified `_validate_domain` (`073d1e7`) checks for this pattern — a syntactically valid, non-empty scope that happens to be a 64-hex-char SHA-256 digest passes today with no rejection. Same family of gap closed overnight for timestamp and derivation: spec states a MUST, validator doesn't check it.

**Not fixed today:** flagged for the next round, not blocking this report.

---

## Note — SafeAgent trail anomaly (f07ee520), investigated per creator's request before publishing

SafeAgent (azender1) is our only Tier 1 Verified Provider with a signed RSA — this anomaly was investigated directly, by name, rather than left as a generic OPEN item, before this report was written.

**Finding:** trail `f07ee520-91c1-44a2-92e2-c09aa031476f` — `agent_id: safeagent-prod`, `operation: test_anchor` (not a real business action_type), `scope` set to a raw SHA-256 hash of the intent object — the exact "scope anti-pattern" `action-ref.md` explicitly documents as breaking recomputability. It is one of a cluster of 7 `test_anchor` trails against `safeagent-prod`, all within a 49-minute window on 2026-06-30, 8 hours before the commit (`b4508eb`) that added preimage storage — consistent with manual testing of the preimage-storage feature against production that same night, before the formal commit. Real SafeAgent business trails (`trade.execute`, `compliance_check`, `submit_action`, `erc20_transfer`) are all outside this cluster and show normal `operation` values. Other integrator traffic in the same 49-minute window (agentoracle-v1, pioneer-agent-001, composed-demo) is unaffected and normal — this is scoped to the 7-trail `safeagent-prod` cluster only, not a systemic issue that night.

**Conclusion:** manual/internal testing artifact, not a real SafeAgent transaction incorrectly recorded. No integrity implication for azender1's actual data. Not escalated to the client — consistent with the creator's stated criterion (migration/testing artifact with no integrity implication today → documented as a technical note, not an alarm).

**Residual uncertainty, stated honestly:** whether the test traffic was generated by us or by azender1 testing their own integration cannot be confirmed with 100% certainty — no request-level logs or source IP from that window were available 6+ weeks later. The naming pattern (`test_anchor`, and an identical `anchor.test` label on 2026-06-04) and the scope-as-hash pattern strongly suggest deliberate technical testing either way, not a client data error.

---

## Requirements Verified and Confirmed Correct

- **§3.2/§3.3 SHA-256(JCS) derivation** — correctly implemented in `jcs.py`; spec example A.1 (`nexus-oracle-signal`) reproduced byte-identical by `action-ref-v1-baseline.fixture.json`.
- **Field-order-drift and payload-drift negative vectors** — 9/9 pass fail-closed in `recompute-drift-v1/verify.py`.
- **§8 Telemetry / Instrumentation Point** — out of scope for this audit; depends on third-party instrumentation code outside argentum-core, not evaluated.
- **No case found where the code requires something the spec does not ask for** (inverse direction). The dominant pattern throughout is the opposite: the code was looser than the spec, not stricter, in every finding above.

## Not Applicable / Not Evaluated

- **§6 multi-value scope segments** (MUST on lexicographic sort + no-space join) — no code path constructs or validates multi-value scopes today; nothing to evaluate against something not in use.
- **Namespace-prefix convention** (`<emitter>:<scope>`) — RECOMMENDED, not MUST, per the spec itself. Not exigible by design.
- **Conformance suite not wired to CI** — `.github/workflows/provider-conformance.yml` only triggers on changes under `examples/conformance/provider-protocol/**`. The vectors that actually exercise -02 §7 (`recompute-drift-v1`, `action-ref-v1-baseline`, `action-ref-v1-domain-negative`) are not hooked to CI — run manually today. Process gap, not a code gap; flagged as a follow-up for Auditoría, not blocking for this report.

---

## Summary

| # | Item | Severity | Status |
|---|------|----------|--------|
| FINDING-001 | Two accepted action_ref derivations | HIGH | REMEDIATED (`d951116`) |
| — | Timestamp grammar-gate purely lexical | MEDIUM | REMEDIATED (`d951116`, `073d1e7`) |
| — | Empty scope accepted | MEDIUM | REMEDIATED (`66df348`) |
| — | `/nexus/trail` duplicated validation logic (root cause) | MEDIUM | REMEDIATED (`073d1e7`) |
| FINDING-002 | `authorization_ref` / three-record-trail not implemented | HIGH | OPEN |
| FINDING-003 | Replay protection insufficient without §5 | HIGH | OPEN |
| FINDING-004 | scope-as-hash anti-pattern not enforced | MEDIUM | OPEN — next round |
| — | UNIQUE constraint on `action_ref`? | — | OPEN (unverified) |
| — | SafeAgent trail f07ee520 | — | RESOLVED (testing artifact, documented, not escalated) |
| — | av-007 / aeoess APS corpus divergence on empty scope | — | Logged in IETF_ID_BACKLOG.txt, not acted on |
| — | Conformance suite not in CI | — | Flagged for Auditoría, not blocking |

**Overall status: PARTIAL GREEN.** The three concrete integrity gaps identified against the production endpoint (double derivation scheme, unvalidated timestamps, unenforced non-empty scope) were fixed the same night, at the root, with CI green on `main`. Two architectural gaps remain open by design decision, not oversight — §5 (authorization_ref / three-record-trail) is not implemented, and replay protection is correspondingly incomplete. These are acknowledged here as HIGH and unresolved, not minimized.

---

*This report was generated during an internal self-audit session, prompted by no external actor. It is not a substitute for professional third-party review. Per this project's standing rule on public documents (see the 2026-08-05 Art.12 dictamen), it is published as-is — including the open HIGH findings — rather than held back or softened before external reviewers see it.*
