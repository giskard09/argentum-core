# action_ref — derivation spec

**Version:** 1.2 | **Published:** 2026-05-23 | **Updated:** 2026-06-03 (×2), 2026-07-29 (version negotiation, Domain enforcement) | **Stable ref (v1):** [`action-ref-v1.0`](https://github.com/giskard09/argentum-core/blob/action-ref-v1.0/docs/spec/action-ref.md) | **Stable ref (v2, domain separation):** [`action-ref-v2.0`](https://github.com/giskard09/argentum-core/blob/action-ref-v2.0/docs/spec/action-ref.md) | **Latest commit:** [96931c9](https://github.com/giskard09/argentum-core/commit/96931c9)

**2026-08-16:** ASCII-only Domain enforcement (2026-07-29, above) closes Unicode
normalization ambiguity (NFC vs. NFD) by design for this canonical profile — NFC and
NFD only diverge on non-ASCII code points, and any non-ASCII value in `agent_id`,
`action_type`, or `scope` is already rejected with `OUT_OF_PROFILE_DOMAIN` before
hashing, so the two forms can never reach the preimage differently. This is an
intentional consequence of the ASCII-only Domain, not a gap pending a fix — see the
Domain paragraph below. Flagged for verification by Henri Sirkkavaara (SCITT list,
2026-08-16, general NFC/NFD-before-JCS point raised in an unrelated ARP/Certisyn
thread). Separately, the community plugin
[`mycelium_evidence_anchor.py`](../../mycelium_evidence_anchor.py) computes its own
domain-separated hash (`mycelium-evidence-anchor:v1:` prefix, distinct hash space, no
production adopters) without this repo's ASCII-only Domain restriction — there,
NFC/NFD divergence was a real gap, closed by normalizing `agent_id`/`action_type`/
`scope` to NFC before hashing (unrelated to and does not change this canonical
`action_ref` profile).

**2026-07-30:** Tagged `action-ref-v2.0` — gate condition met, the two production
adopters (SafeAgent/azender1, CTEF/kenneives) were briefed on the domain-separation
gap by email the same day. v1 (bare 64-hex) is untouched and permanently valid; v2 is
strictly additive per [RFC 002](../rfcs/002-action-ref-v2-domain-separation.md).

**2026-08-15:** `scope` empty-string exception removed (issue #48) — **reverses** the
2026-07-29 wording fix below, it does not merely restate it. Field table and
`plugins/agt_evidence_anchor/action_ref.py::_validate_domain` changed so an empty
`scope` is rejected with `OUT_OF_PROFILE_DOMAIN` before hashing, aligning the local
spec with the published I-D `draft-etcheverry-action-ref-02` §6 ("free-form non-empty
string... no exception") — the externally-committed document, so the local spec was
corrected to match it rather than the reverse. Retroactive check against production
`trails.db`: 3881 total trails, 4 with empty/null scope, none via `/nexus/trail` (the
endpoint that validates this rule) — zero existing data affected. The "Scope
conventions" section further down still referenced the removed `""` exception until
2026-08-25 (found by aeoess/Pidlisnyi in
[`draft-etcheverry-action-ref#6`](https://github.com/giskard09/draft-etcheverry-action-ref/issues/6),
corrected the same day — see next entry).

**2026-07-29:** `compute_action_ref`/`compute_action_ref_v2` in the reference implementation now enforce the Domain paragraph below before hashing (previously they hashed any input). Also fixed a wording conflict in the `scope` field table ("non-empty" vs. "pass `\"\"` if not applicable") — resolved at the time in favor of **allowing** `""`; that resolution was itself reversed on 2026-08-15, above. Both issues reported by aeoess (Pidlisnyi) in [#35](https://github.com/giskard09/argentum-core/issues/35). See [`examples/conformance/action-ref-v1-domain-negative/`](../../examples/conformance/action-ref-v1-domain-negative/) for the rejection vectors.

`action_ref` is a deterministic, content-addressed identifier for an agent action. Any party with the four preimage fields can independently compute it — no trust in the emitting system required.

## Derivation

```python
import hashlib
import json

def compute_action_ref(
    agent_id: str,
    action_type: str,
    scope: str,
    timestamp: str,   # RFC 3339 UTC, 3-digit ms precision: "2026-05-15T10:00:00.123Z"
) -> str:
    payload = {
        "agent_id": agent_id,
        "action_type": action_type,
        "scope": scope,
        "timestamp": timestamp,
    }
    # JCS (RFC 8785): lexicographic key order, no spaces, UTF-8
    canonical = json.dumps(
        dict(sorted(payload.items())),
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
```

**Domain:** the `json.dumps` approach above produces RFC 8785-compatible bytes for the specific input shapes this spec exercises: ASCII-only field values, RFC 3339 timestamp strings in the conformant `YYYY-MM-DDTHH:MM:SS.mmmZ` form (see [Timestamp format](#timestamp-format)), no surrogate-pair Unicode, no `-0.0`. This is the profile's full domain, not a convenience subset — there is no "use a compliant library instead" fallback. A preimage outside this domain (non-ASCII agent identifiers, surrogate-pair scope strings, malformed timestamp grammar, duplicate preimage keys) is not canonicalized by best effort or delegated to a different implementation's number/string handling; the verifier MUST return `OUT_OF_PROFILE_DOMAIN` and stop before any digest comparison — the same pattern already used for `UNSUPPORTED_CANONICAL_PROFILE`. One pinned behavior per profile, never a disjunction between "this path or, failing that, some other path."

Reference implementation: [`plugins/agt_evidence_anchor/action_ref.py`](../../plugins/agt_evidence_anchor/action_ref.py)

## Version negotiation

The derivation above (bare `SHA-256(JCS(preimage))`, no prefix) is **v1**. It has no domain
tag: the raw JCS bytes of the four canonical fields are hashed directly. This means any
other protocol that independently arrives at the same four-field shape and SHA-256 would
produce a colliding reference — a general risk named in an AEOESS comment on
[a2aproject/A2A#2028](https://github.com/a2aproject/A2A/discussions/2028) (not directed at
this spec specifically, but it applies to this preimage exactly as described).

**v1 is not deprecated and never will be retired.** Every `action_ref` computed under v1
— including every hash already anchored on-chain by v1.0-era adopters — remains permanently
valid and permanently verifiable. This section adds a second derivation (v2) alongside v1;
it does not replace or narrow v1's guarantees.

### Distinguishing v1 from v2 — the hash string itself carries the version

A verifier MUST NOT guess which derivation produced a given `action_ref` string. The
version marker is the hash string's own syntax, so no companion field or side-channel
lookup is required:

- **v1**: a bare 64-character lowercase hex string (unchanged from the original spec).
  Example: `fdd7f810499f06be24355ca8e2bfb8c4b965cc80c838f41fa074683443d89f5a`
- **v2**: the literal prefix `v2:` followed by a 64-character lowercase hex string.
  Example: `v2:1a2b3c4d...` (64 hex chars after the prefix)

A verifier reads the string up to the first `:` (or its absence) to determine which
derivation to apply, then recomputes and compares. The two forms are syntactically
disjoint — a v1 hash is never a valid prefix-of or confusable with a `v2:`-prefixed
string, so there is no parsing ambiguity.

This is a prefix on the **hash string**, not an extra field in the preimage object and
not a sibling field in the record. Anything that already persists `action_ref` as a bare
string — including this repo's own `trails.db` — needs no schema migration to support v2
alongside v1: a v2 value is simply a longer string in the same column.

### v2 derivation

```python
import hashlib
import json

V2_DOMAIN_TAG = "mycelium.action-ref:v2:"

def compute_action_ref_v2(
    agent_id: str,
    action_type: str,
    scope: str,
    timestamp: str,   # RFC 3339 UTC, 3-digit ms precision — same format as v1
) -> str:
    payload = {
        "agent_id": agent_id,
        "action_type": action_type,
        "scope": scope,
        "timestamp": timestamp,
    }
    canonical = json.dumps(
        dict(sorted(payload.items())),
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    digest = hashlib.sha256(V2_DOMAIN_TAG.encode("utf-8") + canonical).hexdigest()
    return f"v2:{digest}"
```

The four preimage fields, their types, and the JCS canonicalization rules are **identical
to v1** — the only difference is that the domain tag `mycelium.action-ref:v2:` (ASCII
bytes, not itself part of the JCS object) is prepended to the canonical JSON bytes before
hashing, and the resulting hex digest is prefixed with `v2:` when stored or transmitted.

**Why a spec-named tag, not just a version number:** `"mycelium.action-ref:v2:"` names
this specific spec, not only "version 2 of something." The risk this closes is
cross-protocol collision — a different system's hash of the same four-field shape — not
only cross-version collision within this spec's own history. A version-only tag (e.g.
`"v2:"` prepended to the JCS bytes with no spec name) would still leave two *different*
specs that both adopt bare version-numbered domain tags free to collide with each other.

**Why the tag is a byte prefix and not a fifth JCS field:** keeping the preimage at
exactly four fields preserves the property adopters cite when explaining portability
(see `ADOPTERS.md`, AURA: "any downstream auditor can recompute `SHA-256(JCS(receipt
preimage))`") — the object shape a verifier canonicalizes is unchanged between v1 and v2;
only the bytes hashed alongside it differ.

### Conformance fixtures — v2

[`examples/conformance/action-ref-v2/`](../../examples/conformance/action-ref-v2/) —
vectors are **additive** to the existing v1 fixture set, not a replacement. A verifier
claiming v2 conformance MUST still pass all existing v1 vectors; dropping v1 support is
not a valid migration path.

### Adoption status

This section documents the mechanism only. No adopter has been asked to migrate, no new
git tag has been cut, and this repository's own production code has not switched default
emission to v2. Adoption sequencing (which adopters are briefed, in what order, before any
public v2 announcement) is tracked outside this spec document — see
[`docs/rfcs/002-action-ref-v2-domain-separation.md`](../rfcs/002-action-ref-v2-domain-separation.md).

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | string | Stable identifier for the **executing agent at issuance time** — the terminal executor after full delegation resolution. Not the original delegator; not a display label. In a chain A→B→C where C executes the action, `agent_id` is C. |
| `action_type` | string | What the agent did — semantic label (`code.execute`, `payment.send`, etc.) |
| `scope` | string | Terminal executing agent's requested-intent scope — what the agent requested to do at the point of action. Free-form non-empty string; see [Scope conventions](#scope-conventions). Any value is valid as long as it is non-empty and consistent across all parties deriving the same `action_ref`. |
| `timestamp` | string | RFC 3339 UTC with 3-digit millisecond precision. Format: `"2026-05-15T10:00:00.123Z"`. The trailing `Z` is mandatory. |

> **Conversion note:** The W3C CG ai-agent-protocol discussion (issue #34) established epoch-millisecond integer as the application-layer canonical representation for timestamp. The `action_ref` preimage carries an RFC 3339 string, not the integer. Implementations holding epoch-ms integers MUST convert to RFC 3339 UTC with three-digit millisecond precision before hashing. Implementations that hash the epoch-ms integer directly (without conversion) will produce a different digest and are not conformant with this spec.

## Boundary — what this proves, and what it does not

`action_ref` proves that the four preimage fields hash consistently: any party holding
`agent_id`/`action_type`/`scope`/`timestamp` can recompute the same digest, so the value
was not silently altered after issuance. It does not prove that these fields correspond
to what the agent's runtime actually did. In the reference implementation
([`plugins/agt_evidence_anchor/anchor.py`](../../plugins/agt_evidence_anchor/anchor.py)),
`agent_id`/`action_type`/`scope` are caller-supplied at the call site — `timestamp` is
generated by the anchoring function itself, but the other three are exactly what the
calling code declares them to be. A correctly-formed, byte-verifiable `action_ref` can
still describe the wrong action if the emitting system populated the preimage
dishonestly or by mistake — same shape as the "right-shape coordinate, correct hashes,
wrong object" seam identified independently by babyblueviper1 (Fede) across
`internet-court/internet-court-skill#16` and `microsoft/agent-governance-toolkit#3805`,
2026-08-24: a re-derivation can be fully sound and still be re-deriving the wrong
thing, because the party being verified chose the coordinate.

This is not a gap this spec closes, by design: binding the declared preimage to an
independently-observable effect (an on-chain receipt, a signed external attestation,
etc.) is a *sibling* concern, not a member of this fixed point — the same
sibling-not-member composition already used in
[`composed-attestation-3leg-worked-example`](https://github.com/giskard09/composed-attestation-3leg-worked-example).
Folding effect-binding into the four-field preimage would tie a chain-agnostic
identifier to one particular binding mechanism (a specific chain's receipt shape,
an attestation format, etc.) and duplicate work better done by a purpose-built
sibling ref. `action_ref` answers "was this the action that was authorized/declared,
unaltered since issuance" — it does not and should not answer "did the declared
fields match an independently observable effect." See
[decision-binding-ref-v1.0.md](decision-binding-ref-v1.0.md) for the same boundary
stated for `decision_binding_ref` ("proves content without proving intent").

## Scope conventions

`scope` is a free-form non-empty string with no closed enum. Any value is valid as long as it is non-empty and consistent across all parties deriving the same `action_ref`. There is no `""` (not applicable) exception — an empty `scope` is rejected with `OUT_OF_PROFILE_DOMAIN` before any digest comparison, same as the other domain checks (see [`plugins/agt_evidence_anchor/action_ref.py`](../../plugins/agt_evidence_anchor/action_ref.py)).

**Recommended convention (non-normative):** namespace-prefix with the emitter identifier using `<emitter>:<scope>`.

```
algovoi:compliance_screen
vauban:stark_settlement
agent_os:committed_claim
aura:reputation_observe
```

These examples are verified in production trails anchored on-chain via Mycelium.

**Rationale:** different emitters may independently choose the same scope string (`audit`, `settlement`, `signal`) with semantically distinct meanings. Prefixing avoids collisions when trails from multiple emitters are verified or aggregated by a third party.

**Conformance note — scope anti-pattern:** `scope` captures the terminal executing agent's requested-intent at the point of action — a human-readable label, not a derived hash. A common mistake is to hash the initial intent object and use that hash as the scope value. This breaks the primary verifiability property of `action_ref`: any party holding the four preimage fields must be able to recompute it independently, without retrieving any external record. With a hashed scope, a verifier cannot recompute `action_ref` from the intent tuple alone — they must also retrieve the commitment record to recover the pre-hash value. The correct value is the intent label itself (e.g., `"trade:execute:authorized"`, `"aura:reputation_observe"`), not a digest of the document that describes it.

Emitters that do not namespace their scope remain valid — the convention is a recommendation, not a requirement. A verifier MUST NOT reject a trail solely because its `scope` lacks a namespace prefix.

**Conformance rule — multi-value scope segments:** when a scope segment encodes a set of values (e.g. entity types detected by a screening decision), implementations MUST sort those values lexicographically and join them with a comma and no spaces before embedding in the scope string. This rule ensures byte-determinism across implementations that may produce values in detection order, which is not guaranteed stable.

Example (PII screening):
```
presidio:x402.screen:PII_REDACTED:EMAIL_ADDRESS,US_SSN   ← correct (E < U)
presidio:x402.screen:PII_REDACTED:US_SSN,EMAIL_ADDRESS   ← non-conformant
presidio:x402.screen:clean-allow                          ← correct (no entity segment when set is empty)
```

Two implementations that produce the same entity set in different detection orders MUST both produce the same scope string after applying this rule, and therefore the same `action_ref`.

## Serialization — JCS (RFC 8785)

The four fields are serialized as a JSON object using RFC 8785 JSON Canonicalization Scheme before hashing:

- Keys in lexicographic UTF-16 code unit order (RFC 8785 §3.2.3, equivalent to `Array.prototype.sort()` in JS — not Unicode code point order, which only diverges for astral-plane keys; the four keys here are ASCII so both orderings coincide): `action_type`, `agent_id`, `scope`, `timestamp`
- No whitespace between tokens
- UTF-8 encoded
- Values are JSON strings (no additional escaping beyond standard JSON)

**Example — NEXUS oracle signal:**

```
Input:
  agent_id    = "nexus-agent-xa12.onrender.com"
  action_type = "oracle.signal"
  scope       = "BTC"
  timestamp   = "2025-05-18T11:40:31.000Z"

JCS payload:
  {"action_type":"oracle.signal","agent_id":"nexus-agent-xa12.onrender.com","scope":"BTC","timestamp":"2025-05-18T11:40:31.000Z"}

action_ref:
  fdd7f810499f06be24355ca8e2bfb8c4b965cc80c838f41fa074683443d89f5a
```

## Timestamp format

`timestamp` is the moment the action was claimed (before execution), expressed as RFC 3339 UTC with exactly 3 millisecond digits:

```python
import datetime

def format_timestamp(dt: datetime.datetime) -> str:
    ms = dt.microsecond // 1000
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S.{ms:03d}Z")

# From Unix seconds (no sub-second data):
ts = format_timestamp(datetime.datetime.fromtimestamp(1747568431, tz=datetime.timezone.utc))
# → "2025-05-18T11:40:31.000Z"
```

**JCS determinism:** RFC 3339 without additional constraints admits multiple lexically distinct encodings of the same instant (`Z` vs `+00:00`, `.000` vs no fractional part, etc.), each producing a different SHA-256 digest under JCS RFC 8785. This spec closes that surface at the format level, not the serializer level:

- Timezone: `Z` suffix only. `+00:00` or any other offset is non-conformant.
- Fractional precision: exactly 3 digits (milliseconds). No trailing zero suppression.
- Template: `YYYY-MM-DDTHH:MM:SS.mmmZ` — one valid byte sequence per instant.

A verifier that accepts alternative RFC 3339 forms will compute a different digest and correctly reject the receipt. An emitter generating non-conformant timestamps produces an unverifiable receipt. The `format_timestamp` function above is the normative reference for conformant emission.

**Interoperability note:** implementations using epoch-millisecond integers as an internal representation can convert to the conformant string format losslessly: `datetime.fromtimestamp(ms / 1000, tz=timezone.utc)` followed by `format_timestamp`. The canonical preimage always contains the string form.

## Canonical receipt envelope — v1.0

Implementations that emit a receipt referencing this spec SHOULD include the following fields to ensure long-lived verifiability:

```json
{
  "packet_version": "1.0",
  "action_ref": "<sha256 hex>",
  "hash_algo": "sha256",
  "preimage_format": "jcs-rfc8785-v1",
  "preimage": {
    "agent_id": "...",
    "action_type": "...",
    "scope": "...",
    "timestamp": "2026-05-15T10:00:00.123Z"
  }
}
```

**Why these fields matter:**

- `packet_version` — forward-compat anchor. v1 verifiers can explicitly reject unknown versions rather than fail silently.
- `hash_algo` — makes receipts self-describing. If a future implementation switches to BLAKE3 or keccak256, receipts issued before the change remain replayable.
- `preimage_format: "jcs-rfc8785"` — unambiguously identifies the serialization. Any verifier can recompute the action_ref from the preimage fields using RFC 8785 without trusting the emitter.

## Gap — revocation and policy rotation

The canonical receipt envelope v1.0 records the state at the moment the action was claimed.
It does not record whether that state was still valid when the action was **admitted for
execution** — which may be later.

Two failure modes this gap creates:

1. **Trust tier degradation** — an agent moves from TRUSTED to WATCH between claim and
   execution. The anchor records the claim-time state. A verifier replaying the receipt
   cannot determine from the receipt alone whether the agent was still trusted when the
   action was admitted.

2. **Policy rotation** — the counterparty policy changes between issuance and execution.
   `counterparty_policy_hash` (if present) proves *which* policy was referenced at claim
   time. It does not prove whether that policy was still current when the action was
   admitted.

Both conditions require the receipt to carry additional fields to remain auditable after
the fact.

### Two fields that close this gap

**`policy_version`** (string, optional) — identifies which version of the governing policy
was in force when the action was admitted. Distinct from `counterparty_policy_hash`, which
proves *which* policy was referenced — `policy_version` proves *whether it was still
current* at execution time. A verifier replaying the receipt after a policy rotation can
use this field to establish that the admitted policy was not superseded before execution.

**`authority_verified_at_ms`** (integer, optional) — Unix timestamp in milliseconds at
which the delegation authority was verified at issuance. This is the issuance-side anchor:
it records when the acting agent's authority was confirmed before the action was admitted.
A year-5 supervisor re-verifying a receipt can use this field to establish the issuance
boundary independently of the execution-time check.

**`revocation_check_at_ms`** (integer, optional) — Unix timestamp in milliseconds of the
last non-revocation check performed before execution. A receipt without this field cannot
prove the agent's credentials were valid immediately before the action was admitted — only
that they were valid at claim time. With this field, a verifier can establish a maximum
window of credential exposure.

**`negotiation_ref`** (string, optional) — SHA-256 hex pointer to the negotiation artifact
(capability-grant, covenant, or agreement) that authorized this action. Derived as
`SHA-256(JCS(negotiation_artifact))` — see [`negotiation-ref.md`](./negotiation-ref.md)
for the full spec and derivation. Does not enter the `action_ref` preimage: changing or
removing `negotiation_ref` does not change `action_ref`.

**`revocation_authority_ref`** (string, optional) — SHA-256 hex pointer identifying the
revocation authority consulted at check time. `revocation_check_at_ms` proves a
non-revocation check happened; it does not prove *against what*. A conformant receipt can
carry a fresh `revocation_check_at_ms` while pointing at a revocation registry that is
stale, unreachable, or compromised — same timestamp, same appearance of compliance, no
real guarantee. `revocation_authority_ref` closes that gap by binding the check to a
specific, independently identifiable authority.

Derived as `SHA-256(JCS(authority_descriptor))` where `authority_descriptor` contains at
minimum:

- `authority_type` — one of `"permissionless-registry"` (verifiable by any third party,
  e.g. an on-chain registry), `"private-endpoint"` (operator-controlled, verifiable only
  by trusting the operator), or `"third-party-oracle"` (external service, verifiable by
  querying that service independently).
- `authority_id` — canonical identifier of the authority. For a permissionless registry,
  the registry contract address. For a private endpoint, a stable hash of the endpoint
  (never the raw URL — see `feedback_outofband_nunca_inline` pattern: out-of-band values
  are never pasted inline in a public artifact).
- `version` — identifies the shape of `authority_descriptor` itself, so a future revision
  does not silently change what the pointer means.

Does not enter the `action_ref` preimage — same invariant as `negotiation_ref` and
`revocation_ref`: changing or adding `revocation_authority_ref` does not change
`action_ref`.

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

authority_descriptor = {
    "authority_type": "permissionless-registry",
    "authority_id":   "0x49fEcA52bC634a9Ab773226D16619deC547794aa",
    "version":        "revocation-authority-ref-v1",
}
revocation_authority_ref = hashlib.sha256(jcs(authority_descriptor).encode()).hexdigest()
# 6715df92abbc5adef5dce788e6b64d4fd280f16c6a077d4cf959be5f127a675b
```

Paired with `revocation_check_at_ms`, the two fields together answer "checked when,
against what" instead of just "checked when." A receipt with `revocation_check_at_ms`
but no `revocation_authority_ref` is auditable for timing but not for authority — a
verifier that requires both SHOULD treat a receipt missing `revocation_authority_ref` as
unauditable for authority provenance, not as invalid (same non-invalidating posture as
the other optional rotation fields).

### Updated canonical receipt envelope — v1.0 with optional rotation fields

```json
{
  "packet_version": "1.0",
  "action_ref": "<sha256 hex>",
  "hash_algo": "sha256",
  "preimage_format": "jcs-rfc8785-v1",
  "preimage": {
    "agent_id": "...",
    "action_type": "...",
    "scope": "...",
    "timestamp": "2026-05-15T10:00:00.123Z"
  },
  "policy_version": "2026-05-01",
  "authority_verified_at_ms": 1747568400000,
  "revocation_check_at_ms": 1747568431000,
  "revocation_authority_ref": "6715df92abbc5adef5dce788e6b64d4fd280f16c6a077d4cf959be5f127a675b"
}
```

Both fields are optional in v1.0. A verifier that requires post-rotation auditability
SHOULD treat a receipt missing either field as unauditable for the rotation window — not
as invalid.

**Why milliseconds for `revocation_check_at_ms`:** credential checks in live multi-agent
systems happen at sub-second granularity, and the gap between check and execution is often
under one second. A seconds-precision timestamp cannot distinguish "checked 800ms ago"
from "checked 1200ms ago" — a distinction that matters when the revocation window is
short. Systems that only have second-precision timestamps SHOULD multiply by 1000 and
document the precision loss in the receipt.

---

## authorization_ref — Decision record identifier in the three-record shape

The three-record trail (Commitment → Decision → Receipt) uses `action_ref` as the
correlation key across all three records. `authorization_ref` is the identifier for the
**Decision record** — the specific authorization event that approved execution.

### Derivation

```
authorization_ref = SHA-256(JCS({
  "action_ref": "<correlation key>",
  "authorized_scope": "<scope string>",
  "decision_ts": <epoch-ms integer>,
  "policy_id": "<policy or ruleset identifier>"
}))
```

Keys in JCS lexicographic order: `action_ref`, `authorized_scope`, `decision_ts`, `policy_id`.

`decision_ts` is an epoch-millisecond integer (not an RFC 3339 string). Sub-second
precision matters here: authorization systems may issue multiple decisions per second under
high concurrency, and millisecond timestamps are the standard granularity for policy
evaluation events.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `action_ref` | string | SHA-256 hex of the action intent tuple — the correlation key for the full trail. Embeds the specific action instance inside the decision preimage. |
| `authorized_scope` | string | Scope string at the moment of authorization. Matches the `scope` field in the `action_ref` preimage in the common case; may differ if the guardrail narrowed the scope during authorization. |
| `decision_ts` | integer | Epoch-millisecond timestamp of the authorization decision. |
| `policy_id` | string | Identifier of the policy or ruleset in force at the moment of authorization. |

### Invariants

**1. `action_ref` is embedded in the preimage.**
The authorization decision is bound to the specific action instance. A verifier can confirm
that the decision was not reused across action instances — if `action_ref` differs, the
`authorization_ref` derived from the same policy snapshot will also differ.

**2. Recomputable without operator cooperation.**
Any verifier holding the four decision record fields (`action_ref`, `authorized_scope`,
`decision_ts`, `policy_id`) can recompute `authorization_ref` independently using
SHA-256(JCS(…)). No call to the operator's systems is required.

**3. Must appear in both the pre-execution record and the receipt.**
A verifier comparing both records can confirm that execution occurred under exactly the
same authorization decision — not a different decision window, not a stale snapshot. The
field is the binding link across the trail.

**4. The fourth verifier check.**
A conformant verifier runs four independent checks across the three-record trail:

| Check | Fields compared |
|-------|----------------|
| Same call instance | `action_ref` in pre-execution == `action_ref` in receipt |
| Same proposed payload | `original_args_digest` in pre-execution (verifier-recomputed from disclosed args) |
| Same dispatched payload | `effective_args_digest` in pre-execution == effective args digest verifier-recomputed from receipt context |
| **Same authorization decision** | **`authorization_ref` in pre-execution == `authorization_ref` in receipt** |

A trail that passes the first three checks but fails the fourth proves that execution
proceeded under a different approval than the one recorded in the pre-execution entry —
the authorization binding is broken.

### Conformance example (byte-verified)

From `examples/conformance/guardrail-provider-v1.fixture.json`, step_2b_authorization_ref:

```
Preimage:
  action_ref       = "104812928eb50e0e1ad28f379f8ade03ea0f479ac7abd1bbf9205e9317665c7f"
  authorized_scope = "autogen:guardrail"
  decision_ts      = 1749513600000
  policy_id        = "guardrail-policy-v1"

JCS payload:
  {"action_ref":"104812928eb50e0e1ad28f379f8ade03ea0f479ac7abd1bbf9205e9317665c7f","authorized_scope":"autogen:guardrail","decision_ts":1749513600000,"policy_id":"guardrail-policy-v1"}

authorization_ref:
  b9f8494a4a5943687d105769556be2963271e37f2216d2afd279e5b260261327
```

The fixture also contains NEG-4, the negative case where the receipt carries an
`authorization_ref` derived from a different `decision_ts` (60 seconds earlier). A
verifier detects the mismatch and rejects the trail — same call and same dispatched
payload, but the approval binding is broken.

---

## Canonical linking key

The same `action_ref` is computable from:

- a Mycelium TrailRecord (preimage fields published in each record)
- a Nobulex covenant receipt (`action_type` as semantic label + timestamp + agent_id + scope)
- a SafeAgent claim ([azender1/SafeAgent](https://github.com/azender1/SafeAgent), joint spec [argentum-core#7](https://github.com/giskard09/argentum-core/issues/7))
- a CrewAI idempotency key ([crewAIInc/crewAI#5822](https://github.com/crewAIInc/crewAI/pull/5822)) — key derivation converges on the same primitive from the retry-deduplication direction
- NEXUS oracle receipts ([nexus-agent-xa12.onrender.com/receipt](https://nexus-agent-xa12.onrender.com/receipt)) — implements canonical envelope v1.0

Any verifier holding one artifact can validate against another without trusting either system.

## Use cases — gap class coverage

### Memory provenance attestation (OWASP ASI06)

`action_ref` with `action_type: "memory_write"` and `scope: <memory_key>` produces a
content-addressed receipt per write. A verifier can check the receipt independently —
no operator trust required. The receipt proves what was written, by which agent, at
which moment.

**Memory poisoning defense:** for `action_type: "memory_write"`, `scope` identifies the
specific memory slot. A trail of write receipts gives a verifier the full provenance
graph of any memory state — who wrote what, when, with what authorization. Combined
with `delegation_ref` (who authorized the write) and `revocation_ref` (when that
authorization was invalidated), the provenance chain is complete and independently
replayable.

**Example — memory write receipt (byte-verified):**

```
Input:
  agent_id    = "giskard-self"
  action_type = "memory_write"
  scope       = "mycelium:memory:session_context_v3"
  timestamp   = "2026-05-26T20:15:00.000Z"

JCS payload:
  {"action_type":"memory_write","agent_id":"giskard-self","scope":"mycelium:memory:session_context_v3","timestamp":"2026-05-26T20:15:00.000Z"}

action_ref:
  36fe8d0559bb254c20cdb0e7a0c83e53f0434fc076e856ff769444da2a73b0b4
```

## State vs Identity

`action_ref` is state-agnostic. It identifies an action — who performed it, what type, what scope, at what moment — not the outcome of that action.

Two receipts for the same action instance in different execution states (`in-progress`, `completed`, `failed`) will produce the same `action_ref`. This is correct by design.

**Implication for verifiers:** a shared `action_ref` across two receipts with different states is not a collision and not a replay. A verifier MUST NOT reject on that basis alone.

To determine whether an action reached a terminal state, inspect the `terminal` field (or its equivalent) in the **signed receipt** — not `action_ref` alone.

**Why this separation matters:** `action_ref` binds identity (the four preimage fields). State is a property of the execution record, not of the action itself. Mixing them would mean an in-progress and a completed receipt of the same action compute different identifiers, which breaks cross-system correlation — a verifier holding a terminal receipt would be unable to match it against an in-progress anchor from a different system.

**The signing layer closes the gap:** `signing-trust-ref-v1` covers the full receipt envelope, including the `terminal` field and any other state fields. An attacker cannot swap a terminal receipt for an in-progress one without invalidating the signature. `action_ref` anchors identity; the signed envelope anchors state.

**Conformance:** vector `same_action_ref_different_state` in `examples/conformance/near-miss-v1/near-miss-v1.fixture.json` documents this property with byte-verified hashes and `expected_result: KNOWN_DESIGN_PROPERTY`.

---

## Cross-references

- Reference implementation: [`plugins/agt_evidence_anchor/action_ref.py`](../../plugins/agt_evidence_anchor/action_ref.py)
- Full TrailRecord schema: [MYCELIUM_TRAILS_REFERENCE.md](../MYCELIUM_TRAILS_REFERENCE.md)
- Joint spec with SafeAgent: [argentum-core#7](https://github.com/giskard09/argentum-core/issues/7)
- Nobulex alignment: [MetaGPT#1991](https://github.com/geekan/MetaGPT/issues/1991)
