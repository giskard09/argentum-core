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

**5. the absent/present distinction MUST surface in the verifier's output**

Invariant 4 is a guarantee about the field's semantics, not about what a verifier reports. A verifier implementation MUST expose whether `negotiation_ref` was absent or present as an explicit output field — not leave the distinction implicit in "the key is missing from the JSON" or in operator knowledge of the spec. Reference implementation: `mycelium_trails.verify_chain()` returns `negotiation_linkage: "absent" | "present" | "malformed" | None`. `"present"` means the field was supplied with a non-empty value, not that the referenced artifact was verified — see invariant 3. `"malformed"` means the field was supplied but empty (`""`) — distinct from `"absent"` (field was never set). `None` means the trail record itself was never read (target lookup failed) — the verifier has no basis to claim anything about the field, so it MUST NOT report `"absent"`, which would falsely assert "I read the record and the field was missing."

(2026-08-14, credit: Henri Sirkkavaara / draft-sirkkavaara-vaara-receipt, scitt@ietf.org thread on draft-fassbender-scitt-time-anchor-03 — the same absent-vs-unverified distinction argued there for time-anchor receipts applies directly to negotiation_ref. 2026-08-16, credit: Aleksei Chirkunov, scitt@ietf.org, same thread — found that the reference implementation collapsed "record never read" and "field supplied but empty" into the same `"absent"` value, losing both distinctions. Fixed in `mycelium_trails.py`, tests in `tests/test_negotiation_linkage_status.py`.)

---

## `verify_chain()` — `reason` partition: unreached vs. ran-and-failed

**2026-08-16:** `verify_chain()`'s `valid` field is binary (`True`/`False`). Henri
Sirkkavaara (scitt@ietf.org, 2026-08-16) asked whether that collapses two
distinct situations that his own grader keeps separate (`pass`/`fail`/`unproved`):
a check that ran and produced a negative result, versus a check that could
never be reached in the first place — specifically naming
`missing_signature_ref` as a case he couldn't tell apart from outside the code
("checked but absent" — legitimate finding, or a failure to even obtain the
record to check?).

Rather than a breaking change to `verify_chain()`'s return contract (adding a
third state to `valid`, or a new top-level field every existing caller would
need to learn), the fix is additive and reader-compatible: document that the
`reason` strings `verify_chain()` already returns partition cleanly into the
two categories Henri distinguishes. Nobody reading `valid: False` today loses
anything — this makes explicit a property the implementation already has, it
does not add one.

**Why the partition is clean:** `get_trail_by_id()` is binary by construction
— SQLite has no partial-column read, so it returns `None` or a fully-populated
dict, never a partial record. In `verify_chain()`, the `trail_not_found` check
runs first, on the raw result of `get_trail_by_id()`, and returns immediately
if it's `None`. Every other `reason` below it evaluates fields (`signature_ref`,
`delegation_ref`, `parent_trail_id`) on a record that has already been read in
full — there is no code path where one of those fields is checked without the
whole row being in memory first.

| `reason` | Category | Why |
|---|---|---|
| `trail_not_found` | **unreached** | `get_trail_by_id()` returned `None` — the record was never obtained, so nothing about it (signature, delegation, cycle) could be evaluated at all. |
| `missing_signature_ref` | **ran-and-failed** | The record was read in full; `signature_ref` was checked and found empty. A definitive negative answer, not a missing check — this is the case Henri asked about explicitly. |
| `delegation_ref_parent_mismatch` | **ran-and-failed** | Two records (current and parent) were both read and compared; they don't agree. |
| `cycle_detected` | **ran-and-failed** | A structural finding over records already read — the repeated `trail_id` was necessarily fetched and visited before being detected as a repeat. |

Reference implementation: `mycelium_trails.verify_chain()` — see the docstring
above each `return` for the same partition inline in the code. This is
documentation only; `verify_chain()`'s logic, signature, and return contract
are unchanged. Whether to add a third state to `valid` (or an `unreached`
boolean) is a separate design decision, evaluated later if at all — not made
here.

Credit: Henri Sirkkavaara proposed the additive-partition approach over a
breaking third state, scitt@ietf.org, 2026-08-16.

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
