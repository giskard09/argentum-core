# Changelog

## [Unreleased]

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
