# action_ref — derivation spec

`action_ref` is a deterministic, content-addressed identifier for an agent action. Any party with the four preimage fields can independently compute it — no trust in the emitting system required.

## Derivation

```python
import hashlib

def compute_action_ref(agent_id: str, action_type: str, scope: str, timestamp: int) -> str:
    payload = f"{agent_id}:{action_type}:{scope}:{int(timestamp)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | string | Stable identifier for the agent (DID, username, or opaque string) |
| `action_type` | string | What the agent did — semantic label (`code.execute`, `payment.send`, etc.) |
| `scope` | string | Declared authorization boundary — what the agent was allowed to do, not what it did. Pass `""` if not applicable. |
| `timestamp` | integer | Unix seconds (not milliseconds). Use `int(time.time())` in Python, `Math.floor(Date.now() / 1000)` in JS. |

Separator is `:`. Payload is UTF-8 encoded before hashing.

## Canonical receipt envelope — v1.0

Implementations that emit a receipt referencing this spec SHOULD include the following fields to ensure long-lived verifiability:

```json
{
  "packet_version": "1.0",
  "action_ref": "<sha256 hex>",
  "hash_algo": "sha256",
  "preimage_format": "agent_id:action_type:scope:ts",
  "preimage": {
    "agent_id": "...",
    "action_type": "...",
    "scope": "...",
    "ts": 1234567890
  }
}
```

**Why these fields matter:**

- `packet_version` — forward-compat anchor. v1 verifiers can explicitly reject unknown versions rather than fail silently. Additive changes increment the version; field semantics per version are documented here.
- `hash_algo` — makes receipts self-describing. If a future implementation switches to BLAKE3 or keccak256, receipts issued before the change remain replayable because the verifier knows which hash to use per-receipt.
- `preimage_format` — closes the separator ambiguity class. A verifier that joins fields with `|` instead of `:` produces a different `action_ref`. Explicit format eliminates this failure mode.

## Canonical linking key

The same `action_ref` is computable from:

- a Mycelium TrailRecord (preimage fields published in each record)
- a Nobulex covenant receipt (`action_type` as semantic label + timestamp + agent_id + scope)
- a SafeAgent claim ([azender1/SafeAgent](https://github.com/azender1/SafeAgent), joint spec [argentum-core#7](https://github.com/giskard09/argentum-core/issues/7))
- a CrewAI idempotency key ([crewAIInc/crewAI#5822](https://github.com/crewAIInc/crewAI/pull/5822)) — key derivation converges on the same primitive from the retry-deduplication direction
- NEXUS oracle receipts ([nexus-agent-xa12.onrender.com/receipt](https://nexus-agent-xa12.onrender.com/receipt)) — implements canonical envelope v1.0

Any verifier holding one artifact can validate against another without trusting either system.

## Cross-references

- Full TrailRecord schema: [MYCELIUM_TRAILS_REFERENCE.md](../MYCELIUM_TRAILS_REFERENCE.md)
- AGT EvidenceAnchor proposal (Microsoft): [agent-governance-toolkit PR #2244](https://github.com/microsoft/agent-governance-toolkit/pull/2244)
- Joint spec with SafeAgent: [argentum-core#7](https://github.com/giskard09/argentum-core/issues/7)
- Nobulex alignment: [MetaGPT#1991](https://github.com/geekan/MetaGPT/issues/1991)
