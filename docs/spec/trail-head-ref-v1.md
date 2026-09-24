# trail-head-ref-v1 — Specification

**Stable tag:** `trail-head-ref-v1`
**Status:** draft — reference implementation and tests only. Not yet emitted by Mycelium's production trail pipeline; nothing in this document describes a live deployment.
**Reference implementation:** [`plugins/agt_evidence_anchor/trail_head.py`](../../plugins/agt_evidence_anchor/trail_head.py)
**Tests:** [`plugins/agt_evidence_anchor/tests/test_trail_head.py`](../../plugins/agt_evidence_anchor/tests/test_trail_head.py)

---

## What is trail-head-ref

`action_ref` and [batch anchoring](batch-anchor.md) prove that a given trail record existed and was not altered. They do not prove that a presented list of records is the *whole* list. Drop one record, swap two, or cut the tail, and every record that remains still verifies on its own.

`trail-head-ref-v1` adds that missing property for one agent's trail, in two layers, without changing `action_ref`:

1. **Continuity** — a per-agent hash chain. It detects a removed or reordered record.
2. **Completeness** — a periodic checkpoint of the chain head, anchored on-chain. It detects a truncated tail, which continuity alone cannot see: a genuinely shorter log and a truncated one have identical internal structure.

The split between the two properties, and the attacks used to test them, come from [microsoft/autogen#7353](https://github.com/microsoft/autogen/issues/7353): Yarmoluk's distinction between "the records included" and "every action recorded" and his removal/reorder test; babyblueviper1's tail-truncation test run against a live chain, and his point that a count signed by the same key that signs the log adds no independence; TKCollective's gapless per-session sequence number. The rule that an empty period still seals is from [x402-foundation/x402#2887](https://github.com/x402-foundation/x402/issues/2887) (stillmarcus24): otherwise silence and a dead log are the same bytes.

---

## Entry

Each record in an agent's trail gets a `seq` (integer, starting at 1, no gaps) and a `head`:

```
head = SHA-256(JCS({
  "v":          "trail-head-ref/v1",
  "agent_id":   <agent_id>,
  "seq":        <integer >= 1>,
  "action_ref": <64 lowercase hex, action-ref.md v1>,
  "prev_head":  <head of seq-1>        -- absent at seq 1, present at every later seq
  "agent_seq":  <integer >= 1>         -- OPTIONAL, see "Agent-side counter"
}))
```

`prev_head` is **omitted** at seq 1, never `null` or `""`: either would change the JCS bytes. JCS is RFC 8785 (`jcs.py`).

## Checkpoint

At the end of every period (the period length is a deployment parameter, e.g. one hour), the operator emits one checkpoint per agent that has at least one record:

```
checkpoint = {
  "v":          "trail-head-ref/v1/checkpoint",
  "agent_id":   <agent_id>,
  "period_end": <RFC 3339 UTC, e.g. "2026-09-23T18:00:00.000Z">,
  "seq":        <seq of the agent's last record>,
  "head":       <head of that record>
}
checkpoint_digest = SHA-256(JCS(checkpoint))
```

A checkpoint MUST be emitted for every period, **including periods in which the agent recorded nothing**: it then repeats `seq` and `head` with a later `period_end`. Because a checkpoint is expected every period, a missing one is itself evidence (the log stopped being witnessed), instead of being indistinguishable from an idle agent.

## Sealing a period

All checkpoints of one period are sorted by `agent_id` and committed under one Merkle root with the construction of [batch-anchor.md](batch-anchor.md) (leaves are `checkpoint_digest` values; `plugins/agt_evidence_anchor/merkle.py`, unchanged). The root is anchored with `AnchorRegistry.anchor(bytes32)`, like any other root. One checkpoint per agent per period; all checkpoints in a seal share one `period_end`.

Once the root is on-chain, the operator can no longer serve a history shorter than, or different from, what it committed to for that period. The high-water mark lives on a public chain, not under a key the operator controls.

---

## Verification

Input: the agent's records from seq 1 in presented order, and optionally a checkpoint with its Merkle proof and the period root.

Checks run in this order; the first failure decides the verdict. Each failure has its own `verdict`/`reason`, so a verifier reports *which* attack it saw, not only that it rejected.

| # | Check | Verdict | Reason |
|---|-------|---------|--------|
| 1 | Records are well formed and share one `agent_id` | `malformed` | `empty_or_not_a_list`, `entry_shape`, `agent_mixed`, `entry_preimage` |
| 2a | The seq set is 1..n but presented out of order | `broken` | `seq_order` |
| 2b | Each seq is the previous seq + 1 (a removed record leaves a gap) | `broken` | `seq_gap` |
| 2c | Each `head` recomputes from its own fields | `broken` | `head_mismatch` |
| 2d | Each `prev_head` equals the previous record's `head` (a removed record with the next one renumbered and re-hashed) | `broken` | `link_mismatch` |
| 3 | If any record carries `agent_seq`, all do, starting at 1 with no gaps | `agent_gap` | `agent_seq_partial`, `agent_seq_not_contiguous` |
| 4 | A checkpoint was supplied | `continuity_only` (completeness `not_evaluated`) | `no_checkpoint` |
| 5 | The checkpoint is well formed (`malformed`, `checkpoint_shape`), is for this agent, and its digest is included in the root | `checkpoint_unproven` | `checkpoint_other_agent`, `not_in_root` |
| 6 | The checkpoint is not older than the verifier's bound (optional) | `stale_checkpoint` | `checkpoint_too_old` |
| 7 | The log reaches the checkpoint's seq | `truncated` | `log_shorter_than_checkpoint` |
| 8 | The log's head at the checkpoint's seq equals the checkpoint's head (a log rewritten and re-chained after the fact) | `checkpoint_mismatch` | `head_differs_from_checkpoint` |

Positive verdicts:

| Verdict | Completeness | Meaning |
|---------|--------------|---------|
| `complete` | `proven` | The log ends exactly at the checkpoint. |
| `complete_unsealed_tail` | `proven_through_checkpoint` | Complete up to the checkpoint; the records after it are continuous but not yet externally witnessed. |

`continuity_only` is **not** a pass for completeness. A verifier that has no checkpoint knows the log was not altered internally and nothing about whether it is whole; it MUST report completeness as `not_evaluated`, never fold it into a positive result.

---

## Agent-side counter

The checkpoint witnesses what the operator wrote. It cannot show an action the operator never wrote: a record dropped at ingest, followed by a clean re-chain, produces a valid chain and valid checkpoints.

To close that, the agent MAY carry its own counter, `agent_seq`, inside the request it signs with its own key (Ed25519, verified at ingest as for any trail). The operator copies it into the entry preimage. A verifier that sees `agent_seq` on every record, starting at 1 with no gaps, knows that no signed action *between the first and the last one presented* was dropped before reaching the log; a gap is reported as `agent_gap`. A drop at the tail (the agent's most recent signed actions) leaves the remaining counters contiguous: only the agent, which knows its own last `agent_seq`, can see it, or a verifier that obtains that value from the agent.

This answers the independence question from autogen#7353 only under one condition: the agent's key is held by a party other than the operator. Then whoever can rewrite the log cannot re-sign the count. If the operator holds both keys, it can drop a record and re-sign a gapless count, so `agent_seq` adds no independence and completeness rests on the anchored checkpoint alone. The spec cannot establish who holds the agent's key; a verifier that relies on `agent_seq` for independence has to establish it separately. The reference module checks the sequence of `agent_seq` values it is given; checking the agent's signature over each one is the ingest step's job and is out of scope here.

*Correction (2026-09-24):* the previous text stated as a fact that the operator does not hold the agent's key. That holds only in deployments where a different party holds it; the paragraph above now states it as a condition. No code or vector changes.

---

## What this does NOT prove

- **That the root was anchored.** The module verifies inclusion in the root it is given (`root_anchoring: "not_checked"` in every result). The caller confirms the root on-chain with an AnchorRegistry query, as for any batch root.
- **That the checkpoint is the latest one.** Whoever presents the log could present an old checkpoint to hide a later truncation. The verifier MUST take the checkpoint from the anchor stream for the most recent period, not from the presenter. The optional staleness bound (check 6) limits how old an accepted checkpoint may be; it does not replace fetching the latest one.
- **Anything between the last checkpoint and now.** Records after the last seal are continuous but unwitnessed (`complete_unsealed_tail`). The period length is the window in which a tail cut is undetectable.
- **Actions never submitted.** Without `agent_seq`, an action the agent never sent, or one the operator dropped at ingest, leaves no trace. With `agent_seq`, only actions the agent itself signed are covered, and a drop of the agent's latest actions is visible only against the agent's own last counter.
- **The meaning or legitimacy of any record.** Same limits as [batch-anchor.md](batch-anchor.md) and [action-ref.md](action-ref.md).

---

## Cross-references

- [action-ref.md](action-ref.md) — the per-record digest used as `action_ref`.
- [batch-anchor.md](batch-anchor.md) — Merkle construction and anchoring of the period root.
- [verify-failure-mode-ref.md](verify-failure-mode-ref.md) — why distinct failure states are not collapsed.
- [custody-ref.md](custody-ref.md) — structural vs. organizational independence of keys.
