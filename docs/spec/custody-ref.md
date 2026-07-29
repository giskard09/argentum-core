# custody-ref-v1

`custody-ref` is a content-addressed, typed pointer to a **custody-domain
assertion**: the trust-domain relationship between whoever captured/recorded
an execution record and whoever executed the action it describes.

**v1.1 (2026-07-29):** added `deployer_id` to the preimage and generalized
Rule 3 (`independent_third_party`) to also require `capturer_id != deployer_id`.
Preimage hashes for existing fixtures changed; see the fixture set changelog.
Gap reported by magentixai (Sansone, AXES, axes#3).

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

## References

- `action-ref.md` — canonical field set and derivation (frozen; `custody_ref` is never a preimage member)
- `signing-trust-ref.md` — signer identity and key model; `custody-ref`'s independence check cross-references its `signer_id`
- `verifier-independence.md` — Model A/Model B verification-method distinction (orthogonal to custody domain)
- `guarantee-model.md` — `outcome_handle` and transition semantics (orthogonal to custody domain)
