# Mycelium Trails — Conformance Fixtures

This directory contains conformance fixtures for the action-ref-v1 spec and Mycelium Trails:

1. **action-ref-v1 baseline** — formal substrate for the `action_ref` derivation spec. Use these to verify a conformant implementation.
2. **delegation-ref** — envelope conformance with opaque `delegation_ref` field.
3. **trail-status lifecycle** — three-state lifecycle (PENDING → COMMITTED → FAILED) with tx_hash invariants.
4. **negative fixtures** — cases that MUST fail validation: missing required field, tampered hash.
5. **CTEF vectors** — cross-extension matrix fixtures for `urn:mycelium:trail` (CTEF v0.3.3 row #2).
6. **memory provenance** — `action_type: "memory_write"` + `scope: <memory_key>` pattern for content-addressed receipts per write. Covers OWASP ASI06 gap class #2. See commit [de7dd7e](https://github.com/giskard09/argentum-core/commit/de7dd7e0c09365f465d2c14c62817b1d19e4adef) and `docs/spec/action-ref.md` (memory provenance section).
7. **near-miss vectors** — failure-mode boundary fixtures (`AMBIGUOUS_ISSUER_BINDING`, `RESCOPED_REPLAY`, `SEMANTIC_DRIFT`). Source: [agentgraph-co/agentgraph](https://github.com/agentgraph-co/agentgraph) @ `a07cdf8`.
8. **recompute-drift vectors** - recomputation-property fixtures: 5 positive baselines (basic, unicode, empty scope, `.000` / `.999` millisecond edges) plus 9 negatives across four drift families (field order, timestamp form, casing, payload). Standalone stdlib runner included. See [`recompute-drift-v1/`](./recompute-drift-v1/).

---

## action-ref-v1 baseline — [`action-ref-v1-baseline.fixture.json`](./action-ref-v1-baseline.fixture.json)

Formal conformance substrate for [`docs/spec/action-ref.md`](../../docs/spec/action-ref.md) (`action-ref-v1.0` stable tag).

An independent implementation that reproduces all three vectors byte-identical satisfies **criterion (a)**: an independent implementation of the action-ref-v1 wire format validating against `argentum-core/examples/conformance/`.

| Vector | Description |
|--------|-------------|
| `0001-giskard-baseline` | Minimal — 4 preimage fields, scope namespace-prefixed, no optional envelope fields |
| `0002-dual-timestamps` | Full envelope with `authority_verified_at_ms` + `revocation_check_at_ms` + `policy_version` |
| `0003-scope-namespace-collision-proof` | Proves that prefixed vs unprefixed scope strings produce different `action_ref` values — invariant: `prefixed_action_ref != unprefixed_action_ref` |

### Quick verify

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

# 0001-giskard-baseline
preimage = {
    "action_type": "trail.anchor",
    "agent_id":    "giskard-self",
    "scope":       "mycelium:baseline",
    "timestamp":   "2026-05-23T00:00:00.000Z",
}
assert hashlib.sha256(jcs(preimage).encode()).hexdigest() == \
    "f4ebda732e3c063bdd8547c734e4956f009bbed7f557cb949f7c8033e8c42d1d"

# 0002-dual-timestamps — verify action_ref only
preimage2 = {
    "action_type": "payment.send",
    "agent_id":    "pioneer-agent-001",
    "scope":       "nobulex:bilateral",
    "timestamp":   "2026-05-23T10:00:00.000Z",
}
assert hashlib.sha256(jcs(preimage2).encode()).hexdigest() == \
    "f09eb8c50dfa27a33cdb36efa08194bcba2d7ac32eb1dd6539fb0c3bc811a8e0"

print("all assertions pass — implementation is conformant")
```

---

## delegation-ref-v1 — [`delegation-ref-v1.fixture.json`](./delegation-ref-v1.fixture.json)

Conformance substrate for action-ref-v1 envelopes carrying an opaque `delegation_ref` field.

**Key invariant:** `delegation_ref` is envelope-only — it does NOT enter the preimage. Removing or changing it does not change `action_ref` but does change `envelope_canonical_sha256`.

| Vector | Description |
|--------|-------------|
| `0004-delegation-ref-opaque` | `delegation.execute` with opaque `dlg_opaque_a1b2c3d4e5f6` — action_ref + envelope_sha256 both verified |

---

## trail-status-lifecycle-v1 — [`trail-status-lifecycle-v1.fixture.json`](./trail-status-lifecycle-v1.fixture.json)

Formal conformance substrate for the three-state trail_status lifecycle.

| State | tx_hash | Meaning |
|-------|---------|---------|
| `PENDING` | `null` | Transitional — execution started, outcome unknown |
| `COMMITTED` | non-null | Terminal success — tamper-evident anchor exists |
| `FAILED` | `null` | Terminal failure — no anchor, no recovery possible |

**Critical distinction:** PENDING/null ≠ FAILED. PENDING means "execution started, I do not know if it landed." FAILED means "TTL expired, terminal."

---

## negative-v1 — [`negative-v1.fixture.json`](./negative-v1.fixture.json)

Cases that MUST fail validation. A conformant verifier that accepts any of these has a bug.

| Vector | Failure mode | What to reject |
|--------|-------------|----------------|
| `neg-001-missing-scope` | Missing required field (`scope`) | `broken_action_ref` presented as valid for `complete_preimage` |
| `neg-002-tampered-hash` | Hash tampered (last nibble flipped) | `tampered_action_ref` presented as valid for the stated preimage |

**Verifier rule:** always re-derive `SHA-256(JCS(preimage))` and compare against the presented `action_ref`. Never trust the presented hash without re-derivation.

---

## CTEF Conformance Fixtures

Conformance vectors for `urn:mycelium:trail` — CTEF v0.3.3 cross-extension matrix row #2.

## URN namespace

`urn:mycelium:trail`

| Field | Value |
|-------|-------|
| `claim_type` | `continuity` |
| `evidenceType` | `observational` |
| Canonical spec | [`docs/spec/action-ref.md`](../../docs/spec/action-ref.md) |
| Substrate | JCS (RFC 8785) + SHA-256 lowercase hex |
| Source provider | `https://argentum-api.rgiskard.xyz` |

## Substrate filter

Every fixture in this directory passes the CTEF substrate gate:

1. **RFC 8785 JCS canonicalization** — `json.dumps(obj, separators=(',',':'), sort_keys=True, ensure_ascii=False)`
2. **Lowercase-hex SHA-256** — `hashlib.sha256(canonical_bytes).hexdigest()`
3. **Byte-match reproducible** — `canonical_bytes_hex` is the hex of the raw UTF-8 JCS output; any RFC 8785-conformant implementation produces the same bytes.

## Fixtures

| File | Vectors | Status |
|------|---------|--------|
| [`urn-mycelium-trail-v1.fixture.json`](./urn-mycelium-trail-v1.fixture.json) | 3 | ✓ byte-match verified |
| [`delegation-ref-v1.fixture.json`](./delegation-ref-v1.fixture.json) | 1 | ✓ byte-match verified |
| [`delegation-ref-v2.fixture.json`](./delegation-ref-v2.fixture.json) | 1 | ✓ byte-match verified |
| [`trail-status-lifecycle-v1.fixture.json`](./trail-status-lifecycle-v1.fixture.json) | 3 | ✓ byte-match verified |
| [`negative-v1.fixture.json`](./negative-v1.fixture.json) | 2 | ✓ byte-match verified |
| [`idempotency-ref-v1.fixture.json`](./idempotency-ref-v1.fixture.json) | 1 | ✓ byte-match verified |
| [`revocation-ref-v1.fixture.json`](./revocation-ref-v1.fixture.json) | 1 | ✓ byte-match verified |
| [`trail-complete-v1.fixture.json`](./trail-complete-v1.fixture.json) | 3 | ✓ byte-match verified |
| [`memory-write-v1.fixture.json`](./memory-write-v1.fixture.json) | 3 | ✓ byte-match verified |

### Vectors

| Name | action_type | agent_id | Notes |
|------|------------|----------|-------|
| `nexus-oracle-signal` | `oracle.signal` | `nexus-agent-xa12.onrender.com` | action_ref matches canonical example in `action-ref.md` |
| `giskard-self-enter-oasis` | `enter_oasis` | `giskard-self` | Real trail 2026-04-13, anchored on Base mainnet |
| `pioneer-negotiation-accept` | `negotiation.accept` | `pioneer-agent-001` | Minimal envelope (no trail_id / tx_hash) |

## Reproduce in Python

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

# Step 1 — compute action_ref from the 4 preimage fields
preimage = {
    "action_type": "oracle.signal",
    "agent_id":    "nexus-agent-xa12.onrender.com",
    "scope":       "BTC",
    "timestamp":   "2025-05-18T11:40:31.000Z",
}
action_ref = hashlib.sha256(jcs(preimage).encode()).hexdigest()
# fdd7f810499f06be24355ca8e2bfb8c4b965cc80c838f41fa074683443d89f5a

# Step 2 — build the CTEF envelope
# trail_id and tx_hash are part of the canonical envelope for COMMITTED trails
envelope = {
    "action_ref":      action_ref,
    "claim_type":      "continuity",
    "evidenceType":    "observational",
    "hash_algo":       "sha256",
    "preimage":        preimage,
    "preimage_format": "jcs-rfc8785",
    "source_provider": "https://argentum-api.rgiskard.xyz",
    "trail_id":        "ea145ca5-e9ac-4900-b583-a2e1bea61140",
    "tx_hash":         "7fd0a8ededd1feb65ab37b3324218a0386dbf124174cf122bffc40717c057b84",
    "urn":             "urn:mycelium:trail",
}

# Step 3 — JCS canonicalize + SHA-256
canonical_bytes = jcs(envelope).encode("utf-8")
canonical_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
# 8af1dad8c307513b3a52ad378a7b45ff2812462f7c489baa547cb747c0f5d879
```

## Verify against the live API

```
GET https://argentum-api.rgiskard.xyz/trails/verify?agent_id=<agent_id>&action_ref=<action_ref>
```

No authentication required.

## Cross-references

- CTEF v0.3.3 working doc: `agentgraph-co/agentgraph/docs/standards/v0.3.3-working-doc.md` (branch: `v0.3.3-cross-extension-matrix`)
- Full TrailRecord schema: [`docs/MYCELIUM_TRAILS_REFERENCE.md`](../../docs/MYCELIUM_TRAILS_REFERENCE.md)
- action_ref derivation spec: [`docs/spec/action-ref.md`](../../docs/spec/action-ref.md)
- CTEF canonical anchor: [`cte-test-vectors.json`](https://agentgraph.co/.well-known/cte-test-vectors.json) (agentgraph-co/agentgraph, v0.3.1)

---

## near-miss-v1 — [`near-miss-v1/near-miss-v1.fixture.json`](./near-miss-v1/near-miss-v1.fixture.json)

Near-miss conformance vectors for the `action_ref` verifier boundary. Each vector is a case that a conformant verifier **MUST** reject fail-closed.

**Source:** [agentgraph-co/agentgraph](https://github.com/agentgraph-co/agentgraph) @ commit `a07cdf8`  
**Attribution:** per [A2A discussion #1734](https://github.com/a2aproject/A2A/discussions/1734#discussioncomment-17124409)

| Vector | Error code | What it tests |
|--------|-----------|---------------|
| `ambiguous_issuer_binding` | `AMBIGUOUS_ISSUER_BINDING` | Two issuers, same `action_ref`, disjoint verdicts — injectivity must fail |
| `rescoped_replay` | `RESCOPED_REPLAY` | `read` scope attestation presented as `write` — recomputed `action_ref` diverges |
| `semantic_drift` | `SEMANTIC_DRIFT` | `behavioral_eval` at issuance vs `behavioral` at verification — vocabulary drift from A2A #1786 |

All three `canonical_sha256` values are byte-match verified (JCS + SHA-256). See [`near-miss-v1/README.md`](./near-miss-v1/README.md) for full spec.

---

## talos — [`talos/vectors.json`](./talos/vectors.json)

External conformance set from [konstantinos193/Talos](https://github.com/konstantinos193/Talos) — x402 governance layer with budget caps and Mycelium anchor support.

**Source:** `packages/core/src/action-ref.ts` (`main` branch, `feat/mycelium-anchor` merged 2026-06-14)
**Verification:** Independent cross-verify — giskard09 sent expected hex, konstantinos193 computed via `describeActionRef` primitive. Byte-identical match confirmed in stripe/ai#356. No shared code path.
**Mainnet anchor:** `0xbeff35180e1d8902615a906c4703d4d01afded3efb0aa2be67339887807438ba` (Arbitrum One, autonomous — no operator in the loop)

| Vector | Description |
|--------|-------------|
| `talos-001-transfer-execute` | Real `payment:approved` preimage — same fields behind the live mainnet anchor |

---

## recompute-drift-v1 - [`recompute-drift-v1/`](./recompute-drift-v1/)

Recomputation-property fixtures: a verifier recomputes `action_ref` from the
invocation payload tuple and MUST fail closed, before invocation, on any
mismatch, with no preimage retries, no coercion, and no normalization.

| File | Vectors | What it holds |
|------|---------|---------------|
| `recompute-drift-v1-positive.fixture.json` | 5 | Tuples that recompute byte-identical (basic, unicode, empty scope, `.000` / `.999` ms edges) |
| `recompute-drift-v1-negative.fixture.json` | 9 | Real digests over drifted byte forms (field order, timestamp form, casing, payload drift) that MUST be rejected |

Standalone runner: `python3 recompute-drift-v1/verify.py` (stdlib only,
deterministic, exit 0 on full pass). See [`recompute-drift-v1/README.md`](./recompute-drift-v1/README.md)
for the drift-family table and the explicit not-covered list.

## composed-decision-chain-recompute - [`composed-decision-chain-recompute/`](./composed-decision-chain-recompute/)

Composed profile: admission (signer independence) + recompute (`verdict = f(controls)`) +
chain-fork (`head_hash = sha256(content_hash|prev_head_hash)`), requested by rpelevin on
[autogen#7353](https://github.com/microsoft/autogen/issues/7353). A self-signed ALLOW, a
verdict that doesn't recompute, and a same-sequence fork each fail for a distinct,
individually-diagnosable reason — not one pass/fail bit. Built on the
[`presidio/`](./presidio/) decision fixture. Cross-checked byte-identical against an
independent build of the same profile
([babyblueviper1/preaction-governance-conformance](https://github.com/babyblueviper1/preaction-governance-conformance)).

Standalone runner: `python3 composed-decision-chain-recompute/verify.py` (stdlib only,
exit 0 on full pass). See [`composed-decision-chain-recompute/README.md`](./composed-decision-chain-recompute/README.md).

## Conformance methodology

All sets in this directory use embedded_fixture evidence mode: every key,
canonical byte sequence, and hash needed to reproduce the result is present
in the fixture. No external key resolution, network fetch, or out-of-band
trust input is required. A verifier with only the fixture file and a correct
SHA-256 / Ed25519 implementation reaches the same result as the original run.
