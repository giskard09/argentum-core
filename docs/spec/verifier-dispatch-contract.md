# Verifier–Dispatch Contract

This document defines the interface contract between the verifier and the dispatch layer. The contract is enforced by the conformance fixture at `examples/conformance/guardrail-provider-v1.fixture.json`.

## Invariants

### Invariant 1 — Verifier owns inspection

The verifier inspects all fields of the receipt and the referenced decision record, evaluates them against the canonical precedence order defined in the fixture's `verifier_precedence` section, and returns exactly five fields:

```
format_valid        boolean
observation_valid   boolean
authorization_valid boolean
reason_code         string | null
dispatch_allowed    boolean
```

No other layer inspects receipt or decision fields for authorization purposes. The verifier is the single source of truth for the authorization determination.

### Invariant 2 — Dispatch gates only on `dispatch_allowed`

The dispatch layer treats `dispatch_allowed: true` as the sole executable authority. If `dispatch_allowed` is `false` or absent, the action does not execute. No exceptions by provider, tool category, risk classification, or any other criterion.

The dispatch layer is not an authorization layer. It reads one field and acts on it.

### Invariant 3 — `reason_code` is evidence, not permission

`reason_code` is an output of the verifier for use by: auditing, debugging, user-facing messaging, retry routing, and conformance assertions.

`reason_code` never affects execution. When `dispatch_allowed: true`, `reason_code` must be `null`. A non-null `reason_code` paired with `dispatch_allowed: true` is a verifier implementation error.

## Failure mode to avoid

A dispatch layer that inspects `reason_code` to make local exceptions — "allow expired decisions for this provider", "allow argument mismatch for low-risk tools", "skip authorization check for internal tools" — silently becomes a second authorization policy.

The consequence: different integrations execute different actions from the same verifier output. The verifier's guarantee ("this action is authorized") degrades to "this action is authorized unless the dispatch layer overrides it," which is not a verifiable guarantee at all.

This antipattern is not detectable from the verifier output alone. It is only detectable by auditing the dispatch layer — defeating the purpose of a verifiable authorization contract.

The contract requires: dispatch reads `dispatch_allowed`. Dispatch does not read `reason_code`.

## POS-1 invariant

The positive case (`POS-1` in the conformance fixture) defines the baseline authorized-execution shape:

```json
{
  "format_valid": true,
  "observation_valid": true,
  "authorization_valid": true,
  "reason_code": null,
  "dispatch_allowed": true
}
```

All negative cases (`NEG-1` through `NEG-8`) produce `authorization_valid: false`, `dispatch_allowed: false`, and a non-null `reason_code`. Each negative case remains fully observable and useful for auditing, retry routing, and conformance testing — without being executable.

The invariant holds in both directions: `dispatch_allowed: true` implies `reason_code: null`; `reason_code` non-null implies `dispatch_allowed: false`.

## Relationship to other specs

- Canonical precedence order: `examples/conformance/guardrail-provider-v1.fixture.json` → `verifier_precedence`
- Decision binding: `docs/spec/decision-binding-ref-v1.0.md`
- Verifier independence: `docs/spec/verifier-independence.md`
- Verification semantics: `docs/spec/verification-semantics.md`
