# Composed profile: admission + recompute + chain-fork + fork-matrix

Requested by rpelevin on [autogen#7353](https://github.com/microsoft/autogen/issues/7353)
(2026-07-03): "the useful next conformance step seems to be composing the two properties
that are now being tested separately... a self-signed ALLOW, a verdict that does not
recompute, and a same-sequence fork should fail for different reasons, but the composed
profile should catch all three."

Axis 4 adds pshkv's fork-matrix (same thread, 2026-07-03): formalizing the chain-fork
property as four separately-checkable requirements instead of one demo run — determinism,
branch-fork detection, anti-replay across chain context, and a verifier that reports both
competing heads as structured data instead of a collapsed boolean.

## The two properties this composes

- [`../presidio/`](../presidio/) — is a payment **decision** entitled to its own verdict?
  Two negatives: **admission** (signer independence — a decision signed by the actor's own
  wallet is self-approval, not a second opinion) and **recompute** (the recorded verdict
  must re-derive from its own cited controls, `verdict = f(controls)`, not just carry a
  valid signature). Source fixture:
  [`presidio-x402-decision-ref-v1.fixture.json`](../presidio/presidio-x402-decision-ref-v1.fixture.json)
  (contributed by presidio-v, PR [#29](https://github.com/giskard09/argentum-core/pull/29)).
- **chain-fork** — does the **receipt history** become fork-detectable, not just
  individually-anchored? `head_hash = sha256(content_hash + "|" + prev_head_hash)`. A fork
  is two conflicting, independently-computable heads at the same sequence position — not
  something a verifier has to take the server's word for.

## What "composed" means here

Take the accepted decision (`presidio-x402-decision-001`), commit it as a chain entry, then:

1. **Predictability** — recomputing from the identical content + prior head reproduces the
   identical `head_hash`, deterministically.
2. **Fork detection** — a divergent entry at the *same sequence position* (same
   `prior_head`, different content) produces a *different* `head_hash`. Both heads remain
   independently computable from their own content, so a server showing head A to one party
   and head B to another is caught by comparing recomputed heads against what was published
   — not hidden by a silent overwrite.

`verify.py` runs all three failure modes together and reports which axis each one fails on:

| Vector | Admission | Recompute | Fails on |
|---|---|---|---|
| `presidio-x402-decision-001` (accepted) | ✓ independent | ✓ recomputes | — (the starting point) |
| `presidio-x402-decision-signer-equals-runtime` | ✗ self-signed | ✓ recomputes | **who** signed it |
| `presidio-x402-decision-verdict-not-recomputable` | ✓ independent | ✗ doesn't recompute | **whether** the verdict follows from its inputs |
| divergent same-sequence chain entry | — | — | **where** two conflicting heads meet at one position |

Three distinct, individually-diagnosable failure reasons — not one pass/fail bit.

## Axis 4 — pshkv's fork-matrix

Same `head_hash` construction, checked as four independent properties instead of one
demo run:

| Property | Check |
|---|---|
| (a) determinism | same `content_hash` + same `prior_head` → same `head_hash` |
| (b) branch fork | same sequence position + different `prior_head` → detectable conflict between two competing lineages |
| (c) anti-replay | same payload (`content_hash`) under a different chain context → different `head_hash` |
| (d) structured report | the verifier returns `{sequence_position, heads, prior_heads, conflict}` — never a bare boolean, so corruption, replay, and legitimate branch divergence stay distinguishable |

```
python3 verify.py      # zero-dependency, offline
```

## Independent verification

[babyblueviper1/preaction-governance-conformance](https://github.com/babyblueviper1/preaction-governance-conformance),
`examples/composed-decision-chain-recompute/`, built and shipped the same composed profile
— including Axis 4 — against the same source fixture (byte-identical
`presidio-x402-decision-ref-v1.fixture.json`, this repo is the origin of that file). Both
implementations — this one written independently from the construction description, not
copied — produce byte-identical `head_hash` values:

| Vector | `head_hash` |
|---|---|
| Chain entry A (accepted decision, entry 41, prior_head) | `03d92bae7842b00f8da7fae256abbb8db40c18f532547b2e10a56267e408ce77` |
| Chain entry B (divergent, same sequence, same prior_head) | `e68a162f7b1b9a380a82600f8df312fb0ba21579e664df525edf92a27f5d37d0` |
| Axis 4b branch fork, lineage y (entry 41, prior_head_alt) | `1e1664b322c96c98e261b4776a2f9ba42be245e2f56b1c339479b94a53152a6b` |

See [`vectors.json`](./vectors.json) for the full construction and
`independent_verification` block.
