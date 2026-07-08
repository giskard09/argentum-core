#!/usr/bin/env node
// verify.mjs -- disclosure-scoped-ref-v0 conformance vectors.
//
// Field-level selective disclosure: per-field salted commitments, a canonical
// commitment vector, and a root digest (disclosure_ref). See
// docs/spec/disclosure-scoped-ref.md for the full construction.
//
// Does NOT touch action_ref -- this is a sibling primitive, same pattern as
// screen_ref alongside a settlement action_ref (../presidio/).
//
// Built-ins only (node:crypto, node:fs, node:path). Independently implemented
// from the Python verifier -- both recompute from vectors.json and must land
// on byte-identical digests.
//
// Run: node verify.mjs

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

// RFC 8785 JCS canonical JSON, minimal recursive form: sort keys ascending at
// every level, no whitespace, UTF-8. Arrays preserve given order (the
// commitment_vector's order is itself canonical -- sorted by field name before
// serialization, not by this function).
function jcs(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return "[" + value.map(jcs).join(",") + "]";
  }
  const keys = Object.keys(value).sort();
  return "{" + keys.map((k) => JSON.stringify(k) + ":" + jcs(value[k])).join(",") + "}";
}

function sha256Hex(s) {
  return createHash("sha256").update(s, "utf8").digest("hex");
}

function fieldDigest(field, value, salt) {
  return sha256Hex(jcs({ field, salt, value }));
}

function commitmentVector(record, salts) {
  return Object.keys(record)
    .map((f) => ({ field: f, digest: fieldDigest(f, record[f], salts[f]) }))
    .sort((a, b) => (a.field < b.field ? -1 : a.field > b.field ? 1 : 0));
}

function disclosureRef(vector) {
  return sha256Hex(jcs(vector));
}

function verifyPos(fixture, vectorData) {
  const { record, salts } = fixture;
  const publishedVector = fixture.commitment_vector;
  const publishedRoot = fixture.disclosure_ref;

  const computedVector = commitmentVector(record, salts);
  const vectorOk = JSON.stringify(computedVector) === JSON.stringify(publishedVector);
  const rootOk = disclosureRef(publishedVector) === publishedRoot;

  let openedOk = true;
  for (const [field, o] of Object.entries(vectorData.opened)) {
    const recomputed = fieldDigest(field, o.value, o.salt);
    const stored = publishedVector.find((e) => e.field === field).digest;
    if (recomputed !== stored) openedOk = false;
  }

  console.log(`  [${vectorData.id}]`);
  console.log(`    commitment_vector recomputes from record+salts: ${vectorOk}`);
  console.log(`    root recomputes to published disclosure_ref:    ${rootOk}`);
  console.log(`    all opened fields match their committed digest: ${openedOk}`);
  return vectorOk && rootOk && openedOk;
}

function verifyNegHiddenAltered(fixture, vectorData) {
  const publishedVector = fixture.commitment_vector;
  const publishedRoot = fixture.disclosure_ref;

  const tamperedVector = publishedVector.map((e) => ({ ...e }));
  for (const e of tamperedVector) {
    if (e.field === vectorData.tampered_field) e.digest = vectorData.tampered_digest;
  }

  const tamperedRoot = disclosureRef(tamperedVector);
  const rootBreaks = tamperedRoot !== publishedRoot;
  const matchesExpected = tamperedRoot === vectorData.tampered_root;

  console.log(`  [${vectorData.id}]`);
  console.log(`    tampered root: ${tamperedRoot}`);
  console.log(`    tampered root != published disclosure_ref: ${rootBreaks}`);
  console.log(`    matches fixture's expected tampered root:   ${matchesExpected}`);
  return rootBreaks && matchesExpected;
}

function verifyNegSaltReuseAndSubstitution(fixture, vectorData) {
  const { record, salts } = fixture;
  const publishedVector = fixture.commitment_vector;
  const publishedRoot = fixture.disclosure_ref;
  const sub = vectorData.sub_vectors;

  // (a) salt reuse
  const reuse = sub.salt_reuse;
  const saltsReused = { ...salts };
  for (const f of reuse.reused_by_fields) saltsReused[f] = reuse.reused_salt;
  const saltSet = Object.values(saltsReused);
  const saltsUnique = new Set(saltSet).size === saltSet.length;
  const vectorWithReuse = commitmentVector(record, saltsReused);
  const rootWithReuse = disclosureRef(vectorWithReuse);
  const matchesExpectedReuseRoot = rootWithReuse === reuse.recomputed_root_with_reused_salt;

  console.log(`  [${vectorData.id}] (a) salt reuse`);
  console.log(`    salts unique across fields: ${saltsUnique} (must be false -- structural violation)`);
  console.log(`    root with reused salt still hashes 'correctly': ${matchesExpectedReuseRoot}`);
  const aOk = !saltsUnique && matchesExpectedReuseRoot;

  // (b) digest substitution
  const subst = sub.digest_substitution;
  const substitutedVector = publishedVector.map((e) => ({ ...e }));
  for (const e of substitutedVector) {
    if (e.field === subst.substituted_field) e.digest = subst.substituted_digest;
  }
  const substitutedRoot = disclosureRef(substitutedVector);
  const rootBreaks = substitutedRoot !== publishedRoot;
  const matchesExpectedSubstRoot = substitutedRoot === subst.substituted_root;

  const trueField = subst.substituted_field;
  const trueValue = record[trueField];
  const trueSalt = salts[trueField];
  const recomputedTrueDigest = fieldDigest(trueField, trueValue, trueSalt);
  const storedAfterSwap = substitutedVector.find((e) => e.field === trueField).digest;
  const laterOpenFails = recomputedTrueDigest !== storedAfterSwap;

  console.log(`  [${vectorData.id}] (b) digest substitution`);
  console.log(`    root breaks immediately: ${rootBreaks}`);
  console.log(`    matches fixture's expected substituted root: ${matchesExpectedSubstRoot}`);
  console.log(`    later disclosure of true value also fails to match: ${laterOpenFails}`);
  const bOk = rootBreaks && matchesExpectedSubstRoot && laterOpenFails;

  return aOk && bOk;
}

function main() {
  const fixture = JSON.parse(readFileSync(join(here, "vectors.json"), "utf8"));
  const byId = Object.fromEntries(fixture.vectors.map((v) => [v.id, v]));

  console.log("=".repeat(78));
  console.log("disclosure-scoped-ref-v0 conformance");
  console.log("=".repeat(78));

  const r1 = verifyPos(fixture, byId["pos-subset-disclosure"]);
  console.log();
  const r2 = verifyNegHiddenAltered(fixture, byId["neg-hidden-field-altered"]);
  console.log();
  const r3 = verifyNegSaltReuseAndSubstitution(fixture, byId["neg-salt-reuse-and-digest-substitution"]);

  console.log("\n" + "-".repeat(78));
  console.log(`pos-subset-disclosure                     : ${r1 ? "PASS" : "FAIL"}`);
  console.log(`neg-hidden-field-altered (correctly caught): ${r2 ? "PASS" : "FAIL"}`);
  console.log(`neg-salt-reuse-and-digest-substitution     : ${r3 ? "PASS" : "FAIL"}`);

  const ok = r1 && r2 && r3;
  console.log();
  if (ok) {
    console.log("PASS -- subset disclosure verifies against the root; a tampered closed");
    console.log("        field breaks the root; salt reuse is caught structurally and digest");
    console.log("        substitution breaks both the root and any later disclosure.");
    process.exit(0);
  }
  console.log("FAIL -- one or more vectors did not hold.");
  process.exit(1);
}

main();
