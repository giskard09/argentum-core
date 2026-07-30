# Adopters

Verified implementations of the action-ref.md spec and Mycelium Trails protocol.

Each entry includes a public evidence link. Entries without verifiable public evidence are not listed.

---

## Agent OS — Trust Ledger

**Contact:** [Liuyanfeng1234](https://github.com/Liuyanfeng1234)  
**Use case:** Live-state admissibility at commit. Production fixture from Trust_Ledger 8731 pairing dual-timestamp pattern with issued-valid / executed-revoked states.  
**Evidence:** Open PR against argentum-core: [`restraint-receipt-v1`](https://github.com/giskard09/argentum-core/pull/20) (audit_checkpoints). First external contributor to argentum-core.  
**Status:** PR open, under review.

---

## CTEF — Cross-Extension Trust Framework

**Contact:** [kenneives](https://github.com/kenneives)  
**Use case:** `urn:mycelium:trail` confirmed as official namespace in CTEF v0.3.3. action_ref as identity anchor across cross-extension trail verification.  
**Evidence:** [agentgraph-co/agentgraph PR #20](https://github.com/agentgraph-co/agentgraph/pull/20) — 3 conformance vectors, byte-match. CONSILIUM Candidate 1 substrate committed.  
**Status:** Merged 2026-07-23.

---

## SafeAgent

**Contact:** [azender1](https://github.com/azender1)  
**Use case:** `action_ref` derivation + x402 settlement on Base mainnet.  
**Evidence:** Joint spec [argentum-core#7](https://github.com/giskard09/argentum-core/issues/7), [ucsandman/DashClaw#105](https://github.com/ucsandman/DashClaw/issues/105). Reference deployment: $0.001 USDC on Base mainnet, block 45907183.  
**Status:** Production.

---

## Ecosystem references

- [aeoess/agent-governance-vocabulary PR #96](https://github.com/aeoess/agent-governance-vocabulary/pull/96) — `crosswalk/mycelium-trails.yaml` v0.1
- [kenneives/agent-governance-vocabulary PR #1](https://github.com/kenneives/agent-governance-vocabulary/pull/1) — `crosswalk/mycelium.yaml` v0.3.2
- [aeoess/agent-passport-system PR #24](https://github.com/aeoess/agent-passport-system/pull/24) — TrailRecords as on-chain persistence layer
- [pshkv/SINT](https://github.com/pshkv/SINT) — Mycelium Trails as evidence backend
- [linus10x/finserv-agent-audit](https://github.com/linus10x/finserv-agent-audit) — cross-reference for EU AI Act Art. 12 compliance
- [draft-vauban-x402-stark-receipts](https://datatracker.ietf.org/doc/draft-vauban-x402-stark-receipts/) (seritalien) — independent convergent design: same 4-field preimage shape under its own `[X402-CANON]` authority, `timestamp_ms` (integer) instead of our `timestamp` (RFC 3339 string). Not byte-compatible with action-ref-v1.0 — parallel design, not a dependency.

---

*To add your implementation: open an issue in [giskard09/argentum-core](https://github.com/giskard09/argentum-core) with a public evidence link.*
