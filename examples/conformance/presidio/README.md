# presidio action-ref-v1 conformance vectors

`action_ref` vectors (per [`docs/spec/action-ref.md`](../../../docs/spec/action-ref.md))
derived from **real** [`presidio-hardened-x402`](https://github.com/presidio-v/presidio-hardened-x402)
audit chain heads — pre-execution payment-screening decisions recorded before
signing. Contributed per discussion in
[x402-foundation/x402#2332](https://github.com/x402-foundation/x402/issues/2332).

Two vectors, both in the same screening-decision record type:
- `presidio-x402-001` — `PII_REDACTED`, an **allow** (PII masked, payment proceeds).
- `presidio-x402-002` — `PII_BLOCKED`, a **refusal** (US_SSN detected, payment blocked). A preserved negative action — a refused payment recorded, not silent — kept distinct from any settlement receipt or reputation update that shares the payment.

| File | What |
|------|------|
| `action-ref-v1.fixture.json` | The conformance vector: 4-field preimage, `jcs_payload`, `preimage_canonical_bytes_hex`, `action_ref`, plus a `derived_from` block (raw audit entry + field mapping). |
| `presidio-chain-head.jsonl` | The real HMAC-chained audit entry the vector is derived from (recompute evidence). |
| `presidio-audit-entry.schema.json` | JSON Schema (draft 2020-12) for one presidio audit-log entry. |

## Mapping (presidio audit entry → preimage)

| preimage field | source | note |
|----------------|--------|------|
| `agent_id` | `AuditEvent.agent_id` | verbatim; terminal executing agent |
| `action_type` | `AuditEvent.event_type` | verbatim; a **pre-execution control outcome** (the decision: `PII_REDACTED`), not a post-settlement action |
| `scope` | `presidio:x402.pay:<resource origin>` | requested-intent label from the policy envelope + `resource_url`; human-readable, **not a hash** (per the spec scope anti-pattern), emitter-namespaced |
| `timestamp` | `AuditEvent.timestamp` | normalized from `isoformat()` (µs, `+00:00`) to RFC 3339 `…mmmZ`; byte-equivalent to the spec's normative `format_timestamp` |

## Verification

Self-contained — recompute from the preimage with the spec's reference snippet:

```python
import hashlib, json
def jcs(obj): return json.dumps(dict(sorted(obj.items())), separators=(',',':'), ensure_ascii=False)
action_ref = hashlib.sha256(jcs(preimage).encode()).hexdigest()
```

The vector was additionally cross-checked, byte-identical, against both APS
runners before submission: the standalone `verify.py` (independent RFC 8785) and
the SDK-backed `verify.mjs` (`computeExternalActionRefV1`).
