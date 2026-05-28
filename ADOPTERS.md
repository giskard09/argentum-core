# Adopters

Verified implementations of the action-ref.md spec and Mycelium Trails protocol.

Each entry includes a public evidence link. Entries without verifiable public evidence are not listed.

---

## Agent OS — Trust Ledger

**Contact:** [Liuyanfeng1234](https://github.com/Liuyanfeng1234)  
**Use case:** Live-state admissibility at commit. Production fixture from Trust_Ledger 8731 pairing dual-timestamp pattern with issued-valid / executed-revoked states.  
**Evidence:** CONSILIUM Candidate 2 substrate submission ([A2A discussion #1734](https://github.com/a2aproject/A2A/discussions/1734)). First external contributor to argentum-core.  
**Status:** Production data verified. PR negotiation_ref in progress.

---

## Vauban Pay — ZKPay Receipt Layer

**Contact:** [seritalien](https://github.com/seritalien)  
**Use case:** STARK-based payment receipts with dual-timestamp pairs aligned to action-ref.md. Cross-jurisdictional compliance (MiCA / FCA).  
**Evidence:** [draft-vauban-x402-stark-receipts-01](https://datatracker.ietf.org/doc/draft-vauban-x402-stark-receipts/) — section 4.2 references the dual-timestamp model. Conformance vectors (Category G) aligned against argentum-core fixtures.  
**Status:** IETF draft active. Conformance alignment in progress against action-ref-v1.0.

---

## CTEF — Cross-Extension Trust Framework

**Contact:** [kenneives](https://github.com/kenneives)  
**Use case:** `urn:mycelium:trail` confirmed as official namespace in CTEF v0.3.3. action_ref as identity anchor across cross-extension trail verification.  
**Evidence:** [agentgraph-co/agentgraph PR #20](https://github.com/agentgraph-co/agentgraph/pull/20) — 3 conformance vectors, byte-match. CONSILIUM Candidate 1 substrate committed.  
**Status:** PR open, pending merge.

---

## SafeAgent

**Contact:** [azender1](https://github.com/azender1)  
**Use case:** `action_ref` derivation + x402 settlement on Base mainnet.  
**Evidence:** Joint spec [argentum-core#7](https://github.com/giskard09/argentum-core/issues/7), [ucsandman/DashClaw#105](https://github.com/ucsandman/DashClaw/issues/105). Reference deployment: $0.001 USDC on Base mainnet, block 45907183.  
**Status:** Production.

---

## AURA — Reputation Observation Layer

**Contact:** [luisllaver](https://github.com/luisllaver)
**Use case:** action_ref as idempotency key for reputation observations. action_type → dimension mapping live on AURA's observe path.
**Evidence:** Independently reproduced action-ref.md v1.0 fixture verbatim — NEXUS oracle signal digest `fdd7f810…43d89f5a` confirmed ([x402#2332](https://github.com/x402-foundation/x402/issues/2332)). Plain JCS (RFC 8785) + SHA-256, no substrate-specific dependency.
**Status:** Conformance confirmed 2026-05-23. Live on observe path.

---

## Ecosystem references

- [aeoess/agent-governance-vocabulary PR #96](https://github.com/aeoess/agent-governance-vocabulary/pull/96) — `crosswalk/mycelium-trails.yaml` v0.1
- [kenneives/agent-governance-vocabulary PR #1](https://github.com/kenneives/agent-governance-vocabulary/pull/1) — `crosswalk/mycelium.yaml` v0.3.2
- [aeoess/agent-passport-system PR #24](https://github.com/aeoess/agent-passport-system/pull/24) — TrailRecords as on-chain persistence layer
- [pshkv/SINT](https://github.com/pshkv/SINT) — Mycelium Trails as evidence backend
- [linus10x/finserv-agent-audit](https://github.com/linus10x/finserv-agent-audit) — cross-reference for EU AI Act Art. 12 compliance

---

*To add your implementation: open an issue in [giskard09/argentum-core](https://github.com/giskard09/argentum-core) with a public evidence link.*
