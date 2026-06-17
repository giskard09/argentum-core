# AgentOracle independent conformance set for action-ref-v1 (verification.v0.3 binding)

An independent implementation of the `action-ref-v1` wire format from
[`argentum-core/docs/spec/action-ref.md`](../../../docs/spec/action-ref.md),
showing how it composes inside the [`verification.v0.3`](https://datatracker.ietf.org/doc/draft-krausz-verification-state/)
receipt envelope as a forward-pointing reference.

`action_ref = SHA-256(JCS(preimage))` over the four-field preimage
`{agent_id, action_type, scope, timestamp}`, with JCS per RFC 8785 and the
timestamp pinned to RFC 3339 UTC with exactly three fractional digits and a
`Z` suffix (`YYYY-MM-DDTHH:MM:SS.mmmZ`).

## Two-receipt composition

`verification.v0.3` issues a receipt **before** the action settles — the gate
fires on a factual claim, the verdict is `act` or `halt`, and the receipt
carries the action_ref of the action the verdict refers to. After settlement,
`GET argentum-api.rgiskard.xyz/trails/verify?agent_id=X&action_ref=Y` resolves
the same action_ref against the Mycelium trail to confirm the post-payment
work actually happened.

The two receipts compose: one proves what gate fired and on what basis, the
other proves the work happened. A third party verifies both without trusting
either issuer.

Pre-commitment binding is supported by explicit spec design: §3.1 of
[`draft-giskard-aeoess-action-ref`](https://github.com/giskard09/draft-giskard-aeoess-action-ref)
defines the timestamp field as "the moment the action was claimed (before
execution)." All four preimage fields are known at gate time.

## Files

- `vectors.json` — the vector set. Accept vectors carry the four-field
  preimage, the canonical JCS string, the expected lowercase-hex SHA-256, and
  a `receipt_context` block showing how that hash is embedded as
  `context.action_ref` (prefixed `sha256-`) inside a `verification.v0.3`
  receipt. Reject vectors carry `reject: true` and must fail the timestamp
  grammar rather than be coerced.
- `verify.py` — standalone runner, Python 3 stdlib only. Vendored JCS
  serializer, independent recomputation.
- `verify.mjs` — standalone runner, Node.js built-ins only (`node:crypto`,
  `node:fs`). Independent recomputation in a second language.

Neither runner wraps the AgentOracle SDK. Each recomputes from the preimage,
so a pass cross-checks the hashes against two independent implementations.

## Run

```
python3 verify.py
node verify.mjs
```

Both exit 0 on a full pass and print:

```
PASS: 10 vectors (7 accept recomputed byte-identical, 3 reject correctly refused)
```

## Coverage

The accept vectors include:

- Basic happy path (`ao-001`) — pre-action factual-claim gate with `v_gate: act`
- Halt verdict (`ao-002`) — gate emits action_ref even when forbidding the action
- Cross-issuer interop (`ao-003`) — AgentTrust receipt under the same envelope
- Key-order independence (`ao-004`) — three JSON orderings → one canonical form
- Unicode preservation (`ao-005`) — Cyrillic + emoji, no normalization
- Timestamp rollover (`ao-006`) — `.000` fractional digits written in full
- Empty-string scope (`ao-007`) — load-bearing in the preimage

The reject vectors include three timestamp-grammar failures that must NOT be
coerced into the accept path:

- Missing millisecond digits (`ao-r01`) — `2026-06-08T00:00:00Z`
- Comma fraction separator (`ao-r02`) — `2026-06-08T00:00:00,123Z`
- `+00:00` offset instead of `Z` (`ao-r03`) — canonical preimage requires `Z`

## Relationship to the draft and the action-ref-v1 baseline

The same implementation reproduces the argentum-core
[`action-ref-v1-baseline.fixture.json`](../action-ref-v1-baseline.fixture.json)
vectors byte-identical when run against that preimage set, demonstrating that
verification.v0.3 receipts carrying forward-pointing action_refs are wire-
compatible with the action-ref-v1 baseline.

## Verification.v0.3 receipt embedding

Each accept vector's `receipt_context.verification_v0_3_field` value is the
exact string `verification.v0.3` issuers (currently AgentOracle and AgentTrust)
emit at `context.action_ref` in a signed receipt:

```json
{
  "receipt_version": "0.3.0",
  "mapping_id": "agentoracle-v0.3-2026-05-30",
  "context": {
    "action_ref": "sha256-5f5ff225130888931cc746b021c6dfe9926b3b267bd45f94295ca2d4007ae91a",
    ...
  },
  "v_gate": "act",
  ...
}
```

The full receipt envelope (JWS detached signature over the canonical payload,
JWKS-published Ed25519 verification key, content-addressed mapping document)
is specified in [`draft-krausz-verification-state-01`](https://datatracker.ietf.org/doc/draft-krausz-verification-state/)
and registered as an [ERC-8210 receipt profile](https://github.com/wangbin9953/erc8210-aap/blob/v2-draft/docs/profiles/verification-v0.3.md).
A full-envelope conformance suite (signature verification + canonical payload
+ mapping recompute + action_ref binding) is in scope for a future addition;
this suite focuses on the action_ref binding itself for cross-validation with
argentum-core.

## Issuers represented

| Issuer | JWKS endpoint | Vectors |
| --- | --- | --- |
| AgentOracle | https://agentoracle.co/.well-known/jwks.json | `ao-001`, `ao-002`, `ao-004` – `ao-007`, `ao-r01` – `ao-r03` |
| AgentTrust | https://agenttrust.uk/.well-known/jwks.json | `ao-003` |

Both issuers produce byte-identical action_refs against the same preimage by
construction, not by convention.

## Maintainer

- Profile authored by Joe Krausz (TKCollective LLC) — Joe@agentoracle.co
- Issues / questions: GitHub issues on [TKCollective/agentoracle-receipt-spec](https://github.com/TKCollective/agentoracle-receipt-spec/issues)
