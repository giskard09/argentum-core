# decision_binding_ref — binding spec

**Version:** 1.0 | **Published:** 2026-06-12 | **Status:** stable

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
) -> str:
    payload = {
        "action_ref": action_ref,
        "decision_at_ms": decision_at_ms,
        "decision_id": decision_id,
    }
    if policy_ref is not None:
        payload["policy_ref"] = policy_ref

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

## Invariant

> A verifier can confirm that this specific action instance was authorized without trusting the system that executed it.

The binding is between the *content* of the action (via `action_ref`) and the *fact* of the decision (via `decision_id` + `decision_at_ms`). Changing any preimage field produces a different digest, making post-hoc claim insertion detectable.

## policy_ref absence rule

When `policy_ref` is not applicable, omit the key entirely from the preimage before canonicalization. Do not include `"policy_ref": null`. This ensures two implementations that agree on the other three fields will produce identical bytes regardless of whether they know about the optional field.

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
```

Run `python3 -c "import hashlib,json; p={...}; print(hashlib.sha256(json.dumps(dict(sorted(p.items())),separators=(',',':'),ensure_ascii=False).encode()).hexdigest())"` to independently verify.

## Relationship to other specs

- **action-ref** — `action_ref` in the preimage is derived per [action-ref spec](action-ref.md). The `decision_binding_ref` wraps it: action_ref names the action, decision_binding_ref proves it was authorized.
- **wallet-binding** — a wallet signature over `decision_binding_ref` makes the receipt portable and cross-framework verifiable without a shared checkpoint. See [examples/conformance/wallet-binding-v1/](../../examples/conformance/wallet-binding-v1/).
- **request_id** — scopes the attempt (session, request) but is intentionally outside the canonical preimage. It does not change what the action was or that it was authorized.
