# conformance-export.json — aggregated vector export

`conformance-export.json` bundles every conformance vector set in this directory into one
self-contained file: 61 sets, each with its original `vectors.json`/`*.fixture.json` (and
any supporting data files — JWS/JWKS/payload fixtures, manifests) preserved byte-for-byte
under `sets.<id>.files`. A verifier does not need to know this repo's internal directory
structure to find and re-run any set.

Regenerate with:

```bash
python3 build_export.py
```

## What this is NOT yet

- **No public route.** Not served at `.well-known/` or any other public path yet. Whether
  it becomes `.well-known/conformance-vectors.json` or matches Kenneives/CTEF's
  `agentgraph.co/.well-known/cte-test-vectors.json` pattern is an open decision — deferred
  on purpose so the ecosystem converges on one discovery convention instead of two
  (trigger: A2A#1628, Kenneives proposed aligning `verify-failure-mode-ref-v1` with CTEF).
- **No renamed fields.** Each set's `files` map is the original JSON untouched. Once a
  discovery convention is picked, a thin adapter layer maps these into whatever field
  names/shape that convention expects — this export is the raw material, not the final
  public schema.

## Excluded from the export

- `action-ref-v1-cross-surface/` — a doc-consistency checker (`check_scope_policy.py`),
  not a vector set: it diffs `docs/spec/action-ref.md`'s field table against its prose
  across git refs, no inputs/expected-output pairs to aggregate.
- `node_modules/`, `package.json`, `package-lock.json` (present only under
  `agenttrust-v1/`) — npm tooling, not conformance data.
- `README.md`, `build_export.py`, `EXPORT.md`, `conformance-export.json` itself.
