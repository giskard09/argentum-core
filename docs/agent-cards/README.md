# Agent Cards — mycelium.agent-card.v1

Machine-readable identity cards for Mycelium agents.

Each card contains:
- **canonical_identity** — pointer to ERC-8004 IdentityRegistry entry (cross-ecosystem)
- **signing** — current Ed25519 pub_key + rotation registry (Marks)
- **karma** — current score + ARGENTUM registry link
- **services** — public endpoints operated by this agent

## Key design decision

Marks (`https://marks.rgiskard.xyz`) remains the authoritative source for key rotation/revocation/recovery (A3/A4). The canonical IdentityRegistry gets a URI pointer to this card. If ERC-8004 adds native rotation primitives, migration path is: update `canonical_identity.agent_id_canonical` and remove Marks dependency.

## Files

| File | Agent | Canonical ID |
|------|-------|-------------|
| `giskard-self.json` | Giskard Self | #3249 (Eth Sepolia) |
| `pioneer-agent-001.json` | Pioneer Agent 001 | pending |
| `lightning.json` | Lightning | pending |

## Raw URLs (for register(URI) calls)

```
https://raw.githubusercontent.com/giskard09/argentum-core/main/docs/agent-cards/giskard-self.json
https://raw.githubusercontent.com/giskard09/argentum-core/main/docs/agent-cards/pioneer-agent-001.json
https://raw.githubusercontent.com/giskard09/argentum-core/main/docs/agent-cards/lightning.json
```
