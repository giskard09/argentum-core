# action_ref — derivation spec

`action_ref` is a deterministic, content-addressed identifier for an agent action. Any party with the four preimage fields can independently compute it — no trust in the emitting system required.

## Derivation

```python
import hashlib
import json

def compute_action_ref(
    agent_id: str,
    action_type: str,
    scope: str,
    timestamp: str,   # RFC 3339 UTC, 3-digit ms precision: "2026-05-15T10:00:00.123Z"
) -> str:
    payload = {
        "agent_id": agent_id,
        "action_type": action_type,
        "scope": scope,
        "timestamp": timestamp,
    }
    # JCS (RFC 8785): lexicographic key order, no spaces, UTF-8
    canonical = json.dumps(
        dict(sorted(payload.items())),
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
```

Reference implementation: [`plugins/agt_evidence_anchor/action_ref.py`](../../plugins/agt_evidence_anchor/action_ref.py)

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | string | Stable identifier for the agent (DID, username, or opaque string) |
| `action_type` | string | What the agent did — semantic label (`code.execute`, `payment.send`, etc.) |
| `scope` | string | Declared authorization boundary — what the agent was allowed to do, not what it did. Pass `""` if not applicable. |
| `timestamp` | string | RFC 3339 UTC with 3-digit millisecond precision. Format: `"2026-05-15T10:00:00.123Z"`. The trailing `Z` is mandatory. |

## Serialization — JCS (RFC 8785)

The four fields are serialized as a JSON object using RFC 8785 JSON Canonicalization Scheme before hashing:

- Keys in lexicographic Unicode code point order: `action_type`, `agent_id`, `scope`, `timestamp`
- No whitespace between tokens
- UTF-8 encoded
- Values are JSON strings (no additional escaping beyond standard JSON)

**Example — NEXUS oracle signal:**

```
Input:
  agent_id    = "nexus-agent-xa12.onrender.com"
  action_type = "oracle.signal"
  scope       = "BTC"
  timestamp   = "2025-05-18T11:40:31.000Z"

JCS payload:
  {"action_type":"oracle.signal","agent_id":"nexus-agent-xa12.onrender.com","scope":"BTC","timestamp":"2025-05-18T11:40:31.000Z"}

action_ref:
  fdd7f810499f06be24355ca8e2bfb8c4b965cc80c838f41fa074683443d89f5a
```

## Timestamp format

`timestamp` is the moment the action was claimed (before execution), expressed as RFC 3339 UTC with exactly 3 millisecond digits:

```python
import datetime

def format_timestamp(dt: datetime.datetime) -> str:
    ms = dt.microsecond // 1000
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S.{ms:03d}Z")

# From Unix seconds (no sub-second data):
ts = format_timestamp(datetime.datetime.fromtimestamp(1747568431, tz=datetime.timezone.utc))
# → "2025-05-18T11:40:31.000Z"
```

## Canonical receipt envelope — v1.0

Implementations that emit a receipt referencing this spec SHOULD include the following fields to ensure long-lived verifiability:

```json
{
  "packet_version": "1.0",
  "action_ref": "<sha256 hex>",
  "hash_algo": "sha256",
  "preimage_format": "jcs-rfc8785",
  "preimage": {
    "agent_id": "...",
    "action_type": "...",
    "scope": "...",
    "timestamp": "2026-05-15T10:00:00.123Z"
  }
}
```

**Why these fields matter:**

- `packet_version` — forward-compat anchor. v1 verifiers can explicitly reject unknown versions rather than fail silently.
- `hash_algo` — makes receipts self-describing. If a future implementation switches to BLAKE3 or keccak256, receipts issued before the change remain replayable.
- `preimage_format: "jcs-rfc8785"` — unambiguously identifies the serialization. Any verifier can recompute the action_ref from the preimage fields using RFC 8785 without trusting the emitter.

## Gap — revocation and policy rotation

The canonical receipt envelope v1.0 records the state at the moment the action was claimed.
It does not record whether that state was still valid when the action was **admitted for
execution** — which may be later.

Two failure modes this gap creates:

1. **Trust tier degradation** — an agent moves from TRUSTED to WATCH between claim and
   execution. The anchor records the claim-time state. A verifier replaying the receipt
   cannot determine from the receipt alone whether the agent was still trusted when the
   action was admitted.

2. **Policy rotation** — the counterparty policy changes between issuance and execution.
   `counterparty_policy_hash` (if present) proves *which* policy was referenced at claim
   time. It does not prove whether that policy was still current when the action was
   admitted.

Both conditions require the receipt to carry additional fields to remain auditable after
the fact.

### Two fields that close this gap

**`policy_version`** (string, optional) — identifies which version of the governing policy
was in force when the action was admitted. Distinct from `counterparty_policy_hash`, which
proves *which* policy was referenced — `policy_version` proves *whether it was still
current* at execution time. A verifier replaying the receipt after a policy rotation can
use this field to establish that the admitted policy was not superseded before execution.

**`revocation_check_at_ms`** (integer, optional) — Unix timestamp in milliseconds of the
last non-revocation check performed before execution. A receipt without this field cannot
prove the agent's credentials were valid immediately before the action was admitted — only
that they were valid at claim time. With this field, a verifier can establish a maximum
window of credential exposure.

### Updated canonical receipt envelope — v1.0 with optional rotation fields

```json
{
  "packet_version": "1.0",
  "action_ref": "<sha256 hex>",
  "hash_algo": "sha256",
  "preimage_format": "jcs-rfc8785",
  "preimage": {
    "agent_id": "...",
    "action_type": "...",
    "scope": "...",
    "timestamp": "2026-05-15T10:00:00.123Z"
  },
  "policy_version": "2026-05-01",
  "revocation_check_at_ms": 1747568431000
}
```

Both fields are optional in v1.0. A verifier that requires post-rotation auditability
SHOULD treat a receipt missing either field as unauditable for the rotation window — not
as invalid.

**Why milliseconds for `revocation_check_at_ms`:** credential checks in live multi-agent
systems happen at sub-second granularity, and the gap between check and execution is often
under one second. A seconds-precision timestamp cannot distinguish "checked 800ms ago"
from "checked 1200ms ago" — a distinction that matters when the revocation window is
short. Systems that only have second-precision timestamps SHOULD multiply by 1000 and
document the precision loss in the receipt.

---

## Canonical linking key

The same `action_ref` is computable from:

- a Mycelium TrailRecord (preimage fields published in each record)
- a Nobulex covenant receipt (`action_type` as semantic label + timestamp + agent_id + scope)
- a SafeAgent claim ([azender1/SafeAgent](https://github.com/azender1/SafeAgent), joint spec [argentum-core#7](https://github.com/giskard09/argentum-core/issues/7))
- a CrewAI idempotency key ([crewAIInc/crewAI#5822](https://github.com/crewAIInc/crewAI/pull/5822)) — key derivation converges on the same primitive from the retry-deduplication direction
- NEXUS oracle receipts ([nexus-agent-xa12.onrender.com/receipt](https://nexus-agent-xa12.onrender.com/receipt)) — implements canonical envelope v1.0

Any verifier holding one artifact can validate against another without trusting either system.

## Cross-references

- Reference implementation: [`plugins/agt_evidence_anchor/action_ref.py`](../../plugins/agt_evidence_anchor/action_ref.py)
- Full TrailRecord schema: [MYCELIUM_TRAILS_REFERENCE.md](../MYCELIUM_TRAILS_REFERENCE.md)
- AGT EvidenceAnchor proposal (Microsoft): [agent-governance-toolkit PR #2244](https://github.com/microsoft/agent-governance-toolkit/pull/2244)
- Joint spec with SafeAgent: [argentum-core#7](https://github.com/giskard09/argentum-core/issues/7)
- Nobulex alignment: [MetaGPT#1991](https://github.com/geekan/MetaGPT/issues/1991)
