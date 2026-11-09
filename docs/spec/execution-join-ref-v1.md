# execution-join-ref-v1

**Version:** 1.3

An execution join binds the outcome of a tool call back to the exact guardrail
decision that authorized it. Four identifiers form a chain; each is a
SHA-256(JCS(canonical preimage)) computed at the moment described, not at
record time.

**v1.3 (2026-11-07, additive):** astrogilda/Sankalp ran `probityai/
agent-evidence-vectors`' `authority-at-dispatch/v1` corpus (8 ordered checks,
`agent_evidence_vectors.authoritydispatch.CHECKS`) through this spec's own
`map_authority_at_dispatch.py` and named the gap directly
(`probityai/agent-evidence-vectors#349`): of the corpus's 10 denied records,
7 fail for a reason `decision_id`'s preimage carries no field for at all —
`grant_revoked`, `grant_expired`, `scope_amplified`, `authority_evidence_
stale`, `evidence_age_inconsistent`, `contract_id_missing`,
`contract_id_unknown` — reported `NOT_MODELED`, never forced through
`effective_call_binding`. See "Gap — delegation, revocation and freshness"
below for the four new optional fields this adds to `decision_id`'s preimage,
and the honest, case-by-case accounting of which of the 7 move, partially
move, or stay `NOT_MODELED` — re-run against the real corpus, not asserted
in prose.

**v1.1 (2026-10-18, additive):** built in response to astrogilda/Sankalp
(Open Evidence Lab) asking directly for two file-write-domain cases
(`probityai/agent-evidence-vectors#25`, `#26`) that this spec had never
exercised before: (1) a file path changing before dispatch without a new
approval, and (2) an approved write completing and a later observation
finding the file no longer matches. Case 1 needed no new mechanism — it is
`EFFECTIVE_CALL_REBINDING_FAILED` (already defined below) in a new domain;
see `file-write-rebinding-failed-001` in the fixture. Case 2 is new: a
seventh invariant, `post_commit_consistency`, and failure code
`POST_COMMIT_DIVERGENCE` — see "Post-commit divergence (v1.1/v1.2)" below. This
version also fixes `examples/conformance/execution-join-ref/verify.py`,
which did not exist before this change (the fixture had never been run
against a real verifier; `verification_mode` in vectors.json was
`"asserted"`), and a real bug in `profiles/profile_registry.py`
(`resolve()` called `json.loads` without importing `json` — every call
raised `NameError`, undetected because nothing had ever called it either).

**v1.2 (2026-10-18, additive):** ogasurfproject-jpg (`ogasurfproject-jpg/
horizon-shield#51`) reviewed the worked example composing `post_commit_
consistency` onto their pilot (see "Cross-references" below) and pointed
out that their own real system had already produced a `POST_COMMIT_
DIVERGENCE` on its own, between two audits of the same real call against
two souba-db releases. They asked for one addition: a way for the
`post_commit_observation` itself to name which external dataset it was
recomputed against, so a reader can tell "the responder changed behavior
on an unchanged dataset" apart from "the dataset moved (expected,
anchored)" without the two cases looking identical. `post_commit_
observation.dataset_sha256` (below) is that field — optional, additive,
purely informational: it does not change the `post_commit_consistency`
rule, which still depends only on `observed_hash` vs. `output_hash`.

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
  "version": "execution-join-ref-v1",
  "authority_verified_at_ms": <integer, optional, v1.3>,
  "revocation_check_at_ms": <integer, optional, v1.3>,
  "revocation_authority_ref": "<sha256-hex, optional, v1.3>",
  "delegation_chain_ref": "<sha256-hex, optional, v1.3>"
}
```

The four v1.3 fields are optional and enter the hash only when present — a
`decision_id` without them hashes exactly as it did under v1.2. See "Gap —
delegation, revocation and freshness" below for what each one does and does
not prove.

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

## Gap — delegation, revocation and freshness (v1.3)

Everything above answers one question: was the dispatched call covered by
a decision that permits it? It says nothing about the authority behind
that decision — whether the agent's delegated grant was still unrevoked,
still inside its validity window, and checked against evidence that was
still fresh, at the moment the decision was made. `policy_id` is an opaque
string; a verifier holding it cannot tell whether the delegation chain
behind it was sound.

### Four fields, reused not redefined

- **`authority_verified_at_ms`** (integer, optional) — same field, same
  meaning, as [`action-ref.md`](./action-ref.md#two-fields-that-close-this-gap):
  the timestamp at which the delegation authority behind this decision was
  last confirmed current.
- **`revocation_check_at_ms`** (integer, optional) — same field as
  `action-ref.md`: the timestamp of the last non-revocation check performed
  before this decision.
- **`revocation_authority_ref`** (string, optional) — same field as
  `action-ref.md`: `SHA-256(JCS(authority_descriptor))`, naming the specific,
  independently-identifiable authority consulted — never the raw check
  result itself.
- **`delegation_chain_ref`** (string, optional) — the field defined in
  [`delegation-chain-ref.md`](./delegation-chain-ref.md): a pointer to the
  multi-hop delegation artifact (`hops`, each with `delegatee`, `delegator`,
  `delegation_ref`, `scope`) that authorized the acting agent.

None of the four enters any invariant below as a resolved true/false claim
about revocation, expiry, or staleness — that would require the external
registry or chain artifact these fields point at, which this spec does not
inline, for the same reason `revocation_authority_ref` doesn't inline
revocation status in `action-ref.md`: a pointer a third party can check
independently is a stronger claim than a self-reported boolean. What the
fields buy is narrower and verifiable from the preimage bytes alone:
**invariant 8** below checks that, when present, they are temporally
ordered against each other and against `ts_ms` — the one thing a verifier
*can* confirm without the external material.

### What this does and does not close — the honest accounting

astrogilda's `map_authority_at_dispatch.py` run against `probityai/
agent-evidence-vectors==0.35.0`'s real corpus (`authority-at-dispatch/v1`,
10 denied cases) named 7 reasons this spec had no field for. Re-run after
this change, with `decision_id`'s preimage populated from each case's own
`authorityEvidence`/`delegation`/`contractId` fields:

| corpus reason | after v1.3 | why |
|---|---|---|
| `grant_revoked` | **AUDITABLE_VIA_NAMED_AUTHORITY** | `revocation_check_at_ms` (from `decisionTime`) + `revocation_authority_ref` (binding `authorityEvidence.source`/`.revision`) make the decision point at a specific, named revocation snapshot. A third party holding that snapshot can check whether the grant was revoked before the bound timestamp. This spec's own verifier still cannot — it has no access to the snapshot's contents, only the pointer, same posture as `action-ref.md`'s `revocation_authority_ref`. |
| `authority_evidence_stale` | **AUDITABLE_VIA_NAMED_AUTHORITY** | `authority_verified_at_ms` (from `authorityEvidence.observedAt`) lets any verifier recompute the real age (`ts_ms - authority_verified_at_ms`) directly. The staleness *threshold* (`maxAgeSeconds` in the corpus) is not a field this spec defines — same as `expires_at` in `delegation-ref.md`, checking currency against the threshold is the integrator's policy, not a spec invariant. |
| `evidence_age_inconsistent` | **CLOSED** | this check exists only to catch a record whose self-declared age doesn't match its own timestamps. With `authority_verified_at_ms` in the hashed preimage, there is no separate declared-age value to diverge from the real one — the inconsistency this check detects cannot occur by construction, not merely "mapped to a new code." |
| `grant_expired` | **PARTIALLY MODELED** | `delegation_chain_ref`'s hops each carry a `delegation_ref` pointer, and `delegation-ref.md`'s artifact includes `expires_at`. A verifier with the full chain artifact (not just the hash) can check the upper bound. There is no `notBefore` field anywhere in this spec family — the corpus's two-sided window (`notBefore` ≤ decision time < `expiresAt`) is only half-coverable. |
| `contract_id_missing` / `contract_id_unknown` | **NOT_MODELED, unchanged** | these check which governing contract the whole decision is read under — not a revocation authority specifically. Stretching `revocation_authority_ref`'s `authority_id` to also mean "the policy framework for this decision" would be exactly the kind of forced-fit overclaim this spec has refused elsewhere (see `EFFECTIVE_CALL_REBINDING_FAILED`'s note on not forcing unrelated cases through one invariant). Genuinely out of scope until a field for that is designed on its own terms. |
| `scope_amplified` | **NOT MODELED AS AN INVARIANT, data now available** | `delegation_chain_ref`'s `hops` already carry each hop's `scope` — an implementer holding the chain artifact could write this check themselves. `delegation-chain-ref.md` is explicit that it does not constrain scope narrowing as part of the spec's own invariants; this is unchanged, and this spec adds no invariant for it either. |

Three of seven move to something checkable by a third party holding the
named authority (not resolved by this verifier alone); one collapses
entirely; one is half-covered; two stay genuinely out of scope. Reported
this way, by `map_authority_at_dispatch.py`, rather than as a blanket "7
move" — the corpus's own checks (`authoritydispatch.CHECKS`) distinguish
these for a reason, and this spec's fields don't erase that distinction.

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
| `AUTHORITY_CHECK_ORDER_INVALID` (v1.3) | one or more of `authority_verified_at_ms`, `revocation_check_at_ms` is present in `decision_id`'s preimage, but the temporal order `authority_verified_at_ms ≤ revocation_check_at_ms ≤ ts_ms` does not hold. Does not resolve revocation or staleness itself — see "Gap — delegation, revocation and freshness" above. |

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
   (v1.1/v1.2)" below. Exempt when the envelope carries no `post_commit_ref`.
8. **authority_check_order** (v1.3, additive) — when `decision_id`'s preimage
   carries `authority_verified_at_ms` and/or `revocation_check_at_ms`, each
   present field must be ≤ `ts_ms`, and if both are present,
   `authority_verified_at_ms` ≤ `revocation_check_at_ms`. Exempt when neither
   field is present. See "Gap — delegation, revocation and freshness" above
   for what this does and does not prove.

## Post-commit divergence (v1.1/v1.2)

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
  "version": "execution-join-ref-v1",
  "dataset_sha256": "<sha256-hex, optional, v1.2>"
}
```

`post_commit_ref` is `SHA-256(JCS(post_commit_observation))`. The preimage's
`result_id` binds the observation to one specific terminal record — the
same "preimage must include the thing it is binding to" pattern `proof_ref`
and `decision_id` already use.

**`dataset_sha256`** (v1.2, optional, additive) — the content hash of the
external dataset or snapshot the observation was recomputed against, when
the thing being observed depends on a mutable external input (a price
table, a registry, anything outside the attempt itself). Purely
informational: it is never read by the `post_commit_consistency` rule
below, and its absence is not itself a finding, same as every other
optional field in this spec. What it buys a reader: without it, "the
responder changed what it does" and "an upstream dataset was corrected
(expected, and the correction is itself anchored)" produce the identical
signal — an `observed_hash` that no longer matches `output_hash`. With it,
a reader comparing two observations of the same result_id that disagree
can already tell, from the signed observation alone, whether `dataset_
sha256` also changed, without fetching or trusting the full recomputed
payload. This spec does not define a matching field on the settlement side
(`result_id`'s own preimage does not declare which dataset the original
attempt used) — see the "known gap" note in `examples/conformance/
execution-join-ref/horizon-shield-pilot-case-e/README.md`.

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

**AUTHORITY_CHECK_ORDER_INVALID** (v1.3) — `decision_id`'s preimage carries
`revocation_check_at_ms` earlier than `authority_verified_at_ms`, or either
field later than `ts_ms`. A revocation check cannot precede the authority
verification it depends on, and neither can happen after the decision they
claim to support. Invariant 8 fails. Does not resolve whether the
underlying grant was actually revoked or stale — only that the record's own
claimed order of events is incoherent.

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
  execution-join-ref/horizon-shield-pilot-case-e/` proposes `post_commit_
  consistency` as a fourth, complementary case for the live pilot scoped in
  `ogasurfproject-jpg/horizon-shield#51` — the JCCDB cost database an
  accepted estimate was audited against changing after acceptance. Named
  Case E, not D (astrogilda's case already holds that letter in the issue).
  ogasurfproject-jpg's review of it is also what prompted `dataset_sha256`
  above (v1.2).
