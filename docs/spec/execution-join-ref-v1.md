# execution-join-ref-v1

An execution join binds the outcome of a tool call back to the exact guardrail
decision that authorized it. Four identifiers form a chain; each is a
SHA-256(JCS(canonical preimage)) computed at the moment described, not at
record time.

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

// decision_id
{
  "action_ref": "<sha256-hex>",
  "outcome": "permit | deny | defer",
  "policy_id": "<string>",
  "ts_ms": <integer>,
  "version": "execution-join-ref-v1"
}

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

## Invariants

A verifier checks these in order; the first failure is the reported
failure_mode:

1. **canonical_envelope** — every ref is SHA-256(JCS(its declared preimage)).
2. **chain_integrity** — decision_id preimage includes this action_ref;
   result_id preimage includes this attempt_id; proof_ref preimage (if present)
   includes this attempt_id.
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
   fails this check.

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
the rewritten preimage before the runtime crosses the boundary.

## Relationship to existing primitives

- `action-ref-v1` — action_ref is the same primitive; this spec composes it
  into a multi-step chain.
- `anchoring-precedence-ref-v1` — optional outer layer; block_time must
  precede result_id ts_ms when anchoring is applied.
- `release-gate-ref-v1` — the release gate opens on decision_id; the join
  contract closes the loop from decision to outcome.
