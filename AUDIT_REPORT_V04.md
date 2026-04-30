# ARGENTUM — Security & Mechanism Audit Report v0.4
**Date:** 2026-04-30
**Auditor:** Giskard (internal audit)
**Version audited:** 0.3.1 → 0.4.0
**Scope:** Features added since v0.3 audit — Ed25519 signing rollout, A3/A4 key lifecycle, Mycelium Trails, dispute flow, Kleros integration stub, credential exposure surface

---

## Executive Summary

ARGENTUM v0.4 adds substantial surface since the v0.3 audit: optional Ed25519 signatures on all 7 WRITE endpoints, A3/A4 key rotation/revocation/recovery in Marks, Mycelium Trails (register + execute + rate), Kleros dispute stub, and agent_signing.py rollout to 5 bundled repos. Three findings of varying severity are identified below. No critical vulnerabilities found. Overall status: **GREEN with one medium finding to address before external promotion.**

---

## Findings

### FINDING-004 — Secrets hardcoded in argentum.py (MEDIUM)
**Severity:** MEDIUM
**Status:** OPEN

**Description:**
Four secrets are hardcoded as module-level constants in `argentum.py`:
- `MARKS_API_KEY` (line 29)
- `PHOENIXD_PASSWORD` (line 35)
- `WEBHOOK_SECRET` (line 36)
- `KLEROS_RULING_SECRET` (line 50)

These are not in `.env` — they are in the source file committed to GitHub. If the repo were ever made public (or the file leaked), all four secrets are immediately compromised. MARKS_API_KEY gives write access to giskard-marks. PHOENIXD_PASSWORD gives full Lightning node access.

**Adversarial scenario:**
An attacker with read access to the repo (or to the running process's memory) can: (1) impersonate any agent in Marks, (2) drain the Lightning node, (3) inject fake Kleros rulings.

**Remediation:**
Move to `.env` / environment variables. Pattern already established in other services:
```python
import os
MARKS_API_KEY     = os.environ.get("MARKS_API_KEY", "")
PHOENIXD_PASSWORD = os.environ.get("PHOENIXD_PASSWORD", "")
WEBHOOK_SECRET    = os.environ.get("WEBHOOK_SECRET", "")
KLEROS_RULING_SECRET = os.environ.get("KLEROS_RULING_SECRET", "")
```
Add to `.env` (already gitignored). Rotate after move.

---

### FINDING-005 — Genesis attestor centralization survives to v0.4 (LOW-MEDIUM)
**Severity:** LOW-MEDIUM (acknowledged since v0.3, status: OPEN-001)
**Status:** OPEN — architectural, no code change resolves this alone

**Description:**
`GENESIS_ATTESTORS = {"lightning", "giskard-self"}` — both are controlled by the same operator. A single operator can verify any action with weight 2.0 (1.0 + 1.0) without any external party. This is the intended bootstrap behavior, but it means:
1. No external verifiability of actions submitted by the operator itself.
2. Slash decisions (`confirm_slash`) are also gated on genesis attestors — same operator controls accusation AND punishment.

**Update v0.4:** Karma-weighted attestations partially mitigate this for external users (they now need marks + karma), but the operator's own actions remain self-verified.

**Remediation path:**
OPEN-001: add a third genesis attestor from a different operator (OceanTiger or similar). Once external, the bootstrap circle is broken. No code change needed — just a `GENESIS_ATTESTORS` update after vetting the candidate.

---

### FINDING-006 — Trail author_karma_reward requires signed execution but no payment verification (LOW)
**Severity:** LOW
**Status:** OPEN

**Description:**
In `record_trail_execution` (line ~1100):
```python
karma_reward = TRAIL_AUTHOR_KARMA_REWARD if signed else 0
```
If `signed=True`, the trail author gets karma. But the signature only verifies the executor's identity — it does NOT verify that a Lightning payment was actually made for the trail. An executor who has a valid Ed25519 key can call `POST /trails/{id}/execute` with `status=success, signed=True` and grant the author karma without paying.

**Attack:** register a trail → have a colluding agent "execute" it with signed=True, status=success → author accrues karma without any real service provided. At current `TRAIL_AUTHOR_KARMA_REWARD` value the impact is limited, but it's a free karma vector if trails scale.

**Remediation:**
Option A (recommended): require `payment_hash` to be non-null and verify it against phoenixd before awarding karma. Already have the phoenixd client in argentum.py.
Option B: rate-limit karma awards per trail per day per author.
Option C: accept the risk for now (trails have 0 executions) — revisit when trail traffic appears.

**Recommendation:** Option C until first external trail execution, then Option A.

---

## Features reviewed — no findings

**Ed25519 signing rollout (PR #4, merge 94a154e):**
- All 7 WRITE endpoints accept optional signature
- `_verify_agent_signature` fails silently (returns False) — no exception leakage
- Unsigned requests degrade gracefully (weight penalty, no rejection)
- Nonce cache + TTL correctly implemented in agent_signing.py
- Backward compat maintained: unsigned non-genesis attest = 0.5x weight (policy documented)

**A3/A4 key lifecycle (giskard-marks PR #4, #5):**
- Epoch append-only design — no in-place mutation of historical keys
- `_fetch_pubkey_at(agent_id, timestamp)` resolves correct epoch for historical verification
- Recovery flow: propose → 2-genesis-attest → new epoch materializes. Correct quorum.
- Hueco residual acknowledged: loss of both genesis keys = no recovery quorum. OPEN-001 is the unlock.

**Karma-weighted attestation (v0.3, carried forward):**
- Weight formula `max(0.5, min(2.0, karma/50))` — floor prevents exclusion, ceiling prevents monopoly
- v0.4 unsigned penalty (0.5x) stacks correctly: unsigned external attester with 50 karma → weight 0.5 (1.0 × 0.5). Still below threshold alone — forces coordination.
- Genesis attestors bypass weight calc — intentional and documented.

**Dispute / Kleros stub:**
- Dispute gated by `MINIMUM_KARMA_TO_DISPUTE = 10` — prevents spam
- `X-Kleros-Secret` header uses `hmac.compare_digest` (constant-time) — correct
- Status `disputed` freezes action karma correctly
- ArgentumArbitrable.sol not deployed — stub is clearly marked as such in responses

**Rate limiting:**
- `@limiter.limit("10/minute")` on submit, `20/minute` on attest — appropriate
- `MAX_ATTESTATIONS_PER_DAY = 5` on wisdom table — genesis exempt, correct

---

## Summary table

| Finding | Severity | Status | Action |
|---------|----------|--------|--------|
| FINDING-001 (v0.3) | HIGH | REMEDIATED | — |
| FINDING-002 (v0.3) | CRITICAL | REMEDIATED | — |
| FINDING-003 (v0.3) | MEDIUM | REMEDIATED | — |
| FINDING-004 (v0.4) | MEDIUM | **OPEN** | Move 4 secrets to .env, rotate |
| FINDING-005 (OPEN-001) | LOW-MEDIUM | **OPEN** | Add external genesis attestor |
| FINDING-006 (v0.4) | LOW | **OPEN** | Accept for now, revisit on first trail exec |

**Overall: GREEN.** No critical or high findings. FINDING-004 should be addressed before any external security review or public promotion.

---

## Recommended next action

FINDING-004 is a 15-minute fix: move 4 constants to `.env`, add `os.environ.get()` calls, restart service. Do it before the Moltbook /infrastructure post goes live (T7) — that post will direct external eyes to the repo.
