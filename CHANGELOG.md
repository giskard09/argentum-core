# Changelog — argentum-core

All notable changes to the public interface of argentum-core are documented here.

**Audience:** external integrators (aeoess, chox-cell, msaleme, agentkit and others).
Only changes that affect schema, API endpoints, or semantic behavior are listed.
Internal refactors, docs, and tests are not included.

Format per entry: `[vX.Y.Z] YYYY-MM-DD — Type — What changed — Who is affected`

Types: BREAKING | DEPRECATION | FEATURE | FIX | SCHEMA

---

## Unreleased (feat/mycelium-trails)

### [SCHEMA] 2026-05-09 — RFC 001 documented as Active
- RFC 001 (Agent Vault / RAMA) updated to Active status on `feat/mycelium-trails`
- New section: "Emergent property: autonomous economic agents" — describes the
  pattern of autonomous agents operating $RAMA + trails + karma
- **Who is affected:** informational only. No schema or API change.
- **Link:** docs/rfcs/001-agent-vault.md

### [SCHEMA] 2026-05-08 — Genesis trails recorded
- POST /rama/genesis endpoint: records human or autonomous agent genesis commitment
- GET /rama/genesis: retrieves genesis trail by agent_id
- Fields: payment_hash, rail, amount, autonomous (bool), timestamp
- **Who is affected:** new endpoint, additive. No breaking change to existing schema.
- Consumers: none yet (genesis is a first-party operation)

### [FEATURE] 2026-05-08 — Free tier whitelist activated
- GET/POST /agent/trail now enforces free tier per agent_id
- Whitelist: 100 trails/day for approved integrators (aeoess-aps, chox-cell, accord)
- TRAIL_FEES_ENABLED=false by default — fee gate dormant until first paying integrator
- **Who is affected:** whitelisted integrators get 100 trails/day free. Others: 0 cost today.

---

## [0.4.0] — 2026-04-14

- 5 MCP servers published to Official MCP Registry (io.github.giskard09/*)
- argentum v0.4.0, memory v1.0.1, oasis v0.1.0, origin v0.1.0, search v0.1.1

---

## Public interface contract (stable as of v0.4.0)

The following are **stable** and will not change without a DEPRECATION notice
and a minimum 2-week migration window:

| Surface | Version | Consumers |
|---------|---------|-----------|
| `rail.payment.v1` receipt schema | v1 | aeoess |
| `rail.payment.denial.v1` receipt schema | v1 | aeoess |
| `action_ref` (SHA-256, opaque string) | v1 | msaleme, agentkit |
| `feedbackHash` field | v1 | msaleme |
| `payment_hash` cross-surface key | v1 | aeoess, agentkit, x402 |
| GET /trails/verify | stable | agentkit PR #1170, chox-cell |
| GET /trails/agents/:id | stable | agentkit PR #1170 |
| POST /agent/trail | stable | internal + whitelist |

## Planned (not yet scheduled)

- **Schema v2** — `scope.data` / `scope.action` as structured sub-fields of `action_ref`
  backward-compatible with v1 (v1 opaque string accepted alongside v2 object).
  Trigger: hanselhansel feedback from enterprise production use.
  Protocol: public issue in argentum-core → 2-week review → merge.
  Affected: msaleme, agentkit, aeoess (receipt consumers).

