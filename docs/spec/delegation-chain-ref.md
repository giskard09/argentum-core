# delegation-chain-ref-v1 — Specification

**Stable tag:** `delegation-chain-ref-v1.0`  
**Status:** stable  
**Canonical fixture:** [`docs/spec/fixtures/delegation-chain-ref-v1.fixture.json`](./fixtures/delegation-chain-ref-v1.fixture.json)

---

## What is delegation-chain-ref

`delegation_chain_ref` is a SHA-256 hex pointer to a chain artifact — a structured document that records a multi-hop delegation sequence and the final action executed by the leaf agent. It answers the question a single `delegation_ref` cannot: in a system where agent A authorized B who authorized C who authorized D, is the complete chain verifiable end-to-end without trusting any intermediary?

**What it enables:** a Mycelium verifier holding `delegation_chain_ref` can reconstruct the full authorization path from root delegator to leaf action, verify each hop's `delegation_ref` independently, confirm chain continuity (each `delegatee` equals the next `delegator`), and confirm the leaf agent's final action_ref. No single intermediary needs to be trusted — each hop is a tamper-evident commitment to the delegation artifact that authorized it.

**What it does not do:** `delegation_chain_ref` does not validate that individual delegation artifacts are still in force (see [`revocation-ref.md`](./revocation-ref.md) for invalidation). It does not constrain scope narrowing between hops — that is the implementer's policy. It does not replace the individual `delegation_ref` fields carried in each hop's trail record.

---

## Derivation

`delegation_chain_ref` is `SHA-256(JCS(chain_artifact))` where:

- **JCS** is RFC 8785 canonical JSON: `json.dumps(obj, separators=(',',':'), sort_keys=True, ensure_ascii=False)`
- **SHA-256** lowercase hex
- `chain_artifact` must contain at minimum: `chain_id`, `hops`, `leaf_action_ref`, `root_delegator`, `scope`, `version`
- Each element of `hops` must contain: `delegatee`, `delegator`, `delegation_ref`, `scope`

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

chain_artifact = {
    "chain_id":       "chain_b1f4a2d7c9e3",
    "hops": [
        {"delegatee": "pioneer-agent-001", "delegator": "giskard-self",      "delegation_ref": "fc49ff73ebd629bd3440455115a4ce09e69219f2374f6b0c7a2713a52a579b7e", "scope": "mycelium:payment"},
        {"delegatee": "lightning",          "delegator": "pioneer-agent-001", "delegation_ref": "7243ad56d9b7d90200b0ad488150b00c6edea21a126cda0067573028f3ef73e9", "scope": "mycelium:payment"},
        {"delegatee": "soma-agent",         "delegator": "lightning",         "delegation_ref": "e471778fe440b4373251a32ef1e04388d0be7e51bcb341deb2cec27f1f146669", "scope": "mycelium:payment"},
    ],
    "leaf_action_ref": "ba524423fdc3d2c1366627f39e74c31934115480c82e1b59f0758daadbe4263c",
    "root_delegator":  "giskard-self",
    "scope":           "mycelium:payment",
    "version":         "delegation-chain-ref-v1",
}
delegation_chain_ref = hashlib.sha256(jcs(chain_artifact).encode()).hexdigest()
# 453529e323616b344fef58c203ea9bb0caae79954661d3d344fa1b4707457197
```

---

## Fields

### chain_artifact

| Field | Type | Description |
|-------|------|-------------|
| `chain_id` | string | Client-generated unique identifier for this chain instance. |
| `hops` | array | Ordered list of delegation hops, root→leaf. **Order is semantic, not incidental**: `hops` encodes the chain of custody itself, not a sortable collection of equivalent entries. JCS canonicalizes object *keys* within each hop, never array *element* order — two chain artifacts with the same hop objects in different array order are different documents and MUST produce different `delegation_chain_ref` digests. A verifier or implementer MUST NOT sort `hops` before hashing under any circumstance. See hop fields below. |
| `leaf_action_ref` | SHA-256 hex | `action_ref` of the final action executed by `hops[-1].delegatee`. Derived per [`action-ref.md`](./action-ref.md). |
| `root_delegator` | string | The origin of the chain. Must equal `hops[0].delegator`. |
| `scope` | string | Top-level scope for the chain. Must match `hops[0].scope`. |
| `version` | string | Always `"delegation-chain-ref-v1"` for this spec version. |

### hop object

| Field | Type | Description |
|-------|------|-------------|
| `delegatee` | string | Agent that received this delegation. Must equal `hops[i+1].delegator` for all non-leaf hops. |
| `delegator` | string | Agent that granted this delegation. Must equal `hops[i-1].delegatee` for all non-root hops. |
| `delegation_ref` | SHA-256 hex | Hash of the delegation artifact for this hop, derived per [`delegation-ref.md`](./delegation-ref.md). |
| `scope` | string | Scope of this hop. Implementers SHOULD verify it is equal to or a subset of the parent hop's scope. |
| `hop_signature` | base64 (optional) | Ed25519 signature by `delegator` over the UTF-8 bytes of this hop's `delegation_ref`. Additive field — omitting it does not change conformance of a chain that predates it (see "Cross-org attenuation" below). |

---

## Chain linkage via parent_delegation_ref

Individual delegation artifacts in a chain SHOULD include a `parent_delegation_ref` field pointing to the preceding hop's `delegation_ref`. This is not required by the chain_artifact schema — the chain artifact itself encodes ordering via the `hops` array — but `parent_delegation_ref` in each artifact creates an independent linked-list structure that a verifier can traverse without the chain artifact:

```
hop1_artifact.delegation_ref  ←──────────────────────────────  (root, no parent)
hop2_artifact.parent_delegation_ref = hop1_artifact.delegation_ref
hop3_artifact.parent_delegation_ref = hop2_artifact.delegation_ref
```

A verifier with only `leaf_action_ref` and the hop3 delegation artifact can walk backward to the root by following `parent_delegation_ref` at each step. `delegation_chain_ref` provides forward traversal (root→leaf) in a single hash; `parent_delegation_ref` provides backward traversal (leaf→root) without the chain artifact.

---

## Invariants

**1. chain continuity**

For all `i` from 0 to `len(hops)-2`: `hops[i].delegatee == hops[i+1].delegator`. A verifier who finds a break in this chain MUST reject it as non-conformant.

**2. root anchoring**

`root_delegator == hops[0].delegator`. The chain artifact commits to who started the chain.

**3. leaf anchoring**

`leaf_action_ref` is the `action_ref` derived from the leaf agent's action preimage. It connects the authorization chain to the specific action that was taken. A verifier can independently derive `leaf_action_ref` from the four preimage fields and compare.

**4. envelope-only — does not enter action_ref preimage**

`delegation_chain_ref` is carried in the trail envelope. It never enters the four-field preimage (`action_type`, `agent_id`, `scope`, `timestamp`).

**5. hops are append-only**

`delegation_chain_ref` commits to a specific chain snapshot. If the chain is extended by another hop, a new chain artifact is created with a new `chain_id`. The original chain artifact is not mutated.

**6. minimum chain length is two hops**

A single delegation is expressed as `delegation_ref` per [`delegation-ref.md`](./delegation-ref.md). `delegation_chain_ref` is for chains of two or more hops.

---

## Critical negative case

**HOPS_REORDERED** — two chain artifacts carry the identical set of hop
objects (same `delegatee`/`delegator`/`delegation_ref`/`scope` values) but in
different array order. JCS sorts object keys, not array elements, so the two
`hops` arrays serialize to different byte sequences and produce different
`delegation_chain_ref` digests — **by design**. This is not a determinism bug:
`hops` order *is* the claimed chain of custody (root→leaf), so a reordering
that still passes invariant 1 (chain continuity checked pairwise) would
silently assert a different delegation path than the one that actually
occurred, even though the set of hop objects is identical. A verifier MUST
treat two artifacts differing only in `hops` order as two distinct, unrelated
`delegation_chain_ref` values — never as equivalent representations of the
same chain. See `chain-002-hops-reordered-negative` in the conformance
fixture for a byte-level demonstration (same three hop objects as
`chain-001-three-hop-payment-route`, hop 0 and hop 1 swapped, digest
differs).

---

## Cross-org attenuation via hop_signature (additive, optional)

`chain_continuity` (invariant 1) only proves that the claimed `delegatee`/`delegator`
strings line up — it says nothing about who actually authorized a hop when the parties
are independent organizations with no shared authority. `hop_signature` closes that gap:
each hop's `delegator` signs the UTF-8 bytes of that hop's `delegation_ref` with an
Ed25519 keypair, and a verifier checks the signature against the delegator's known
public key before treating the hop as attenuated rather than merely claimed.

- **Optional and additive.** A hop without `hop_signature` conforms exactly as before —
  this field was not part of `delegation-chain-ref-v1.0` (tag, 2026-05-26) and every
  existing conformant chain artifact, including the canonical fixture in this document
  and `docs/spec/fixtures/delegation-chain-ref-v1.fixture.json`, produces the same
  `delegation_chain_ref` digest with or without this section — the field only enters the
  hash for artifacts that include it, which are new artifacts by definition.
- **Required for a cross-org claim.** A chain where hops span independent
  organizations (no shared signing authority between `delegator` values) MUST carry a
  valid `hop_signature` on every hop to be treated as verified rather than merely
  claimed continuity. Same-operator chains (e.g. this spec's own root example, where
  giskard-self/pioneer-agent-001/lightning share an operator) are conformant without it.
- **Failure mode `hop_signature_invalid`.** A hop signature that does not verify against
  its claimed `delegator`'s public key — including a valid signature copied from a
  different hop (`signature_substitution`) — MUST be rejected. See
  `cross-org-neg-signature-substitution` in
  `examples/conformance/delegation-chain-ref/cross-org-vectors.json` for a case where
  chain continuity, root/leaf anchoring and scope narrowing all still pass, and only the
  signature check catches the forgery.
- **Key resolution is implementer-defined.** This spec does not mandate a registry; the
  conformance fixture is self-contained (embeds a `pubkeys` map) so it verifies offline
  without depending on a live key-registry service. A production verifier may resolve
  keys however it already does for signed artifacts in its system (e.g. a pubkey
  registry with historical epoch resolution).

---

## Replay guard (additive, optional)

`delegation_chain_ref` and `hop.delegation_ref` are content-addressed hashes, not
single-use tokens by themselves — nothing in the base invariants stops a chain that was
already accepted from being resubmitted to claim the same authorization a second time.
A conformant verifier SHOULD track `chain_id` and every hop's `delegation_ref` it has
already accepted, and reject a resubmission of either as `replay_detected`, even when
the resubmitted artifact is byte-identical and would otherwise pass every other
invariant. See `examples/conformance/delegation-chain-ref/replay-vectors.json`
(`replay-001-first-submission` PASS, `replay-002-resubmission-same-chain-id` FAIL —
vectors run in order, registry state carries across the file). Same additive pattern as
`hop_signature`: a verifier without replay tracking is not non-conformant for chains it
has never seen before, but MUST NOT claim replay protection unless it holds this state.

---

## Position in the envelope

`delegation_chain_ref` is carried at the envelope level of the leaf agent's trail record — the record that commits the final action:

```json
{
  "packet_version":        "1.0",
  "action_ref":            "<leaf_action_ref>",
  "delegation_ref":        "<hop N delegation_ref — the leaf's direct delegation>",
  "delegation_chain_ref":  "<sha256 hex — derived from chain_artifact>",
  "hash_algo":             "sha256",
  "preimage_format":       "jcs-rfc8785-v1",
  "preimage": {
    "action_type": "payment.route",
    "agent_id":    "soma-agent",
    "scope":       "mycelium:payment",
    "timestamp":   "2026-05-26T20:00:00.000Z"
  }
}
```

The leaf record carries both its direct `delegation_ref` (the authorization from its immediate parent) and `delegation_chain_ref` (the full chain from root to leaf). Intermediate hop records carry only their own `delegation_ref`.

---

## Relationship to composition-ref

| Ref | What it answers |
|-----|----------------|
| `delegation_ref` | Who authorized this single hop, under what policy? |
| `delegation_chain_ref` | Is the full authorization chain from root to leaf valid? |
| `composition_ref` | Did delegation + revocation + dual-timestamps compose correctly for one action? |

`delegation_chain_ref` and `composition_ref` are complementary. A leaf action in a multi-hop chain may carry both: `delegation_chain_ref` for chain integrity and `composition_ref` for lifecycle completeness at the leaf hop.

---

## Cross-references

- `action_ref` derivation: [`docs/spec/action-ref.md`](./action-ref.md)
- `delegation_ref` (per-hop primitive): [`docs/spec/delegation-ref.md`](./delegation-ref.md)
- `revocation_ref` (per-hop invalidation): [`docs/spec/revocation-ref.md`](./revocation-ref.md)
- `composition_ref` (lifecycle composition at leaf): [`docs/spec/composition-ref.md`](./composition-ref.md)
- TrailRecord schema: [`docs/MYCELIUM_TRAILS_REFERENCE.md`](../MYCELIUM_TRAILS_REFERENCE.md)
