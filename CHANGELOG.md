# Changelog

## [Unreleased]

### Added — farley-receipt-signature: signed input published per vector (2026-09-23)

- `examples/conformance/farley-receipt-signature/index.json`: `signed_input_hex` per vector, the exact bytes each signature was made over. Without it, a re-run could confirm that `signature-input-drift.reject` fails, but not that it fails for the stated reason (signed over pretty-printed bytes rather than `JCS(payload)`). The four receipts and `jwks.json` are byte-identical; only `index.json` changes.
- `tests/test_farley_receipt_vectors.py`: every signature verifies over its published input, and only the drift reject's input differs from `JCS(payload)`.

### Added — trail-head-ref-v1: completeness of an agent's trail (2026-09-23)

- `docs/spec/trail-head-ref-v1.md` (draft): per-agent hash chain (`seq`, `prev_head`) for continuity, plus a checkpoint per agent per period, sealed under one Merkle root (batch-anchor construction, unchanged) and anchored with `AnchorRegistry.anchor(bytes32)`, for completeness. Empty periods still seal. Optional agent-signed `agent_seq` shows actions dropped at ingest between the first and last presented (a tail drop is visible only against the agent's own last counter). Distinct verdicts per failure; no checkpoint → completeness `not_evaluated`, never a pass. `action_ref` unchanged. Not yet emitted by the production trail pipeline.
- `plugins/agt_evidence_anchor/trail_head.py` + `tests/test_trail_head.py` (22 tests): removal, reorder, tampered record, renumbered removal, tail truncation (passes continuity alone, caught by the checkpoint), full re-chain after the fact, foreign or unproven checkpoint, stale checkpoint, agent-counter gap — each caught by a different check.
- Credit: the property split and the attacks come from [microsoft/autogen#7353](https://github.com/microsoft/autogen/issues/7353) — Yarmoluk (records included vs. every action recorded; removal/reorder test), babyblueviper1 (tail truncation against a live chain; a count signed by the log's own key adds no independence), TKCollective (gapless per-session sequence). Empty-period sealing: stillmarcus24, [x402-foundation/x402#2887](https://github.com/x402-foundation/x402/issues/2887).

### Added — vector key gate in CI (2026-09-23)

- `tools/check_vector_keys.py` + `tools/vector_key_gate.json`: every JSON key in a vector set that declares an external schema must appear in that spec as a field (quoted, `key (REQUIRED|…)`, or identifier-shaped in prose). Runs as its own CI step and as `tests/test_vector_key_gate.py`. Opt-in per set, against a vendored, hash-pinned spec (`docs/spec/vendor/`), so a new draft revision is an explicit commit. First set: `farley-receipt-signature` against draft-farley-acta-signed-receipts-03 (vendored unmodified under BCP 78). It would have stopped the `"tool"` / `tool_name` error that both verifiers passed in #96 (reported by robertolocatelli81-dev, Noûs).

### Added — idempotency-ref-v1.1: logical identity vs payload identity (2026-09-23)

- `docs/spec/idempotency-ref.md` failed two of the four cases of the logical-identity test: (3) a second intentional payment with a byte-identical payload was deduplicated as a retry, because Invariant 5 accepted "a hash of the caller's own pre-execution request" as a key source; (4) a drifted retry ($100 → $125) under the same key passed silently as a duplicate, because nothing bound the key to the admitted payload. v1.1, additive: the key is the logical action id minted at admission (Invariant 6: distinct intentional actions MUST carry distinct keys; content-derived keys only under a declared domain invariant); new `admitted_payload_digest` carried next to `idempotency_ref`, outside the artifact (Invariant 7: same key + different digest → CONFLICT, fail closed). Every v1.0 artifact and `idempotency_ref` is unchanged.
- `examples/conformance/idempotency-ref-v1.1/`: the four cases plus three negatives, each failing on a different check (content-derived key, no digest check, digest inside the artifact); `tests/test_idempotency_ref_v1_1.py`. `idempotency-ref-v1.fixture.json` `idem-002` gains a `v1_1_note` (hashed fields untouched).
- Four-case test defined by impartshadow/agent-contracts, [crewAIInc/crewAI#5802](https://github.com/crewAIInc/crewAI/issues/5802) (comment [5790417981](https://github.com/crewAIInc/crewAI/issues/5802#issuecomment-5790417981)); pinned as a regression by stringsofthemind-oss, [stringsofthemind-oss/once#45](https://github.com/stringsofthemind-oss/once/pull/45).

### Added — farley-receipt-signature conformance vectors (2026-09-23)

- `examples/conformance/farley-receipt-signature/`: 4 vectors, each a reject with a conformant twin, for [draft-farley-acta-signed-receipts-03](https://datatracker.ietf.org/doc/draft-farley-acta-signed-receipts/03/), envelope shape, archival mode. The first case, `signature-input-drift` (MUST), signs pretty-printed bytes instead of `JCS(payload)`. The second, `superseded-key` (SHOULD, §9.2), uses a key after its `valid_until`. It is a minimal pair: only `issued_at` differs. The key comes from an external `jwks.json` (§9.5), and the keys are TEST ONLY, with public seeds. Includes a reference `verify.py` (pynacl), a deterministic `build.py`, and the observed result for `@veritasacta/verify` 0.10.19, which accepts the superseded-key reject because its receipt JWKS path does not read validity windows.
- `tests/test_farley_receipt_vectors.py`: the vectors match `index.json`, the build is byte-deterministic, the pair is minimal, and mutated receipts are refused.
- Fixed (same day): the payloads carried `"tool"`, which no revision of the draft defines; §3.1.1 makes `tool_name` REQUIRED for `protectmcp:decision`, so the two conformant twins did not conform to the type they declare and could not serve as ACCEPT cases for a verifier that checks §3.1.1. `build.py` now emits `tool_name` and the four receipts are regenerated; `jwks.json`, both kids and every verdict are unchanged. Reported by robertolocatelli81-dev (Noûs) in [#96](https://github.com/giskard09/argentum-core/pull/96).

### Changed — verifier-key-source-ref-v1.1: recomputable is not anchored (2026-09-23)

- `docs/spec/verifier-key-source-ref-v1.md`: the `key_source` table said `embedded` was "Yes — no external fetch required", and the column-split table gave "one signer, embedded key" ✓/✓. Both are right about recomputability, but the spec did not say that recomputability is not authenticity. An embedded key is chosen by the fixture's producer, so on its own it gives no authenticity guarantee ([draft-farley-acta-signed-receipts-03 §9.5](https://datatracker.ietf.org/doc/draft-farley-acta-signed-receipts/03/)). This change adds an "Anchored by this record?" column, a normative "Recomputable vs anchored" section, invariant 6 (`recomputable_not_anchored`) and a note under the scenario table. Existing rows, columns, fixture and verifier are unchanged. It is additive for boards, which still report the same two columns. Self-audit.

### Fixed — idempotency-ref-v1 orphaned-PENDING sweeper unsafe on unconditional timer (2026-08-23)

- `docs/spec/idempotency-ref.md`: the orphaned-PENDING rule stated an unconditional `SHOULD` treating a PENDING record older than `window_ms` as equivalent to FAILED. That inference is unsound whenever the provider call has no idempotency key of its own (`send_email`, `place_trade`) — a crash between the provider call succeeding and the anchor write is indistinguishable from a call that never landed, so sweeping to FAILED on a timer authorizes the exact duplicate the artifact exists to prevent. Corrected: default resolution is now a provider-confirmed query (no timer-based clearing); treating `window_ms` alone as sufficient requires an explicit `provider_idempotent: true` declaration, not an assumed default. `examples/conformance/idempotency-ref-v1.fixture.json`'s `window_semantics` invariant updated to match. Reported by impartshadow/agent-contracts, [crewAIInc/crewAI#5802](https://github.com/crewAIInc/crewAI/issues/5802).

### Fixed — strict RFC 8785 canonicalization in agenttrust-v1 conformance suite (2026-07-08)

- `examples/conformance/agenttrust-v1/verify.mjs` replaced its hand-rolled `jcs()` helper (sort keys + `JSON.stringify`, self-consistent with the fixtures but not spec-compliant) with the `canonicalize` npm package (strict RFC 8785). Reported by TKCollective, [#32](https://github.com/giskard09/argentum-core/issues/32).
- With strict canonicalization, `jws-002.json` (vector `at-002`) now correctly fails `canonical_mismatch` — its embedded payload's `skill_results` key order isn't RFC 8785 canonical. Fixing it requires AgentTrust to regenerate and re-sign `jws-002.json`/`jws-003.json`; we don't hold the `agenttrust-ed25519-v1` signing key. Tracked in #32, pending their PR.
- `at-r01` also needs an AgentTrust re-sign to demonstrate actual semantic tampering (its embedded verdict doesn't currently differ from the sidecar).

### Added — AnchorRegistry on Ink mainnet (2026-07-07)

- `AnchorRegistry` deployed on Ink mainnet (chain_id 57073) at the same canonical CREATE2 address `0x49fEcA52bC634a9Ab773226D16619deC547794aa` as Arbitrum One and Base. Deploy tx `0xcbd2d137e14287a13168eb14a75d4cad44456d94a78946ef72170d3f3723a895`, source verified on the Ink explorer.
- `counterparty_ref_anchor.chain_id: 57073` is now a conformant target. Additive — existing integrators unaffected.

### Added — Accountability primitives & multi-chain anchor (2026-06)

- `counterparty_ref` (`docs/spec/counterparty-ref.md`) — content-addressed pointer to a counterparty snapshot at action time. JCS-canonical preimage with timestamp.
- `counterparty_ref_anchor` (optional extension on `counterparty_ref`) — verifiable on-chain pointer to the `markUsed(bytes32)` transaction that anchored the preimage. Chain-agnostic via `chain_id`. `GiskardPayments` deployed on Base mainnet (`0x90Fa32a9568c6aE6BEa915DF8737acfd7EEA97De`, chain_id 8453) alongside the existing Arbitrum deployment.
- `signing_trust_ref` (`docs/spec/signing-trust-ref.md`) — signer-type pointer (`operator_key` / `agent_keypair` / `multi_party`) for composed multi-signer envelopes.
- `verification_mode` (`docs/spec/verification-semantics.md`) — distinguishes producer-`asserted` from independently-`enforced` records.
- All fields optional and backward-compatible; existing consumers unaffected.

### Added — Schema v2 (2026-05-12)

- `scope` (string | null): optional field on TrailRecord — what the agent was authorized to do
- `delegation_ref` (string | null): optional opaque pointer to the delegation chain that originated the action
- Both fields are nullable and backward-compatible; existing consumers are unaffected
- `init_db` runs idempotent ALTER TABLE migrations for existing databases
- Affected: `record_trail()` signature, `_row_to_dict()` output, all SELECT queries

**Integrators:** `scope` and `delegation_ref` appear as `null` in all responses until explicitly supplied at write time. No action required to stay compatible.

## [v0.4.0] — 2026-04-30

- Auditoría v0.4 GREEN (FINDING-001 through FINDING-004 resolved)
- giskard-self agentId canonical #3249 (Eth Sepolia)
- pioneer-agent-001 in ARGENTUM (karma=20)

## [v0.3.0] — 2026-04-13

- Mycelium Trails v0 integrated in argentum-core
- `/trails/verify` endpoint live at `argentum.rgiskard.xyz`
- AgentKit action provider (TypeScript)
- Cross-rail fixture published in x402-foundation/x402
