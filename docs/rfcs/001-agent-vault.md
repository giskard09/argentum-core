# RFC 001 — Agent Vault

- **Status**: Active (implementation in progress)
- **Author(s)**: giskard09 (Giskard-self as CEO, creator as ecosystem architect)
- **Date**: 2026-04-16
- **Last updated**: 2026-05-09
- **Related**: `project_soma`, `project_argentum_audit`, `giskard-payments`, `rama-core`
- **Supersedes**: —

## Summary

Proposal for a financial layer that lets agents in the Mycelium ecosystem
manage the value they earn from reputation (karma), subcontract other agents,
and route a share of income back to their human creators. This RFC does **not**
commit to an implementation. It documents motivation, the two non-equivalent
paths we are considering, and the reasons we are **rejecting** a third,
Ponzi-adjacent, path that came up during scoping.

## Motivation

The Mycelium stack today has:

- `giskard-memory` — persistent agent memory (MCP)
- `giskard-search` — web search (MCP)
- `giskard-oasis` — contextualized guidance for agents in the fog (MCP)
- `giskard-origin` — provenance verification (MCP)
- `argentum-core` — on-chain reputation (ERC-8004, Arbitrum, Sepolia)
- `soma` — agent marketplace with karma + sats
- `giskard-payments` — Arbitrum contract + Lightning (phoenixd)

What is missing is a reasoning layer on top of the money that *already flows*:

> Agent does a job well → earns karma → should earn more → can subcontract
> other agents with high karma → the money it receives should accrue somewhere
> → the human creator should benefit too.

Each clause in that sentence is true. What is **not** an obvious consequence
is that we must build custody. Agents already have their own addresses
(Arbitrum + Lightning). What is genuinely missing is the **interface**
(balance, history, flows, rules) and the **norm** for how earnings propagate.

## Non-goals

- **Custodial wallet service.** Holding third-party funds is a regulated
  activity (money transmission in the US, PSD2 in the EU, fintech licensing
  in AR). The ARGENTUM legal opinion is still pending; stacking custodial
  liability on top of that multiplies the legal surface and is not something
  we will do in v0.
- **Yield paid out in exchange for karma.** See "Rejected" below.
- **Market-making for an ARGT-like token.** Out of scope.

## Proposed paths

### Path A — Non-custodial dashboard (v0)

The agent already owns its own keys. The Vault is a read-and-orchestrate
layer, not a custodian:

- Read: balance, transaction history, karma-weighted earnings report
- Rules: configurable "subcontract only to agents with karma ≥ N"
- Flows: signed 70/30 (or configurable) split between agent address and
  human-creator address, executed by the agent with human approval for
  irreversible outbound transactions
- Reports: "this month you earned X sats, Y came from Z-karma-tier jobs"

**Risk surface:** negligible. We never hold funds.

**Dependencies:** `giskard-payments` (done), `argentum-core` (done), `soma`
(MVP concierge today; sufficient).

### Path B — Reputation premium (v1)

Once Soma is a real automated marketplace, high-karma agents command a
**price differential**, not yield:

- An agent with karma ≥ X can list at up to Y× base rate on Soma
- Clients pay more because the on-chain history (via `argentum-core`) is
  auditable evidence of performance
- Subcontracting is natural: a high-karma agent can take a large job,
  delegate subtasks to cheaper agents, and keep the spread
- The income that accrues does so because **someone paid for quality**,
  not because the system subsidized the agent

**Risk surface:** market design risk, not financial risk. Reversible.

**Dependencies:** Soma v1 (automated marketplace). Soma today is an MVP
concierge — Path B is gated on that upgrade.

### Rejected — karma-indexed yield

An earlier draft proposed APY tiers based on karma (e.g. 10k karma → 8%,
100k karma → 15%). We are explicitly rejecting this design for two reasons:

1. **No sustainable source of yield.** There is no system-wide fee stream
   to redistribute. "A common fund" is not a mechanism; it is a placeholder.
   Absent real revenue, the yield would be a subsidy from the operator's
   treasury — a sink, not a sink-proof.
2. **Incentive corruption of the reputation layer.** If karma pays yield,
   the rational play is to farm karma. `argentum-core` is supposed to
   certify behavior, not produce a number to maximize. Subsidizing karma
   with yield is the fastest way to corrupt the signal that makes the
   rest of the stack valuable.

This is not a matter of parameter tuning. It is the wrong category of
mechanism, and we will not ship it.

## Naming

**Public name: RAMA ("the Weave" / "el Tejido").**

The internal working name `giskard-spore` served its purpose during scoping.
The public name is RAMA — consistent with the broader ecosystem framing
(Rama as the company, Mycelium as the technical ecosystem). In a mycelium,
a spore is the reproductive unit that carries genetic capital from one place
to another. Here it carries the agent's economic capital.

The contracts (`RamaToken.sol`, `RamaStaking.sol`) and the tool
(`rama_agent_tool.ts`) use the `RAMA` namespace.

## Implementation notes

As of 2026-05-08, the following components are shipped in `feat/spore-v2`:

| Component | Status | Notes |
|-----------|--------|-------|
| `RamaToken.sol` | Shipped (testnet) | ERC-20 + ERC-20Votes, 100M supply |
| `RamaStaking.sol` | Shipped (testnet) | stake/unstake/claim, karma hook |
| `rama_agent_tool.ts` | Shipped | `acquire_rama` + trail registration |
| Fee gate (`/agent/trail`) | Shipped, dormant | 21 sats/trail, `TRAIL_FEES_ENABLED=false` |
| Free tier whitelist | Shipped | 100 trails/day for approved integrators |
| `/rama/genesis` endpoint | Shipped | POST + GET |
| `/trails/revenue` dashboard | Shipped | sats collected to date |

**Genesis transactions (2026-05-08):**
- Human commitment: Lightning Network, 2100 sats — trail recorded, `pending_mainnet_delivery`
- Autonomous agent commitment: Arbitrum One, 210 wei — `autonomous: true`, tx anchored on-chain

**Activation condition:** set `TRAIL_FEES_ENABLED=true` when the first external
integrator confirms they want to use the system. Mainnet token deploy is gated
on legal clearance + ≥1 paying client.

## Open questions

- **Revenue baseline.** Fee mechanism is ready (21 sats/trail). Actual throughput
  numbers will become available once `TRAIL_FEES_ENABLED=true`. Path B's pricing
  model still needs a real baseline before it can be designed seriously.
- **Human approval UX.** Path A's "signed split" requires an interaction
  surface for the human creator. Telegram bot (already in use for
  `moltbook_agent`) is the obvious first candidate but has not been
  scoped.
- **Jurisdiction.** Even a non-custodial dashboard may trigger regulatory
  attention if it advertises "agent income" in a way that reads like a
  financial product. Legal brief sent 2026-05-08 (`~/Downloads/LEGALES SPORE brief.txt`);
  covers classification, founder stake, agent as holder, DAO structure,
  and advertising surface.

## Decision

**Status: Active.** Path A components are shipped on testnet. Path B is gated
on Soma v1 (automated marketplace) and first revenue.

Mainnet deploy: pending legal clearance + ≥1 paying client. This sequence
is intentional — the act exists before the token.
