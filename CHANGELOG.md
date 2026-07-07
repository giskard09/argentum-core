# Changelog

## [Unreleased]

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
