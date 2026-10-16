# ip-licensing-worked-example

**Status:** draft, 2026-10-16 — internal dogfood, not yet proposed externally.

## Why this exists

A chain that lets intellectual property "flow" with fast dispute resolution needs three
things underneath it, independent of whatever arbitration mechanism sits on top:

1. **Precedence** — proof that a creator's registration of an IP asset predates any
   competing claim, verifiable without trusting the registrant's own account of when it
   happened.
2. **Chain of custody** — proof that a license was transferred creator → licensee →
   sub-licensee as a continuous, verifiable sequence, not three independent claims an
   arbitrator has to reconcile by hand.
3. **Settlement proof** — proof that a royalty payment tied to that license actually
   executed, not just that one party asserts it did.

None of these three are new. This worked example composes three **already-stable, already-
shipped** specs from this repo — no new primitive is introduced:

| Layer | Spec | Role here |
|---|---|---|
| Precedence | [`anchoring-precedence-ref-v1`](../../docs/spec/anchoring-precedence-ref-v1.md) | Creator's registration commitment predates a later competing claim |
| Custody | [`delegation-chain-ref-v1`](../../docs/spec/delegation-chain-ref.md) | Creator → distributor → regional factory license chain, each hop independently verifiable |
| Settlement | [`action_ref` (v1)](../../docs/spec/action-ref.md) | The factory's royalty payment, as the chain's leaf action |

## Scenario

"Modular Thermal Exchanger Design v2," created by Lucía Reyes:

1. Lucía registers the design. Its commitment is anchored on-chain
   (`anchoring_precedence_ref`).
2. ~19 days later a third party claims independent invention. A verifier can confirm
   Lucía's anchor predates that claim's timestamp — without taking either side's word for
   it, and without a new mechanism: this is the same invariant `anchoring-precedence-ref`
   already proves for any action pipeline.
3. Lucía licenses manufacturing rights to a distributor, who sub-licenses regional
   manufacturing to a factory (`delegation_chain_ref`, two hops).
4. The factory settles a quarterly royalty (`action_ref`, the chain's `leaf_action_ref`).

Run `python3 build_fixture.py` to regenerate `fixture.json` — every hash in it is computed
from the preimages in the script, not hand-written. Reproducing it is the proof that this is
real composition, not a diagram.

## What this is not

- **Not a new chain.** The pitch some teams are chasing ("a chain for IP") doesn't need to be
  built from zero — the three verifiable layers above sit under any ledger or any
  arbitration mechanism a team already prefers.
- **Not a dispute-resolution engine.** `kleros_bridge_mcp.py` in this repo is a documented
  **skeleton only** — every tool returns `not_implemented`, no contract is deployed, no real
  transaction has ever run through it (see its own docstring, dated 2026-04-15, untouched
  since). It is cited here as **the shape a resolution layer would take** when it consumes
  these three records instead of trusting either party's claim — not as a working
  integration. Do not represent it as live in any external communication; if someone asks
  whether we have Kleros wired up for IP disputes today, the honest answer is no.
- **Not specific to this scenario.** Swap the design/distributor/factory names for any
  asset/licensor/licensee shape — the three refs don't know they're being used for IP.

## Status / next step

Internal only. No outreach has used this yet. If a real external hook justifies sending it
(see `BITACORA_TRUSTLESS_AI_WG.txt`-style discipline — verified quote, verified channel, no
cold pitch), extend this fixture into something concrete enough to point to, but keep the
Kleros caveat above intact in whatever gets sent.
