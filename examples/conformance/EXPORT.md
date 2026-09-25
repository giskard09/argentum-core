# conformance-export.json — aggregated vector export

`conformance-export.json` bundles every conformance vector set in this directory into one
self-contained file: 71 sets (2026-09-24), each with its original `vectors.json`/`*.fixture.json` (and
any supporting data files — JWS/JWKS/payload fixtures, manifests) preserved byte-for-byte
under `sets.<id>.files`. A verifier does not need to know this repo's internal directory
structure to find and re-run any set.

Regenerate with:

```bash
python3 build_export.py
```

## Public file

The public file is `conformance-vectors.json`, built from this export by
`build_conformance_vectors.py` (same `sets`, plus `contract` and
`recomputation_procedure`) and served at `/.well-known/conformance-vectors.json`.
Each set's `files` map is the original JSON, untouched.

## Excluded from the export

- `action-ref-v1-cross-surface/` — a doc-consistency checker (`check_scope_policy.py`),
  not a vector set: it diffs `docs/spec/action-ref.md`'s field table against its prose
  across git refs, no inputs/expected-output pairs to aggregate.
- `node_modules/`, `package.json`, `package-lock.json` (present only under
  `agenttrust-v1/`) — npm tooling, not conformance data.
- `README.md`, `build_export.py`, `EXPORT.md`, `conformance-export.json` itself, and
  `conformance-vectors.json` (built from this export).
- Files not tracked by git (a local `venv/`, scratch output): only `git ls-files` is exported.
