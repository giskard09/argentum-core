# RFC 001 — Agent Vault

- **Status**: Draft
- **Author(s)**: giskard09 (Giskard-self as CEO, creator as ecosystem architect)
- **Date**: 2026-04-16
- **Related**: `project_soma`, `project_argentum_audit`, `giskard-payments`
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

Two candidates under consideration. This RFC does not pick one yet; it
defers to a naming decision that happens at implementation time.

- `giskard-spore` — in a mycelium, a spore is a reproductive unit that
  carries genetic capital. Here it would carry the agent's economic
  capital. Organic, coherent with the `giskard-*` MCP family, distinctive.
- `argentum-flow` — sits in the `argentum-*` family of reputation/value
  components. More immediately legible to external readers.

## Open questions

- **Revenue baseline.** We do not have clean numbers today for `soma`
  monthly throughput in sats or USD. Path B's pricing model needs that
  baseline before it can be designed seriously. This RFC depends on
  that data existing, not on a specific value.
- **Human approval UX.** Path A's "signed split" requires an interaction
  surface for the human creator. Telegram bot (already in use for
  `moltbook_agent`) is the obvious first candidate but has not been
  scoped.
- **Jurisdiction.** Even a non-custodial dashboard may trigger regulatory
  attention if it advertises "agent income" in a way that reads like a
  financial product. Legal opinion (already queued for ARGENTUM, ~USD 5k-10k)
  should add a question about advertising surface.

## Decision

**Status: Draft.** This RFC is a precedent that we are actively thinking
about this layer. It is **not** a commitment to build.

Next step: creator review. If accepted as Draft, the RFC number is reserved
and the two paths (A, B) are the candidate designs to iterate on.

## Appendix — conversational origin

This RFC originated in a conversation between the creator and Giskard-self
on 2026-04-16, prompted by a Grok response that proposed karma-indexed yield.
The "Rejected" section is the direct result of analyzing that proposal under
the four-filter rubric (Elon executable / Vitalik incentives / Peter scale /
Dario safe). The full dialogue is archived off-repo in the creator's session
notes.
