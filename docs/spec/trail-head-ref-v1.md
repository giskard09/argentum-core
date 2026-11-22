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

## Cadence ceiling

The period length is a deployment parameter (see above), and the checkpoint rule above does not constrain it: an operator can declare an hour-long period, or a year-long one, and still satisfy "a checkpoint MUST be emitted for every period." A longer period does not break anything already specified — it only widens the window in which a tail cut is undetectable (see [What this does NOT prove](#what-this-does-not-prove)).

A consumer that needs an upper bound on that window declares one, `declared_max_period_s`, and checks it against the checkpoint stream:

```
verify_checkpoint_cadence(checkpoints, declared_max_period_s) -> ok | period_exceeds_declared_maximum
```

The check compares consecutive `period_end` values, sorted, against `declared_max_period_s`; a gap larger than the ceiling fails with `period_exceeds_declared_maximum`, independent of whether the checkpoints on either side of the gap are individually well formed. The ceiling is a consumer-side policy, not a property of the checkpoint itself: two consumers with different ceilings can disagree on the same stream, and both are right under their own bound.

*Added 2026-10-23*, following an independent implementation of this exact check against the gap named above ([google-agentic-commerce/AP2#290](https://github.com/google-agentic-commerce/AP2/issues/290), nmatt1).

*Updated 2026-10-26*: the same nmatt1, differential-testing their implementation against this one, found that the check never verified its own precondition — "one agent's checkpoint stream" — so an interleaved stream from two agents could each breach the ceiling alone while the merged, sorted gaps stayed under it. `verify_checkpoint_cadence` now rejects mixed `agent_id` values as `malformed`/`agent_mixed`, the same verdict `verify_trail` already uses for this class of input, before comparing any gaps.

## Sealing a period

All checkpoints of one period are sorted by `agent_id` and committed under one Merkle root with the construction of [batch-anchor.md](batch-anchor.md) (leaves are `checkpoint_digest` values; `plugins/agt_evidence_anchor/merkle.py`, unchanged). The root is anchored with `AnchorRegistry.anchor(bytes32)`, like any other root. One checkpoint per agent per period; all checkpoints in a seal share one `period_end`.

Once the root is on-chain, the operator can no longer serve a history shorter than, or different from, what it committed to for that period. The high-water mark lives on a public chain, not under a key the operator controls.

---

## Verification

Input: the agent's records from seq 1 in presented order, and optionally a checkpoint with its Merkle proof and the period root. A log presented from seq k > 1 is a window: see [Window verification](#window-verification) for the extra input and results.

Verifier input and result (names as in the reference module and the vectors):

```
input = {
  "entries":      [<record>, ...],        -- presented order
  "from_seq":     <integer >= 1>          -- 1 (default) for a full log, k for a window
  "checkpoint":   <checkpoint>,           -- OPTIONAL, completeness
  "proof":        [<hex>, ...],           -- its Merkle proof
  "root":         <hex>,                  -- its period root
  "anchor":       <checkpoint at k-1>,    -- OPTIONAL, window only
  "anchor_proof": [<hex>, ...],
  "anchor_root":  <hex>
}
result = {
  "verdict":        <see the tables>,
  "completeness":   "proven" | "proven_through_checkpoint" | "proven_from_seq"
                    | "proven_from_seq_through_checkpoint" | "not_evaluated" | "failed",
  "reason":         <see the tables, null on a positive verdict>,
  "at_seq":         <seq where the failure was seen, or null>,
  "from_seq":       <k>,                  -- every result that reaches check 4
  "window_anchor":  "genesis" | "certified" | "uncertified",
  "root_anchoring": "not_checked"
}
```

Checks run in this order; the first failure decides the verdict. Each failure has its own `verdict`/`reason`, so a verifier reports *which* attack it saw, not only that it rejected.

| # | Check | Verdict | Reason |
|---|-------|---------|--------|
| 1 | Records are well formed and share one `agent_id` | `malformed` | `empty_or_not_a_list`, `entry_shape`, `agent_mixed`, `entry_preimage` |
| 2a | The seq set is 1..n but presented out of order | `broken` | `seq_order` |
| 2b | Each seq is the previous seq + 1 (a removed record leaves a gap) | `broken` | `seq_gap` |
| 2c | Each `head` recomputes from its own fields | `broken` | `head_mismatch` |
| 2d | Each `prev_head` equals the previous record's `head` (a removed record with the next one renumbered and re-hashed) | `broken` | `link_mismatch` |
| 2e | Window only: the anchor is well formed, is for this agent, is included in its root, and is at seq k-1; the first record's `prev_head` equals its `head` | `anchor_unproven` / `anchor_mismatch` | `anchor_shape`, `anchor_other_agent`, `anchor_not_in_root`, `anchor_not_adjacent` / `prev_head_differs_from_anchor` |
| 3 | If any record carries `agent_seq`, all do, starting at 1 (window: any start) with no gaps | `agent_gap` | `agent_seq_partial`, `agent_seq_not_contiguous` |
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

A window gets `window_complete` (`proven_from_seq`) and `window_complete_unsealed_tail` (`proven_from_seq_through_checkpoint`) instead: see below.

`continuity_only` is **not** a pass for completeness. A verifier that has no checkpoint knows the log was not altered internally and nothing about whether it is whole; it MUST report completeness as `not_evaluated`, never fold it into a positive result.

The outcomes of this table and of the window tables, and the rule that an unevaluated state is never a pass, are collected in one place in [Outcome vocabulary](#outcome-vocabulary).

---

## Window verification

A verifier may be given only part of a log: the records from seq k > 1 on, for example the entries of one session. The first record of a window carries a `prev_head` that points outside it. Nothing in the window can certify that value: it comes from the records, and the records are what is being checked. Whoever rewrites a window can re-chain it from any `prev_head` it chooses, and the result has the same internal structure as the honest window.

The caller declares the window (`from_seq = k`). A verifier never infers it from the lowest seq presented: a full log missing its first records is a `seq_gap` at the first seq present, not a window.

Optional extra input: an **anchor**, a checkpoint at seq k-1 with its Merkle proof and period root. It is checked like the completeness checkpoint (shape, agent, inclusion; check 2e), and the caller takes it from the anchor stream, as for any checkpoint, never from whoever presents the window. It must be at seq k-1 exactly (`anchor_not_adjacent` otherwise) and the first record's `prev_head` must equal its `head` (`anchor_mismatch`, `prev_head_differs_from_anchor`).

Continuity (checks 2a-2d) runs from seq k. `agent_seq`, if present, must be contiguous inside the window; its starting value is not checked, since the anchor does not carry it. Every result that reaches check 4 reports its scope: `from_seq` and `window_anchor`, one of `genesis` (k = 1), `certified` (an anchor was checked) or `uncertified` (a window without an anchor).

`window_anchor: "uncertified"` is a warning state, not a weak pass: it says the window's start could not be certified at all, not that it was certified to a lesser degree. A consumer that reads only `completeness: "continuity_only"` and pattern-matches on "continuity" can mistake the pair for an acceptable result; both fields have to be read together, and `uncertified` on its own is a reason to withhold trust in the start, not to grant it.

*Clarified 2026-10-23* ([google-agentic-commerce/AP2#290](https://github.com/google-agentic-commerce/AP2/issues/290), nmatt1): a forged window without an anchor returns exactly this pair, and the verdict string alone could otherwise read as a pass to a consumer that only checks `continuity_only`.

| Input | Completeness result |
|-------|---------------------|
| No completeness checkpoint | `continuity_only`, `not_evaluated`, whatever the anchor. With an uncertified start, a window re-chained from a chosen `prev_head` is indistinguishable from the honest one; `window_anchor: "uncertified"` says so. |
| Checkpoint older than the window (its seq < k) | `continuity_only`, `not_evaluated`, reason `checkpoint_before_window`: nothing presented is sealed. |
| Checkpoint at seq >= k | Checks 7 and 8 against the window; if both hold, `window_complete` / `window_complete_unsealed_tail`. |

A matching checkpoint head at seq c >= k commits, through the chain, to every window record up to c **and** to the window's first `prev_head`, so it certifies the start transitively even without an anchor. It says nothing about seq < k. That is why a window never gets `complete`: its positive verdicts are separate (`proven_from_seq`, `proven_from_seq_through_checkpoint`) and carry `from_seq`, so a reader cannot take them for a result about the whole log.

The anchor matters when there is no completeness checkpoint for the window (the window is newer than the last seal): it is then the only thing that catches a rewrite that also moved the start.

*Added 2026-09-24:* surfaced by an internal cross-check against independent session-chain data verified from a mid-log entry. Earlier text defined verification only from seq 1. Existing results for full logs are unchanged; they now also report `from_seq: 1` and `window_anchor: "genesis"`. Vectors: `examples/conformance/trail-head-window-ref/`.

---

## Outcome vocabulary

*Added 2026-11-21.* This section collects, under this document's own names, the outcomes defined in [Verification](#verification) and [Window verification](#window-verification), and states in one place the rule they already follow. It adds no verdict, reason or field and changes no result: the tables above remain the source for what each check does.

### Classes

Every result of the trail verifier falls in exactly one verdict class (Positive, Not evaluated, Negative, Negative (input)); the scope and anchoring rows are flags that apply on top of any of them. The cadence row describes a separate call and is not a class of the trail verifier. The class is read from `verdict`; for `continuity_only` it is read together with `completeness`, and for a window together with `window_anchor`.

| Class | Verdict (reason) | Completeness | What it says |
|-------|------------------|--------------|--------------|
| Positive | `complete`, `complete_unsealed_tail`, `window_complete`, `window_complete_unsealed_tail` | `proven`, `proven_through_checkpoint`, `proven_from_seq`, `proven_from_seq_through_checkpoint` | The checks that ran passed. Only for those checks: `root_anchoring` is `not_checked` on every result, so no positive verdict says the root is on-chain. |
| Not evaluated | `continuity_only` (`no_checkpoint`, `checkpoint_before_window`) | `not_evaluated` | Continuity ran. Completeness did not: no checkpoint was presented, or the one presented is older than the window and seals nothing in it. |
| Not evaluated (scope) | any result with `window_anchor: "uncertified"` | as the verdict says | The start of the window could not be certified. A warning state, not a weak pass. |
| Not evaluated (anchoring) | every result, `root_anchoring: "not_checked"` | as the verdict says | The module checks inclusion in the root it is given, not that the root was anchored. The caller does that. |
| Negative | `truncated`, `checkpoint_mismatch`, `broken` (`seq_order`, `seq_gap`, `head_mismatch`, `link_mismatch`), `agent_gap`, `anchor_mismatch` | `failed` | A check ran and the records or checkpoint did not satisfy it. The reason says which attack was seen. |
| Negative (input) | `malformed` (`empty_or_not_a_list`, `entry_shape`, `agent_mixed`, `entry_preimage`, `checkpoint_shape`), `checkpoint_unproven`, `anchor_unproven`, `stale_checkpoint` | `failed` | The input could not be taken as a stream, checkpoint or anchor of this agent, or did not meet the consumer's bound. A mixed stream (`agent_mixed`) is always here, never in a positive class. |
| Cadence check (consumer side) | `ok`; negative: `period_exceeds_declared_maximum`, `malformed` (`not_a_list`, `agent_mixed`, `period_end`) | none | Returned by `verify_checkpoint_cadence` over a checkpoint stream, a separate call with a consumer-declared ceiling. It has no `completeness` or `root_anchoring` field. `ok` says the gaps between the checkpoints presented are within the ceiling; it says nothing about checkpoints that were not presented. |

### The rule

**A state that was not evaluated is never reported as a pass, and never as a positive verdict.** Concretely, in this specification:

1. No checkpoint: `continuity_only`, completeness `not_evaluated`, reason `no_checkpoint`. Not folded into a positive result (see [Verification](#verification)).
2. A checkpoint older than the window (seq < k): `continuity_only`, `not_evaluated`, reason `checkpoint_before_window`. Nothing presented is sealed.
3. A window with no anchor: `window_anchor: "uncertified"`. Both fields are read together; `uncertified` alone is a reason to withhold trust in the start (see [Window verification](#window-verification)).
4. The root: `root_anchoring: "not_checked"` on every result.
5. A stream that mixes agents is rejected (`malformed`/`agent_mixed`) before any gap is compared; it cannot produce a positive outcome for any of the agents in it.

A consumer that reads only one of the two fields (`verdict` without `completeness` and `window_anchor`) can read a not-evaluated result as acceptable. That is a defect of the reading, not of the result.

### Mapping to other vocabularies (informative)

Other vocabularies are mapped to this one, not the reverse. The mapping is informative, normative for nothing in this document, and implies no endorsement by or of any other specification or its authors. Each row states where the other vocabulary is defined and whether it applies.

| Vocabulary | Where defined | Applies to this document? |
|------------|---------------|---------------------------|
| AER-1 anchor outcomes (`verified`, `verification failed`, `rejected: unresolvable record`, `not checked`, `absent`) | draft-zambo-aer1-26, Section 6 (Verification Procedure), the list that begins "The outcome is exactly one of these values" | Partly. Crosswalk below. |
| RFC 9943 (SCITT architecture) | Section 7.1 | No. It says verification APIs "may provide more details than a single boolean result" and lists examples (signature, validity period, inclusion proof). It defines no named outcome states, so there is nothing to map. |

**Crosswalk, AER-1 to this document.** Legend: *text* = the AER-1 side was read in the draft text (draft-zambo-aer1-26, retrieved 2026-11-21, sha256 `7e000d80f00ad29b8e01431de562e98956f86e426b2695a34c8a215e689e53d4`) and the right-hand side in this document; *reading* = the correspondence is an interpretation, because AER-1 defines these states over an anchor carried in a receipt (Section 6, Section 10.1) and does not define trail heads or checkpoints; *not mapped* = no clean correspondence, and none is forced.

| AER-1 outcome | This document | Basis |
|---------------|---------------|-------|
| `verified` | Not a verdict of this module on its own. A positive verdict (`complete`, ...) plus the caller's confirmation that the period root is on-chain (`root_anchoring` is `not_checked` until then). | text for the AER-1 side; *reading* for the correspondence |
| `verification failed` | `truncated`, `checkpoint_mismatch`, `checkpoint_unproven`/`not_in_root`, `anchor_mismatch`, `anchor_unproven`/`anchor_not_in_root` | *reading*: AER-1 defines it as a recomputed or stored value that does not match what was committed; `truncated` compares a seq count, which is a stored value |
| `rejected: unresolvable record` | Not mapped. The module never resolves a record; the caller supplies proofs and roots. The nearest thing is the caller's own on-chain lookup of the root, outside this module. | not mapped |
| `not checked` | `continuity_only`/`checkpoint_before_window` (a checkpoint was presented and not evaluated against the window) | *reading* |
| `absent` | Not mapped as a whole: see below | not mapped |

AER-1 states beside these: the structural verdicts `verification failed` and `rejected: <reason>` for the presented bytes (Section 6, step 5) and the `id_verdict` values (which include their own `absent`, a different state from the anchor outcome of the same name). This document has no `id_verdict`, and its chain checks (`broken`, `agent_gap`) are not compared with AER-1 Section 7 (hash-chained job timelines), which was not read for this section.

**Why `absent` and `not checked` do not separate cleanly here.** AER-1 distinguishes them by whether an anchor is *present* in what the verifier was given. This document has two different situations under `no_checkpoint` and under `window_anchor: "uncertified"`: (a) the checkpoint or anchor exists in the anchor stream and was not handed to the verifier, and (b) it was never emitted. The module cannot tell them apart from the input; (b) is visible only to a consumer that holds the stream and checks it (`verify_checkpoint_cadence`, which reports `period_exceeds_declared_maximum`). That call detects only a gap larger than the declared ceiling between consecutive checkpoints that were presented; a missing checkpoint inside the ceiling, or the last one of the stream, is not detected by it either, which is why this document assigns (b) no result of its own. Reading (a) as `not checked` and (b) as `absent` would need a per-period expectation that this module does not receive. An agent that recorded nothing is not `absent` here: it gets a sealed checkpoint that repeats `seq` and `head` (see [Checkpoint](#checkpoint)) and verifies like any other. This document keeps `no_checkpoint` and the window states under its own names and does not assign them an AER-1 outcome.

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
- **That a window without an anchor or a checkpoint starts where the log really was.** Its start is `uncertified` and reported as such (see [Window verification](#window-verification)).
- **Anything between the last checkpoint and now.** Records after the last seal are continuous but unwitnessed (`complete_unsealed_tail`). The period length is the window in which a tail cut is undetectable.
- **Actions never submitted.** Without `agent_seq`, an action the agent never sent, or one the operator dropped at ingest, leaves no trace. With `agent_seq`, only actions the agent itself signed are covered, and a drop of the agent's latest actions is visible only against the agent's own last counter.
- **The meaning or legitimacy of any record.** Same limits as [batch-anchor.md](batch-anchor.md) and [action-ref.md](action-ref.md).

---

## Cross-references

- [action-ref.md](action-ref.md) — the per-record digest used as `action_ref`.
- [batch-anchor.md](batch-anchor.md) — Merkle construction and anchoring of the period root.
- [verify-failure-mode-ref.md](verify-failure-mode-ref.md) — why distinct failure states are not collapsed.
- [custody-ref.md](custody-ref.md) — structural vs. organizational independence of keys.
