#!/usr/bin/env node
/**
 * AgentTrust verification.v0.3+composed conformance verifier
 * Verifies JWS general serialization signatures against published JWKS
 * Node stdlib only — no external deps
 */

import { readFileSync } from 'fs';
import { createPublicKey, verify as cryptoVerify } from 'crypto';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));

function jcs(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    return JSON.stringify(value);
  }
  const keys = Object.keys(value).sort();
  const parts = keys.map(k => `${JSON.stringify(k)}:${jcs(value[k])}`);
  return `{${parts.join(',')}}`;
}

function b64urlDecode(str) {
  return Buffer.from(str, 'base64url');
}

function jwkToPem(jwk) {
  const key = createPublicKey({ key: jwk, format: 'jwk' });
  return key;
}

function verifySignature(protectedB64, payloadB64, signatureB64, jwk) {
  const sigInput = Buffer.from(`${protectedB64}.${payloadB64}`);
  const sig = b64urlDecode(signatureB64);
  const pubKey = jwkToPem(jwk);
  return cryptoVerify(null, sigInput, pubKey, sig);
}

function main() {
  const vectorsPath = join(__dirname, 'vectors.json');
  const vectors = JSON.parse(readFileSync(vectorsPath, 'utf8'));
  const jwksPath = join(__dirname, 'jwks-agenttrust.json');
  const jwks = JSON.parse(readFileSync(jwksPath, 'utf8'));
  const jwk = jwks.keys.find(k => k.kid === 'agenttrust-ed25519-v1');

  if (!jwk) {
    console.error('FAIL: agenttrust-ed25519-v1 key not found in JWKS');
    process.exit(1);
  }

  let pass = 0, fail = 0;

  for (const vector of vectors.accept_vectors) {
    const payloadFile = join(__dirname, vector.payload_file);
    const jwsFile = join(__dirname, vector.jws_file);

    const payload = JSON.parse(readFileSync(payloadFile, 'utf8'));
    const jws = JSON.parse(readFileSync(jwsFile, 'utf8'));

    // 1. Recompute canonical bytes via JCS, compare to what was signed
    const canonical = jcs(payload);
    const expectedPayloadB64 = Buffer.from(canonical, 'utf8').toString('base64url');

    if (expectedPayloadB64 !== jws.payload) {
      console.error(`FAIL ${vector.id}: canonical payload mismatch (JCS recompute != jws.payload)`);
      fail++;
      continue;
    }

    // 2. Verify AT signature
    const atSig = jws.signatures.find(s => {
      const header = JSON.parse(b64urlDecode(s.protected).toString('utf8'));
      return header.kid === 'agenttrust-ed25519-v1';
    });

    if (!atSig) {
      console.error(`FAIL ${vector.id}: no agenttrust-ed25519-v1 signature found`);
      fail++;
      continue;
    }

    const sigValid = verifySignature(atSig.protected, jws.payload, atSig.signature, jwk);
    if (!sigValid) {
      console.error(`FAIL ${vector.id}: signature verification failed`);
      fail++;
      continue;
    }

    // 3. Check expected verdict fields
    if (payload.v_gate_skill.verdict !== vector.expected_v_gate_skill_verdict) {
      console.error(`FAIL ${vector.id}: v_gate_skill.verdict mismatch — expected ${vector.expected_v_gate_skill_verdict}, got ${payload.v_gate_skill.verdict}`);
      fail++;
      continue;
    }

    if (payload.composed_decision !== vector.expected_composed_decision) {
      console.error(`FAIL ${vector.id}: composed_decision mismatch — expected ${vector.expected_composed_decision}, got ${payload.composed_decision}`);
      fail++;
      continue;
    }

    console.log(`PASS ${vector.id}: ${vector.description.slice(0, 60)}...`);
    pass++;
  }

  // Reject vectors — MUST fail canonical check
  const rejectVectors = vectors.reject_vectors || [];
  let rejectPass = 0, rejectFail = 0;

  for (const vector of rejectVectors) {
    const payloadFile = join(__dirname, vector.payload_file);
    const jwsFile = join(__dirname, vector.jws_file);
    const payload = JSON.parse(readFileSync(payloadFile, 'utf8'));
    const jws = JSON.parse(readFileSync(jwsFile, 'utf8'));

    const canonical = jcs(payload);
    const expectedPayloadB64 = Buffer.from(canonical, 'utf8').toString('base64url');

    if (expectedPayloadB64 !== jws.payload) {
      console.log(`PASS (reject) ${vector.id}: canonical mismatch detected correctly`);
      rejectPass++;
    } else {
      console.error(`FAIL (reject) ${vector.id}: tampered payload was NOT detected`);
      rejectFail++;
    }
  }

  console.log(`\nPASS: ${pass} accept + ${rejectPass} reject, FAIL: ${fail + rejectFail}`);
  process.exit((fail + rejectFail) > 0 ? 1 : 0);
}

main();
