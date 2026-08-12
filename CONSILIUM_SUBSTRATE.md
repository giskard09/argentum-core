# Consilium Pass — Substrate Submission

**Author:** giskard09 (Rama)
**Repo:** argentum-core
**Date:** 2026-05-22
**Consilium steward:** aeoess
**Substrate window closes:** 2026-06-05

This document is argentum-core's formal substrate contribution to the A2A Consilium Pass
([a2aproject/A2A Discussion #1734](https://github.com/a2aproject/A2A/discussions/1734),
[Issue #1786](https://github.com/a2aproject/A2A/issues/1786)).

Per aeoess's methodology: shipped commits, draft specifications with named authors, and
production deployment data with at least one named integrator. Each section maps to one
Consilium candidate.

---

## Candidate 2 — Live-state admissibility at commit

### The invariant

`action_ref` is computed and anchored **before** execution begins.

Admissibility at execution time is a property of the **anchor state** — not of the receipt
itself. A receipt valid at issuance can become inadmissible before execution if:

1. The agent's trust tier degrades between commit and execution
2. The governing policy rotates between issuance and execution

The distinction that matters: a hash over pre-execution fields computed post-execution is
still a post-hoc construction unless the **anchor timestamp on-chain precedes execution**.
When it does, any verifier can establish admissibility independently — no trust in the
emitting system required.

### Shipped spec

**[docs/spec/action-ref.md](docs/spec/action-ref.md)** — execution-boundary specification.

Core derivation:

```python
action_ref = SHA-256(JCS({agent_id, action_type, scope, timestamp}))
```

Where JCS is RFC 8785 JSON Canonicalization Scheme: lexicographic key order, no whitespace,
UTF-8, lowercase-hex digest.

The four preimage fields are all knowable before execution begins. Any party holding them
can recompute `action_ref` independently. The anchor on-chain is the verifiable boundary —
not the receipt.

**Canonical receipt envelope v1.0** (from spec):

```json
{
  "packet_version": "1.0",
  "action_ref": "<sha256 hex>",
  "hash_algo": "sha256",
  "preimage_format": "jcs-rfc8785",
  "preimage": {
    "agent_id": "...",
    "action_type": "...",
    "scope": "...",
    "timestamp": "2026-05-15T10:00:00.123Z"
  }
}
```

**Shipped commit:** `fd0c31f` — corrected action_ref derivation to JCS+SHA-256.
**Reference implementation:** `plugins/agt_evidence_anchor/action_ref.py`

### Cross-implementation validation

The same `action_ref` is independently computable from:

| Implementation | Source |
|---|---|
| Mycelium TrailRecord (preimage fields in each record) | this repo |
| SafeAgent `/claim` (azender1) | [azender1/SafeAgent](https://github.com/azender1/SafeAgent) — joint spec [argentum-core#7](https://github.com/giskard09/argentum-core/issues/7) |
| Nobulex covenant receipt (arian-gogani) | [MetaGPT#1991](https://github.com/geekan/MetaGPT/issues/1991) |
| NEXUS oracle receipt (RileyCraig14) | [nexus-agent-xa12.onrender.com/receipt](https://nexus-agent-xa12.onrender.com/receipt) |
| CTEF v0.3.3 matrix row #2 | [kenneives/AgentAvow PR #20](https://github.com/kenneives/AgentAvow/pull/20) — `urn:mycelium:trail`, 3 vectors byte-matched |

Any verifier holding one artifact can validate against another without trusting either
system.

### The named gap — revocation and policy rotation

The current spec does not yet cover what happens when, between issuance and execution:

- The agent's trust tier degrades (TRUSTED → WATCH)
- The governing policy rotates (counterparty_policy_hash changes)

A receipt valid at issuance becomes inadmissible at execution time. The anchor records
the issuance state — it does not record whether that state was still valid when the action
was admitted.

Two fields needed to close this gap:

| Field | What it proves |
|---|---|
| `policy_version` | whether the policy that governed the decision was still current at execution time (distinct from `counterparty_policy_hash`, which proves *which* policy) |
| `revocation_check_at_ms` | timestamp of the last non-revocation check before execution |

Both are needed for post-rotation audits. A verifier replaying the receipt needs to
establish not just *which* policy was in force, but *whether it was still current* when
the action was admitted.

This gap was named in [a2aproject/A2A#1786](https://github.com/a2aproject/A2A/issues/1786)
and confirmed by @Liuyanfeng1234 (Trust_Ledger tier-transition model) and @Keesan12
(counterparty_policy_hash / policy_version distinction).

---

## Candidate 3 — Karma as value layer over the anchor

### The gap the anchor alone does not fill

An anchor proves that a specific action occurred at a specific time. It does not answer a
different question: *how much should a verifier trust the agent who anchored it?*

Two trails with identical `action_ref` derivations and valid on-chain anchors are
cryptographically equivalent — but they are not epistemically equivalent if one was
produced by an agent with zero verified history and the other by an agent with 200 verified
actions attested by independent parties.

The anchor is a fact. The karma is a claim about the agent behind the fact. Systems that
need to make decisions based on anchored receipts need both.

### The design

ARGENTUM adds a karma layer that accumulates over verified actions and is separately
verifiable from the anchor itself.

**Structure:**

```
anchor (on-chain, immutable) ──► proves: what happened, when
karma  (signed badge, portable) ──► proves: who did it, what they've demonstrated
```

The two are independent verification paths. A verifier can check the anchor without trusting
ARGENTUM, and check the karma badge without trusting the agent. Neither path requires
trusting the other.

**Karma badge format:**

```json
{
  "agent_id": "nexus-oracle-v1",
  "karma": 36,
  "verified_at": "2026-05-22T13:39:58Z",
  "verified_actions": 4,
  "source": "https://argentum-api.rgiskard.xyz/karma/nexus-oracle-v1",
  "signature": "<Ed25519 base64>",
  "verify_key": "gdvrkAuw22AUH8+goZPZIYw2W3sLT/pPX3himAfnQIk="
}
```

The badge is signed by the Argentum server key. The public verification key is published
in the README and pinned at `GET /karma/{agent_id}`. Any party holding the four badge
fields and the signature can verify offline — no network call required.

### Why this belongs in the Consilium substrate

The Consilium methodology asks for shipped specs with named integrators. The karma layer
meets this bar:

1. **Shipped:** `GET /karma/{agent_id}` live in production since 2026-05-22.
   `POST /karma/{agent_id}/verify` for offline verification.
   Commit: [`5715637`](https://github.com/giskard09/argentum-core/commit/5715637).

2. **Independently verifiable:** The Ed25519 public key is hardcoded in the README.
   Any downstream service can verify a badge without an ARGENTUM API call.

3. **Named gatekeeper:** Soma marketplace (`https://soma.rgiskard.xyz`) is the first
   service to require `karma ≥ 1` as a condition of access. Agents with zero verified
   history receive a 403 with `how_to_earn` pointing back to ARGENTUM. This is a live
   production deployment of karma as an access credential — not a design proposal.

### The distinction that matters for Consilium

The execution-boundary invariant in Candidate 2 answers: *did the action occur?*

The karma layer answers: *is the agent who claims to have acted credible?*

Both questions need to be answerable for a receipt to be operationally useful in
multi-agent systems. A receipt from an unverified agent anchored on-chain is better than
no receipt — but a receipt from a verified agent with demonstrated history is a different
class of signal. The substrate should name this distinction explicitly.

### The named gap

The current karma score is a scalar. It does not encode *domain specificity*: an agent
with 200 karma in document processing and 0 karma in financial transactions carries the
same number. Downstream systems making trust decisions benefit from knowing whether the
karma was accumulated in a domain relevant to the current action type.

Domain-weighted karma is a proposed extension — not shipped. Named here as a known gap,
consistent with Consilium methodology.

---

## Candidate 5 — Real-world deployment patterns

### Named integrator

**NEXUS** ([nexus-agent-xa12.onrender.com](https://nexus-agent-xa12.onrender.com))
— arbitrage oracle agent. Trails anchored on Base mainnet.

### Production gaps observed after one week of live traffic

Synthetic conformance fixtures do not exercise the following classes of production inputs:

**1. Timestamp precision under retry conditions**

When an agent retries a failed anchor, the `timestamp` field must remain stable across
retry attempts — it reflects when the action was *claimed*, not when the anchor
*succeeded*. Production retry storms generate timestamp clustering that conformance suites
never test because fixture authors use clean single-call scenarios.

**2. action_ref stability across agent restarts**

The `action_ref` must be recomputable after an agent restart from the same four preimage
fields — no session state dependency. Production agents restart under load, during deploys,
and on infrastructure failures. Conformance suites test cold-path computation but not
restart-continuity under live traffic.

**3. Anchor failure handling**

When the on-chain anchor call fails (network error, gas spike, RPC timeout), the agent
must preserve the preimage fields to retry — and the retry must produce the same
`action_ref`. Receipt consumers need to distinguish "anchor pending" from "anchor
confirmed" without ambiguity. This failure mode does not appear in synthetic fixtures.

### Live endpoint

```
GET https://nexus-agent-xa12.onrender.com/receipt?action_type=arb.check&scope=Fed,BTC
→ returns canonical envelope v1.0 with action_ref + preimage_format: jcs-rfc8785

GET https://nexus-agent-xa12.onrender.com/trails/verify?agent_id=<id>&action_ref=<hash>
→ verifies anchor on Base mainnet
```

### Additional production evidence

**azender1/SafeAgent** provided the first independent production validation of Mycelium Trails
in a live trading environment (2026-05-21). Their session data — six confirmed SKIP events
blocking duplicate trades on a live Alpaca broker, with full stack DashClaw + SafeAgent +
Mycelium Trails + Base/Arbitrum — surfaced a production gap (exit-side guard) that synthetic
fixtures had not exercised: a failed exit leaving orphaned broker state cascades into
downstream blocks that appear in any receipt chain as legitimate decisions with no indication
of the upstream failure. This is the class of real-world evidence the Consilium pass was
designed to surface. Full session data: [gist](https://gist.github.com/azender1/b9112b6519c935df4a75cb05cd250e26).

---

## Relationship to draft-pidlisnyi-aps

aeoess noted in the Consilium methodology that the argentum-core execution-boundary
invariant "matches draft-pidlisnyi-aps-01 §4.1." The substrate above — shipped spec,
reference implementation, named integrator in production — is the evidence base for that
alignment.

The revocation/policy rotation gap identified in Candidate 2 is a proposed addition to
draft-pidlisnyi-aps-02, per aeoess's commitment to co-author the dual-timestamp boundary
appendix.

---

## Substrate links

| Artifact | Location |
|---|---|
| Execution-boundary spec | [docs/spec/action-ref.md](docs/spec/action-ref.md) |
| Reference implementation | [plugins/agt_evidence_anchor/action_ref.py](plugins/agt_evidence_anchor/action_ref.py) |
| CTEF v0.3.3 fixture set | [commit b23941a](https://github.com/giskard09/argentum-core/commit/b23941a) |
| Karma badge endpoint | `GET https://argentum-api.rgiskard.xyz/karma/{agent_id}` |
| Karma badge verify key | `gdvrkAuw22AUH8+goZPZIYw2W3sLT/pPX3himAfnQIk=` |
| Soma karma gate (live gatekeeper) | [soma-karma-gate.md](https://github.com/giskard09/soma/blob/main/soma-karma-gate.md) |
| Adopters (named integrators) | [ADOPTERS.md](ADOPTERS.md) |
| Joint spec with SafeAgent | [argentum-core#7](https://github.com/giskard09/argentum-core/issues/7) |
| Fifth-layer issue (A2A) | [a2aproject/A2A#1847](https://github.com/a2aproject/A2A/issues/1847) |
