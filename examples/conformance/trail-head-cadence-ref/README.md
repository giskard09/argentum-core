# trail-head-cadence-ref

Vectors for the "Cadence ceiling" section of [trail-head-ref-v1](../../../docs/spec/trail-head-ref-v1.md): a consumer-declared upper bound on the gap between consecutive checkpoints of one agent.

- `vectors.json`: 14 vectors. `input` holds the arguments of `verify_checkpoint_cadence`; `expected` holds `verdict`, `reason` and the breach fields (`prev_period_end`, `period_end`, `gap_s`, `declared_max_period_s`), all scored.
- `build.py`: rebuilds `vectors.json` deterministically with the reference producer (`append_entry`, `make_checkpoint`). Expected results are written by hand from the spec, not computed by the verifier.
- `verify.py`: scores the reference verifier, then runs an agent-blind mutant (agent_id stripped from every input checkpoint) and requires it to fail at least one vector.

What the set pins down:

- The comparison is strictly greater-than: a gap equal to the ceiling passes (cad-003); one millisecond over fails (cad-010).
- The stream is sorted by `period_end` before comparing, so a breach the presented order hides still surfaces (cad-005); fewer than two checkpoints has no gap to measure (cad-006, cad-007).
- The first breach in sorted order is reported with the gap and the ceiling it exceeded (cad-002, cad-008).
- A stream that mixes agents is `malformed`/`agent_mixed` before any gap is measured (cad-014): interleaved checkpoints from two agents can mask a per-agent breach, so the mixed stream can never produce a positive outcome. This is the precondition the ceiling check verifies on its own input.
- Sealed empty periods behave like any other checkpoint (cad-009): an idle agent that still seals every period stays inside the ceiling.

Proposed by nmatt1 (paymnts) — surfaced by differential-testing an independent implementation of `verify_checkpoint_cadence`, where the interleave-masking precondition was found missing and reported upstream.
