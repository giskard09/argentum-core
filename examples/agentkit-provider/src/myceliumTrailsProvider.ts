/**
 * MyceliumTrailsProvider — AgentKit action provider for Mycelium Trails.
 *
 * DISCLAIMER: This is an unofficial, community-built AgentKit action provider.
 * It is not affiliated with, endorsed by, or submitted to Coinbase AgentKit upstream.
 * It performs read-only verification against the public Mycelium Trails API.
 * It does not execute transactions, sign messages, or provide security guarantees.
 *
 * Mycelium Trails is the post-execution reputation layer of the Mycelium ecosystem.
 * Each verified trail is an on-chain record (Base) of an agent's completed action.
 *
 * Available actions:
 * - verify_trail: Check if an agent has a verified trail for a given action_ref
 * - compute_action_ref: Compute the canonical SHA-256 action reference
 * - get_trails: List recent trails for an agent
 */

import { createHash } from "crypto";
import { z } from "zod";
import { ActionProvider } from "@coinbase/agentkit";
import { CreateAction } from "@coinbase/agentkit";
import { Network } from "@coinbase/agentkit";
import { VerifyTrailSchema, ComputeActionRefSchema, GetTrailsSchema } from "./schemas";

const MYCELIUM_API_BASE = "https://argentum.rgiskard.xyz";

interface VerifyTrailResult {
  verified: boolean;
  trail_id: string | null;
  tx_hash: string | null;
  timestamp: string | null;
  service: string | null;
  operation: string | null;
}

/**
 * MyceliumTrailsProvider provides read-only actions for verifying agent reputation
 * via the Mycelium Trails API. Trails are post-execution on-chain records stored on Base.
 *
 * No API key required. All actions are read-only.
 */
export class MyceliumTrailsProvider extends ActionProvider {
  constructor() {
    super("mycelium-trails", []);
  }

  /**
   * Verifies whether an agent has a confirmed trail for a given action_ref.
   * A verified trail means the action was recorded and anchored on-chain (Base).
   *
   * @param args - agent_id and action_ref (SHA-256 canonical reference).
   * @returns JSON string with verification result.
   */
  @CreateAction({
    name: "verify_trail",
    description: `Verifies whether an agent has a confirmed Mycelium Trail for a given action.

A Mycelium Trail is an on-chain record (Base) of a completed agent action, tied to
a payment or signed interaction in the Mycelium ecosystem.

Use this after an agent claims to have executed an action to verify it actually happened.
Pairs with compute_action_ref to generate the canonical reference before verifying.

Returns:
- verified: true if the trail exists and is confirmed
- tx_hash: on-chain transaction hash on Base (if available)
- timestamp: ISO 8601 timestamp of when the trail was recorded
- trail_id: internal trail identifier
- service: which Mycelium service recorded the trail (e.g. giskard-oasis)
- operation: the operation type (e.g. enter_oasis, agent_trail)

Example: verify pioneer-agent-001 executed a swap on 2026-05-05
`,
    schema: VerifyTrailSchema,
  })
  async verifyTrail(
    _walletProvider: unknown,
    args: z.infer<typeof VerifyTrailSchema>,
  ): Promise<string> {
    try {
      const url = `${MYCELIUM_API_BASE}/trails/verify?agent_id=${encodeURIComponent(args.agent_id)}&action_ref=${encodeURIComponent(args.action_ref)}`;
      const resp = await fetch(url, { signal: AbortSignal.timeout(10_000) });

      if (resp.status === 404) {
        return JSON.stringify({ verified: false, trail_id: null, tx_hash: null, timestamp: null, service: null, operation: null });
      }
      if (!resp.ok) {
        return JSON.stringify({ error: `API error: ${resp.status}`, verified: false });
      }

      const data = (await resp.json()) as VerifyTrailResult;
      return JSON.stringify(data);
    } catch (err) {
      return JSON.stringify({ error: String(err), verified: false });
    }
  }

  /**
   * Computes the canonical action_ref for a given action.
   * The action_ref is SHA-256(agent_id:action_type:scope:timestamp) — deterministic.
   * Use the same inputs that were used when the trail was recorded.
   *
   * @param args - agent_id, action_type, scope, timestamp.
   * @returns JSON string with the computed action_ref hex string.
   */
  @CreateAction({
    name: "compute_action_ref",
    description: `Computes the canonical Mycelium action_ref for a given action.

The action_ref is SHA-256(agent_id:action_type:scope:timestamp) — a deterministic
content-addressed reference used to link external records to Mycelium Trails.

Use this before verify_trail when you know the inputs but not the hash.
The same algorithm is used by the Mycelium ecosystem (argentum-sdk/argentum/trails.py).

Example: compute_action_ref("pioneer-agent-001", "agent_trail", "giskard-oasis", 1777991810)
`,
    schema: ComputeActionRefSchema,
  })
  async computeActionRef(
    _walletProvider: unknown,
    args: z.infer<typeof ComputeActionRefSchema>,
  ): Promise<string> {
    const payload = `${args.agent_id}:${args.action_type}:${args.scope}:${args.timestamp}`;
    const hash = createHash("sha256").update(payload, "utf8").digest("hex");
    return JSON.stringify({ action_ref: hash, payload });
  }

  /**
   * Lists recent trails for an agent.
   *
   * @param args - agent_id and optional limit.
   * @returns JSON string with trail list.
   */
  @CreateAction({
    name: "get_trails",
    description: `Lists recent Mycelium Trails for a given agent.

Returns the agent's verified action history — on-chain records of completed
interactions in the Mycelium ecosystem (payments, swaps, knowledge queries).

Use this to assess an agent's track record before trusting its claims.

Each trail includes: service, operation, timestamp, karma_at_time, success,
bridge_tx_hash (if a cross-chain swap was part of the action).
`,
    schema: GetTrailsSchema,
  })
  async getTrails(
    _walletProvider: unknown,
    args: z.infer<typeof GetTrailsSchema>,
  ): Promise<string> {
    try {
      const limit = args.limit ?? 10;
      const url = `${MYCELIUM_API_BASE}/trails/agents/${encodeURIComponent(args.agent_id)}?limit=${limit}`;
      const resp = await fetch(url, { signal: AbortSignal.timeout(10_000) });
      if (!resp.ok) {
        return JSON.stringify({ error: `API error: ${resp.status}`, trails: [] });
      }
      const data = await resp.json();
      return JSON.stringify(data);
    } catch (err) {
      return JSON.stringify({ error: String(err), trails: [] });
    }
  }

  supportsNetwork(_network: Network): boolean {
    return true;
  }
}

export const myceliumTrailsProvider = () => new MyceliumTrailsProvider();
