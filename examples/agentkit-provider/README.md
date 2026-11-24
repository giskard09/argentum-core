# Mycelium Trails — AgentKit Action Provider

> **Disclaimer:** This is an unofficial, community-built AgentKit action provider.
> It is not affiliated with, endorsed by, or submitted upstream to Coinbase AgentKit.
> It performs **read-only** verification against the public Mycelium Trails API.
> It does **not** execute transactions, sign messages, or provide security guarantees.
> Not audited. Use at your own risk.

---

Post-execution reputation layer for AI agents. Each Mycelium Trail is an on-chain record (Base) of a completed agent action — payment, swap, or signed interaction.

Use this provider to verify that an agent actually did what it claims.

## Actions

### `verify_trail`

Check if an agent has a verified trail for a given `action_ref`.

```typescript
const result = await agentkit.run(
  "verify trail for pioneer-agent-001 with action_ref 689ebc4c..."
);
```

Returns what `GET /trails/verify` returns: `{ verified, trail }`, where `trail` holds `trail_id`, `tx_hash`, `service`, `operation`, `action_ref` and the other trail fields (`trail` is absent when `verified` is false).

### `compute_action_ref`

Compute the action_ref (v1) from action inputs: `SHA-256(JCS({agent_id, action_type, scope, timestamp}))`,
RFC 8785. Reference: [`docs/spec/action-ref.md`](../../docs/spec/action-ref.md).

```typescript
const result = await agentkit.run(
  'compute action_ref for giskard-self, action_type trail.anchor, scope mycelium:baseline, timestamp "2026-05-23T00:00:00.000Z"'
);
// { action_ref: "f4ebda732e3c063bdd8547c734e4956f009bbed7f557cb949f7c8033e8c42d1d", canonical: "{...}" }
```

The timestamp is a **string**, exactly `YYYY-MM-DDTHH:MM:SS.mmmZ`. `agent_id`, `action_type` and `scope` must be
ASCII and `scope` must not be empty. An input outside that domain returns
`{ "error": "OUT_OF_PROFILE_DOMAIN", "field": ..., "reason": ... }` instead of a hash.

> **Breaking change in this example (schema `timestamp`: number -> string).** Earlier revisions of this example
> hashed a colon-joined string of the four fields, with the time as a Unix-seconds number. That construction does not
> match action_ref v1: a value computed that way is not what `POST /nexus/trail` recomputes. This README, the
> demo and the code now follow v1.

### `get_trails`

List recent trails for an agent.

```typescript
const result = await agentkit.run("get trails for pioneer-agent-001");
```

## Setup

```bash
npm install
npm run demo   # runs against live Mycelium API, no API key needed
```

## Demo

```bash
npm run demo
```

The verify step uses a trail that existed when this was written. If it no longer verifies, take the
`anchor_proof.preimage` and `action_ref` of any current trail from `GET /trails/{trail_id}` and use those instead.

Output:
```
=== Mycelium Trails AgentKit Provider Demo ===

1. compute_action_ref()
   inputs: { agent_id: 'giskard-self', action_type: 'trail.anchor', ... }
   result: { action_ref: 'f4ebda73...', canonical: '...' }
   matches known ref: true

2. verify_trail()
   result: { verified: true, trail: { ... } }

3. get_trails()
   count: 11
   latest trail: { service: 'giskard-oasis', operation: 'agent_trail', ... }
```

Live dashboard: https://argentum.rgiskard.xyz/trails/demo

## Integration

```typescript
import { AgentKit } from "@coinbase/agentkit";
import { myceliumTrailsProvider } from "./src";

const agentkit = await AgentKit.from({
  walletProvider,
  actionProviders: [
    myceliumTrailsProvider(),
    // ... other providers
  ],
});
```

## Related

- [Mycelium Trails API](https://argentum.rgiskard.xyz/trails/demo)
- [action_ref spec](../../docs/spec/action-ref.md) — v1 derivation and Domain rules
- [ERC-8004](https://eips.ethereum.org/EIPS/eip-8004) — Agent identity standard
