# verdict-ref-v1 — binding action_ref to an independent judgment

Answers a specific gap: does an action_ref-anchored record ever carry a
third party's judgment on whether *this instance* was sound, or is
admission strictly self-attested?

Today it's self-attested. `authorization_ref` and the freshness fields
(`authority_verified_at_ms`, `revocation_check_at_ms` — [action-ref.md §4.2](../../../docs/spec/action-ref.md))
prove the delegation chain was valid and current at admission. None of them
carry an independent party's verdict on the instance itself.

`verdict_ref` is an optional envelope-adjacent field that closes that gap
without touching the four-field preimage:

```
verdict_ref = SHA-256(JCS(verdict_object))
verdict_object = {action_ref, confidence, issuer_id, ts_ms, verdict}
```

Two checks, not one:

1. **Recomputability** — anyone with the verdict object recomputes
   `verdict_ref` byte-identical, same as any other content-addressed field
   in this spec family.
2. **Independence** — `verdict.issuer_id != action_ref.preimage.agent_id`.
   A verdict object that hashes correctly but was issued by the same agent
   it judges is not conformant (`vr-003`, `VERDICT_ISSUER_NOT_INDEPENDENT`).
   Hash validity and independence are separate checks — matches the
   pattern in [`composition-ref-v1`](../composition-ref-v1.fixture.json),
   where non-conformant vectors still recompute correctly and fail on a
   semantic invariant instead.

Independence gates conformance, not the verdict's outcome: `vr-004` shows
an independent `reject` is exactly as conformant as an independent
`approve` (`vr-002`). A scheme that only accepted independent citations on
favorable verdicts would let the subject agent suppress unfavorable ones
by omission.

## Relationship to agentoracle-v1

[`agentoracle-v1`](../agentoracle-v1/) already ships the other direction:
a pre-action gate receipt (`verification.v0.3`) embeds `action_ref` as a
forward pointer from the verdict to the action it authorizes. `verdict-ref-v1`
is the reverse binding — the action's own envelope citing the verdict that
judged it. Both directions are now conformance-covered; together they let a
verifier walk the join in either order without trusting either issuer.

## Run

```
python3 verify.py
```

Exits with a full pass printed per vector; raises on the first mismatch or
independence-invariant violation.
