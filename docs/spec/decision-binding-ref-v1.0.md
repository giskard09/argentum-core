# decision_binding_ref — binding spec

**Version:** 1.0 | **Published:** 2026-06-12 | **Status:** stable
**Extended:** 2026-08-04 — added optional `context_digest` field (additive, non-breaking; see [context_digest](#context_digest)). Proposed by eriknewton (co-founder, trust-evidence-format) in [A2A discussion#1734](https://github.com/a2aproject/A2A/discussions/1734#discussioncomment-17896415).

A `decision_binding_ref` is a content-addressed identifier for the binding between a specific action instance and the authorization decision that permitted it. Any verifier with the preimage fields can independently confirm that this exact instance was authorized — without trusting the system that executed it.

## Derivation

```python
import hashlib
import json

def compute_decision_binding_ref(
    action_ref: str,          # "sha256:<hex>" — from action-ref spec
    decision_id: str,         # opaque identifier of the authorization decision
    decision_at_ms: int,      # epoch-milliseconds when the decision was taken
    policy_ref: str = None,   # optional — hash or URI of the applied policy
    context_digest: str = None,  # optional — SHA-256(JCS(assembled context)) at decision time
) -> str:
    payload = {
        "action_ref": action_ref,
        "decision_at_ms": decision_at_ms,
        "decision_id": decision_id,
    }
    if policy_ref is not None:
        payload["policy_ref"] = policy_ref
    if context_digest is not None:
        payload["context_digest"] = context_digest

    # JCS (RFC 8785): lexicographic key order, no spaces, UTF-8
    canonical = json.dumps(
        dict(sorted(payload.items())),
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()
```

**Domain:** the `json.dumps` approach above is RFC 8785-compatible for the input shapes this spec exercises: ASCII-only string fields, integer `decision_at_ms` within the RFC 8785 safe-integer range (`[0, 2^53-1]`), no `-0.0`, no surrogate-pair Unicode, no duplicate preimage keys. This is the profile's full domain, not a convenience subset — there is no "use a compliant library instead" fallback. A preimage outside this domain is not canonicalized by best effort; the verifier MUST return `OUT_OF_PROFILE_DOMAIN` and stop before any digest comparison — the same pattern already used for `UNSUPPORTED_CANONICAL_PROFILE`. One pinned behavior per profile, never a disjunction between "this path or, failing that, some other path."

## Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action_ref` | string | yes | `"sha256:<hex>"` — the content-addressed identifier of the action being authorized. Derived per [action-ref spec](action-ref.md). |
| `decision_id` | string | yes | Opaque identifier for the authorization decision. Format is implementation-defined; MUST be non-empty and stable for the lifetime of the decision. |
| `decision_at_ms` | integer | yes | Epoch-milliseconds (UTC) when the authorization decision was taken. Integer, not string. |
| `policy_ref` | string | no | Hash or URI of the policy applied at decision time. If absent, the field MUST be omitted from the preimage entirely — not set to `null`. |
| `context_digest` | string | no | `"sha256:<hex>"` — `SHA-256(JCS(assembled_context))`, where `assembled_context` is the set of memories/documents/artifacts that fed the decision, computed at decision time. If absent, the field MUST be omitted from the preimage entirely — not set to `null`. Same absence rule as `policy_ref`. |

## Invariant

> A verifier can confirm that this specific action instance was authorized without trusting the system that executed it.

The binding is between the *content* of the action (via `action_ref`) and the *fact* of the decision (via `decision_id` + `decision_at_ms`). Changing any preimage field produces a different digest, making post-hoc claim insertion detectable.

## policy_ref absence rule

When `policy_ref` is not applicable, omit the key entirely from the preimage before canonicalization. Do not include `"policy_ref": null`. This ensures two implementations that agree on the other three fields will produce identical bytes regardless of whether they know about the optional field.

## context_digest

`context_digest` binds the *inputs available to the decision* — not just the action and the fact of the decision. `assembled_context` is implementation-defined in shape (a list of content-addressed refs, a structured object, etc.) but MUST itself be canonicalized per JCS before hashing, same as every other digest in this spec family.

**Invariant:** a verifier holding the context set (the actual memories/documents/artifacts, or their content-addressed refs) can independently recompute `SHA-256(JCS(assembled_context))` and confirm it equals the `context_digest` embedded in the preimage — i.e. confirm *these artifacts were present in the input of this decision*. This does NOT resolve attribution or steering (which artifact caused which part of the outcome) — it only proves presence, the same way `action_ref` proves content without proving intent.

**context_digest absence rule:** identical to `policy_ref` — omit the key entirely when not applicable, never `null`. A preimage may carry `policy_ref`, `context_digest`, both, or neither; the four combinations all canonicalize deterministically because omission (not nulling) is the only encoding for "not applicable."

**Mismatch handling:** if a verifier recomputes `SHA-256(JCS(presented_context))` and it diverges from the embedded `context_digest`, the verifier MUST reject with `CONTEXT_SET_MISMATCH` — same fail-closed pattern as `POLICY_SNAPSHOT_MISMATCH` in [policy-change-v1](../../examples/conformance/policy-change-v1.fixture.json). A dropped or substituted artifact from the context set changes the digest; it does not go undetected.

## Byte-verified fixture

```python
# Fixture A — with policy_ref
preimage = {
    "action_ref": "sha256:9752a870dac7100010453be9494ec631c78fd55bb7cb41355cf03592da3862ce",
    "decision_at_ms": 1748736000000,
    "decision_id": "approval:7f3a9c21-4e5b-4d8f-b3c2-1a9e8f7d6c5b",
    "policy_ref": "sha256:b94f6f125c79e3a5ffaa826f584c10d52ada669e6762051b826b55776d05a6c7",
}
# canonical_bytes_utf8:
# {"action_ref":"sha256:9752a870dac7100010453be9494ec631c78fd55bb7cb41355cf03592da3862ce","decision_at_ms":1748736000000,"decision_id":"approval:7f3a9c21-4e5b-4d8f-b3c2-1a9e8f7d6c5b","policy_ref":"sha256:b94f6f125c79e3a5ffaa826f584c10d52ada669e6762051b826b55776d05a6c7"}
# decision_binding_ref: sha256:dec9af2f3bf362442fd25ebc4bf1dc9e3499981d6d25df0626e05bb08312a943

# Fixture B — without policy_ref
preimage_b = {
    "action_ref": "sha256:9752a870dac7100010453be9494ec631c78fd55bb7cb41355cf03592da3862ce",
    "decision_at_ms": 1748736000000,
    "decision_id": "approval:7f3a9c21-4e5b-4d8f-b3c2-1a9e8f7d6c5b",
}
# canonical_bytes_utf8:
# {"action_ref":"sha256:9752a870dac7100010453be9494ec631c78fd55bb7cb41355cf03592da3862ce","decision_at_ms":1748736000000,"decision_id":"approval:7f3a9c21-4e5b-4d8f-b3c2-1a9e8f7d6c5b"}
# decision_binding_ref: sha256:a114ce067cf804a3cd4c3b06edc91d4e9f0746bfc4700329f43974df77e70634

# Fixture C — with context_digest (no policy_ref)
preimage_c = {
    "action_ref": "sha256:9752a870dac7100010453be9494ec631c78fd55bb7cb41355cf03592da3862ce",
    "decision_at_ms": 1748736000000,
    "decision_id": "approval:7f3a9c21-4e5b-4d8f-b3c2-1a9e8f7d6c5b",
    "context_digest": "sha256:c2bf3a88a2e5d8d63b95b22eab6b31bf2b7ab6108002b37a9b0945b722d4b9bb",
}
# canonical_bytes_utf8:
# {"action_ref":"sha256:9752a870dac7100010453be9494ec631c78fd55bb7cb41355cf03592da3862ce","context_digest":"sha256:c2bf3a88a2e5d8d63b95b22eab6b31bf2b7ab6108002b37a9b0945b722d4b9bb","decision_at_ms":1748736000000,"decision_id":"approval:7f3a9c21-4e5b-4d8f-b3c2-1a9e8f7d6c5b"}
# decision_binding_ref: sha256:5caf1298c5c8ea661effc266d8e0179505a84fc63507533ac97d3b38ea4eccdf

# Fixture D — with both policy_ref and context_digest
preimage_d = {
    "action_ref": "sha256:9752a870dac7100010453be9494ec631c78fd55bb7cb41355cf03592da3862ce",
    "decision_at_ms": 1748736000000,
    "decision_id": "approval:7f3a9c21-4e5b-4d8f-b3c2-1a9e8f7d6c5b",
    "policy_ref": "sha256:b94f6f125c79e3a5ffaa826f584c10d52ada669e6762051b826b55776d05a6c7",
    "context_digest": "sha256:c2bf3a88a2e5d8d63b95b22eab6b31bf2b7ab6108002b37a9b0945b722d4b9bb",
}
# canonical_bytes_utf8:
# {"action_ref":"sha256:9752a870dac7100010453be9494ec631c78fd55bb7cb41355cf03592da3862ce","context_digest":"sha256:c2bf3a88a2e5d8d63b95b22eab6b31bf2b7ab6108002b37a9b0945b722d4b9bb","decision_at_ms":1748736000000,"decision_id":"approval:7f3a9c21-4e5b-4d8f-b3c2-1a9e8f7d6c5b","policy_ref":"sha256:b94f6f125c79e3a5ffaa826f584c10d52ada669e6762051b826b55776d05a6c7"}
# decision_binding_ref: sha256:4b0220dcd431f313f0c06510c163d561e787a32567cb55fa42bb906df9ac60cd
```

Extended conformance vectors (positive + negative, `CONTEXT_SET_MISMATCH`): [examples/conformance/decision-binding-context-digest-v1/](../../examples/conformance/decision-binding-context-digest-v1/).

Run `python3 -c "import hashlib,json; p={...}; print(hashlib.sha256(json.dumps(dict(sorted(p.items())),separators=(',',':'),ensure_ascii=False).encode()).hexdigest())"` to independently verify.

## Relationship to other specs

- **action-ref** — `action_ref` in the preimage is derived per [action-ref spec](action-ref.md). The `decision_binding_ref` wraps it: action_ref names the action, decision_binding_ref proves it was authorized.
- **wallet-binding** — a wallet signature over `decision_binding_ref` makes the receipt portable and cross-framework verifiable without a shared checkpoint. See [examples/conformance/wallet-binding-v1/](../../examples/conformance/wallet-binding-v1/).
- **request_id** — scopes the attempt (session, request) but is intentionally outside the canonical preimage. It does not change what the action was or that it was authorized.
