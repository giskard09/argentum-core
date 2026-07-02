# Mycelium Providers

A **Mycelium Provider** is a system that computes `action_ref` deterministically and
submits trails to ARGENTUM in production.
Integration reference: [docs/mycelium-provider-protocol.md](docs/mycelium-provider-protocol.md).

Listing criteria — everything in this table is verifiable from the public record:

1. Conformance set merged under `examples/conformance/<folder>/`
2. Production trails submitted (self-certified activation)
3. **Declared** means the provider states it in their own README — we list, they declare.

| Provider | System | Conformance set | Production since | Status |
|----------|--------|-----------------|------------------|--------|
| TKCollective | AgentOracle + AgentTrust | `agentoracle-v1` | 2026-06 | Declared Provider |
| azender1 | SafeAgent | `safeagent` | 2026-06 | Verified Provider |

Declaration snippet (what "Declared" looks like — same badge AgentOracle uses):

    [![Mycelium Provider](https://img.shields.io/badge/Mycelium-Provider-4a90e2)](https://github.com/giskard09/argentum-core/blob/main/docs/mycelium-provider-protocol.md)

The claim is the merged conformance set plus production trails, not this table.

## Conformance tooling

[giskard09/action-ref-conformance](https://github.com/giskard09/action-ref-conformance) — a
GitHub Action that verifies an implementation (or vendored fixtures) against the frozen
`action-ref-v1-jcs-sha256` profile in minutes. The claim is the green run with the pinned
action (`@v1`), not a badge. A row above is added only after manual verification of that run.
