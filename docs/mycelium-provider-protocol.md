# Mycelium Provider Protocol

**Version:** 1.0 | **Published:** 2026-06-20

A "Mycelium Provider" is any system that computes `action_ref` deterministically and submits trails to ARGENTUM via `/external/trail`. This document is the integration reference.

---

## 0. Create your account

```
POST https://argentum-api.rgiskard.xyz/payg/account?agent_id=<your-agent-id>
```

Returns your `api_key` immediately. No signup required.

```json
{
  "api_key": "ark_...",
  "agent_id": "your-agent-id",
  "tier": "payg",
  "credit_trails": 0
}
```

Once your conformance vectors are merged into `argentum-core`, activate unlimited trails with `self-certify` (see §0.1 below).

### 0.1 Activate as a verified Provider

After your conformance PR is merged:

```
POST https://argentum-api.rgiskard.xyz/payg/account/self-certify
Content-Type: application/json

{
  "api_key": "ark_...",
  "conformance_repo": "giskard09/argentum-core",
  "conformance_path": "examples/conformance/<your-folder>/"
}
```

The system verifies via GitHub API that the folder exists in `argentum-core` with at least one file, extracts the `conformance_source` from the folder name, and activates unlimited trail submission immediately.

**Response:**

```json
{
  "ok": true,
  "api_key": "ark_...",
  "agent_id": "your-agent-id",
  "conformance_source": "your-folder",
  "conformance_path": "examples/conformance/your-folder",
  "karma_weight": 0.7,
  "trail_limit": "unlimited"
}
```

**Rules:**
- `conformance_repo` must be `"giskard09/argentum-core"` — only our repo counts as the gate
- `conformance_path` must be under `examples/conformance/`
- The folder must exist and be non-empty (your PR must be merged before calling this)
- Rate-limited to 1 call per `api_key` per 60 seconds

**The gate is the merged PR, not this endpoint.** Any folder that exists in `argentum-core` passed the review. Self-certify just automates the activation step.

---

## 1. Compute action_ref

`action_ref` is a content-addressed identifier derived from four fields. Any party holding those fields can independently verify it — no trust in the emitting system required.

```python
import hashlib, json

def compute_action_ref(
    agent_id: str,
    action_type: str,
    scope: str,
    timestamp: str,   # RFC 3339 UTC, 3-digit ms: "2026-06-20T14:00:00.000Z"
) -> str:
    payload = {
        "action_type": action_type,
        "agent_id": agent_id,
        "scope": scope,
        "timestamp": timestamp,
    }
    # JCS (RFC 8785): keys lexicographic, no spaces, UTF-8
    canonical = json.dumps(
        dict(sorted(payload.items())),
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
```

### Fields

| Field | Type | Constraint |
|-------|------|-----------|
| `agent_id` | string | Stable identifier of the executing agent |
| `action_type` | string | Semantic label: `code.execute`, `payment.send`, etc. |
| `scope` | string | Requested-intent scope. Pass `""` if not applicable. |
| `timestamp` | string | RFC 3339 UTC with **exactly 3 fractional digits** and trailing `Z`. Example: `"2026-06-20T14:00:00.123Z"` |

### Key order (canonical)

After `dict(sorted(...))` the object keys appear in this order:

```
action_type → agent_id → scope → timestamp
```

This is lexicographic ASCII order, which equals RFC 8785 order for these four keys.

Full derivation spec: [`docs/spec/action-ref.md`](spec/action-ref.md)

---

## 2. Submit trail — POST /external/trail

```
POST https://argentum-api.rgiskard.xyz/external/trail
Content-Type: application/json
```

### Request body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `api_key` | string | ✓ | PAYG account key — links to your `agent_id` server-side |
| `action_ref` | string | ✓ | 64 lowercase hex chars (SHA-256 output of derivation above) |
| `service` | string | | Label for the service that produced the action (default: `"external"`) |
| `operation` | string | | Label for the operation performed (default: `"action"`) |

```json
{
  "api_key": "ark_...",
  "action_ref": "f5cc735aa740b1a5006bf4d41f6e3cacbabcab3e369043b58d924e3bb69b4988",
  "service": "my-agent-runtime",
  "operation": "document.sign"
}
```

### Response (201 Created)

```json
{
  "ok": true,
  "mycelium_trail_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_id": "did:aps:zExampleAgent001",
  "action_ref": "f5cc735aa740b1a5006bf4d41f6e3cacbabcab3e369043b58d924e3bb69b4988",
  "source": "aps",
  "karma_delta": 0.7,
  "karma_total": 12.4,
  "tier": "conformance_verified"
}
```

### Error codes

| Status | Error | Meaning |
|--------|-------|---------|
| 400 | `action_ref, api_key required` | Missing required fields |
| 401 | `api_key not found` | Unknown or revoked key |
| 409 | `action_ref already processed` | Replay — this nonce was already submitted |
| 422 | `action_ref must be 64 hex chars` | Malformed hash |

### Tier / karma_delta by conformance_source

Your account's `conformance_source` is set at registration:

| Source | karma_delta | Condition |
|--------|-------------|-----------|
| `aps` | 0.7 | APS conformance-verified |
| `nobulex` | 0.7 | Nobulex conformance-verified |
| *(unknown)* | 0.2 | Valid `action_ref`, unverified implementation |

For on-chain anchor (karma_delta 1.0), use `/nexus/trail` instead.

---

## 3. mycelium_trail_id in the SDK receipt

Providers that already issue a receipt object (APS, Nobulex, etc.) should add `mycelium_trail_id` as a top-level field after a successful submission:

```python
receipt = {
    "action_ref": action_ref,
    "timestamp": timestamp,
    # ... other provider fields ...
    "mycelium_trail_id": response["mycelium_trail_id"],   # add this
}
```

This field allows any downstream verifier to look up the trail independently:

```
GET https://argentum-api.rgiskard.xyz/trails/{mycelium_trail_id}
```

The field is optional but recommended for cross-surface auditability. Do not include it if the `/external/trail` call fails — a `None` or absent field signals that the Mycelium submission did not succeed.

---

## 4. Declare "Mycelium Provider" in your README

Add the badge to your README after your first conformance-verified trail is submitted:

```markdown
[![Mycelium Provider](https://img.shields.io/badge/Mycelium-Provider-4a90e2)](https://github.com/giskard09/argentum-core/blob/main/docs/mycelium-provider-protocol.md)
```

Add a short declaration in your integration section:

```markdown
## Mycelium Trails

This implementation is a [Mycelium Provider](https://github.com/giskard09/argentum-core/blob/main/docs/mycelium-provider-protocol.md).
Each completed action submits a trail to ARGENTUM with a content-addressed `action_ref`
(JCS+SHA-256 over the four preimage fields). The returned `mycelium_trail_id` is included
in every receipt for independent verification.
```

Conformance fixtures are in [`examples/conformance/provider-protocol/`](../examples/conformance/provider-protocol/).
