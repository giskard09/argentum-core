# Adopters

Public evidence for the traction figure cited externally (decks, pitch materials). Every entry
below is independently checkable — no self-reported claim is counted without a link a third
party can verify directly. Tiered by evidence strength, not flattened into one number.

Corrected 2026-08-09 after an external independent re-audit (rhein1/agoragentic-integrations#244)
found the previous flat "8" mixed four different evidence tiers and included one entry that had
explicitly declined to integrate. See MOAT.txt / RETROSPECTIVA.txt for the full account.

---

## Tier 1 — Verified Provider (production trails submitted to ARGENTUM, independently verified)

### SafeAgent

**Contact:** [azender1](https://github.com/azender1)
**Use case:** `action_ref` derivation + x402 settlement on Base mainnet.
**Evidence:** Joint spec [argentum-core#7](https://github.com/giskard09/argentum-core/issues/7), [ucsandman/DashClaw#105](https://github.com/ucsandman/DashClaw/issues/105). Reference deployment: $0.001 USDC on Base mainnet, block 45907183. Real trading use ($3,600 notional blocked), stack published in Microsoft AutoGen.
**Status:** Verified Provider (production).

---

## Tier 2 — Independent spec adoption (merged into the partner's own codebase; not a production-trail submission to ARGENTUM)

### CTEF — Cross-Extension Trust Framework

**Contact:** [kenneives](https://github.com/kenneives)
**Use case:** `urn:mycelium:trail` confirmed as official namespace in CTEF v0.3.3, `custody-ref-v1.2` adopted as their own reference implementation. REQUIRED as of CTEF v0.4.
**Evidence:** [agentgraph-co/agentgraph PR #20](https://github.com/agentgraph-co/agentgraph/pull/20) — 3 conformance vectors, byte-match.
**Status:** Merged 2026-07-23.

### Agent Passport System (APS)

**Contact:** [aeoess](https://github.com/aeoess)
**Use case:** `action_ref` implemented directly in their own codebase.
**Evidence:** [`src/core/action-ref.ts`](https://github.com/aeoess/agent-passport-system/blob/main/src/core/action-ref.ts). Also: [aeoess/agent-passport-system PR #24](https://github.com/aeoess/agent-passport-system/pull/24) — TrailRecords as on-chain persistence layer.
**Status:** Real code, in production repo.

### AXES

**Contact:** [magentixai](https://github.com/magentixai)
**Use case:** `custody-ref-v1.2` cited and adopted as reference implementation for interop.
**Evidence:** [`docs/interop/x402-and-anchoring.md`](https://github.com/magentixai/axes/blob/main/docs/interop/x402-and-anchoring.md) cites `action_ref` explicitly.
**Status:** Real code, in production repo.

---

## Tier 3 — Independently verified conformance implementation (passes `action-ref-conformance@v1` via pinned CI; explicitly NOT a Provider — no production trails submitted)

### whawk46 (flareclaw-verifier)

**Evidence:** [flareclaw-conformance](https://github.com/whawk46/flareclaw-conformance), pinned CI run [30819828942](https://github.com/whawk46/flareclaw-conformance/actions/runs/30819828942), conclusion `success`.
**Status:** Verified conformant implementation. Never sent production trails — not a Provider, listed separately by design in [PROVIDERS.md](PROVIDERS.md).

### vstantch (aps-conformance-suite)

**Evidence:** [vstantch/aps-conformance-suite](https://github.com/vstantch/aps-conformance-suite) vendorizes our fixtures directly (`test-fixtures/argentum-core/{near-miss-v1.fixture.json, recompute-drift-v1-positive/negative.fixture.json, PROVENANCE.md}`), separate fork of this repo. PR#13 merged, hash byte-identical.
**Status:** Verified conformant implementation, not confirmed production.

---

## Tier 4 — Declared Provider (self-reported, not yet independently verified by us)

### TKCollective — AgentOracle + AgentTrust

**Contact:** [TKCollective](https://github.com/TKCollective)
**Use case:** `agentoracle-v1` conformance set merged.
**Evidence:** [PROVIDERS.md](PROVIDERS.md) — listed as "Declared Provider": the provider states production use in their own README, we list it, they declare it. Production trail volume has not been independently confirmed by us.
**Status:** Declared, not verified. Do not cite as "verified" until it is.

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
