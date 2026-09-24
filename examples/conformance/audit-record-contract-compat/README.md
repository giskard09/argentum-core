# Compat vectors: MCP SEP-3004 (Tamper-Evident Audit Record Contract)

Prior art: [modelcontextprotocol/modelcontextprotocol#3004](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/3004)
— "Tamper-Evident Audit Record Contract" (Standards Track SEP, Scott Rhodes /
Notboatanchor Labs, co-authored with Syed Maaz Ahmed / Interlock and Alfredo
Metere / Enclawed LLC). Specifies a canonical byte form (sorted-key JSON), a
type-keyed `extensions` mechanism, and an append-only SHA-256 hash chain for
audit records, with a fixed cross-implementation known-answer digest pinned in
the PR text.

**Correction (2026-09-24).** Vectors 4–5 (boundary anchoring) stated
`outcome_ts_ms: 1749211200000` as taken from the record's `occurred_at`
(`2026-06-06T12:00:00.000Z`). That value is 2025-06-06T12:00:00.000Z, one year
earlier, and the two anchor times (`1749211500`, `1749211100`) were offset from
it. They now read `outcome_ts_ms: 1780747200000` (the record's actual
`occurred_at`), with anchors at `1780747500` (300 s after, existence only) and
`1780747100` (100 s before, precedence). The offsets are unchanged, so both
outcomes are too: vector 4 is still FAIL on `anchoring_precedence` and vector 5
still PASS. No digest depends on these fields. The same four values are
corrected in `../conformance-export.json` and `../conformance-vectors.json`.
The error dates from commit 4cd11b6 (2026-07-08). It was found with this
repository's own probe (`tools/probe_expected_flip.py`, pull request 105).

## What this reproduces

**1. Known-answer digest.** SEP-3004 §Conformance publishes a two-extension
record and states its SHA-256 as `f733fed9…`. Reproduced here with a runner
written independently from the SEP's own rule text (§2.1–§2.4 of the PR diff),
not from either implementation it cites (the GIF reference implementation or
Interlock's runtime-security implementation). The single-extension form of the
same record (`caller-governance` only) reproduces the SEP's separately-stated
`d494769c…` digest as a byproduct of building vector 2 — a second, independent
confirmation against the published text.

**2. `action_ref` join.** SEP-3004's protected core (§2.1) gives every record
an `event_id` — an opaque id "unique within the chain," not independently
recomputable by a party without access to that chain. `action_ref`
([`docs/spec/action-ref.md`](../../../docs/spec/action-ref.md)) is a
content-addressed identifier for the same class of event (agent, action type,
scope, RFC 3339 timestamp), computable by any party holding the four preimage
fields with no access to the chain that produced the audit record. The vector
set shows both computed from the same tool-call event, and a negative: a 1ms
`occurred_at` drift moves both `event_hash` and `action_ref` together — the
two constructions carry the same field sensitivity, expressed through
different preimages for different purposes (chain-scoped integrity vs.
cross-producer correlation).

**3. Boundary anchoring.** SEP-3004 §2.8 explicitly reserves and defers
external anchoring: "Anchoring a chain to an external witness... addresses a
distinct, weaker-priority threat... orthogonal to the within-system chain
construction." The hash chain (§2.4–2.6) proves internal consistency —
tamper-evidence within the record set — not existence-in-time or precedence
relative to an outside event. [`../anchoring-precedence-ref/`](../anchoring-precedence-ref/)
already draws this distinction for Mycelium trails (`anchoring_existence` vs.
`anchoring_precedence`, strict `anchor_block_time * 1000 < outcome_ts_ms`);
vectors 4–5 here apply the same split to a SEP-3004 chain head. A verifier
checking only chain integrity cannot see the gap between an anchor that
exists and one that precedes.

## Run

```
python3 verify.py      # zero-dependency, offline
```

## Files

- [`verify.py`](./verify.py) — computes all five vectors from source, no
  fixture dependency beyond this directory.
- [`vectors.json`](./vectors.json) — the fixed records, digests, and
  `action_ref` preimages, for reproduction outside this runner.
