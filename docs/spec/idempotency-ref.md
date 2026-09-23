# idempotency-ref-v1 — Specification

**Stable tag:** `idempotency-ref-v1.0`  
**Current revision:** v1.1 (additive — every v1.0 artifact and `idempotency_ref` is unchanged)  
**Status:** stable  
**Canonical fixture:** [`examples/conformance/idempotency-ref-v1.fixture.json`](../../examples/conformance/idempotency-ref-v1.fixture.json)  
**v1.1 vectors:** [`examples/conformance/idempotency-ref-v1.1/`](../../examples/conformance/idempotency-ref-v1.1/)

---

## What is idempotency-ref

`idempotency_ref` is a SHA-256 hex pointer to an idempotency artifact — a structured document that declares: "this action is the same logical operation as any prior action that presented the same key, within the stated time window."

**What it enables:** a Mycelium verifier or integrator can detect duplicate trail records for the same logical operation without replaying business logic. Two trail records with the same `idempotency_ref` represent the same intended action; the one with `trail_status=COMMITTED` is the canonical outcome.

**What it does not do:** `idempotency_ref` does not prevent an agent from submitting a duplicate action — it enables the receiving system to detect and short-circuit it. Enforcement is the responsibility of the integrator.

---

## Derivation

`idempotency_ref` is `SHA-256(JCS(idempotency_artifact))` where:

- **JCS** is RFC 8785 canonical JSON: object keys sorted recursively by UTF-16 code units (§3.2.3), no whitespace, literal UTF-8 — **not** `json.dumps(sort_keys=True)`, which sorts by code point and diverges for keys outside the BMP. Reference implementation: [`jcs.py`](../../jcs.py)
- **SHA-256** lowercase hex
- `idempotency_artifact` must contain at minimum: `idempotency_key`, `action_type`, `agent_id`, `scope`, `window_ms`, `version`

```python
import hashlib, json

def jcs(obj):
    # RFC 8785 §3.2.3: object keys sorted recursively by UTF-16 code units.
    # Not json.dumps(sort_keys=True): that sorts by code point and diverges
    # from RFC 8785 for keys outside the BMP. Floats additionally need
    # ECMA-262 Number::toString formatting -- see jcs.py.
    def canon(o):
        if isinstance(o, dict):
            return {k: canon(o[k]) for k in sorted(o, key=lambda k: k.encode("utf-16-be", "surrogatepass"))}
        if isinstance(o, list):
            return [canon(v) for v in o]
        return o
    return json.dumps(canon(obj), separators=(',', ':'), ensure_ascii=False)

idempotency_artifact = {
    "action_type":      "payment.send",
    "agent_id":         "pioneer-agent-001",
    "idempotency_key":  "idem_7f3a9b2c4d1e8f05",
    "scope":            "mycelium:payment",
    "version":          "idempotency-ref-v1",
    "window_ms":        300000,
}
idempotency_ref = hashlib.sha256(jcs(idempotency_artifact).encode()).hexdigest()
# 4a6aa060624b6e3ec4fafb941a546e5842d0a1172861f6d21ffec9de4b098a97
```

---

## Logical identity and admitted payload (v1.1)

`idempotency_ref` identifies a **logical action**, not a payload. The `idempotency_key` is the logical action id, minted at admission — before any model or tool execution — and carried unchanged through every attempt and re-dispatch. Attempt ids MAY be fresh per dispatch; they remain children of the logical action.

v1.1 adds `admitted_payload_digest`: `SHA-256(JCS(admitted_payload))`, lowercase hex, where `admitted_payload` is the effect-bearing payload committed durably at admission (what will be sent to the provider). It is carried in the envelope next to `idempotency_ref` and recorded with the admission. An artifact whose integration applies the v1.1 rules sets `version` to `idempotency-ref-v1.1`; v1.0 artifacts keep `idempotency-ref-v1`. It MUST NOT be placed inside `idempotency_artifact`: the ref would then change with the payload, and a drifted retry would present a fresh `idempotency_ref` and execute as a new action.

Decision rule, for a dispatch presenting (`idempotency_ref`, `admitted_payload_digest`) within `window_ms` of a prior admission:

| Prior admission under this `idempotency_ref` | Outcome |
|---|---|
| none | **EXECUTE** — record the admission |
| same `admitted_payload_digest` | **DUPLICATE** — reconcile against the prior outcome; MUST NOT create a second effect |
| different `admitted_payload_digest` | **CONFLICT** — fail closed; MUST NOT execute, and MUST NOT treat it as a duplicate of the prior action or as a new action |

A changed payload is a new logical action and MUST be admitted under a new `idempotency_key`. This spec does not define supersession or cancellation of the original action; an integration that needs it declares it explicitly.

The four-case test this rule satisfies:

| Event | `idempotency_key` | payload | Outcome |
|---|---|---|---|
| first intentional payment | A | $100 → X | EXECUTE |
| retry after lost acknowledgement | A | $100 → X | DUPLICATE |
| second intentional payment | B | $100 → X | EXECUTE, despite the identical payload |
| drifted retry | A | $125 → X | CONFLICT |

A record without `admitted_payload_digest` (v1.0) can still be deduplicated by `idempotency_ref`, but drift against it cannot be detected; an implementation MUST NOT claim drift detection for such records.

*(Added 2026-09-23: four-case test defined by impartshadow/agent-contracts ([crewAIInc/crewAI#5802](https://github.com/crewAIInc/crewAI/issues/5802), comment [5790417981](https://github.com/crewAIInc/crewAI/issues/5802#issuecomment-5790417981)) and pinned as a regression by stringsofthemind-oss ([stringsofthemind-oss/once#45](https://github.com/stringsofthemind-oss/once/pull/45)). v1.0 failed cases 3 and 4.)*

---

## Trail lifecycle with idempotency_ref

An action with `idempotency_ref` follows the same three-state lifecycle as any trail record:

| State | Meaning | tx_hash |
|-------|---------|---------|
| `PENDING` | Execution started, outcome unknown | `null` |
| `COMMITTED` | Execution completed, anchor confirmed | non-null |
| `FAILED` | TTL expired, no anchor | `null` |

**Orphaned PENDING records:** a PENDING trail record with `idempotency_ref` that has not transitioned to COMMITTED or FAILED within `window_ms` milliseconds of its `timestamp` is an orphaned PENDING.

`window_ms` elapsing is not evidence of outcome — only the downstream provider knows whether the underlying effect actually landed. A conformant implementation MUST NOT treat an orphaned PENDING as equivalent to FAILED on the basis of `window_ms` alone: doing so authorizes exactly the duplicate the idempotency artifact exists to prevent, and the failure is asymmetric — a stalled action costs a manual reconciliation, a wrongly-cleared PENDING costs a duplicate side effect.

An orphaned PENDING resolves in one of two ways:

- **Provider-confirmed resolution** (default): the integrator queries the underlying provider by the effect's own identifier and transitions the record to COMMITTED or FAILED based on what it finds. This is the only source of evidence; `window_ms` elapsing is not a substitute for it.
- **Declared provider-side idempotency** (explicit opt-in): an implementation MAY treat an orphaned PENDING as safely retryable on `window_ms` alone *only if* the underlying provider call itself carries a provider-enforced idempotency key (e.g. Stripe's `Idempotency-Key` header), so a retry is absorbed upstream rather than producing a duplicate. This is a property of the integration, not of the trail lifecycle — a conformant implementation MUST declare it explicitly (e.g. `provider_idempotent: true` on the `idempotency_artifact`) rather than assume it as a default.

Any resolution remains a read-side decision — it MUST NOT mutate the original record.

*(Correction 2026-08-23: the earlier text of this section stated an unconditional `SHOULD` treating orphaned PENDING as equivalent to FAILED after `window_ms` — unsafe for any provider call without its own idempotency key, e.g. `send_email` or `place_trade`. Gap identified by impartshadow/agent-contracts, [crewAIInc/crewAI#5802](https://github.com/crewAIInc/crewAI/issues/5802).)*

---

## Invariants

**1. envelope-only — does not enter action_ref preimage**

`idempotency_ref` is carried in the trail envelope. It never enters the four-field preimage (`action_type`, `agent_id`, `scope`, `timestamp`). Changing or removing `idempotency_ref` does not change `action_ref`.

**2. idempotency_key is client-generated**

The `idempotency_key` inside the artifact is generated by the submitting agent. Mycelium does not generate or validate it — only stores the hash. Two agents submitting different keys for logically identical operations will produce different `idempotency_ref` values; deduplication across agents is the integrator's responsibility.

**3. window_ms scopes the deduplication window**

A record outside its `window_ms` window is not eligible for deduplication even if the `idempotency_ref` matches. Implementations MAY cache the `idempotency_ref` for up to `window_ms` ms after the `timestamp` of the first COMMITTED record.

**4. opaque artifact format**

The idempotency artifact schema is implementer-defined. Only the JCS+SHA-256 derivation is normative. Additional fields (e.g. `request_id`, `correlation_id`) are permitted, as long as they are fixed at admission and identical across every attempt of the action — any field that can change between attempts (including `admitted_payload_digest`) changes the ref and breaks deduplication.

**5. idempotency_key MUST derive from durable inputs, never from model-regenerated content**

`idempotency_key` MUST be recomputable by a process that did not itself execute the step — from inputs that existed *before* the step ran and are stable across retries of it (e.g. the originating request id, or a caller-assigned operation id minted at admission). Deriving it from the content of the request is conformant only under Invariant 6. It MUST NOT be derived from, or include, any value the model generated *during* the step being retried — most commonly tool-call arguments that an LLM re-emits when a guardrail or validation failure triggers a retry loop.

When a retry re-enters through the model (not through the original caller), the regenerated arguments are not guaranteed byte-identical to the first attempt even when the *intent* is identical — different token sampling, a rephrased justification field, reordered list items. A key derived from `SHA(args)` then changes between attempts, so equality-based deduplication never fires: the two attempts don't collide as a detected duplicate, they land as **two distinct committed effects** (e.g. two charges for different amounts) — the failure mode isn't a missed dedup, it's a false negative that idempotency-ref exists to prevent, and the artifact schema's silence on this today permits it.

A conformant `idempotency_artifact` derives `idempotency_key` from data the *caller* fixed before invoking the model for that attempt — never from the model's output for that attempt. If a runtime cannot supply such a durable input at the point of retry, the correct action is to widen `window_ms` and rely on provider-side reconciliation (see [Trail lifecycle](#trail-lifecycle-with-idempotency_ref)), not to hash whatever arguments the model happens to produce.

*(Added 2026-09-03: gap identified by vasilisnasopoulos ([crewAIInc/crewAI#5802](https://github.com/crewAIInc/crewAI/issues/5802), comment [5462928784](https://github.com/crewAIInc/crewAI/issues/5802#issuecomment-5462928784)), cross-verified against mstevens843/crashpoint's independent finding that LangGraph/Temporal/DBOS all had to add a fifth outcome — DIVERGED — because EXACTLY_ONCE dedup assumes the retried step is reproducible from durable inputs, which a model-regenerated tool call is not.)*

*(Amended 2026-09-23, v1.1: the v1.0 text listed "a hash of the caller's own pre-execution request" as a durable source without qualification. Two intentional actions with identical requests then share one key, and the second is deduplicated as a retry — see Invariant 6.)*

**6. distinct intentional actions MUST carry distinct keys (v1.1)**

Two intentional actions MUST carry different `idempotency_key` values, even when their payloads are byte-identical. A key derived from request content (e.g. `charge:{order_id}`, or a hash of the request) is conformant only under a domain invariant the integration declares explicitly — for example, "at most one charge is admitted per order". Without such an invariant, a content-derived key collapses the second action into the first.

**7. same key, different admitted payload → conflict (v1.1)**

A dispatch whose `idempotency_ref` matches a prior admission within `window_ms` but whose `admitted_payload_digest` differs MUST fail closed as a conflict (see [Logical identity and admitted payload](#logical-identity-and-admitted-payload-v11)). A retry that re-enters through the model dispatches the admitted payload from the durable record; if it dispatches regenerated arguments that differ in any effect-bearing field, the digest differs and the dispatch is a conflict, not a duplicate.

---

## Position in the envelope

```json
{
  "packet_version": "1.0",
  "action_ref":       "<sha256 hex — derived from preimage>",
  "idempotency_ref":  "<sha256 hex — derived from idempotency_artifact>",
  "admitted_payload_digest": "<sha256 hex — JCS(admitted_payload), v1.1, optional>",
  "hash_algo":        "sha256",
  "preimage_format":  "jcs-rfc8785-v1",
  "preimage": {
    "action_type": "payment.send",
    "agent_id":    "pioneer-agent-001",
    "scope":       "mycelium:payment",
    "timestamp":   "2026-05-24T10:00:00.000Z"
  }
}
```

---

## Cross-references

- `action_ref` derivation: [`docs/spec/action-ref.md`](./action-ref.md)
- Trail lifecycle: [`docs/spec/guarantee-model.md`](./guarantee-model.md)
- `delegation_ref` (who authorized the action): [`docs/spec/delegation-ref.md`](./delegation-ref.md)
- `revocation_ref` (invalidation of an authorization): [`docs/spec/revocation-ref.md`](./revocation-ref.md)
- TrailRecord schema: [`docs/MYCELIUM_TRAILS_REFERENCE.md`](../MYCELIUM_TRAILS_REFERENCE.md)
