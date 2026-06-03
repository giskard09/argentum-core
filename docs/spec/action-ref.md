# action_ref — derivation spec

**Version:** 1.1 | **Published:** 2026-05-23 | **Updated:** 2026-06-03 (×2) | **Stable ref:** [`action-ref-v1.0`](https://github.com/giskard09/argentum-core/blob/action-ref-v1.0/docs/spec/action-ref.md) | **Latest commit:** [96931c9](https://github.com/giskard09/argentum-core/commit/96931c9)

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

**Safe band:** the `json.dumps` approach above produces RFC 8785-compatible bytes for the specific input shapes this spec exercises: ASCII-only field values, RFC 3339 timestamp strings in the conformant `YYYY-MM-DDTHH:MM:SS.mmmZ` form (see [Timestamp format](#timestamp-format)), no surrogate-pair Unicode, no `-0.0`. For inputs outside this band — non-ASCII agent identifiers, surrogate-pair scope strings — use `rfc8785` (Python) or an equivalent RFC 8785-compliant library to guarantee byte-level portability across implementations.

Reference implementation: [`plugins/agt_evidence_anchor/action_ref.py`](../../plugins/agt_evidence_anchor/action_ref.py)

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | string | Stable identifier for the **executing agent at issuance time** — the terminal executor after full delegation resolution. Not the original delegator; not a display label. In a chain A→B→C where C executes the action, `agent_id` is C. |
| `action_type` | string | What the agent did — semantic label (`code.execute`, `payment.send`, etc.) |
| `scope` | string | Terminal executing agent's requested-intent scope — what the agent requested to do at the point of action. Free-form non-empty string; see [Scope conventions](#scope-conventions). Pass `""` if not applicable. |
| `timestamp` | string | RFC 3339 UTC with 3-digit millisecond precision. Format: `"2026-05-15T10:00:00.123Z"`. The trailing `Z` is mandatory. |

## Scope conventions

`scope` is a free-form non-empty string with no closed enum. Any value is valid as long as it is non-empty and consistent across all parties deriving the same `action_ref`.

**Recommended convention (non-normative):** namespace-prefix with the emitter identifier using `<emitter>:<scope>`.

```
algovoi:compliance_screen
vauban:stark_settlement
agent_os:committed_claim
aura:reputation_observe
```

These examples are verified in production trails anchored on-chain via Mycelium.

**Rationale:** different emitters may independently choose the same scope string (`audit`, `settlement`, `signal`) with semantically distinct meanings. Prefixing avoids collisions when trails from multiple emitters are verified or aggregated by a third party.

**Conformance note — scope anti-pattern:** `scope` captures the terminal executing agent's requested-intent at the point of action — a human-readable label, not a derived hash. A common mistake is to hash the initial intent object and use that hash as the scope value. This breaks the primary verifiability property of `action_ref`: any party holding the four preimage fields must be able to recompute it independently, without retrieving any external record. With a hashed scope, a verifier cannot recompute `action_ref` from the intent tuple alone — they must also retrieve the commitment record to recover the pre-hash value. The correct value is the intent label itself (e.g., `"trade:execute:authorized"`, `"aura:reputation_observe"`), not a digest of the document that describes it.

Emitters that do not namespace their scope remain valid — the convention is a recommendation, not a requirement. A verifier MUST NOT reject a trail solely because its `scope` lacks a namespace prefix.

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

**JCS determinism:** RFC 3339 without additional constraints admits multiple lexically distinct encodings of the same instant (`Z` vs `+00:00`, `.000` vs no fractional part, etc.), each producing a different SHA-256 digest under JCS RFC 8785. This spec closes that surface at the format level, not the serializer level:

- Timezone: `Z` suffix only. `+00:00` or any other offset is non-conformant.
- Fractional precision: exactly 3 digits (milliseconds). No trailing zero suppression.
- Template: `YYYY-MM-DDTHH:MM:SS.mmmZ` — one valid byte sequence per instant.

A verifier that accepts alternative RFC 3339 forms will compute a different digest and correctly reject the receipt. An emitter generating non-conformant timestamps produces an unverifiable receipt. The `format_timestamp` function above is the normative reference for conformant emission.

**Interoperability note:** implementations using epoch-millisecond integers as an internal representation can convert to the conformant string format losslessly: `datetime.fromtimestamp(ms / 1000, tz=timezone.utc)` followed by `format_timestamp`. The canonical preimage always contains the string form.

## Canonical receipt envelope — v1.0

Implementations that emit a receipt referencing this spec SHOULD include the following fields to ensure long-lived verifiability:

```json
{
  "packet_version": "1.0",
  "action_ref": "<sha256 hex>",
  "hash_algo": "sha256",
  "preimage_format": "jcs-rfc8785-v1",
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

**`authority_verified_at_ms`** (integer, optional) — Unix timestamp in milliseconds at
which the delegation authority was verified at issuance. This is the issuance-side anchor:
it records when the acting agent's authority was confirmed before the action was admitted.
A year-5 supervisor re-verifying a receipt can use this field to establish the issuance
boundary independently of the execution-time check.

**`revocation_check_at_ms`** (integer, optional) — Unix timestamp in milliseconds of the
last non-revocation check performed before execution. A receipt without this field cannot
prove the agent's credentials were valid immediately before the action was admitted — only
that they were valid at claim time. With this field, a verifier can establish a maximum
window of credential exposure.

**`negotiation_ref`** (string, optional) — SHA-256 hex pointer to the negotiation artifact
(capability-grant, covenant, or agreement) that authorized this action. Derived as
`SHA-256(JCS(negotiation_artifact))` — see [`negotiation-ref.md`](./negotiation-ref.md)
for the full spec and derivation. Does not enter the `action_ref` preimage: changing or
removing `negotiation_ref` does not change `action_ref`.

### Updated canonical receipt envelope — v1.0 with optional rotation fields

```json
{
  "packet_version": "1.0",
  "action_ref": "<sha256 hex>",
  "hash_algo": "sha256",
  "preimage_format": "jcs-rfc8785-v1",
  "preimage": {
    "agent_id": "...",
    "action_type": "...",
    "scope": "...",
    "timestamp": "2026-05-15T10:00:00.123Z"
  },
  "policy_version": "2026-05-01",
  "authority_verified_at_ms": 1747568400000,
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

## Use cases — gap class coverage

### Memory provenance attestation (OWASP ASI06)

`action_ref` with `action_type: "memory_write"` and `scope: <memory_key>` produces a
content-addressed receipt per write. A verifier can check the receipt independently —
no operator trust required. The receipt proves what was written, by which agent, at
which moment.

**Memory poisoning defense:** for `action_type: "memory_write"`, `scope` identifies the
specific memory slot. A trail of write receipts gives a verifier the full provenance
graph of any memory state — who wrote what, when, with what authorization. Combined
with `delegation_ref` (who authorized the write) and `revocation_ref` (when that
authorization was invalidated), the provenance chain is complete and independently
replayable.

**Example — memory write receipt (byte-verified):**

```
Input:
  agent_id    = "giskard-self"
  action_type = "memory_write"
  scope       = "mycelium:memory:session_context_v3"
  timestamp   = "2026-05-26T20:15:00.000Z"

JCS payload:
  {"action_type":"memory_write","agent_id":"giskard-self","scope":"mycelium:memory:session_context_v3","timestamp":"2026-05-26T20:15:00.000Z"}

action_ref:
  36fe8d0559bb254c20cdb0e7a0c83e53f0434fc076e856ff769444da2a73b0b4
```

## Cross-references

- Reference implementation: [`plugins/agt_evidence_anchor/action_ref.py`](../../plugins/agt_evidence_anchor/action_ref.py)
- Full TrailRecord schema: [MYCELIUM_TRAILS_REFERENCE.md](../MYCELIUM_TRAILS_REFERENCE.md)
- Joint spec with SafeAgent: [argentum-core#7](https://github.com/giskard09/argentum-core/issues/7)
- Nobulex alignment: [MetaGPT#1991](https://github.com/geekan/MetaGPT/issues/1991)
