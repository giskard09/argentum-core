# execution-join-ref-v1

**Version:** 1.1

An execution join binds the outcome of a tool call back to the exact guardrail
decision that authorized it. Four identifiers form a chain; each is a
SHA-256(JCS(canonical preimage)) computed at the moment described, not at
record time.

**v1.1 (2026-10-18, additive):** built in response to astrogilda/Sankalp
(Open Evidence Lab) asking directly for two file-write-domain cases
(`probityai/agent-evidence-vectors#25`, `#26`) that this spec had never
exercised before: (1) a file path changing before dispatch without a new
approval, and (2) an approved write completing and a later observation
finding the file no longer matches. Case 1 needed no new mechanism — it is
`EFFECTIVE_CALL_REBINDING_FAILED` (already defined below) in a new domain;
see `file-write-rebinding-failed-001` in the fixture. Case 2 is new: a
seventh invariant, `post_commit_consistency`, and failure code
`POST_COMMIT_DIVERGENCE` — see "Post-commit divergence (v1.1)" below. This
version also fixes `examples/conformance/execution-join-ref/verify.py`,
which did not exist before this change (the fixture had never been run
against a real verifier; `verification_mode` in vectors.json was
`"asserted"`), and a real bug in `profiles/profile_registry.py`
(`resolve()` called `json.loads` without importing `json` — every call
raised `NameError`, undetected because nothing had ever called it either).

## Fields

**action_ref** — identity of the proposed action, computed from its JCS
preimage before the tool call crosses the runtime boundary. This is the same
`action_ref` used in `action-ref-v1`; it is included here so the join contract
is self-contained.

**decision_id** — the guardrail's decision on that exact preimage. Its JCS
preimage must include `action_ref`, ensuring the decision binds to one specific
proposed action and not to an abstract policy evaluation.

**attempt_id** — the execution instance. A retry is a new attempt_id over a
new preimage (with incremented `attempt_seq`). Reusing attempt_id across retries
breaks the join contract: the verifier cannot distinguish the original execution
from its retry.

**result_id** — terminal outcome of the attempt. Its JCS preimage must include
`attempt_id`. A verifier that receives two records with the same result_id but
conflicting `outcome` fields must reject both: the registry cannot contain two
terminal states for one attempt.

**proof_ref** — optional. Compact reference to evidence attached to the original
attempt. The preimage must include `attempt_id` of the original, not of any
rewrite or retry. Attaching proof to a rewrite that shares none of the original
attempt's bytes is a binding failure even if the proof itself is valid.

## JCS preimage shapes

```json
// action_ref
{
  "actor_id": "<string>",
  "input_hash": "<sha256-hex>",
  "scope": "<string>",
  "ts_ms": <integer>,
  "version": "execution-join-ref-v1"
}

// decision_id (decision evidence object)
{
  "action_ref": "<sha256-hex>",
  "canonicalization_profile_id": "<string>",
  "outcome": "permit | deny | defer",
  "policy_id": "<string>",
  "ts_ms": <integer>,
  "version": "execution-join-ref-v1"
}
```

`canonicalization_profile_id` is a required field in the decision evidence
object. The verifier reads it before comparing any digests. If the field is
absent or names a profile the verifier does not support, the verifier must
return a failure code specific to that condition — not DIGEST_MISMATCH. This
ensures that a verifier that only implements JCS cannot silently pass evidence
encoded with a different canonicalization scheme.

The value of `canonicalization_profile_id` is `SHA-256(JCS(profile_doc))` —
content-addressed. Same id implies same doc, verifiable by construction.
Human-readable aliases resolve to their canonical hash via
`profiles/profile_registry.py`. Each profile doc lives at
`profiles/<profile_id>.json`.

Currently defined profiles:

| alias | profile_id (SHA-256 of doc) | canonical form |
|---|---|---|
| `jcs-rfc8785-v1` | `f018a62879ab01f21e8fe5e9e7486dadba0b795e9358b32fd24d38d2c1f1f07d` | JSON Canonicalization Scheme (RFC 8785) — decision evidence preimage. `duplicate_keys: REJECT`; `numeric_domain`: safe integers `[0, 2^53-1]` for `ts_ms`, out of range → `OUT_OF_PROFILE_DOMAIN` |
| `jcs-rfc8785-action-ref-v1` | `bcf8ae8c1105b8b59f892935d076540f54813b0d87c30cab741e4c29847a0cf5` | JSON Canonicalization Scheme (RFC 8785) — action_ref preimage; `timestamp` is `string`, NOT integer. `duplicate_keys: REJECT`; `numeric_domain: not_applicable` (no numeric fields) |

Also used by [`governance-block-join-ref-v1`](governance-block-join-ref-v1.md)
(`canonicalization_profile_id: jcs-rfc8785-v1`) — same profile doc, same
domain pinning.

Superseded profile_ids (schema gap closed 2026-07-03: `duplicate_keys` and
`numeric_domain` were previously unpinned — a single behavior per profile now,
not an implementation-defined fallback). The old docs remain on disk and
remain resolvable by hash for evidence minted before this change; the aliases
above resolve to the current docs.

| superseded profile_id | superseded by |
|---|---|
| `82b5df2a487988d5ba773cf40ffa92a614769de6fbea6f4b2745794125e1c9fa` | `f018a62879ab01f21e8fe5e9e7486dadba0b795e9358b32fd24d38d2c1f1f07d` |
| `8c7f71754e3daae1a0390d5e0287d51097d011e40df36bf15cad5c0f47efa05a` | `bcf8ae8c1105b8b59f892935d076540f54813b0d87c30cab741e4c29847a0cf5` |

```json

// attempt_id
{
  "action_ref": "<sha256-hex>",
  "attempt_seq": <integer>,
  "executor_id": "<string>",
  "ts_ms": <integer>,
  "version": "execution-join-ref-v1"
}

// result_id
{
  "attempt_id": "<sha256-hex>",
  "outcome": "completed | failed | cancelled",
  "output_hash": "<sha256-hex>",
  "ts_ms": <integer>,
  "version": "execution-join-ref-v1"
}

// proof_ref (optional)
{
  "attempt_id": "<sha256-hex>",
  "evidence_type": "<string>",
  "external_ref": "<string>",
  "ts_ms": <integer>,
  "version": "execution-join-ref-v1"
}
```

## Anchoring

Optional. rpelevin's framing: join contract first, anchors after. A
conformant implementation must pass all five positive invariants without any
on-chain anchor. Anchoring may be layered on top via
`anchoring-precedence-ref-v1` once the join record exists.

## Failure code taxonomy

All verifier results map to exactly one of these codes:

| code | condition |
|---|---|
| `AUTHORIZED_EFFECTIVE_CALL` | all invariants pass; effective call is bound to a valid decision |
| `MALFORMED_EVIDENCE` | decision evidence object is missing a required field or is not valid JCS |
| `UNSUPPORTED_CANONICAL_PROFILE` | `canonicalization_profile_id` is present but the verifier does not implement that profile |
| `OUT_OF_PROFILE_DOMAIN` | profile is supported, but the preimage violates a domain constraint the profile pins explicitly (duplicate keys when `duplicate_keys: REJECT`; a number outside the declared `numeric_domain`) — checked before any digest comparison, never coerced or passed to a fallback library |
| `DIGEST_MISMATCH` | profile is supported, preimage is within domain, all fields are present, but recomputed digest does not match the claimed ref |
| `EXPIRED_POLICY_BINDING` | decision evidence is structurally valid but `policy_id` was not in force at `ts_ms` |
| `POST_COMMIT_DIVERGENCE` (v1.1) | invariants 1-6 all pass — the join record is fully valid — but a `post_commit_observation` reports a content hash for the same `result_id` that does not match the original `output_hash`. Does not retroactively change any other invariant's result. |

`VERIFIER_OFFLINE` remains a distinct code when the verifier cannot access the
preimage material needed to recompute any ref. It does not collapse into
`MALFORMED_EVIDENCE`.

## Invariants

A verifier checks these in order; the first failure is the reported
failure_mode:

1. **canonical_envelope** — every ref is SHA-256(JCS(its declared preimage)).
2. **chain_integrity** — decision_id preimage includes this action_ref;
   result_id preimage includes this attempt_id. (`proof_ref`'s binding to
   `attempt_id` is checked exclusively by invariant 5, `proof_binding`, not
   here — a record can satisfy chain_integrity while proof_binding still
   fails; see `PROOF_BINDING_FAILED` below. v1.1: this is a wording fix, not
   a behavior change — the reference verifier added in v1.1 is the first
   thing to ever actually check this, and the fixture's own vectors had
   already settled on this separation before the prose caught up to it.)
3. **no_duplicate_attempt** — attempt_id does not appear in any prior record
   for this action_ref.
4. **result_uniqueness** — no two records carry the same result_id with
   different `outcome` values.
5. **proof_binding** — if proof_ref is present, its preimage's attempt_id
   matches this record's attempt_id (not a rewrite's).
6. **effective_call_binding** — if the guardrail rewrote the args before
   dispatch, the runtime must present an `effective_action_ref` computed from
   the rewritten preimage, and a decision_id that covers that effective ref.
   A record where `effective_action_ref` is present but no decision covers it
   fails this check. Domain-agnostic: "args" here means whatever the proposed
   action's `input_hash` is derived from — a file path, an API payload, a
   trade order — not specifically Stripe's request body. See
   `file-write-rebinding-failed-001` (v1.1) for the same failure in the
   file-write domain.
7. **post_commit_consistency** (v1.1, additive) — see "Post-commit divergence
   (v1.1)" below. Exempt when the envelope carries no `post_commit_ref`.

## Post-commit divergence (v1.1)

Everything above answers one question: was the dispatched call authorized?
It says nothing about whether the thing the attempt produced is still the
thing it produced, later. `result_id` is a terminal record of the attempt's
outcome *at completion time* — it is not, and was never meant to be, a
live attestation that the output still matches days or months afterward.
astrogilda/Sankalp (Open Evidence Lab) asked for this case directly
(`probityai/agent-evidence-vectors#26`, 2026-10-18): an approved write
completes cleanly, and someone — or something — changes the file
afterward, outside the join chain entirely.

**The field:** `post_commit_ref`, an optional envelope field, same pattern
as `effective_action_ref` and `proof_ref` — present only when a post-commit
observation exists, absent by default, changing nothing about how an
envelope without it hashes or evaluates.

```json
// post_commit_observation
{
  "observed_hash": "<sha256-hex>",
  "observed_at_ms": <integer>,
  "observer_id": "<string>",
  "result_id": "<sha256-hex>",
  "version": "execution-join-ref-v1"
}
```

`post_commit_ref` is `SHA-256(JCS(post_commit_observation))`. The preimage's
`result_id` binds the observation to one specific terminal record — the
same "preimage must include the thing it is binding to" pattern `proof_ref`
and `decision_id` already use.

**The rule:** `post_commit_consistency` holds when `post_commit_observation
.observed_hash` equals the `output_hash` declared in that `result_id`'s own
preimage. It fails when they differ — this is `POST_COMMIT_DIVERGENCE`.

**This does not retroactively change anything about the original record.**
`canonical_envelope`, `chain_integrity`, `no_duplicate_attempt`,
`result_uniqueness`, `proof_binding`, and `effective_call_binding` are
computed exactly as they would be without any `post_commit_observation` at
all, and stay true if they were true. The guardrail decided correctly, the
attempt executed what was approved, and the result it produced at
completion time is exactly what it declared. What changed is *later*, and
outside the execution the join record describes. Collapsing the two into
one state — reporting the original execution as itself invalid — would
destroy the distinction this invariant exists to preserve: *this specific
attempt was authorized and completed cleanly* is a fact that remains true
independent of what happens to the artifact afterward. See
`post-commit-divergence-001` in the fixture, where invariants 1-6 all pass
and only `post_commit_consistency` fails.

**What this does not do:** a `post_commit_observation` is itself only as
trustworthy as whatever produced `observed_hash` — this spec does not
define how that observation is captured, authenticated, or how often it
runs. A missing `post_commit_ref` is not itself a finding; absence of a
later check is not evidence that nothing changed, the same "don't collapse
unknown into known" principle
[`verify-failure-mode-ref.md`](./verify-failure-mode-ref.md) applies
elsewhere in this repo.

## Critical negative cases

**DUPLICATE_ATTEMPT** — a retry submits a result with the same attempt_id as
the original execution. Invariant 3 fails. A verifier that only checks
chain_integrity will silently accept this.

**NONCONFORMANT_DECISION** — the result record claims a decision_id whose JCS
preimage binds to a different action_ref. Invariant 2 fails at the
decision_id↔action_ref link.

**PROOF_BINDING_FAILED** — proof_ref is present but its preimage's attempt_id
is the attempt_id of a rewrite, not of this attempt. Invariant 5 fails.

**RESULT_ID_CONFLICT** — two records carry the same result_id string but
declare different `outcome` values. A registry that accepts the second record
silently corrupts the terminal state. Invariant 4 fails.

**VERIFIER_OFFLINE** — recomputing action_ref requires the actor's runtime
input buffer, which is no longer available. The verifier must return
`VERIFIER_OFFLINE` rather than pass or fail the record on partial evidence.

**EFFECTIVE_CALL_REBINDING_FAILED** — the guardrail reviewed the original args
and issued a permit decision (decision_id covers action_ref). The guardrail
then rewrote the args. The runtime dispatched the rewritten call without
issuing a new decision_id that covers the effective preimage. The join record
carries `effective_action_ref` pointing to the rewritten args, but no
decision_id in the registry covers it. Invariant 6 fails. A verifier that
only checks chain_integrity will silently accept this: the internal chain
action_ref→decision_id→attempt_id→result_id is consistent; the failure is
that the guardrail never evaluated the call that was actually dispatched.
A conformant guardrail that rewrites args must compute a new decision_id over
the rewritten preimage before the runtime crosses the boundary. Applies
across domains: see `file-write-rebinding-failed-001` (v1.1) for the file
path case astrogilda/Sankalp asked about directly
(`probityai/agent-evidence-vectors#26`, 2026-10-18) — no new mechanism, the
same failure in a new domain.

**POST_COMMIT_DIVERGENCE** (v1.1) — decision, attempt, and result are all
present, complete, and mutually consistent; invariants 1-6 all pass. A
`post_commit_observation` for the same `result_id`, taken later and
independently, reports a content hash that does not match the original
`output_hash`. Invariant 7 fails. A verifier with no concept of post-commit
observation has no way to ever detect this — the join record it can see is,
and remains, entirely valid. See `post-commit-divergence-001`.

## Relationship to existing primitives

- `action-ref-v1` — action_ref is the same primitive; this spec composes it
  into a multi-step chain.
- `anchoring-precedence-ref-v1` — optional outer layer; block_time must
  precede result_id ts_ms when anchoring is applied.
- `release-gate-ref-v1` — the release gate opens on decision_id; the join
  contract closes the loop from decision to outcome.

## Cross-references

- Source of the two v1.1 file-write-domain cases: astrogilda/Sankalp (Open
  Evidence Lab), `probityai/agent-evidence-vectors#25` and `#26`,
  2026-10-18.
- `post_commit_consistency`'s "a correction is a separate, later fact, not
  a retroactive one" posture follows the same non-collapsing precedent
  `peer-reconciliation-ref-v1.md`'s `supersedes` mechanism and tri-state
  comparator already set in this repo.
- Composed onto a different domain's shape, same day: `examples/conformance/
  execution-join-ref/horizon-shield-pilot-case-d/` proposes `post_commit_
  consistency` as a fourth, complementary case for the live pilot scoped in
  `ogasurfproject-jpg/horizon-shield#51` — the JCCDB cost database an
  accepted estimate was audited against changing after acceptance.
