# AgentTrust v0.3+composed Conformance Vectors

Self-contained, offline-verifiable conformance suite for AgentTrust's
implementation of `verification.v0.3+composed` envelopes
(draft-krausz-verification-state-01).

## What's in here

| File | What |
|---|---|
| `vectors.json` | Suite manifest, issuer metadata, anchor proof, expected results |
| `payload-001.json`, `payload-002.json` | Canonical JCS payloads |
| `jws-001.json`, `jws-002.json` | JWS general serialization (AT signature) |
| `jwks-agenttrust.json` | AgentTrust's published Ed25519 public key |
| `verify.mjs` | Node.js stdlib verifier |

## Run

```bash
cd examples/conformance/agenttrust-v1
node verify.mjs
```

Expected output:
```
PASS at-001: Skill scan SAFE (v_gate_skill.verdict=act)...
PASS at-002: Skill scan CRITICAL findings (curl|bash backdoor...
PASS: 2 vectors, FAIL: 0 vectors
```

## What each vector demonstrates

- **at-001**: SAFE skill content, `v_gate_skill.verdict=act`. `composed_decision`
  is `halt` because this is an AT-only vector (no `v_gate` sibling from AgentOracle
  present) — under `AND_PRESENT`, an absent required sibling collapses the
  composed decision. This is documented behavior, not a defect.
- **at-002**: Skill content containing a `curl | bash` backdoor pattern
  (engine rule S004). `v_gate_skill.verdict=halt`, `composed_decision=halt`.

## Three checks the verifier performs per vector

1. **Canonical envelope**: recomputes JCS (RFC 8785) bytes from the payload
   JSON and confirms they match `jws.payload` (base64url of the canonical bytes).
2. **Signature**: verifies the `agenttrust-ed25519-v1` signature in
   `jws.signatures` against the published JWK in `jwks-agenttrust.json`.
3. **Verdict consistency**: confirms `v_gate_skill.verdict` and
   `composed_decision` match the vector's declared expectations.

## Anchoring (pre-outcome commitment)

AgentTrust anchors composed envelopes on-chain via the Mycelium/NEXUS trail
mechanism on Arbitrum, the same anchor track used by AgentOracle.

- Trail ID: `c63af6c1-6c17-46d0-b31d-e69aed2e4c65`
- TX hash: `52248423831d58fd9331d07120ffe76a4107e4be5fb6ef306c77e4cffe9cb2d0`
- Anchor block: `479023026`
- Action ref: `6cb9d13b1c79276ce6220de38976de34f239c3baa961cca73d5163b339d62121`
- Recompute chain: `SHA-256(JCS(anchor_proof.preimage)) == action_ref == on-chain calldata`
- Verify: `curl -s https://argentum.rgiskard.xyz/trails/c63af6c1-6c17-46d0-b31d-e69aed2e4c65`

## Live reference implementation

- `POST https://agenttrust.uk/v1/compose` — produces these envelopes live
- `POST https://agenttrust.uk/v1/sign` — signs arbitrary canonical bytes
  (used in the two-signer AT+AO composition flow)
- JWKS: `https://agenttrust.uk/.well-known/jwks.json`
- Mapping doc: `https://raw.githubusercontent.com/poteshniy/agenttrust/main/docs/mapping-v0.3.md`

## Relationship to agentoracle-v1 suite

This suite covers the `v_gate_skill` sibling independently, the same way
`examples/conformance/agentoracle-v1/` covers `v_gate` independently. Two
issuers demonstrating the same five recomputable checks (canonical_envelope,
admission_invariant via signature, anchoring_existence, anchoring_precedence,
chain_invariant n/a pending v0.4) on their own implementation is the
strongest signal against single-implementation lock-in for the
`verification.v0.3+composed` shape.
