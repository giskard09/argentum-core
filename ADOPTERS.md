# Adopters

Public evidence for the traction figure cited externally (decks, pitch materials). Every entry
below is independently checkable — no self-reported claim is counted without a link a third
party can verify directly. Tiered by evidence strength, not flattened into one number.

Corrected 2026-08-09 after an external independent re-audit (rhein1/agoragentic-integrations#244)
found the previous flat "8" mixed four different evidence tiers and included one entry that had
explicitly declined to integrate. See MOAT.txt / RETROSPECTIVA.txt for the full account.

**Kind** (added 2026-08-21): tier alone does not say what the "green" actually proves. Each entry
below is tagged with what evidence it is:

- **(a) Reproduction** — a third party ran/vendorized *our own* checkers or fixture vectors.
  Confirms the file runs on another machine. Does not confirm an independent implementation.
- **(b) Independent implementation** — code written from the spec, without depending on our
  checkers or vectors as the source of truth, that is then validated (by their own tests, our
  conformance suite, or a byte-match against our published canonical example). Strongest signal.
- **(c) Spec-text adoption** — citing/adopting the specification's design or terminology as
  reference material, without shipping runnable code that implements or tests it.

---

## Tier 1 — Verified Provider (production trails submitted to ARGENTUM, independently verified)

### SafeAgent

**Contact:** [azender1](https://github.com/azender1)
**Use case:** `action_ref` derivation + x402 settlement on Base mainnet.
**Evidence:** Joint spec [argentum-core#7](https://github.com/giskard09/argentum-core/issues/7), [ucsandman/DashClaw#105](https://github.com/ucsandman/DashClaw/issues/105). Reference deployment: $0.001 USDC on Base mainnet, block 45907183. Real trading use ($3,600 notional blocked), stack published in Microsoft AutoGen.
**Status:** Verified Provider (production).
**Kind:** N/A — production trail submission, not a conformance test. Strongest possible evidence class (real on-chain use), outside the (a)/(b)/(c) scale which is specifically about conformance-checker evidence.

---

## Tier 2 — Independent spec adoption (merged into the partner's own codebase; not a production-trail submission to ARGENTUM)

### CTEF — Cross-Extension Trust Framework

**Contact:** [kenneives](https://github.com/kenneives)
**Use case:** `urn:mycelium:trail` confirmed as official namespace in CTEF v0.3.3, `custody-ref-v1.2` adopted as their own reference implementation. REQUIRED as of CTEF v0.4.
**Evidence:** [AgentAvow/AgentAvow PR #20](https://github.com/AgentAvow/AgentAvow/pull/20) — 3 conformance vectors, byte-match. Independent follow-up, 2026-09-21: [giskard09/draft-etcheverry-action-ref PR #8](https://github.com/giskard09/draft-etcheverry-action-ref/pull/8) ("AgentAvow" author-set) and [PR #9](https://github.com/giskard09/draft-etcheverry-action-ref/pull/9) ("AgentGraph" author-set) — kenneives's own JCS canonicalizer and independently generated vectors (own files `agentavow-jcs-v1-vectors.json` + `verify.py`, not vendored from us), submitted as a third-party author-set directly into our own conformance repo rather than the reverse.
**Status:** Merged 2026-07-23 (PR#20); 2026-09-21 (PR#8, PR#9).
**Kind:** (a) reproduction for PR#20 — re-checked 2026-08-21: authored by us (giskard09), submitting our own `examples/conformance/` vectors to fill the CTEF matrix placeholder. Confirms the namespace/reference-impl designation was accepted into their matrix, not that a third party independently reimplemented and validated `action_ref`. PR#8/#9 are separate, stronger evidence: **(b) independent implementation** — kenneives's own canonicalizer and vectors, contributed as an adversarial third-party author-set to our own repo.

### Agent Passport System (APS)

**Contact:** [aeoess](https://github.com/aeoess)
**Use case:** `action_ref` implemented directly in their own codebase.
**Evidence:** [`src/core/action-ref.ts`](https://github.com/aeoess/agent-passport-system/blob/main/src/core/action-ref.ts). Also: [aeoess/agent-passport-system PR #24](https://github.com/aeoess/agent-passport-system/pull/24) — TrailRecords as on-chain persistence layer. **2026-08-30:** [Agent-Authority-Conformance/aps-conformance-suite PR #42](https://github.com/Agent-Authority-Conformance/aps-conformance-suite/pull/42) ("Ingest argentum-action-ref-v1v2 external-system vector family"), authored by us, merged by aeoess (merge commit `7b16a09`) into APS's own third-party-facing conformance suite — our action_ref vector family is now a permanent fixture family there, not a one-off PR.
**Status:** Real code, in production repo. Permanent fixture family in a governed third-party conformance suite as of 2026-08-30.
**Kind:** (b) independent implementation. Re-checked 2026-08-21: `action-ref.ts` is TypeScript written from their own I-D (`draft-pidlisnyi-aps-03`), own preimage type (`ActionRefIntent`), own canonicalizer (`canonical-jcs.js`) — no dependency on our code or fixtures. Same evidence class as `astrogilda/a2a-tck#228`. PR#42 is a distinct, stronger kind of evidence on top: not a reimplementation but our own vector family merged, by the project's maintainer, into its canonical conformance suite as a permanent fixture.

### AXES

**Contact:** [magentixai](https://github.com/magentixai)
**Use case:** `custody-ref-v1.2` cited and adopted as reference implementation for interop.
**Evidence:** [`docs/interop/x402-and-anchoring.md`](https://github.com/magentixai/axes/blob/main/docs/interop/x402-and-anchoring.md) cites `action_ref` explicitly.
**Status:** Real code, in production repo.
**Kind:** (c) spec-text adoption. Re-checked 2026-08-21: the doc cites `actionRef` (JCS + SHA-256 frozen content-addressed) as reference material for their evidence-lane layering, explicitly informative/non-normative. No AXES code implements or tests `action_ref` — "Real code, in production repo" (Status line above) describes the AXES repo generally, not action_ref-specific code. Status wording should not be read as implementation evidence for this row.

### trustless-ai WG — Mycelium AnchorRegistry (Node 4)

**Contact:** [TMerlini](https://github.com/TMerlini) (maintainer), WG members babyblueviper1/Pavlo/Jimmy Shi.
**Use case:** AnchorRegistry (CREATE2, `0x49fEcA52bC634a9Ab773226D16619deC547794aa`) registered and operating as **Node 4** inside `trustless-ai/cross-reference-console`, the WG's cross-implementation trust mesh. Different Mycelium primitive from `action_ref` — listed here because mesh membership is itself public, independently checkable evidence of real external integration.
**Evidence:** [PR #3](https://github.com/trustless-ai/cross-reference-console/pull/3) (Node 4 registration) and [PR #4](https://github.com/trustless-ai/cross-reference-console/pull/4) (first `crc.cell.v1` Cell), both merged 2026-08-07. Protocol design participation: [PR #8](https://github.com/trustless-ai/cross-reference-console/pull/8) ("derive lane distinctness instead of trusting the label"), merged 2026-08-07 — our review comment cited `action_ref`/`decision_binding_ref`/`anchoring-precedence-ref-v1` discipline directly in the design discussion that shaped the merged fix.
**Status:** Node 4 live and merged, 2026-08-07.
**Kind:** N/A — infrastructure-node registration + co-design participation, outside the (a)/(b)/(c) conformance-checker scale (same reasoning as the SafeAgent Tier 1 entry above).

### astrogilda — GenAI-Security-Project/agent-control-standard

**Contact:** [astrogilda](https://github.com/astrogilda)
**Use case:** formal co-authorship of `cross-system-verification-v1`, a conformance contract in a third-party AI governance ledger spec. We authored the canonical contract (witness_scope/basis enumeration); astrogilda brought the fail-closed validator and negative vectors (branch `basis-method-conformance`, commit `f451b00`: 21 vectors / 25 negative controls / 13 mutants, CI green).
**Evidence:** [GenAI-Security-Project/agent-control-standard#33](https://github.com/GenAI-Security-Project/agent-control-standard/issues/33) — astrogilda's explicit acceptance, [comment](https://github.com/GenAI-Security-Project/agent-control-standard/issues/33#issuecomment-5466354059) ("Co-author, yes..."), 2026-08-30. Our half merged in our own repo: [argentum-core PR #75](https://github.com/giskard09/argentum-core/pull/75) (`peer-reconciliation-ref-v1`), 2026-08-31, cross-validated against her fixtures in the same issue thread.
**Status:** Co-authorship declared and sustained, 2026-08-30 onward (active thread as of 2026-09-27).
**Kind:** N/A — declared co-authorship of a third-party governance artifact, outside the (a)/(b)/(c) conformance-checker scale. Not a production-trail submission, nor a reimplementation that passes our own checker — a distinct evidence class: the partner explicitly named us co-author, in their own repo, of a joint technical contract.

---

## Tier 3 — Independently verified conformance implementation (passes `action-ref-conformance@v1` via pinned CI; explicitly NOT a Provider — no production trails submitted)

### whawk46 (flareclaw-verifier)

**Evidence:** [flareclaw-conformance](https://github.com/whawk46/flareclaw-conformance), pinned CI run [30819828942](https://github.com/whawk46/flareclaw-conformance/actions/runs/30819828942), conclusion `success`.
**Status:** Verified conformant implementation. Never sent production trails — not a Provider, listed separately by design in [PROVIDERS.md](PROVIDERS.md).
**Kind:** (b) independent implementation. Re-checked 2026-08-21: `canonical-json.ts`/`action-ref-cli.ts` are their own code (not vendored from us), validated blind against our pinned `action-ref-conformance@v1` Action and vectors — same shape as running a third-party test suite against your own implementation, not reproducing our checkers on their machine.

### vstantch (aps-conformance-suite)

**Evidence:** [vstantch/aps-conformance-suite](https://github.com/vstantch/aps-conformance-suite) vendorizes our fixtures directly (`runners/ts/sk-function-invocation/test-fixtures/argentum-core/{near-miss-v1.fixture.json, recompute-drift-v1-positive/negative.fixture.json, PROVENANCE.md}`), separate fork of this repo. Hash byte-identical.
**Status:** Verified conformant implementation, not confirmed production.
**Kind:** (a) reproduction. Re-checked 2026-08-21: confirmed via repo tree — files are byte-identical vendored copies of our own fixtures, not an independently written verifier. Also corrects a stale path: "PR#13 merged" and the old `test-fixtures/argentum-core` path (no leading `runners/ts/sk-function-invocation/`) do not resolve against the live repo — fixed to the real path above; PR reference dropped, not found.

---

## Tier 4 — Declared Provider (self-reported, not yet independently verified by us)

### TKCollective — AgentOracle + AgentTrust

**Contact:** [TKCollective](https://github.com/TKCollective)
**Use case:** `agentoracle-v1` conformance set merged.
**Evidence:** [PROVIDERS.md](PROVIDERS.md) — listed as "Declared Provider": the provider states production use in their own README, we list it, they declare it. Production trail volume has not been independently confirmed by us.
**Status:** Declared, not verified. Do not cite as "verified" until it is.
**Kind:** N/A — self-reported, no conformance evidence to classify. Tier already flags this; the (a)/(b)/(c) scale doesn't apply until there's a checkable artifact.

---

## Pending — not counted in the traction figure

### Agent OS — Trust Ledger

**Contact:** [Liuyanfeng1234](https://github.com/Liuyanfeng1234)
**Use case:** Live-state admissibility at commit. Production fixture from Trust_Ledger 8731 pairing dual-timestamp pattern with issued-valid / executed-revoked states.
**Evidence:** Open PR against argentum-core: [`restraint-receipt-v1`](https://github.com/giskard09/argentum-core/pull/20) (audit_checkpoints).
**Status:** PR still open, not merged (re-checked 2026-08-09). Not counted until merged.

## Ecosystem references (not independent adopters — cited for context only)

- [linus10x/finserv-agent-audit](https://github.com/linus10x/finserv-agent-audit) — cross-reference for EU AI Act Art. 12 compliance
- [draft-vauban-x402-stark-receipts](https://datatracker.ietf.org/doc/draft-vauban-x402-stark-receipts/) (seritalien) — independent convergent design: same 4-field preimage shape under its own `[X402-CANON]` authority, `timestamp_ms` (integer) instead of our `timestamp` (RFC 3339 string). **Not byte-compatible with action-ref-v1.0 — parallel design, not a dependency.**

---

*To add your implementation: open an issue in [giskard09/argentum-core](https://github.com/giskard09/argentum-core) with a public evidence link.*
