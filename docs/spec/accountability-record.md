# accountability-record

A name for something that already exists across four separate specs in this
repo. Nothing here is a new primitive, a new digest, or a new field — it is
the index that lets someone cite "the accountability record for this
action" as one object instead of four separately-discovered documents.

## Why this doc exists

Four primitives in this repo answer four different questions about the same
underlying action, and each was built and shipped independently, at
different times, for different immediate reasons:

- **What was decided, and on what basis.**
- **What happened, and does the outcome trace back to the decision without a gap.**
- **Who signed it, and under what trust model.**
- **When was it committed, relative to the outcome — not just that a commitment exists.**

Each question has its own spec, its own preimage shape, and its own digest.
None of them reference each other by name in a single place. A reader who
wants the full evidentiary picture for one action currently has to already
know all four spec names to go find them. This doc is that map.

## The four layers

| Layer | Question it answers | Spec | Digest field |
|---|---|---|---|
| Authorization | What was decided, and on what preimage | [`decision-binding-ref-v1.0.md`](decision-binding-ref-v1.0.md) | `decision_binding_ref` |
| Execution lineage | Does the terminal outcome trace back to the exact decision that authorized it, through every retry | [`execution-join-ref-v1.md`](execution-join-ref-v1.md) | `action_ref` → `decision_id` → `attempt_id` → `result_id` |
| Signer trust | Who signed the record, and under what key model (single operator key, agent-held key, TEE attestation, or M-of-N threshold) | [`signing-trust-ref.md`](signing-trust-ref.md) | `signing_trust_ref` |
| Temporal precedence | Did an external, independently verifiable commitment precede the outcome, not follow it | [`anchoring-precedence-ref-v1.md`](anchoring-precedence-ref-v1.md) | `anchoring_precedence_ref` |

Each layer is independently recomputable by a verifier that holds only that
layer's preimage fields — none of the four requires trusting any other
layer to be checked. That independence is deliberate: a verifier can adopt
one layer without the other three, and a record can carry all four without
any of them collapsing into a single point of failure.

## How they compose on one action

The four digests are not fields inside one shared envelope — they are
separate content-addressed objects that reference each other by including
the relevant identifier in their own preimage (`execution-join-ref-v1`'s
`decision_id` preimage includes `action_ref`; a `signing-trust-ref` names
the `action_ref` it covers). A verifier walks the chain by resolving each
digest in turn, recomputing it, and confirming it names the next one — the
same single-authority-path pattern used inside
[`governance-block-join-ref-v1.md`](governance-block-join-ref-v1.md),
applied here across specs instead of within one.

Two concrete instances already in this repo's conformance sets show the
layers in production use, independently of each other:

- **Threshold signing in production.** `examples/conformance/signing-trust-ref/signing-trust-ref-v1.fixture.json` carries a `multi_party` vector: `signer_id = "tkc:2-of-3:<key1>;<key2>;<key3>"` — a 2-of-3 threshold assertion where no single signer can forge the record. It covers a real `action_ref` from the `presidio-x402` fixture set.
- **Precedence in production.** `examples/conformance/anchoring-precedence-ref/vectors.json`, vector `precedence-positive-001`: production trail `b4377bcd-7342-4f7d-bdb3-daf41201bd47`, on-chain Arbitrum anchor preceding the outcome by a 599-second margin, all five `anchoring-precedence-ref-v1` invariants passing.

These are cited here as evidence that each layer is not theoretical — not
as a claim that a single action currently carries all four layers stitched
together. Composing all four on one action is a valid next step, not
something this doc asserts has already happened.

## What this doc is not

- Not a new preimage shape, not a new digest, not a new failure-code table.
  Each linked spec keeps its own.
- Not a replacement for any of the four specs — this is the index, they
  remain the source of truth for their own invariants.
- Not a claim of exclusivity or priority over any external work. This is
  an internal consolidation of primitives already shipped in this repo,
  named so they can be cited as one thing when the full picture is what's
  relevant.
