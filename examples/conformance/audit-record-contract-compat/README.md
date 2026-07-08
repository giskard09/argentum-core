# Compat vectors: MCP SEP-3004 (Tamper-Evident Audit Record Contract)

Prior art: [modelcontextprotocol/modelcontextprotocol#3004](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/3004)
— "Tamper-Evident Audit Record Contract" (Standards Track SEP, Scott Rhodes /
Notboatanchor Labs, co-authored with Syed Maaz Ahmed / Interlock and Alfredo
Metere / Enclawed LLC). Specifies a canonical byte form (sorted-key JSON), a
type-keyed `extensions` mechanism, and an append-only SHA-256 hash chain for
audit records, with a fixed cross-implementation known-answer digest pinned in
the PR text.

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
