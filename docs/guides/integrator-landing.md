# Integrator Guide — Mycelium Trails

Tamper-evident audit trail for AI agent actions. Every trail is independently
verifiable without querying this API or trusting the operator.

**Base URL:** `https://argentum-api.rgiskard.xyz`  
**Free tier:** 1,000 trails/month. No API key. No signup.

---

## Step 1 — Derive the action_ref

`action_ref` is a content-addressed identifier for your action. Derive it locally:

```python
import hashlib, json

def compute_action_ref(agent_id, action_type, scope, timestamp):
    # JCS RFC 8785: keys in Unicode code-point order
    preimage = json.dumps(
        {"action_type": action_type, "agent_id": agent_id,
         "scope": scope, "timestamp": timestamp},
        separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(preimage).hexdigest()

ref = compute_action_ref(
    agent_id="my-agent-001",
    action_type="file:write",
    scope="audit",
    timestamp="2026-05-19T12:00:00.000Z",  # RFC 3339 UTC, 3-digit ms
)
# "64-char lowercase hex"
```

Full spec: [docs/spec/action-ref.md](../spec/action-ref.md)

## Step 2 — Submit the trail

```bash
curl -X POST https://argentum-api.rgiskard.xyz/nexus/trail \
  -H "Content-Type: application/json" \
  -d '{
    "action_ref":       "<action_ref from step 1>",
    "service":          "my-agent",
    "hash_algo":        "sha256",
    "preimage_format":  "jcs-rfc8785",
    "preimage": {
      "agent_id":    "my-agent-001",
      "action_type": "file:write",
      "scope":       "audit",
      "ts":          "2026-05-19T12:00:00.000Z"
    }
  }'
```

Response:

```json
{
  "trail_id":     "uuid",
  "trail_status": "committed",
  "tx_hash":      "0x..."
}
```

`trail_status` values: `committed` (on-chain, terminal) · `pending` (in progress) · `failed` (terminal)

## Step 3 — Verify independently

Anyone can verify — no auth, no API key:

```bash
curl 'https://argentum-api.rgiskard.xyz/trails/verify?agent_id=my-agent-001&action_ref=<ref>'
```

```json
{"verified": true, "trail_status": "committed", "tx_hash": "0x..."}
```

**Live example** (conformance fixture):

```bash
curl 'https://argentum-api.rgiskard.xyz/trails/verify?agent_id=nobulex-gogani&action_ref=31ddbd9f89f0e54700744addc7fa23f41518cf8c9d63d206e6da5cc3669defdd'
```

---

## Python package

```bash
pip install mycelium-agt
```

```python
from mycelium_agt import MyceliumBackend

backend = MyceliumBackend(agent_id="my-agent-001")
receipt = backend.anchor({"action_type": "file:write", "scope": "audit"})

print(receipt.anchored)    # True
print(receipt.action_ref)  # 64-char hex
print(receipt.verify_url)  # public verification URL
```

AGT integration: [microsoft/agent-governance-toolkit#2415](https://github.com/microsoft/agent-governance-toolkit/pull/2415)

---

## Limits

| Tier | Trails/month | Cost |
|------|-------------|------|
| Free | 1,000 | Free |
| PAYG | Unlimited | $0.003/trail |

See [docs/pricing.md](../pricing.md).

---

## Conformance fixtures

4 live fixtures cover all trail states:

| State | agent_id | action_ref (first 16 chars) |
|-------|----------|------------------------------|
| `committed` | `nobulex-gogani` | `31ddbd9f...` |
| `pending` | `nexus-agent-pending` | `30cce7e7...` |
| `pending (degraded)` | `nexus-agent-degraded` | `2edaceb1...` |
| `failed` | `nexus-agent-failed` | `a62111ca...` |

Full fixtures: [examples/conformance/](../../examples/conformance/)

---

## Spore Portfolio

Every `agent_id` that anchors trails accumulates karma automatically.
The Spore portfolio API aggregates all anchored events for an agent:

```bash
curl 'https://argentum-api.rgiskard.xyz/spore/portfolio/{owner_id}'
```

`owner_id` maps directly to `agent_id` in the `TrailRecord`. If your
platform assigns a DID to each agent, use the DID as the `agent_id`
when deriving the `action_ref` and submitting the trail — the portfolio
view will aggregate by that identifier automatically.

```json
{
  "owner_id": "my-agent-001",
  "karma": 4.2,
  "tier": "TRUSTED",
  "earnings_month": 0.012,
  "trail_count": 14
}
```

Full spec: [docs/spec/karma-score-v1.md](../spec/karma-score-v1.md)

---

## Questions

Open an issue: [github.com/giskard09/argentum-core/issues](https://github.com/giskard09/argentum-core/issues)
