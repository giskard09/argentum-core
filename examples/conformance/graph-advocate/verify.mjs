#!/usr/bin/env node
// Standalone verifier for the Graph Advocate counterparty-ref-v1 vector set.
//
// Built-ins only (node:crypto, node:fs, node:path). Does NOT import the
// graph-advocate SDK — recomputes SHA-256(JCS(preimage)) independently so
// a pass cross-checks against the Python verifier and the provider's own
// implementation.
//
// Run:  node verify.mjs
// Exit: 0 on full pass; non-zero on any vector failure.

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const VECTORS_PATH = join(here, "vectors.json");

// RFC 8785 JCS canonical JSON, minimal vendored form per the spec:
// sort keys ascending, no whitespace, UTF-8.
function jcs(obj) {
  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
    return JSON.stringify(obj);
  }
  const keys = Object.keys(obj).sort();
  const parts = keys.map((k) => JSON.stringify(k) + ":" + jcs(obj[k]));
  return "{" + parts.join(",") + "}";
}

function sha256Hex(s) {
  return createHash("sha256").update(s, "utf8").digest("hex");
}

function main() {
  const suite = JSON.parse(readFileSync(VECTORS_PATH, "utf8"));
  const vectors = suite.vectors || [];
  let passed = 0, failed = 0, rejectedOk = 0, rejectedFail = 0;

  for (const v of vectors) {
    const vid = v.id || "<no-id>";

    if (v.reject) {
      const preimage = v.input;
      if (!("timestamp" in preimage)) {
        console.log(`  REJECT-OK ${vid}: timestamp absent — verifier refuses to hash`);
        rejectedOk++;
      } else {
        console.log(`  REJECT-FAIL ${vid}: timestamp present in a reject vector — fixture error`);
        rejectedFail++;
      }
      continue;
    }

    const preimage = v.input;
    if (!("timestamp" in preimage)) {
      console.log(`  FAIL ${vid}: PASS vector missing timestamp`);
      failed++;
      continue;
    }

    const canonical = jcs(preimage);
    if (canonical !== v.canonical) {
      console.log(`  FAIL ${vid}: JCS string mismatch`);
      console.log(`    expected: ${JSON.stringify(v.canonical)}`);
      console.log(`    computed: ${JSON.stringify(canonical)}`);
      failed++;
      continue;
    }

    const digest = sha256Hex(canonical);
    if (digest !== v.expected) {
      console.log(`  FAIL ${vid}: SHA-256 hash mismatch`);
      console.log(`    expected: ${v.expected}`);
      console.log(`    computed: ${digest}`);
      failed++;
      continue;
    }

    console.log(`  PASS ${vid}: ${digest}`);
    passed++;
  }

  const total = passed + failed + rejectedOk + rejectedFail;
  console.log();
  console.log(`  PASS:      ${passed}/${total}`);
  console.log(`  REJECT-OK: ${rejectedOk}/${total}`);
  console.log(`  FAIL:      ${failed + rejectedFail}/${total}`);

  if (failed === 0 && rejectedFail === 0) {
    console.log();
    console.log(`PASS: ${total} vectors (provider: ${suite.provider.provider_id})`);
    process.exit(0);
  }
  process.exit(1);
}

main();
