/**
 * demo.ts — Mycelium Trails AgentKit provider demo.
 *
 * Runs verify_trail + compute_action_ref + get_trails against live data.
 * No wallet required. No API key required.
 *
 * Usage: npm run demo
 */

import { MyceliumTrailsProvider } from "./myceliumTrailsProvider";

const DEMO_AGENT_ID = "pioneer-agent-001";
// Real action_ref from a verified trail in the Mycelium ecosystem
const DEMO_ACTION_REF = "3ad733678e731d4cb3f11bce1f4906e764b9e517be93abb231f4dc7a55f3b08c";
// Inputs that produce the above action_ref
const DEMO_INPUTS = {
  agent_id: DEMO_AGENT_ID,
  action_type: "agent_trail",
  scope: "giskard-oasis",
  timestamp: 1777991810,
};

async function main() {
  const provider = new MyceliumTrailsProvider();

  console.log("=== Mycelium Trails AgentKit Provider Demo ===\n");

  // 1. compute_action_ref
  console.log("1. compute_action_ref()");
  console.log("   inputs:", DEMO_INPUTS);
  const refResult = await provider.computeActionRef(null, DEMO_INPUTS);
  const ref = JSON.parse(refResult);
  console.log("   result:", ref);
  const matches = ref.action_ref === DEMO_ACTION_REF;
  console.log("   matches known ref:", matches, "\n");

  // 2. verify_trail
  console.log("2. verify_trail()");
  console.log(`   agent_id: ${DEMO_AGENT_ID}`);
  console.log(`   action_ref: ${DEMO_ACTION_REF}`);
  const verifyResult = await provider.verifyTrail(null, {
    agent_id: DEMO_AGENT_ID,
    action_ref: DEMO_ACTION_REF,
  });
  const verified = JSON.parse(verifyResult);
  console.log("   result:", verified, "\n");

  // 3. get_trails
  console.log("3. get_trails()");
  console.log(`   agent_id: ${DEMO_AGENT_ID}, limit: 3`);
  const trailsResult = await provider.getTrails(null, { agent_id: DEMO_AGENT_ID, limit: 3 });
  const trails = JSON.parse(trailsResult);
  console.log("   count:", trails.count ?? (trails.trails || []).length);
  if (trails.trails?.length) {
    const t = trails.trails[0];
    console.log("   latest trail:", {
      service: t.service,
      operation: t.operation,
      timestamp: new Date(t.timestamp * 1000).toISOString(),
      karma_at_time: t.karma_at_time,
    });
  }

  console.log("\n=== Demo complete ===");
  console.log("Live trail dashboard: https://argentum.rgiskard.xyz/trails/demo");
}

main().catch(console.error);
