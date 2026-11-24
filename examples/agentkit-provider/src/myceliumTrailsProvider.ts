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
 * - compute_action_ref: Compute the action_ref (v1: SHA-256 of the JCS of the four preimage fields)
 * - get_trails: List recent trails for an agent
 */

import { z } from "zod";
import { ActionProvider } from "@coinbase/agentkit";
import { CreateAction } from "@coinbase/agentkit";
import { Network } from "@coinbase/agentkit";
import { VerifyTrailSchema, ComputeActionRefSchema, GetTrailsSchema } from "./schemas";
import { computeActionRef, OutOfProfileDomainError } from "./actionRef";

const MYCELIUM_API_BASE = "https://argentum.rgiskard.xyz";

// Shape of GET /trails/verify: { verified: false } or { verified: true, trail: {...} }.
interface VerifyTrailResult {
  verified: boolean;
  trail?: Record<string, unknown>;
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
- verified: true if the trail exists
- trail (only when verified): trail_id, tx_hash (if anchored), service, operation, action_ref, timestamp (Unix seconds) and the other trail fields

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
        return JSON.stringify({ verified: false });
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
   * Computes the action_ref (v1) for a given action:
   * SHA-256(JCS({agent_id, action_type, scope, timestamp})), RFC 8785.
   * Use the same inputs that were used when the trail was recorded. Inputs outside the
   * v1 domain (non-ASCII, empty scope, a timestamp that is not YYYY-MM-DDTHH:MM:SS.mmmZ
   * or not a real instant) are refused, not hashed.
   *
   * @param args - agent_id, action_type, scope, timestamp (string).
   * @returns JSON string with the action_ref hex string and the canonical bytes hashed,
   *          or { error, field, reason } when an input is outside the domain.
   */
  @CreateAction({
    name: "compute_action_ref",
    description: `Computes the Mycelium action_ref (v1) for a given action.

The action_ref is SHA-256 of the RFC 8785 (JCS) serialization of
{agent_id, action_type, scope, timestamp} -- a deterministic content-addressed
reference used to link external records to Mycelium Trails.

The timestamp is a STRING, exactly YYYY-MM-DDTHH:MM:SS.mmmZ (UTC, three fractional
digits). agent_id, action_type and scope must be ASCII and scope must not be empty.
Inputs outside that domain return an error instead of a hash.

Use this before verify_trail when you know the inputs but not the hash.

Example: compute_action_ref("giskard-self", "trail.anchor", "mycelium:baseline", "2026-05-23T00:00:00.000Z")
`,
    schema: ComputeActionRefSchema,
  })
  async computeActionRef(
    _walletProvider: unknown,
    args: z.infer<typeof ComputeActionRefSchema>,
  ): Promise<string> {
    try {
      const action_ref = computeActionRef(args.agent_id, args.action_type, args.scope, args.timestamp);
      const canonical = JSON.stringify({
        action_type: args.action_type,
        agent_id: args.agent_id,
        scope: args.scope,
        timestamp: args.timestamp,
      });
      return JSON.stringify({ action_ref, canonical });
    } catch (err) {
      if (err instanceof OutOfProfileDomainError) {
        return JSON.stringify({ error: "OUT_OF_PROFILE_DOMAIN", field: err.field, reason: err.reason });
      }
      return JSON.stringify({ error: String(err) });
    }
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
