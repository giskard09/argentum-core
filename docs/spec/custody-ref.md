# custody-ref-v1

`custody-ref` is a content-addressed, typed pointer to a **custody-domain
assertion**: the trust-domain relationship between whoever captured/recorded
an execution record and whoever executed the action it describes.

**v1.1 (2026-07-29):** added `deployer_id` to the preimage and generalized
Rule 3 (`independent_third_party`) to also require `capturer_id != deployer_id`.
Preimage hashes for existing fixtures changed; see the fixture set changelog.
Gap reported by magentixai (Sansone, AXES, axes#3).

**v1.2 (2026-07-29):** added `boundary_ref` and `capture_phase` as **sibling**
declarations to `custody-ref` (never preimage members — the preimage from
v1.1 is unchanged, no hashes affected). Reconciled with magentixai (Sansone,
AXES) in axes#3: `custody-ref-v1` is being folded in as the reference
implementation for AXES's `capture_relationship` field assessment (axes#10),
with a two-sided fixture cross-check against AXES's Golden Trace corpus. See
[Sibling declarations](#sibling-declarations-boundary_ref--capture_phase)
below.

## Motivation

Two byte-identical records — same `action_ref`, same `signing_trust_ref` —
can carry different probative weight in front of a supervisor depending on
who captured them relative to who executed the action. A record captured by
the same operator that ran the agent is not the same evidence as one
captured by a genuinely independent third party, even when the bytes match.
If that relationship lives only in prose on a webpage or in the platform's
word, the verifier has to trust the exact party whose independence is in
question — which defeats the purpose of claiming independence at all.

`custody-ref` makes the relationship a typed, hashed, verifiable field
instead of an unverified claim.

Proposed by Sansone (magentixai) in AGT discussion #276, building on a point
raised by neldan00077.

## Preimage schema

```json
{
  "action_ref":   "<action_ref this custody assertion covers>",
  "custody_type": "same_domain" | "deployer_domain" | "independent_third_party",
  "capturer_id":  "<identity of the party that captured/recorded this record>",
  "executor_id":  "<identity of the party that executed the action>",
  "deployer_id":  "<identity of the party that deploys/operates the executor>",
  "timestamp_ms": <uint64, Unix epoch milliseconds>
}
```

`deployer_id` (added v1.1) names the deployer of `executor_id` explicitly, so a
verifier can check `independent_third_party` claims against the deployer
relationship, not only against `executor_id` and the signer. For `same_domain`
and `deployer_domain` records `deployer_id` is expected to equal `capturer_id`
or `executor_id` respectively (see Fail-closed structural check below); for
`independent_third_party` it must differ from `capturer_id`.

`custody-ref` is a **sibling** field to `action_ref`, never a member of its
preimage. `action_ref`'s four-field preimage (`agent_id`, `action_type`,
`scope`, `timestamp`) is frozen — see `action-ref.md` — and does not change
to accommodate this primitive.

## Derivation

```
custody_ref = SHA-256(JCS(preimage))
```

JCS: RFC 8785 canonical JSON (keys sorted, no extra whitespace).

```python
import hashlib, json

def jcs(obj):
    return json.dumps(dict(sorted(obj.items())), separators=(',',':'), ensure_ascii=False)

custody_ref = hashlib.sha256(jcs(preimage).encode()).hexdigest()
```

## `custody_type` values

| Value | Meaning |
|-------|---------|
| `same_domain` | The capturer and the executor are the same operational domain — one operator runs the agent and records the evidence. |
| `deployer_domain` | The capturer is the deployer of the agent — a distinct domain from the agent's own executing identity (e.g. a platform hosting a third-party agent), but not neutral: the deployer has an operational stake in the executor. |
| `independent_third_party` | The capturer has no operational control over, and no commercial relationship with, the executor. This is the category that carries the most probative weight — and the one most in need of a verifiable check, not a claim. |

`custody_type` is a closed enum, fail-closed: an unrecognized value is not a
degraded case of one of the three, it is a validation failure.

## Fail-closed structural check

A `custody_type` declaration is not self-certifying. A conformant verifier
MUST check it against the identities in the record, not accept the label at
face value:

1. **`same_domain`** requires `capturer_id == executor_id`. If they differ,
   the record does not describe the same domain regardless of what
   `custody_type` claims.
2. **`deployer_domain`** requires `capturer_id != executor_id`. A deployer
   is by definition distinct from the identity it deploys.
3. **`independent_third_party`** requires all three of:
   - `capturer_id != executor_id`
   - `capturer_id != deployer_id`
   - `capturer_id` must not equal the `signer_id` of the `signing-trust-ref`
     that covers the same `action_ref`

   The last two legs are both needed and neither substitutes for the other.
   The signer check catches the case where a party is nominally distinct
   from the executor (`capturer_id != executor_id`) while still being the
   sole issuer who signed the whole record — i.e. the only attestation in
   the system is the issuer's own.

   The deployer check (added v1.1, gap reported by magentixai/Sansone, AXES,
   axes#3) catches a different case: a capturer that IS the deployer's own
   control plane, with the record signed by a genuinely distinct third
   party. Before this check existed, such a record passed both the
   executor-id and the signer-id legs — `capturer_id != executor_id` holds
   (the control plane isn't the agent) and `capturer_id != signer_id` holds
   (a real third party signed it) — and would be wrongly accepted as
   `independent_third_party`. But `deployer_domain`'s own definition says
   the deployer "has an operational stake in the executor"; a capturer that
   *is* the deployer cannot simultaneously be a neutral third party, no
   matter who signs the record. `independent_third_party` asserts a witness
   that has no operational control over, and no commercial relationship
   with, the executor — being the deployer is exactly the relationship that
   rules that out. See `cr-005` (negative) / `cr-006` (positive, same record
   correctly labeled `deployer_domain`) in the conformance fixtures.

Rule 3 is why `custody-ref` composes with `signing-trust-ref` rather than
duplicating it: `signing-trust-ref` already names who signs a record and
under what key model; `custody-ref` reuses that identity to check whether an
independence claim is real or whether "independent" only means "given a
different label by the same issuer." The `deployer_id` field closes the
remaining gap: distinctness from the signer is necessary but not sufficient
— the capturer must also be distinct from the deployer.

## Sibling declarations: `boundary_ref` / `capture_phase`

Two fields carried **alongside** `custody-ref` on the trail record — like
`signing_trust_ref` and `custody_ref` themselves — never inside its
preimage. Both were open design questions in v1.1, resolved with magentixai
(Sansone, AXES) in axes#3.

### `boundary_ref`

A capture boundary declares what was in scope of capture and what was
deliberately excluded — e.g. an interbank leg of a payment flow that the
capturing system never observed. Without it, a verifier cannot distinguish a
faithful gap (disclosed, out of scope) from a silent one (undisclosed,
looks like nothing happened). `boundary_ref` makes that declaration a
typed, hashed, verifiable field, the same pattern `custody-ref` applies to
the capturer/executor/deployer relationship.

Kept **out of `custody-ref`'s preimage** deliberately: the custody-domain
relationship (who captured relative to who executed) must not change
identity depending on how the boundary happens to be declared for a given
run. Folding it into the six-field preimage above would make the same
capturer/executor/deployer triple hash differently under different boundary
declarations — the same reasoning that already keeps `custody-ref` itself
out of `action_ref`'s frozen preimage.

Preimage schema (own SHA-256(JCS(·)), a sibling ref in its own right):

```json
{
  "action_ref":       "<action_ref the boundary declaration covers>",
  "captured_scope":   ["<items that were in scope of capture>"],
  "excluded_scope":   ["<items deliberately excluded from capture>"]
}
```

**Fail-closed structural check:** `captured_scope` and `excluded_scope` MUST
NOT both be empty arrays. An empty/empty declaration is indistinguishable
from no declaration at all — a `boundary_ref` that asserts nothing is not a
degraded case of a real boundary, it is a validation failure, same posture
as `custody_type`'s closed enum. At least one of the two arrays must be
non-empty.

### `capture_phase`

```
capture_phase: "pre_execution" | "at_commit" | "post_execution"
```

A typed declaration of when, relative to the executed action, the record
was captured — carried **in addition to** `custody-ref`'s `timestamp_ms`,
never in place of it. The pre-versus-post distinction ("was this sealed
before the outcome existed") is load-bearing for probative weight and is
not always safely derivable from a raw timestamp alone under clock skew or
a soft execution boundary — it earns an explicit, checked field rather than
being inferred.

**Fail-closed structural check**, against a sibling `execution_commit_ts`
(uint64 ms, the moment the action's outcome was committed) that MUST be
present on the record for `capture_phase` to be checkable — same pattern
as Rule 3 requiring `executor_id` and a deployer reference both present:

- `pre_execution` requires `custody_ref.preimage.timestamp_ms <= execution_commit_ts`.
- `post_execution` requires `custody_ref.preimage.timestamp_ms >= execution_commit_ts`.
- `at_commit` has no ordering requirement beyond both timestamps being
  present — it declares "at the same operational step as commit," which
  clock skew alone cannot falsify.
- An unrecognized `capture_phase` value, or a record declaring the field
  without a paired `execution_commit_ts`, MUST be rejected — the phase
  claim cannot be checked, and an unverifiable claim is treated as false,
  not passed through.

## Relationship to existing primitives

```
action_ref          → immutability of the record (what happened)
signing_trust_ref    → trust level of the signer (who attested it and how)
custody_ref          → trust-domain relationship between capturer and executor
```

`custody-ref` does not restate `verifier-independence.md`'s Model A/Model B
distinction (that document is about the *verification method* — signed
record vs. content-addressed anchor). `custody-ref` is orthogonal: it
answers who is watching, not how the watching is verified. All three fields
can coexist as siblings in a trail record:

```json
{
  "action_ref":        "25b9c32f...",
  "signing_trust_ref": "1d1becb3...",
  "custody_ref":       "a94e5623..."
}
```

Nor does `custody-ref` restate `outcome_handle` (`guarantee-model.md`):
`outcome_handle` is a follow-up verification reference for a specific
backend transition (`PENDING`→`COMMITTED`); `custody-ref` is a static
declaration about who captured the record, independent of the action's
execution status.

## Conformance fixtures

[`examples/conformance/custody-ref/`](../../examples/conformance/custody-ref/)

- `cr-001` — `same_domain` (valid): capturer and executor share one operator identity.
- `cr-002` — `deployer_domain` (valid): capturer is the deployer, distinct from the agent's own executing key.
- `cr-003` — `independent_third_party` (valid): capturer is a genuinely separate identity from both the executor and the signer.
- `cr-004` — `independent_third_party` **(negative)**: capturer_id equals the sole signer_id covering that `action_ref` — the only attestation in the record is the issuer's own. Structurally invalid; a conformant validator MUST reject it.
- `cr-005` — `independent_third_party` **(negative, v1.1)**: capturer_id equals deployer_id — the capturer is the deployer's own control plane, signed by a genuinely distinct third party. Passes the executor-id and signer-id checks alone but fails the deployer-id check. Gap reported by magentixai (Sansone, AXES, axes#3).
- `cr-006` — `deployer_domain` **(positive, v1.1)**: same underlying record as `cr-005`, correctly labeled.
- `cr-007` — `capture_phase: pre_execution` **(positive, v1.2)**: custody `timestamp_ms` precedes `execution_commit_ts` — consistent with the declared phase.
- `cr-008` — `capture_phase: post_execution` **(negative, v1.2)**: declared `post_execution` but custody `timestamp_ms` precedes `execution_commit_ts` — the record claims it was sealed after the outcome existed when it was actually sealed before. Structurally invalid.
- `cr-009` — `boundary_ref` **(positive, v1.2)**: `captured_scope` non-empty, `excluded_scope` non-empty (explicit disclosed gap, AXES's `outside_capture_boundary` pattern) — valid declaration.
- `cr-010` — `boundary_ref` **(negative, v1.2)**: `captured_scope` and `excluded_scope` both empty — an undeclared boundary masquerading as a declared one. Structurally invalid.

## Interop note — AXES cross-check

`custody-ref-v1` is the reference implementation for AXES's `capture_relationship`
field assessment (magentixai/axes#10; proposed by neldan00077 on the AXES
side, `custody-ref-v1` credited as the implementation). Two-sided fixture
cross-check: this repo's `examples/conformance/custody-ref/` vectors run
against AXES's Golden Trace corpus (`examples/golden-trace`,
`examples/golden-trace-ind` in magentixai/axes), and AXES's custody vectors
seeded in axes#6 (including a "deployer-signed twin" matching `cr-005`/`cr-006`)
run against `custody-ref-v1`. A clean pass in both directions is the interop
evidence the field assessment needs — not yet run as of v1.2, pending AXES's
seed update.

AXES also tracks a **corroboration_state** per fact (who confirms it,
distinct from who captured it) and proposed one consistency rule between the
two suites: a fact must not declare `independent_third_party` custody while
its corroboration is only issuer-internal, or vice versa. `custody-ref-v1`
does not implement a corroboration primitive itself (no `corroboration_state`
field exists in this repo's trail records today) — noted here as a forward
compatibility point for whichever side that lands on next, not implemented
in v1.2.

## References

- `action-ref.md` — canonical field set and derivation (frozen; `custody_ref` is never a preimage member)
- `signing-trust-ref.md` — signer identity and key model; `custody-ref`'s independence check cross-references its `signer_id`
- `verifier-independence.md` — Model A/Model B verification-method distinction (orthogonal to custody domain)
- `guarantee-model.md` — `outcome_handle` and transition semantics (orthogonal to custody domain)
