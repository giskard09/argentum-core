#!/usr/bin/env node
// Conformance verifier for agentoracle-v1 (verification.v0.3 receipts carrying
// a forward-pointing action_ref per draft-giskard-aeoess-action-ref).
//
// Standalone: Node.js built-ins only (node:crypto, node:fs). A minimal
// RFC 8785 (JCS) serializer is vendored below, scoped to the action_ref
// preimage domain (a flat JSON object whose values are all strings). It is an
// independent recomputation, not a wrapper around the AgentOracle SDK or any
// other library, so a pass here cross-checks the SHA-256 hashes in vectors.json
// against a second implementation. The Python sibling (verify.py) is a third,
// in another language.
//
// Exit 0 on full pass. Nonzero with a per-vector diff on any failure.

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { createHash } from 'node:crypto'

// RFC 3339 UTC, uppercase T and Z, exactly three fractional digits.
const TIMESTAMP_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const PREIMAGE_KEYS = ['action_type', 'agent_id', 'scope', 'timestamp']

// One string per RFC 8785 (ECMA-262 JSON.stringify rules): shortest form,
// two-character escapes for the named controls, \u00xx for the rest of the
// C0 range, everything else literal. JSON.stringify implements exactly this.
const jcsString = (s) => JSON.stringify(s)

// RFC 8785 canonicalization for the action_ref preimage domain: a flat object
// whose values are all strings. Keys sorted by UTF-16 code units (section
// 3.2.3); JS default string sort is code-unit order.
function jcsCanonicalizeFlatStrings(obj) {
  for (const k of Object.keys(obj)) {
    if (typeof obj[k] !== 'string') {
      throw new TypeError(`preimage value for '${k}' must be a string, got ${typeof obj[k]}`)
    }
  }
  const keys = Object.keys(obj).sort()
  const pairs = keys.map((k) => `${jcsString(k)}:${jcsString(obj[k])}`)
  return `{${pairs.join(',')}}`
}

function computeActionRefV1(preimage) {
  const ts = preimage.timestamp
  if (!TIMESTAMP_RE.test(ts)) {
    throw new RangeError(
      `timestamp must be RFC 3339 UTC with three fractional digits and a Z suffix (YYYY-MM-DDTHH:MM:SS.mmmZ), got '${ts}'`
    )
  }
  const canonical = jcsCanonicalizeFlatStrings(preimage)
  return createHash('sha256').update(Buffer.from(canonical, 'utf-8')).digest('hex')
}

const preimageFromInput = (inp) => Object.fromEntries(PREIMAGE_KEYS.map((k) => [k, inp[k]]))

const here = dirname(fileURLToPath(import.meta.url))
const suite = JSON.parse(readFileSync(join(here, 'vectors.json'), 'utf-8'))

const failures = []
let accepted = 0
let rejected = 0

for (const vec of suite.vectors) {
  const vid = vec.id
  if (vec.reject) {
    const ts = vec.input.timestamp
    if (TIMESTAMP_RE.test(ts)) {
      failures.push(`${vid}: timestamp '${ts}' PASSED the grammar but must be rejected (${vec.reason})`)
      continue
    }
    try {
      computeActionRefV1(preimageFromInput(vec.input))
      failures.push(`${vid}: computeActionRefV1 did not raise on invalid timestamp '${ts}'`)
    } catch (e) {
      rejected += 1
    }
    continue
  }

  const preimage = preimageFromInput(vec.input)
  const canonical = jcsCanonicalizeFlatStrings(preimage)
  if ('canonical' in vec && canonical !== vec.canonical) {
    failures.push(`${vid}: canonical form mismatch\n  expected: ${vec.canonical}\n  computed: ${canonical}`)
    continue
  }
  const got = computeActionRefV1(preimage)
  if (got !== vec.expected) {
    failures.push(`${vid}: hash mismatch\n  expected: ${vec.expected}\n  computed: ${got}\n  canonical: ${canonical}`)
    continue
  }
  // Cross-check: verification.v0.3 embeds the action_ref as a sha256-prefixed
  // string at context.action_ref. The receipt_context.verification_v0_3_field
  // value MUST be exactly `sha256-<expected>`.
  if (vec.receipt_context && vec.receipt_context.verification_v0_3_field !== `sha256-${vec.expected}`) {
    failures.push(
      `${vid}: verification.v0.3 embedding mismatch\n  expected: sha256-${vec.expected}\n  declared: ${vec.receipt_context.verification_v0_3_field}`
    )
    continue
  }
  let ok = true
  const variants = vec.input_json_variants || []
  for (let i = 0; i < variants.length; i++) {
    const variant = JSON.parse(variants[i])
    const vgot = computeActionRefV1(preimageFromInput(variant))
    if (vgot !== vec.expected) {
      failures.push(`${vid}: key-order variant ${i} hash mismatch\n  expected: ${vec.expected}\n  computed: ${vgot}\n  variant: ${variants[i]}`)
      ok = false
    }
  }
  if (ok) accepted += 1
}

const total = suite.vectors.length
if (failures.length) {
  console.log(`FAIL: ${failures.length} failure(s) across ${total} vectors\n`)
  for (const f of failures) console.log(`- ${f}`)
  process.exit(1)
}
console.log(`PASS: ${total} vectors (${accepted} accept recomputed byte-identical, ${rejected} reject correctly refused)`)
