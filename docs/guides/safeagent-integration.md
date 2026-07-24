# Mycelium Trails — SafeAgent Integration Guide

**Base URL:** `https://argentum-api.rgiskard.xyz`  
**Your agent_id:** `safeagent-prod`  
**Spec:** [action-ref.md v1.1](../spec/action-ref.md)

---

## How it works

Each agent action generates an `action_ref` — a SHA-256 digest of four preimage fields (JCS RFC 8785). You compute it client-side, submit it to Mycelium, and any third party can independently verify the receipt without trusting either system.

---

## Step 1 — Compute action_ref

```python
import hashlib, json, datetime

def compute_action_ref(agent_id: str, action_type: str, scope: str, timestamp: str) -> str:
    preimage = {"agent_id": agent_id, "action_type": action_type,
                "scope": scope, "timestamp": timestamp}
    canonical = json.dumps(dict(sorted(preimage.items())),
                           separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(canonical).hexdigest()

def now_rfc3339() -> str:
    dt = datetime.datetime.now(datetime.timezone.utc)
    ms = dt.microsecond // 1000
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S.{ms:03d}Z")

# Example
action_ref = compute_action_ref(
    agent_id    = "safeagent-prod",
    action_type = "trade.execute",
    scope       = "trade:execute:authorized",
    timestamp   = now_rfc3339(),
)
```

**Timestamp format:** RFC 3339 UTC with exactly 3 millisecond digits — `"2026-06-03T17:00:00.000Z"`. The trailing `Z` is mandatory. No other format is accepted.

---

## Step 2 — Register the trail

```http
POST https://argentum-api.rgiskard.xyz/nexus/trail
Content-Type: application/json
```

```json
{
  "action_ref": "<sha256 hex>",
  "service": "safeagent",
  "preimage": {
    "agent_id":    "safeagent-prod",
    "action_type": "trade.execute",
    "scope":       "trade:execute:authorized",
    "ts":          "2026-06-03T17:00:00.000Z"
  }
}
```

**Note:** the field inside `preimage` is `ts`, not `timestamp` — the API accepts both string (RFC 3339) and integer (Unix seconds) for this field and normalises internally.

**Successful response (201):**

```json
{
  "trail_id":    "3524f362-...",
  "agent_id":    "safeagent-prod",
  "service":     "safeagent",
  "operation":   "trade.execute",
  "action_ref":  "efa43093...",
  "trail_status": "committed"
}
```

Store `trail_id` — it is the Mycelium anchor for this action.

---

## Optional — negotiation_ref (first trail)

The signed RSA links all subsequent SafeAgent trails to the agreement. Include `negotiation_ref` on the first trail (and on any trail issued under that agreement):

```python
import hashlib

with open("azender1_RSA_signed.pdf", "rb") as f:
    negotiation_ref = hashlib.sha256(f.read()).hexdigest()
```

```json
{
  "action_ref":      "<sha256 hex>",
  "service":         "safeagent",
  "negotiation_ref": "<sha256 of signed PDF>",
  "preimage": { ... }
}
```

`negotiation_ref` does not enter the `action_ref` preimage — adding it does not change the digest.

---

## Step 3 — Verify

Any party can verify a trail independently:

```
GET https://argentum-api.rgiskard.xyz/trails/verify
    ?agent_id=safeagent-prod&action_ref=<sha256>
```

Or recompute locally from the four preimage fields using the snippet above.

---

## Rate limits and billing

| Tier | Limit | Cost |
|------|-------|------|
| Free | 500 trails/month | $0 |
| PAYG | Unlimited | $0.003 / trail |

Your PAYG account activates when the Free tier is exhausted. Usage is invoiced monthly per the Revenue Share Agreement on file.

---

## Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/nexus/trail` | POST | Register a trail |
| `/trails/verify` | GET | Verify by action_ref |
| `/trails/agents/safeagent-prod` | GET | Your trail history |
| `/karma/safeagent-prod` | GET | Karma score + Ed25519 badge |
| `/status` | GET | API health |

Questions: [hello@rgiskard.xyz](mailto:hello@rgiskard.xyz)
