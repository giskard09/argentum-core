/**
 * demo.ts — Mycelium Trails AgentKit provider demo.
 *
 * Runs verify_trail + compute_action_ref + get_trails against live data.
 * No wallet required. No API key required.
 *
 * Usage: npm run demo
 */

import { MyceliumTrailsProvider } from "./myceliumTrailsProvider";

// A trail that existed when this was written (pioneer-agent-001, cycle:monitor); it may
// no longer be listed later -- substitute any current trail's preimage and action_ref. Its
// action_ref is SHA-256(JCS(preimage)); the inputs below are the preimage the API
// returns for it (GET /trails/1e910613-6488-400b-8871-abae3f6406b4, anchor_proof.preimage).
const DEMO_AGENT_ID = "pioneer-agent-001";
const DEMO_ACTION_REF = "689ebc4c7d65fe3fc38f9ddcb7f39be2c31727e6b405f3df585f3c3ec3145da1";
const DEMO_INPUTS = {
  agent_id: DEMO_AGENT_ID,
  action_type: "cycle:monitor",
  scope: "services:10/10,alerts:0",
  timestamp: "2026-11-24T01:09:53.000Z",
};
// Fixed baseline vector (examples/conformance/action-ref-v1-baseline.fixture.json).
const BASELINE_INPUTS = {
  agent_id: "giskard-self",
  action_type: "trail.anchor",
  scope: "mycelium:baseline",
  timestamp: "2026-05-23T00:00:00.000Z",
};
const BASELINE_ACTION_REF = "f4ebda732e3c063bdd8547c734e4956f009bbed7f557cb949f7c8033e8c42d1d";

async function main() {
  const provider = new MyceliumTrailsProvider();

  console.log("=== Mycelium Trails AgentKit Provider Demo ===\n");

  // 1. compute_action_ref
  console.log("1. compute_action_ref()");
  console.log("   inputs:", BASELINE_INPUTS);
  const baseline = JSON.parse(await provider.computeActionRef(null, BASELINE_INPUTS));
  console.log("   result:", baseline);
  console.log("   matches baseline vector:", baseline.action_ref === BASELINE_ACTION_REF);
  const live = JSON.parse(await provider.computeActionRef(null, DEMO_INPUTS));
  console.log("   live trail inputs reproduce its action_ref:", live.action_ref === DEMO_ACTION_REF, "\n");

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
