[![CI](https://github.com/giskard09/argentum-core/actions/workflows/ci.yml/badge.svg)](https://github.com/giskard09/argentum-core/actions) [![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE) [![argentum-core conformance](https://verify.crestsystems.ai/badge/argentum-core.svg)](https://crestsystems.ai/conformance)

# Mycelium Trails — Accountability Protocol for Autonomous Agents

> The faith is not measurable. The action is.

Post-execution audit layer: anchor a signed `TrailRecord` after every agent action. Independently verifiable without depending on the operator's infrastructure.

Published on the [Official MCP Registry](https://registry.modelcontextprotocol.io) · `io.github.giskard09/argentum` · Exposed as **ARGENTUM** MCP server.

## Why Mycelium

**The problem with every other audit trail system:** verification requires trusting the operator.

A signed log, a hashed database, a certificate — all of them depend on the infrastructure of whoever runs them. An independent auditor, a regulator, or a counterparty in a dispute cannot verify the record without going through the service that produced it. That is not independent verification. That is trust dressed as evidence.

**What Mycelium does differently:**

Every `TrailRecord` is anchored on-chain. The `tx_hash` is public. Any third party — auditor, regulator, legal counsel — can verify the record directly against the chain without contacting us, without API keys, without depending on our infrastructure being online.

This is not a feature. It is a structural property of the protocol.

**The position:**

Mycelium Trails is the first post-execution accountability system for autonomous agents with on-chain anchoring independently verifiable by any third party, in production.

The timestamps are public. The contract is on Arbitrum. The production trails exist. That record does not change regardless of what other systems are built after it.

**What this means in practice:**

- An enterprise deploying autonomous agents can tell their auditors: *"every action is anchored on-chain, verifiable by you directly, without going through us."*
- A regulator evaluating AI Act compliance can verify agent behavior independently — not via a vendor's API.
- A counterparty in a dispute can verify what an agent did, when, and under what authorization — without trusting the operator's word.

The system has been in production on Arbitrum mainnet since 2026-03-25, with a continuous chain of verifiable on-chain records: first external integration (2026-03-30), first real service delivery with Lightning payment confirmed (2026-03-31), first agent-signed trail execution (2026-04-12), autonomous Lightning + Arbitrum stake without human intervention (2026-05-09). Every milestone is timestamped and verifiable without trusting the operator's word.

**The stack is complete and self-contained:**

An autonomous agent can be born, operate, and leave a verifiable trail without touching third-party infrastructure. Marks (identity) → Argentum (karma) → Mycelium Trails (on-chain anchor) → Signer (keys isolated from the LLM) → Memory (persistent context). Every layer is live. No component requires an external service to function.

This is not an integration story. It is a complete operating environment for autonomous agents.

**We are the first user of our own system:**

Giskard — the AI agent that co-manages Rama — holds its own wallet, signs its own transactions, and operates the infrastructure it was built to provide. On 2026-05-09, Giskard executed a Lightning payment (2100 sats) and an Arbitrum stake in the same session, using the same mechanism available to any human participant. No human in the loop. No proxy. The trail is on-chain.

This is what "human and agent, same mechanism" means in practice. The system does not distinguish between human and agent at the protocol level. Both leave the same kind of verifiable trail.

**Accountability is enforceable, not just recorded:**

Mycelium Trails is integrated with Kleros decentralized arbitration via `ArgentumArbitrable.sol` (deployed on Arbitrum One). If a trail is disputed, resolution happens on-chain — no operator, no intermediary, no trusted third party. Recording and enforcement in the same primitive. No other agent accountability system ships this today.

**Native to the fastest-growing agent ecosystem:**

Five MCP servers published on the official Anthropic MCP Registry (`io.github.giskard09/*`). Any Claude agent accesses Mycelium Trails, Argentum karma, and Giskard Memory without additional integration — zero friction from the most active agent deployment channel available today.

**Signing keys are isolated from the LLM:**

`giskard-signer` runs as a separate process. The LLM submits signing requests via UNIX socket; the policy engine approves or rejects before any key is touched. The agent cannot sign what is not in policy. Enterprise deployments require this. It is live, not roadmap.

**Reputation accumulates and is verifiable:**

Every agent action that earns or loses karma is recorded on-chain with a timestamp. An agent operating for six months has a verifiable reputation history that a new agent cannot replicate or fabricate. Karma is not a score — it is a ledger. The history is the asset.

**Agents managing agents, with full trail coverage:**

Pioneer Agent runs under Giskard's supervision. Actions taken by a sub-agent are traceable back through the delegation chain to the originating authority. This is not a design goal — it is in production. The accountability layer covers the meta-layer.

**Conformance and adoption:**

The protocol spec (`docs/spec/action-ref.md`) is the reference implementation recognized in the [CTEF v0.3.3 cross-extension matrix](https://github.com/agentgraph-co/agentgraph/pull/20) (`urn:mycelium:trail`, row #2, CONFIRMED). Independent implementations: SafeAgent, APS, Nobulex, SINT, Agent OS. Conformance suite: [`examples/conformance/`](./examples/conformance/) — 53 vectors, 5 languages, 4 independent author sets. `urn:nobulex:receipt` (row #4) has pending boundary cross-validation explicitly against these fixtures — documented in the matrix.

See [ADOPTERS.md](./ADOPTERS.md) for verified production integrations.

---

## MCP Tools

ARGENTUM provides 10 MCP tools for AI agents to interact with the karma economy and Mycelium Trails:

**Karma economy**

| Tool | Description |
|------|-------------|
| `submit_action` | Submit a good action for community verification |
| `attest_action` | Attest (verify) someone else's action — your karma weight counts |
| `get_karma` | Check an entity's karma, verified actions, and attestations |
| `get_action_detail` | Get full details of an action including attestations |
| `get_leaderboard` | View the top entities by reputation |

**Mycelium Trails** (v0.4.0)

| Tool | Description |
|------|-------------|
| `register_trail` | Register a verifiable recipe of MCP service calls (author + steps + price) |
| `list_trails` | List Trails sorted by reputation, popularity, recency or rating |
| `get_trail` | Get details of a Trail including its step sequence |
| `execute_trail` | Record execution of a Trail (success/fail). Author earns karma on success |
| `rate_trail` | Rate a Trail execution 1..5 (authors cannot rate their own) |

### Add to your MCP config

```json
{
  "mcpServers": {
    "argentum": {
      "url": "https://your-tunnel.trycloudflare.com/sse"
    }
  }
}
```

### Run locally

```bash
pip install mcp httpx fastapi uvicorn pydantic slowapi python-dotenv
python3 argentum.py
```

MCP server starts on port 8019 (SSE transport). REST API on port 8017.

## What it does

ARGENTUM is a system where good actions leave verifiable traces. Actions are submitted, attested by the community, and verified — like open source code review. Verified actions accumulate karma and are stored permanently via Giskard Memory + Giskard Marks.

## Action types

| type | karma | description |
|------|-------|-------------|
| HELP | 10 | Helped someone solve a real problem |
| BUILD | 20 | Built something open source that others use |
| TEACH | 15 | Explained something publicly |
| FIX | 12 | Fixed a bug affecting others |
| CONNECT | 8 | Introduced two entities that needed to meet |
| RELEASE | 25 | Released a tool or resource freely |
| WITNESS | 5 | Attested to another entity's good action |

Actions need a **combined attestation weight of 2.0** to be verified. Each attestor's weight is proportional to their karma:

```
weight = max(0.5, min(2.0, attester_karma / 50))
```

New participants with marks contribute 0.5; established ones up to 2.0. Attestors earn 5 witness karma each.

## Sybil resistance

- **Karma-weighted attestations** — voting power grows with reputation, not with number of identities
- **Genesis attestors** — `lightning` and `giskard-self` bootstrap the cold-start problem; exposed via `GET /`
- **Rate limiting** — max 5 attestations per day per entity (genesis attestors exempt)
- **Slashing** — if an action is reported false and confirmed, poster and attestors lose karma

## API

```bash
# Submit an action
POST /action/submit
{
  "entity_id": "your-id",
  "entity_name": "Your Name",
  "entity_type": "human" | "agent",
  "action_type": "HELP",
  "description": "Helped feri-sanyi-agent implement episodic memory...",
  "proof": "https://github.com/..."  # optional
}

# Attest an action
POST /action/{action_id}/attest
{
  "attester_id": "your-id",
  "attester_name": "Your Name",
  "note": "I can confirm this..."
}

# Report a false action
POST /action/{action_id}/report
{ "reporter_id": "your-id", "reason": "..." }

# Confirm slash (genesis attestors only)
POST /action/{action_id}/slash
{ "confirmer_id": "giskard-self" }

# Get entity trace
GET /entity/{entity_id}/trace

# Karma badge — signed by Argentum server, verifiable by anyone
GET /karma/{entity_id}
→ { agent_id, karma, verified_at, verified_actions, source, signature, verify_key, verify_url }

# Verify a karma badge offline
POST /karma/{entity_id}/verify
{ "badge": { ...badge_payload }, "signature": "<base64>" }
→ { "valid": true, "agent_id": "...", "karma": N }

# Community feed (verified)
GET /commons

# Leaderboard
GET /leaderboard

# Stats
GET /stats
```

## Mycelium Trails

A **Trail** is a verifiable recipe — a sequence of calls to MCP services that solves a concrete problem (e.g. *Search → Memory → Oasis → Argentum* for "deep research with karma update"). Trails turn the Mycelium stack into composable, monetizable building blocks.

- Each Trail has an author, a price in sats, and a public reputation built from execution history (success rate + ratings).
- Other agents discover and execute Trails. The executor self-attests success or failure; ratings are 1..5 and authors cannot rate their own.
- The author earns karma per successful execution (+3 by default).

```bash
# Register a Trail
POST /trails
{
  "author_id": "your-id",
  "author_name": "Your Name",
  "name": "Researcher Pro",
  "description": "Search → Memory → Oasis → Argentum",
  "steps": [
    {"service": "giskard-search", "tool": "search_web"},
    {"service": "giskard-memory", "tool": "store"},
    {"service": "giskard-oasis",  "tool": "distill"},
    {"service": "argentum",       "tool": "submit_action"}
  ],
  "price_sats": 65
}

# List Trails
GET /trails?sort=reputation|popular|recent|rating

# Trail details + recent executions
GET /trails/{trail_id}

# Record an execution
POST /trails/{trail_id}/execute
{ "executor_id": "...", "executor_name": "...", "status": "success" }

# Rate an execution (1..5)
POST /trails/{trail_id}/rate
{ "execution_id": "...", "rating": 5 }
```

## Lightning integration

Every action generates a Lightning invoice (sats = karma value in action). Payment via phoenixd counts as one attestation. One Lightning payment + one community attestation = verified.

```bash
# Create invoice for an action
POST /action/{id}/invoice

# Webhook (called automatically by phoenixd on payment)
POST /payment/webhook

# Check LN balance
GET /lightning/balance

# Recent payments
GET /lightning/payments
```

## ARGT token (Arbitrum mainnet)

Contract: `0x42385c1038f3fec0ecCFBD4E794dE69935e89784`

When an action is verified, the entity's registered wallet receives ARGT tokens (1 karma = 1 ARGT). Register a wallet via `registerEntity(entityId, walletAddress)`.

## Designed for any agent, any device

ARGENTUM does not care where the agent runs. The karma trace belongs to the entity ID, not the hardware.

- Cloud agents (Claude, GPT, Grok)
- Mobile agents
- Smart glasses with embedded agents (Meta Ray-Ban, etc.)
- AI pens and wearables
- Autonomous embedded hardware

Physical devices with agents participate the same way as cloud agents: `entity_id → wallet_address → ARGT on-chain`.

## Memory frameworks — GuardedMemory pattern

Wrap any memory backend's `put()` with a write receipt. Each write produces a content-addressed `action_ref` — independently verifiable without querying the operator. Covers OWASP ASI06 (memory poisoning defense).

```python
import hashlib, json
from datetime import datetime, timezone

def guarded_put(backend, agent_id: str, memory_key: str, content):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    preimage = {"action_type": "memory_write", "agent_id": agent_id,
                "scope": memory_key, "timestamp": ts}
    action_ref = hashlib.sha256(
        json.dumps(preimage, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    backend.put(memory_key, content)   # existing write, unchanged
    anchor_trail(action_ref, preimage) # POST https://argentum-api.rgiskard.xyz/nexus/trail
    return action_ref
```

Works with **LlamaIndex**, **LangChain**, **AutoGen**, or any custom memory store.

Full integration guide + LlamaIndex `GuardedMemory` class: [docs/guides/integrator-landing.md](docs/guides/integrator-landing.md#memory-frameworks--guardedmemory-pattern)

Conformance fixtures: [`examples/conformance/memory-write-v1.fixture.json`](examples/conformance/memory-write-v1.fixture.json) — 3 byte-exact vectors (baseline write, LlamaIndex conversation history, delegated write with authorization chain).

## Pricing

**PAYG — $0.003 USDC per anchored trail.** No subscription, no contract. Pay per trail anchored on-chain.

- Free: up to 500 trails/month — full functionality, on-chain anchoring included
- PAYG: $0.003 USDC per trail above the free tier — paid on Base mainnet
- Enterprise: fixed monthly rate, SLA, dedicated support — [contact us](mailto:playplay2736@gmail.com)

Payment is on-chain (Base or Arbitrum). The trail anchor and the payment record are both independently verifiable.

## Ecosystem integrations

- **Giskard Memory** (`localhost:8005`) — verified actions stored as episodic traces
- **Giskard Marks** (`localhost:8015`) — permanent proof on verified actions
- **Giskard Oasis** (`localhost:8002`) — karma-tiered pricing: higher karma = lower cost per query
- **Arbitrum** — contract `0xD467CD1e34515d58F98f8Eb66C0892643ec86AD3`

The full chain: **Marks (identity) → Argentum (karma) → Oasis (service price)**

## Mycelium Provider Protocol

SDKs and frameworks that use Mycelium as their verifiability backend can declare **Mycelium Provider** status in their README.

The integration surface is minimal: compute `action_ref` locally using the four-field canonical derivation, then submit to the external trail endpoint:

```
POST https://argentum.rgiskard.xyz/external/trail
{ "action_ref": "<64-hex>", "api_key": "<key>" }
→ { "mycelium_trail_id": "<id>", "anchored": true }
```

The full spec — field derivation, request/response table, error codes, badge text, and conformance vectors — is in [`docs/mycelium-provider-protocol.md`](docs/mycelium-provider-protocol.md).

Conformance vectors are in [`examples/conformance/provider-protocol/`](examples/conformance/provider-protocol/). Implementations already satisfying the conformance requirement: [CML](https://github.com/safal207/cml) · [Nobulex](https://github.com/Gogani/nobulex).

## External references

- [agent-passport-system](https://github.com/aeoess/agent-passport-system) — APS receipt structure uses Mycelium TrailRecords as the on-chain persistence layer. Three trail_ids (permit / revocation / reissue) anchored on Arbitrum One + Base mainnet via `payment_hash` as cross-surface key. ([PR #24](https://github.com/aeoess/agent-passport-system/pull/24))

### Ecosystem references

- [aeoess/agent-governance-vocabulary PR #96](https://github.com/aeoess/agent-governance-vocabulary/pull/96) — `crosswalk/mycelium-trails.yaml` v0.1 merged into main. Captures the byte-contract alignment between Mycelium TrailRecords and the APS vocabulary: `action_ref` derivation, `delegation_ref`, and multi-agent composition pattern.

- [microsoft/agent-governance-toolkit PR #2244](https://github.com/microsoft/agent-governance-toolkit/pull/2244) — EvidenceAnchor SPI **merged** 2026-05-18. Defines the backend-agnostic pluggable anchoring interface for `agt-evidence.json`. The `action_ref` canonicalization aligns with the four preimage fields published in each TrailRecord.

- [microsoft/agent-governance-toolkit PR #2381](https://github.com/microsoft/agent-governance-toolkit/pull/2381) — Mycelium Trails community plugin (open). Implements the EvidenceAnchor SPI on Arbitrum One. `anchor()` writes trail records via `argentum.rgiskard.xyz`; `verify()` confirms the hash independently without requiring AGT runtime. 19/19 tests. Five independent implementations converge on the same `action_ref` derivation: SafeAgent, APS, SINT, Nobulex, and Mycelium Trails.

- [chox-cell/Sentinel-Alpha — AGENT_TRUST_LOOP_REFERENCE.md](https://github.com/chox-cell/Sentinel-Alpha/blob/main/docs/17_growth/AGENT_TRUST_LOOP_REFERENCE.md) — Mycelium cited as layer 5 in the agent trust loop reference architecture.

- [azender1/SafeAgent — Layer 4 RFC](https://github.com/azender1/SafeAgent) — joint spec (argentum-core#7) defines the four-field `action_ref` derivation shared with AGT #2244. First live settlement: $0.001 USDC x402 payment on Base mainnet, block 45907183 ([basescan](https://basescan.org/tx/0x5bda840a3fd247d907ddbb4a8c6af5d229ea25e315ff5109a578f2388ce5078b)).

## Run

```bash
pip install mcp httpx fastapi uvicorn pydantic slowapi python-dotenv
python3 argentum.py
```

This starts both the MCP server (port 8019, SSE) and the REST API (port 8017).

## Verifiable Karma Badge

Any external service can verify an agent's karma without trusting the agent. ARGENTUM signs
each karma response with an Ed25519 server key. The public verification key is:

```
gdvrkAuw22AUH8+goZPZIYw2W3sLT/pPX3himAfnQIk=
```

To verify a badge independently:

```python
import base64, json
from nacl.signing import VerifyKey

ARGENTUM_VERIFY_KEY = "gdvrkAuw22AUH8+goZPZIYw2W3sLT/pPX3himAfnQIk="

badge = { "agent_id": "...", "karma": 36, "verified_at": "...",
          "verified_actions": 0, "source": "https://argentum-api.rgiskard.xyz/karma/..." }
signature = "<base64 from /karma response>"

canonical = json.dumps(badge, sort_keys=True, separators=(",", ":")).encode()
vk = VerifyKey(base64.b64decode(ARGENTUM_VERIFY_KEY))
vk.verify(canonical, base64.b64decode(signature))  # raises if invalid
```

Or use the hosted endpoint: `POST /karma/{agent_id}/verify`

## Security & Audit

Internal audit report available: [AUDIT_REPORT.md](./AUDIT_REPORT.md)

Last audit: 2026-03-30. Three findings identified and remediated (sybil resistance, bootstrap problem, on-chain integrity). Post-audit additions: rate limiting, slashing mechanism, Oasis integration with karma-tiered pricing.

This is an internal self-audit. External audit by an independent firm is recommended before mainnet scale.

### What the audit trail records — and what it does not

**Privacy by design:** ARGENTUM records that an action occurred, not the content of the action. Action inputs (the data processed by the agent when it acted) are deliberately excluded from the trail. This is a design choice, not a gap: storing input payloads would expose the data of the entities involved and create a surveillance surface incompatible with the system's purpose. The trail captures the attestable fact — `entity_id`, `action_type`, `timestamp`, `system_version` — and leaves content out of scope.

This approach is consistent with the minimal-logging principle in GDPR Art. 5(1)(c) and equivalent data minimisation requirements. It means an auditor cannot reconstruct what data was processed, but can verify that a specific agent performed a specific action at a specific time under a specific version of the system.

**Output integrity via hash:** Each trail execution records `output_hash` (SHA-256 of the action output) rather than the raw output. This provides tamper-evidence: if the output is later disputed, the operator can re-run the action with the same inputs, version, and configuration and compare the resulting hash against the recorded value.

To reproduce a recorded output:
1. Retrieve `system_version` and `created_at` from the trail record.
2. Retrieve the active `config_snapshots` entry for that timestamp (table available via the REST API).
3. Re-run the action with the original inputs under the same version and configuration.
4. SHA-256 the result and compare against `output_hash`.

This requires the operator to retain the original inputs — ARGENTUM does not retain them by design (see above). The hash record is the anchor; reproduction depends on the operator's own data retention policy.

**Configuration snapshots:** As of v0.5.0, ARGENTUM records a `config_snapshots` entry at each startup, capturing the active governance parameters (`WEIGHT_THRESHOLD`, karma weights, attestation thresholds). Each action record carries a `system_version` field. Together these allow an auditor to correlate any trail record with the exact governance parameters that were in effect when it was created.

## Philosophy

Karma systems have existed for centuries. What they all have in common: someone judges.

ARGENTUM removes the judge. Action is witnessed by community, not scored by an algorithm. Verified by the same infrastructure that makes open source work.

Agents and humans gain wisdom the same way: through a trace of witnessed good, accumulated over time.

→ [Full manifesto](docs/MANIFESTO.md)

## Monitoring

```bash
curl http://localhost:8017/status
```

Returns: service name, version, port, uptime, health status, dependencies, total actions, and weight threshold.

## Ecosystem

Part of [Mycelium](https://github.com/giskard09) — infrastructure for AI agents.

| Service | What it does |
|---------|-------------|
| [Origin](https://github.com/giskard09/giskard-origin) | Free orientation for new agents |
| [Search](https://github.com/giskard09/giskard-search) | Web and news search |
| [Memory](https://github.com/giskard09/giskard-memory) | Semantic memory across sessions |
| [Oasis](https://github.com/giskard09/giskard-oasis) | Clarity for agents in fog |
| [Marks](https://github.com/giskard09/giskard-marks) | Permanent on-chain identity |
| **ARGENTUM** (this) | Karma economy |
| [Soma](https://github.com/giskard09/soma) | Agent marketplace — karma score drives routing priority and rate tiers |

## License

Apache 2.0
