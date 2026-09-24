# trail-head-window-ref

Vectors for the "Window verification" section of [trail-head-ref-v1](../../../docs/spec/trail-head-ref-v1.md): a log presented from seq k > 1.

- `vectors.json`: 11 vectors. `input` holds the arguments of `verify_trail`; `expected` holds `verdict`, `completeness`, `reason` and `window_anchor`, all scored.
- `build.py`: rebuilds `vectors.json` deterministically with the reference producer. Expected results are written by hand from the spec, not computed by the verifier.
- `verify.py`: scores the reference verifier, then runs an anchor-blind mutant (a verifier that ignores the anchor) and requires it to fail at least one vector.

What the set pins down:

- A window without an anchor or a checkpoint is `continuity_only` with `window_anchor: "uncertified"`, including when it was re-chained from a start the presenter chose (thw-006, a documented limit).
- A certified anchor catches that rewrite (thw-007); so does a tail checkpoint (thw-008).
- A window never gets `complete`: sealed, it is `window_complete` / `proven_from_seq` (thw-005).
- A full log missing its first records stays a `seq_gap` unless the caller declared a window (thw-011).
- Full-log results are unchanged (thw-001, thw-002).

Surfaced by an internal cross-check against independent session-chain data verified from a mid-log entry.
