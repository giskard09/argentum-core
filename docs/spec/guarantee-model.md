# Guarantee Model: Mycelium Trails × SafeAgent × DashClaw

This document defines what each layer of the joint Mycelium × SafeAgent × DashClaw stack
proves — and what it does not prove — so that consumers can reason about guarantees without
misreading orthogonal properties as stacked dependencies.

## What a COMMITTED SafeAgent claim proves

- This action was claimed before execution
- A duplicate retry with the same `request_id` would have returned `SKIP`
- The exactly-once property held at the execution boundary

## What a COMMITTED SafeAgent claim does not prove

- That the action was recorded externally
- That the outcome is tamper-evident after the fact

## What a Mycelium TrailRecord proves

- This action occurred, with this hash, anchored at this block
- The record has not been modified since anchor time

## What a Mycelium TrailRecord does not prove

- That the action occurred exactly once

## Composing Layer 2 + Layer 4

Both guarantees together: a verifier who finds a `TrailRecord` **AND** a `COMMITTED` claim
for the same `action_ref` can assert the action ran **exactly once AND** the outcome is
tamper-evident. Neither guarantee requires the other — consumers can adopt either
independently based on their requirements.

## Trail status states

A `TrailRecord` carries a `trail_status` field with three terminal or transitional values,
tracked against an `outcome_handle` — a follow-up verification reference that a third party
can refetch independently at audit time. `outcome_handle` is backend-agnostic: it names
whatever identifier lets an auditor query the actual post-execution state directly, rather
than trusting the write's own ack. An on-chain `tx_hash` is one instance of this — the
handle is a transaction hash and the refetch is a chain query — but the same shape holds
for an idempotent `GET` against a payment processor's charge ID, a case number at a
regulator, or any other resource an external system will return the same terminal state for
on repeated, independent query.

| Status | Meaning | `outcome_handle` | Verifiable externally? |
|--------|---------|-----------|----------------------|
| `COMMITTED` | Execution completed, outcome confirmed by independent refetch | non-null | Yes — via `outcome_handle` |
| `PENDING` | External call started, outcome not yet verified | non-null | Follow-up — query `outcome_handle` directly |
| `PENDING` (degraded) | Signer crashed before recovering verification reference | null | No — signer has nothing to hand off |
| `FAILED` | Terminal. Execution did not complete or post-execution receipt never arrived | null | Yes — absence of `outcome_handle` |

`PENDING` has two named variants distinguished by `outcome_handle`:

- **`PENDING/non-null`** — effect crossed the boundary, follow-up verification handle exists. The signer knows where to look; the next agent turn or operator can verify independently.
- **`PENDING/null`** (degraded) — effect may have crossed the boundary, but the signer crashed before recovering the reference. The honest record is "I started, I do not know if it landed, I have nothing to hand off." This is a different quality of not-knowing, not a different outcome.

### Crash-after-charge handling

For non-idempotent external systems (payments, regulated actions), the crash window between
the external call starting and the outcome being verified produces a `PENDING` record.
Resolution:

1. Pre-execution receipt emitted → `trail_status: PENDING`, `outcome_handle: null` (degraded)
2. Verification reference recovered → `outcome_handle` populated, status remains `PENDING/non-null`
3. Post-execution receipt arrives → status transitions to `COMMITTED`, `outcome_handle` confirmed
4. If post-execution receipt does not arrive within TTL → status resolves to `FAILED`

No happy-path assumption is baked in. A `COMMITTED` record without a corresponding
post-execution receipt cannot exist.

### Verification reference

`outcome_handle` is the follow-up verification reference. Any auditor can query the resource
directly using `outcome_handle` without trusting the operator's logs or database, and the
query must be an independent refetch of terminal state — not the response to the original
write. For on-chain backends this is `tx_hash` and the refetch is a chain query, where the
anchor is the single source of truth for terminal state; for other backends `outcome_handle`
takes whatever shape that backend's independent refetch requires (a charge ID resolved via
idempotent `GET`, for example), but the non-null/null distinction and the refetch-not-ack
requirement carry over unchanged.

A `PENDING/null` record is not a verification failure — it is an honest declaration that
the signer's knowledge ended before a handle could be recovered. The contract: the receipt
never lies about what the signer actually knew at signing time.

## `confirmation_predicate` per backend

For each backend, three things must be defined explicitly: the field that
correlates `outcome_handle` to the original action (`correlation field`),
the exact refetch state that counts as confirmed vs not-yet
(`confirmation_predicate`), and how long a verifier should wait before a
still-`PENDING` record is treated as suspicious (`freshness window`).
Previously this was left implicit — asked directly by xsa520
([`a2aproject/A2A#1672`](https://github.com/a2aproject/A2A/issues/1672),
comment `5086390308`): is this defined in the guarantee model, or does
today's integration assign it producer-side? Verified: it was the
latter, only the general pattern (independent refetch + non-null/null)
was named. This section closes that gap, drawn from the on-chain path
this repo runs and from the confirmation-gap patterns already catalogued
across the `*-action-ref-anchor` worked examples series.

| Backend | correlation field | `confirmation_predicate` | freshness window |
|---|---|---|---|
| On-chain (`AnchorRegistry`/`GiskardPayments`, this repo) | `tx_hash` | tx receipt exists and `status == 1` (included). This repo's own `anchor_action_ref` (`arb_pay.py`) writes `tx_hash` at broadcast time and does not currently poll for the receipt — today `PENDING/non-null` never transitions to an explicit `COMMITTED` write; the predicate above is the target, not yet enforced in code. Open item, not a spec gap. | no fixed block-confirmation count enforced yet; chain finality (~12 blocks Arbitrum/Base) is the reference target |
| Payment processor REST API (PayPal `capture`, pattern from [`paypal-action-ref-anchor`](https://github.com/giskard09/paypal-action-ref-anchor)) | processor's capture id (`purchase_units[].payments.captures[0].id`) | idempotent `GET` on that id returns a terminal `status` value (e.g. `COMPLETED`) — not the response to the original write | bounded by the processor's own settlement SLA (typically seconds, not on-chain finality) |
| MPC/custody signer (Turnkey `eth_send_transaction`, pattern from [`turnkey-action-ref-anchor`](https://github.com/giskard09/turnkey-action-ref-anchor)) | `eth.txHash` from the poll response | same predicate as the on-chain row above once the tx lands — the signer only adds an intermediate `ACTIVITY_STATUS_*` state before broadcast, which is not itself the confirmation | signer-side polling interval + underlying chain finality |
| MPC signer with confirmation gate (Fireblocks `x402_get_and_pay`, pattern from [`fireblocks-action-ref-anchor`](https://github.com/giskard09/fireblocks-action-ref-anchor)) | facilitator's `transaction` field from the `PAYMENT-RESPONSE` header | same on-chain predicate as above; the `confirmed` flag in this backend is a **pre-execution** approval gate, not the post-execution `confirmation_predicate` — the two are orthogonal and must not be conflated | same as on-chain row |

The distinction the table makes explicit: `confirmation_predicate` is
always a property of the **outcome refetch**, never of any pre-execution
approval step (elicitation, policy consensus, `confirmed: true`) that a
given backend may or may not have. A backend can have a strong
pre-execution gate and a weak or missing `confirmation_predicate`, or
vice versa — the `*-action-ref-anchor` worked examples series exists
precisely because those two axes vary independently across backends.

## Canonical key derivation

All three systems converge on the same linking key:

```
action_ref = SHA-256(
  agent_id.encode('utf-8') ||
  action_type.encode('utf-8') ||
  scope.encode('utf-8') ||
  timestamp_ms.to_bytes(8, 'big')
)
```

All four fields are required. `timestamp_ms` is millisecond-precision Unix time at claim time
(before execution), encoded as int64 big-endian.

### DashClaw field mapping

| Joint spec field | DashClaw field |
|-----------------|----------------|
| `agent_id` | `agent_id` |
| `action_type` | `action_type` |
| `scope` | `authorization_scope` |
| `action_ref` / `request_id` | `idempotency_key` (caller-computed) |
| `action_id` | DashClaw's local evidence/outcome row ID |

Callers compute `action_ref` externally and pass it as `idempotency_key`. DashClaw consumes
it opaquely; SafeAgent and Mycelium standardize the key. No runtime coupling required.

## References

- SafeAgent RFC: [`RFC_EXECUTION_GUARD.md`](https://github.com/azender1/SafeAgent/blob/main/RFC_EXECUTION_GUARD.md)
- Joint spec issue: [`giskard09/argentum-core#7`](https://github.com/giskard09/argentum-core/issues/7)
- DashClaw issue: [`ucsandman/DashClaw#105`](https://github.com/ucsandman/DashClaw/issues/105)

Co-authored-by: azender1 <azender1@users.noreply.github.com>
