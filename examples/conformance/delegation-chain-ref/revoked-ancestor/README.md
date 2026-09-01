# delegation-chain-ref · revoked-ancestor

A differential vector requested by MoltyCel (AAE conformance vectors author,
x402#2332): the same `chain_artifact`/`leaf_preimage` verified twice — once
alone, once alongside a `revocation_artifact` that revokes the mid-chain
ancestor hop (`hops[1]`, `pioneer-agent-001 -> lightning`) before the leaf
action's timestamp.

## What it exercises

3-hop chain, `mycelium:payment` scope throughout:

```
giskard-self -> pioneer-agent-001 -> lightning -> soma-agent
```

`hops[1]`'s delegation (`pioneer-agent-001` delegating to `lightning`) is
revoked at `2026-08-15T09:00:00.000Z`, before the leaf action executes at
`2026-09-01T12:00:00.000Z`. The two vectors carry byte-identical
`chain_artifact` and `leaf_preimage` — the only difference between them is
whether a `revocation_artifact` for the ancestor hop exists alongside the
submission.

## Result

Both vectors PASS with an empty failure list. `run verify.py` prints an
explicit differential check confirming `baseline verdict == with-revocation
verdict -> True`.

This is not a bug in the reference verifier — it is the documented "what it
does not do" from `docs/spec/delegation-chain-ref.md`:

> `delegation_chain_ref` does not validate that individual delegation
> artifacts are still in force (see `revocation-ref.md` for invalidation).

`delegation_chain_ref`'s six invariants (`chain_continuity`, `root_anchoring`,
`leaf_anchoring`, `monotonic_scope_narrowing`, `hop_signature_valid`,
`replay_detected`) are computed entirely from `chain_artifact` and
`leaf_preimage`. Neither `revocation_ref` nor `revoked_action_ref` enters
`delegation_chain_ref`'s hash or any invariant check — a verifier holding
only this spec's tooling has no way to know a chain contains a revoked
ancestor unless it separately cross-references `revocation-ref.md` records,
which `revocation-ref.md` itself does not define how to do for an ancestor
mid-chain (see the note on `revoked_action_ref` below).

## `revoked_action_ref` targets a `delegation_ref`, not an `action_ref`

`revocation-ref.md`'s schema anchors `revoked_action_ref` to a trail action's
`action_ref` (invariant 3: "links back to the delegation" via the action that
*used* it). This vector's `revocation_artifact` instead points
`revoked_action_ref` directly at `hops[1].delegation_ref` — the delegation
grant itself, not an action that consumed it — because
`delegation-chain-ref.md` does not yet define what an ancestor-in-a-chain
revocation event should reference. That is a separate, still-open modeling
question from the one this vector demonstrates: regardless of what
`revoked_action_ref` points at, the chain verifier does not look at it.

## What changed in the spec because of this

`docs/spec/delegation-chain-ref.md` gained a new section, "Revocation and
already-committed hops (default model)", naming explicit default behavior for
implementers who do not define their own policy: hops that already executed
stay valid; a revoked ancestor blocks only future use of the chain, not
retroactive invalidation of what already closed. This is the same treatment
already given to `OUT_OF_PROFILE_DOMAIN` elsewhere in the spec suite — a
declared limit, not a fix, since fixing would require the chain verifier to
grow a real revocation-checking invariant, which is out of scope here.

## Run

```
python verify.py
```

Expected: `2/2 passed`, with the differential check printing `True`.

## Provenance

Gap identified by MoltyCel (x402#2332) via a differential test comparing this
verifier's verdict against AAE's own verifier on the same preimage with an
ancestor revoked. Confirmed against `docs/spec/delegation-chain-ref.md:15`
("does not validate that individual delegation artifacts are still in
force... implementer's policy") and `docs/spec/revocation-ref.md` (103 lines,
no ancestor/cascade semantics defined) before treating the gap as real.
