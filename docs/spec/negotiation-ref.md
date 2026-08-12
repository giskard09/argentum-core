# negotiation-ref-v1 — Specification

**Stable tag:** `negotiation-ref-v1.0`  
**Status:** stable  
**Canonical fixture:** [`docs/spec/fixtures/negotiation-composition-v1.json`](./fixtures/negotiation-composition-v1.json)

---

## What is negotiation-ref

`negotiation_ref` is a SHA-256 hex pointer to a negotiation artifact that preceded an action. It enables a verifier to establish that an action was admitted under a specific prior agreement, capability-grant, or covenant — without embedding the artifact itself in the trail record.

**What it points to:** any structured document representing a prior agreement between two agents. In the minimal form, a capability-grant JSON object (see fixture). In richer forms: a covenant, a signed authorization envelope, or a multi-round protocol summary.

**What it does not do:** `negotiation_ref` is opaque to Mycelium. The system stores the hash verbatim and does not fetch, parse, or validate the referenced document. Verification of the artifact itself is the responsibility of the querying party.

---

## Derivation

`negotiation_ref` is `SHA-256(JCS(negotiation_artifact))` where:

- **JCS** is RFC 8785 canonical JSON: `json.dumps(obj, separators=(',',':'), sort_keys=True, ensure_ascii=False)`
- **SHA-256** lowercase hex
- `negotiation_artifact` is any JSON object — the spec imposes no schema on its fields

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

negotiation_artifact = {
    "capability": "delegation.execute",
    "expires_at": "2026-05-27T00:00:00.000Z",
    "grantee":    "pioneer-agent-001",
    "grantor":    "giskard-self",
    "scope":      "mycelium:delegation",
    "version":    "negotiation-ref-v1",
}
negotiation_ref = hashlib.sha256(jcs(negotiation_artifact).encode()).hexdigest()
# a0e8bc2658eee9266d87d56b205a5f01e5b1ecc445f0693b3bba46cb8764ad52
```

Five lines. Any RFC 8785-conformant implementation produces the same hash byte-identical.

---

## Invariants

**1. envelope-only — does not enter action_ref preimage**

`negotiation_ref` is carried in the trail envelope. It is never included in the four-field preimage that determines `action_ref`. Changing or removing `negotiation_ref` does not change `action_ref`.

The four preimage fields are: `action_type`, `agent_id`, `scope`, `timestamp`. See [`action-ref.md`](./action-ref.md).

**2. hash is over the artifact, not the envelope**

`negotiation_ref = SHA-256(JCS(negotiation_artifact))` — the hash commits to the artifact document, not to any trail record field. A verifier who has the original artifact can reproduce the hash independently.

**3. opaque to Mycelium**

Mycelium stores `negotiation_ref` verbatim as a `TEXT` field. The system applies no schema validation, no fetch, and no cross-reference check against the artifact. The field is a pointer, not a verified link.

**4. optional**

`negotiation_ref` is `null` when not supplied. Its presence signals that an upstream agreement exists; its absence makes no claim about whether one exists or not.

---

## Pattern: `policy_commitment` for policy/rubric-based artifacts

**2026-08-12:** documented after reviewing babyblueviper1's ERC-8299 reference
implementation (`ethereum/ERCs#1810`), which found that a bare `policy_version`
string (e.g. `"invinoveritas.review.v9"`) is a label, not a pin — a verifier has
to trust the producer's later account of what that version meant, since the
string itself isn't recomputable against anything.

`negotiation_ref` already avoids this class of gap by construction: it hashes
whatever `negotiation_artifact` object is supplied, with no schema imposed, so
nothing stops a producer from including a recomputable commitment instead of a
bare label. This section makes that pattern explicit rather than leaving it
implicit in "any JSON object."

When `negotiation_artifact` represents a policy- or rubric-based authorization
(as opposed to a simple capability-grant), include a `policy_commitment` field
alongside — not replacing — `policy_version`:

```python
policy_commitment = SHA256(JCS({
    "policy_version":          "<string>",
    "rubric_sha256":           "<sha256 hex of the rubric text>",
    "conformance_suite_repo":  "<string>",
    "conformance_suite_commit": "<string>",
}))
```

`policy_version` stays useful as a human-readable label. `policy_commitment` is
what a stranger actually recomputes: fetch the rubric text and conformance
vectors at the pinned commit, hash them the same way, and confirm the producer's
later claim about what the policy said at that version is the same thing they
committed to at negotiation time — independent of the producer's word.

This is documentation only. No change to the derivation, no new required field,
no effect on any existing `negotiation_ref` hash — a `negotiation_artifact`
without `policy_commitment` remains fully conformant; the field is a recommended
convention for a specific artifact shape, not a spec requirement.

---

## Position in the envelope

```json
{
  "packet_version": "1.0",
  "action_ref":      "<sha256 hex — derived from preimage>",
  "negotiation_ref": "<sha256 hex — derived from negotiation_artifact>",
  "hash_algo":       "sha256",
  "preimage_format": "jcs-rfc8785-v1",
  "preimage": {
    "action_type": "delegation.execute",
    "agent_id":    "pioneer-agent-001",
    "scope":       "mycelium:delegation",
    "timestamp":   "2026-05-24T09:00:00.000Z"
  }
}
```

`negotiation_ref` sits alongside `action_ref` in the envelope. It is a sibling field — not nested inside `preimage`.

---

## Cross-references

- `action_ref` derivation: [`docs/spec/action-ref.md`](./action-ref.md)
- TrailRecord schema: [`docs/MYCELIUM_TRAILS_REFERENCE.md`](../MYCELIUM_TRAILS_REFERENCE.md)
- Conformance fixtures: [`examples/conformance/`](../../examples/conformance/)
