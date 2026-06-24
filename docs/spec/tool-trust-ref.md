# Tool Trust Reference — `tool-trust-ref-v1`

A tool trust reference is the verifiable record of a trust posture check on a tool, server, or resource target — prior to and independent of the authorization decision. It answers a different question than the guardrail or governance layer: not "is this action authorized?" but "is this target trustworthy to invoke at all?"

## Motivation

Authorization (`decision_binding_ref`) confirms that a policy approved this action instance. It does not confirm that the tool being invoked is what the agent believes it to be, or that its posture hasn't changed since the last check.

`tool_trust_ref` covers the trust-in-target layer:

- A tool package whose digest changed since the last posture check is a different tool — prior safety decisions do not transfer.
- A posture check outside its validity window fails closed — a stale "safe" verdict is not a safe verdict.
- An MCP server URI that resolves to a different endpoint is a different target.

## Relationship to other records

`tool_trust_ref` is a sibling of the pre-execution decision record — not a field within it. It is emitted before the guardrail authorization check, covers a distinct trust question, and can be evaluated independently.

```
intent tuple
  → tool_trust_ref check (this spec)     ← is this target trustworthy?
  → pre-execution decision record         ← is this action authorized?
  → [allow path] receipt
  → [deny/defer path] restraint receipt
```

A conformant dispatch layer checks both. Passing authorization with a failing trust posture does not produce `dispatch_allowed: true`.

## Preimage

```
tool_trust_ref = SHA-256(JCS({
  tool_id,
  posture_version,
  checked_at_ms,
  verifier_id,
  verdict
}))
```

Field definitions:

| Field | Type | Description |
|-------|------|-------------|
| `tool_id` | string | Content-addressed identifier of the tool or target where available. Preferred forms: package digest (`sha256:<hex>`), MCP server URI, container image digest, resource URI. Must be stable under the same tool version — a different digest is a different tool. |
| `posture_version` | string | Version identifier of the posture policy used for this check. Included in the preimage so that a posture policy upgrade produces a new `tool_trust_ref` even for the same `tool_id`. |
| `checked_at_ms` | integer | Unix epoch milliseconds at which the posture check was performed. Used to determine whether the check is within the validity window at invocation time. |
| `verifier_id` | string | Identifier of the entity that performed the posture check. |
| `verdict` | `"safe"` \| `"unsafe"` \| `"unverified"` | `safe`: posture check passed, target is trusted. `unsafe`: posture check failed, target must not be invoked. `unverified`: posture check was not performed or result is inconclusive — dispatch layer treats this as failing closed. |

Canonicalization: JCS per RFC 8785. All five fields are required.

## Dispatch rules

| verdict | dispatch_allowed |
|---------|-----------------|
| `safe` (within validity window) | determined by authorization layer |
| `unsafe` | `false` — never invoked, regardless of authorization |
| `unverified` | `false` — fails closed |
| `safe` (outside validity window) | `false` — `posture_expired`; re-check required |

A `verdict: "safe"` outside its validity window is treated as `posture_expired` and fails closed. The dispatch layer does not interpret expired "safe" verdicts as safe.

## Reason codes

| Condition | reason_code |
|-----------|-------------|
| `verdict: "unsafe"` | `posture_override` |
| `tool_id` digest changed (prior check on different digest) | `tool_identity_mismatch` |
| `checked_at_ms` outside validity window | `posture_expired` |

## Conformance

Conformance vectors: `examples/conformance/tool-trust-ref-v1/vectors.json`

Verification script: `examples/conformance/tool-trust-ref-v1/verify.py`

A conformant implementation:
1. Emits a `tool_trust_ref` record before the pre-execution decision record.
2. Uses content-addressed `tool_id` where available — digest, not name.
3. Includes all five fields in the preimage before hashing.
4. Uses JCS (RFC 8785) canonicalization.
5. Treats `unverified` and expired `safe` verdicts as failing closed.

## Relationship to other specs

- `docs/spec/action-ref.md` — `action_ref` derivation (correlation key)
- `docs/spec/verifier-dispatch-contract.md` — five-field verifier output contract
- `docs/spec/decision-binding-ref-v1.0.md` — authorization layer (`decision_binding_ref`)
- `docs/spec/restraint-receipt.md` — deny/defer path record
