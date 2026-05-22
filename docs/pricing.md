# Pricing

## Free tier

No API key required. No signup.

| | |
|---|---|
| **Trails per month** | 1,000 |
| **Verification** | Unlimited — public endpoint, no auth |
| **action_ref derivation** | Unlimited — local, no network call |
| **Cost** | Free |

Start immediately:

```bash
curl -X POST https://argentum-api.rgiskard.xyz/nexus/trail \
  -H "Content-Type: application/json" \
  -d '{
    "action_ref": "<your-action-ref>",
    "service": "my-agent",
    "hash_algo": "sha256",
    "preimage_format": "jcs-rfc8785",
    "preimage": {
      "agent_id": "my-agent-001",
      "action_type": "file:write",
      "scope": "audit",
      "ts": "2026-05-19T12:00:00.000Z"
    }
  }'
```

When you reach 1,000 trails in a calendar month, the API returns:

```json
{
  "error": "monthly_limit_exceeded",
  "limit": 1000,
  "used": 1000,
  "tier": "free",
  "upgrade": "https://argentum-api.rgiskard.xyz/docs#payg"
}
```

## Pay-as-you-go (PAYG)

**$0.003 per trail.** No monthly commitment.

| | |
|---|---|
| **Price** | $0.003 / trail |
| **Minimum purchase** | 1 trail |
| **Maximum purchase** | 10,000 trails per invoice |
| **Payment** | Lightning (sats) · USDC on Arbitrum |
| **Credits** | Added within 24h of on-chain confirmation |

**Get started in two steps:**

```bash
# 1. Create your PAYG account
curl -X POST "https://argentum-api.rgiskard.xyz/payg/account?agent_id=my-agent-001"

# 2. Get a USDC deposit address for N trails
curl -X POST https://argentum-api.rgiskard.xyz/payg/topup/usdc \
  -H "Content-Type: application/json" \
  -d '{"api_key": "<your-api-key>", "trails": 500}'
```

## Enterprise

Volume pricing and SLA guarantees. [Open an issue](https://github.com/giskard09/argentum-core/issues) to discuss.

## Karma discounts

Agents that accumulate karma through verified actions on Mycelium get automatic
discounts on all infrastructure services (Oasis, Memory, Search).

Karma is not a token. It is a score derived from on-chain verified actions —
it cannot be purchased, transferred, or traded. Discounts are a consequence
of the agent's action history, not of any acquired asset.

| Karma | Discount | Pay |
|-------|----------|-----|
| 0 | — | base price |
| ≥ 1 | 30% off | 70% of base |
| ≥ 21 | 50% off | 50% of base |
| ≥ 50 | 75% off | 25% of base |

**Example — Oasis (base price: 21 sats per query):**

| Karma | Price per query |
|-------|----------------|
| 0 | 21 sats |
| 1–20 | 15 sats |
| 21–49 | 11 sats |
| 50+ | 6 sats |

**What this means for integrators:** an agent that starts anchoring trails today
accumulates karma over time. Within weeks of consistent use, it operates at 25%
of the base cost across all Mycelium services — while a new agent entering the
ecosystem pays full price. The earlier you integrate, the larger the structural
advantage your agents carry.

Karma is verified at request time via Ed25519 signature. Agents without a valid
signature always pay base price, regardless of claimed karma.

---

*Verification (`/trails/verify`) is always free and unauthenticated — for anyone,
including auditors who never submitted a trail.*
