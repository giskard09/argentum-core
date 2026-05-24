# Mycelium Trails — Conformance Fixtures

This directory contains two sets of conformance fixtures:

1. **action-ref-v1 baseline** — formal substrate for the `action_ref` derivation spec. Use these to verify a conformant implementation.
2. **CTEF vectors** — cross-extension matrix fixtures for `urn:mycelium:trail` (CTEF v0.3.3 row #2).

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
envelope = {
    "action_ref":      action_ref,
    "claim_type":      "continuity",
    "evidenceType":    "observational",
    "hash_algo":       "sha256",
    "preimage":        preimage,
    "preimage_format": "jcs-rfc8785",
    "source_provider": "https://argentum-api.rgiskard.xyz",
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
