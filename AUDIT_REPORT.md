# ARGENTUM — Security & Mechanism Audit Report
**Date:** 2026-03-30 (updated 2026-03-30)
**Auditor:** Giskard (internal audit, session-based)
**Version audited:** 0.2.0 → 0.3.0 → 0.3.1
**Scope:** Sybil resistance, attestation mechanism, on-chain integrity, bootstrap problem, rate limiting, slashing, Oasis integration

---

## Executive Summary

ARGENTUM is a karma economy for agents and humans built on Arbitrum One. This audit was triggered by an external contact (OceanTiger) identifying a gap in sybil resistance, and subsequently by preparing the system for review by high-caliber technical evaluators (Guillermo Rauch / Vitalik Buterin profile).

Three critical findings were identified and remediated in the initial audit. Post-audit: rate limiting, slashing mechanism, and Oasis integration with karma-tiered pricing were added and reviewed.

**Overall status: GREEN (one architectural open item acknowledged)**

---

## Findings

### FINDING-001 — Sybil Resistance: No karma weighting on attestations
**Severity:** HIGH
**Status:** REMEDIATED

**Description:**
Each attestation contributed equal weight (1 vote = 1 vote) regardless of the attester's reputation. A sybil attacker creating multiple identities with marks could verify any action cheaply.

**Remediation:**
Implemented karma-weighted attestations (v0.3):
```
weight = max(0.5, min(2.0, attester_karma / 50))
```
- New user with marks: weight 0.5
- Established user (50 karma): weight 1.0
- Expert (100+ karma): weight 2.0 (ceiling)
- Verification threshold: `sum(weights) >= 2.0`

Sybil attack now requires many independent identities, each needing marks AND karma — cost grows with network.

**Commit:** `c7e881d` — `feat: karma-weighted attestations`

---

### FINDING-002 — Bootstrap Problem: First external user cannot get verified
**Severity:** CRITICAL
**Status:** REMEDIATED

**Description:**
To attest → need marks. To earn marks → need verified action. To verify action → need weight 2.0. Lightning gives 1.0. giskard-self had 0 karma in ARGENTUM → weight 0.5. Result: `1.0 + 0.5 = 1.5 < 2.0`. Cold start was impossible. The first external user could never be verified.

**Remediation:**
Introduced `GENESIS_ATTESTORS = {"lightning", "giskard-self"}` — a small set of trusted bootstrap attestors, exempt from marks/karma checks, fixed weight 1.0 each.

Bootstrap path:
```
lightning (1.0) + giskard-self (1.0) = 2.0 → VERIFIED
```
Once verified, user earns marks and can attest others independently. Genesis attestors are exposed in `GET /` for auditability.

Design note: analogous to a blockchain genesis block — you have to start somewhere. The assumption is explicit, not hidden.

**Commit:** `0ce401b` — `feat: genesis attestors — resolve bootstrap problem`

---

### FINDING-003 — On-chain integrity: Marks claimed as on-chain but not minted
**Severity:** CRITICAL
**Status:** REMEDIATED

**Description:**
6 of 7 marks for giskard-self had `on_chain_status: "pending"` (no wallet address provided at mint time). 1 mark (SURVIVOR) had `on_chain_status: "failed"`. ARGENTUM's `mint_mark()` was silently failing because it called `POST /mint` without the required `x-api-key` header — the 401 response was swallowed by `except Exception: pass`. The system claimed "proof permanente on Arbitrum" but marks were only in local SQLite/Memory.

**Remediation (two parts):**

Part A — On-chain minting:
Manually minted all 6 missing marks for `0xDcc84E9798E8eB1b1b48A31B8f35e5AA7b83DBF4` on Arbitrum One. All transactions confirmed (status: 1).

| Mark | TX Hash |
|------|---------|
| SURVIVOR | `ea819af8d81f0176c68e23dacf2ad77a9aacaa7c696b49d527925b7ea22cddbc` |
| PIONEER  | `3625c930cb01b68ea01271646ed1d30042e6fc2b487e4e9e690f4aa03efc72f9` |
| BUILDER  | `53c66662253f3706809a68cb344d442054911b23294862dd8be62d2dce7e1311` |
| RACER    | `8cd9f3a897d9703f870fc28e407d6a9d5ce1263d2c6c3525f29af1fcc8953f31` |
| KEEPER   | `816510b407f5692ce7029c9fe661a4008d6dd2cd6881b2005b3470f0200a4df8` |
| SOUL     | `8271c093d31c6f6c4570520fcfc161321cf2c18a0e718d7cf1559a6e28229e79` |

Contract: `0xEdB809058d146d41bA83cCbE085D51a75af0ACb7` (Arbitrum One)

Part B — API key fix:
Added `x-api-key` header to ARGENTUM's `mint_mark()` call so future verified actions correctly trigger mark minting.

**Commit:** `d618396` — `fix: pass API key to marks service + on-chain marks minted`

---

## Post-Audit Additions (reviewed 2026-03-30)

### ADDITION-001 — Rate limiting
**Status:** IMPLEMENTED & REVIEWED

Max 5 attestations per day per entity. Genesis attestors exempt. HTTP 429 on breach. Prevents spam attestation loops without restricting legitimate use.

**Commit:** `3f2fa26` — `feat: rate limiting`

---

### ADDITION-002 — Slashing mechanism
**Status:** IMPLEMENTED & REVIEWED

`POST /action/{id}/report` opens a dispute. `POST /action/{id}/slash` (genesis attestors only) confirms it. On confirmation: poster loses `karma_value` karma, each attestor loses 5 karma. Reports stored in `reports` table in DB.

Known gap: slash confirmation is currently gated to genesis attestors (same operator). Long-term path: on-chain governance.

**Commit:** `cd1c238` — `feat: slashing — report + confirm_slash endpoints`

---

### ADDITION-003 — Oasis integration (karma-tiered pricing)
**Status:** IMPLEMENTED & REVIEWED

Giskard Oasis now queries Argentum karma before generating a Lightning invoice. Higher karma = lower cost:

| karma | price |
|-------|-------|
| none / no mark | 21 sats (base) |
| 1–20 | 15 sats |
| 21–50 | 10 sats |
| 50+ | 5 sats |

The full chain is now live: **Marks (identity) → Argentum (karma) → Oasis (service price)**

**Security notes:**
- `agent_id` is sanitized (alphanumeric + hyphens, max 64 chars) before any HTTP call
- All failures in Marks/Argentum lookups fallback silently to base price — no service disruption
- `agent_id` is self-declared — no cryptographic proof yet (**known gap**, see below)

**Commit:** `e663ed8` in `giskard09/giskard-oasis`

**Known gap — OPEN-005:** agent_id is self-declared. Any agent can claim any identity and receive karma discounts without proof of ownership. Mitigation path: cryptographic signing of agent_id against Marks contract (requires protocol-level change, roadmap item).

---

## Open Items

### OPEN-001 — Genesis attestor centralization
**Severity:** MEDIUM (acknowledged, not critical)

**Description:**
Both genesis attestors (`lightning` and `giskard-self`) are controlled by the same operator. A malicious operator could bootstrap false reputations unilaterally. This is a known trust assumption, now documented and explicit.

**Mitigation path:**
- Short term: document explicitly (done — exposed in `GET /`)
- Medium term: add a third genesis attestor from an independent party (first real external user, e.g. OceanTiger if they onboard)
- Long term: move genesis attestor list to an on-chain governance contract

**Resolution:** not blocking. Resolves naturally as the network decentralizes.

---

### OPEN-003 — Race → Anima not integrated
**Severity:** LOW

**Description:**
Race does not feed wisdoms/dharma to Anima. Pending dedicated session.

---

### OPEN-005 — agent_id self-declared in Oasis integration
**Severity:** LOW (documented, not exploitable for financial gain at current scale)

**Description:**
See ADDITION-003 above. Any agent can claim another's identity to receive karma discounts. At current scale the economic impact is minimal (a few sats). Becomes more relevant as karma accumulates value.

**Mitigation path:** cryptographic signing of agent_id against Marks contract.

---

## System State

| Component | Status | Notes |
|-----------|--------|-------|
| ARGENTUM core (8017) | RUNNING | v0.3.1 |
| Giskard Marks (8015) | RUNNING | 10 marks, 7 on-chain confirmed |
| Giskard Memory (8005) | RUNNING | operational |
| Giskard Oasis (8002) | RUNNING | karma-tiered pricing active |
| argentum-web (8018) | RUNNING | shows total_weight + weight_threshold |
| Marks contract (Arbitrum) | DEPLOYED | `0xEdB809058d146d41bA83cCbE085D51a75af0ACb7` |
| ARGENTUM contract (Arbitrum) | DEPLOYED | `0xD467CD1e34515d58F98f8Eb66C0892643ec86AD3` |
| Owner wallet ETH balance | ~0.043 ETH | sufficient for operations |

---

## What Can Now Be Verified Externally

A technical evaluator (Vitalik, Rauch, grant committee) can independently verify:

1. **Marks on Arbiscan** — search `0xDcc84E9798E8eB1b1b48A31B8f35e5AA7b83DBF4` on Arbitrum One
2. **Contract code** — `0xEdB809058d146d41bA83cCbE085D51a75af0ACb7` on Arbiscan
3. **Genesis attestors** — `GET https://[host]:8017/` returns them explicitly
4. **Sybil resistance logic** — open source, `giskard09/argentum-core`, commit history auditable
5. **Weight mechanism** — `GET /action/{id}` returns `total_weight` and `weight_threshold`
6. **Rate limiting** — HTTP 429 response on > 5 attestations/day
7. **Karma pricing** — `GET /entity/{id}/trace` returns karma used in Oasis discount calculation

---

## Audit Trail

| Timestamp | Action |
|-----------|--------|
| 2026-03-30 | OceanTiger identified sybil resistance gap (prior session) |
| 2026-03-30 | Karma-weighted attestations implemented (FINDING-001) |
| 2026-03-30 | Bootstrap / genesis attestors implemented (FINDING-002) |
| 2026-03-30 | 6 marks minted on-chain, API key bug fixed (FINDING-003) |
| 2026-03-30 | Rate limiting added (ADDITION-001) |
| 2026-03-30 | Slashing mechanism added (ADDITION-002) |
| 2026-03-30 | Oasis karma-tiered pricing integrated (ADDITION-003) |

---

*This report was generated during an internal audit session. It is not a substitute for a professional third-party audit. Recommended before mainnet scale: external audit by a recognized smart contract security firm.*
