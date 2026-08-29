# Guarantee Model: Mycelium Trails × SafeAgent × DashClaw

This document defines what each layer of the joint Mycelium × SafeAgent × DashClaw stack
proves — and what it does not prove — so that consumers can reason about guarantees without
misreading orthogonal properties as stacked dependencies.

## What a COMMITTED SafeAgent claim proves

- This action was claimed before execution
- A duplicate retry with the same `request_id` would have returned `SKIP`
- The exactly-once property held at the execution boundary

**Boundary on the second bullet:** "the same `request_id`" assumes the caller reuses one
claim — one `request_id` / `action_ref` / `timestamp` — across every retry of that attempt.
A transport-level retry (network timeout, 5xx) that resends the identical, already-computed
request body keeps that assumption, because nothing about the claim was recomputed. A retry
that re-enters the agent and lets the model decide again — a guardrail retry with a
rewritten prompt, for instance — does not: it produces a new claim with a new `timestamp`
(and, if the tool's own arguments changed, new argument content) rather than a resend of the
old one. Two claims with different `request_id`s are, by this guarantee's own definition,
two different actions, not a duplicate of one — the SKIP guard has nothing to match against
for the second claim, so it does not block that second execution the way it would a true
resend. If both executions otherwise succeed, the result is two distinct effects (e.g. two
charges for different amounts), not one effect duplicated — a `DIVERGED` outcome, not a
caught retry. Identified by vasilisnasopoulos
(crewAIInc/crewAI#5802, comment
[5462928784](https://github.com/crewAIInc/crewAI/issues/5802#issuecomment-5462928784)) and
[langchain-ai/langgraph#8039](https://github.com/langchain-ai/langgraph/issues/8039); the
`DIVERGED` outcome name is mstevens843's, measured across LangGraph 1.2.11, Temporal, and
DBOS over 2,490 crash-and-recover trials
([crashpoint/results/06-nondeterminism.md](https://github.com/mstevens843/crashpoint/blob/main/results/06-nondeterminism.md)).
This repo did not identify the gap; it is recorded here because the guarantee above is
silent about which retries it covers.

## What a COMMITTED SafeAgent claim does not prove

- That the action was recorded externally
- That the outcome is tamper-evident after the fact
- That a retry which re-invoked the agent (rather than resending the same claim) produced
  the same `request_id` — see the boundary note above

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

`PENDING/null` itself collapses two evidentiarily distinct cases — raised directly by
xsa520 ([`A2A#1672`](https://github.com/a2aproject/A2A/issues/1672), comment
[`5128801280`](https://github.com/a2aproject/A2A/issues/1672#issuecomment-5128801280)),
following up on the sandboxed-filesystem/evidence-path backend below where both are
observable in practice:

- **`PENDING/null:non-arrival-observed`** — an independent observation path exists, but no
  correlated outcome arrives within the freshness window. The system watched and saw nothing
  land — a negative result, not an absence of monitoring.
- **`PENDING/null:no-observation-path`** — no independent observation path exists at all. The
  system has no way to know whether the effect landed, independent of whether it did.

Both surface as `outcome_handle: null` today; the sub-state is a property of whether a
backend's negative-evidence condition can fire at all, not of the handle itself. This is the
same shape as the non-null/null split above, one level down: it narrows what "I don't know"
means without inventing a new terminal status.

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
| On-chain (`AnchorRegistry`/`GiskardPayments`, this repo) | `tx_hash` | tx receipt exists and `status == 1` (included). **Enforced in code** (`argentum.py:_anchor_confirmation_poller` + `_classify_anchor_receipt`, `mycelium_trails.py:confirm_trail_anchor`/`fail_trail_anchor`): `anchor_action_ref` (`arb_pay.py`) writes `tx_hash` at broadcast time (`PENDING/non-null`, `anchor_submitted_at` recorded), a background poller resolves `status == 0x1` → `COMMITTED` (`anchor_status='anchored'`), `status == 0x0` → `FAILED` terminal immediately (`reverted`, no need to wait out the freshness window once the answer is known), and no receipt within `ANCHOR_FRESHNESS_TTL_SECONDS` → `FAILED` terminal (`non_arrival_timeout` — the existing `PENDING/null:non-arrival-observed` → `FAILED` resolution above, not a new state). Conformance: `tests/test_anchor_confirmation.py` (positive + both terminal-failure transitions). | no fixed block-confirmation count enforced yet; chain finality (~12 blocks Arbitrum/Base) is the reference target |
| Payment processor REST API (PayPal `capture`, pattern from [`paypal-action-ref-anchor`](https://github.com/giskard09/paypal-action-ref-anchor)) | processor's capture id (`purchase_units[].payments.captures[0].id`) | idempotent `GET` on that id returns a terminal `status` value (e.g. `COMPLETED`) — not the response to the original write | bounded by the processor's own settlement SLA (typically seconds, not on-chain finality) |
| MPC/custody signer (Turnkey `eth_send_transaction`, pattern from [`turnkey-action-ref-anchor`](https://github.com/giskard09/turnkey-action-ref-anchor)) | `eth.txHash` from the poll response | same predicate as the on-chain row above once the tx lands — the signer only adds an intermediate `ACTIVITY_STATUS_*` state before broadcast, which is not itself the confirmation | signer-side polling interval + underlying chain finality |
| MPC signer with confirmation gate (Fireblocks `x402_get_and_pay`, pattern from [`fireblocks-action-ref-anchor`](https://github.com/giskard09/fireblocks-action-ref-anchor)) | facilitator's `transaction` field from the `PAYMENT-RESPONSE` header | same on-chain predicate as above; the `confirmed` flag in this backend is a **pre-execution** approval gate, not the post-execution `confirmation_predicate` — the two are orthogonal and must not be conflated | same as on-chain row |
| Sandboxed filesystem / evidence-path (no on-chain settlement, no REST capture id, no MPC signer — raised by xsa520, [`A2A#1672`](https://github.com/a2aproject/A2A/issues/1672), comment [`5125166130`](https://github.com/a2aproject/A2A/issues/1672#issuecomment-5125166130), agreed as its own row rather than a REST variant in comment [`5128801280`](https://github.com/a2aproject/A2A/issues/1672#issuecomment-5128801280)) | path/handle to the evidence artifact in the sandbox's own store (e.g. an append-only log offset or artifact digest the sandbox assigns at write time) | an independent read of that path/handle returns the artifact with content matching the claimed effect — not the sandbox's own write ack. Absent an independent observation path for the backend, the predicate cannot fire at all, which is exactly the `PENDING/null:no-observation-path` case above | bounded by however often the evidence-path store is independently polled or re-read; no chain-finality analog |

The distinction the table makes explicit: `confirmation_predicate` is
always a property of the **outcome refetch**, never of any pre-execution
approval step (elicitation, policy consensus, `confirmed: true`) that a
given backend may or may not have. A backend can have a strong
pre-execution gate and a weak or missing `confirmation_predicate`, or
vice versa — the `*-action-ref-anchor` worked examples series exists
precisely because those two axes vary independently across backends.

## Pre-execution verdict correlation: `verdict_ref`

`confirmation_predicate`/`outcome_handle` above correlate a trail to its **post-execution**
refetch. The same correlation problem exists one step earlier, on the **pre-execution** side,
wherever a policy gate or guardrail evaluates a tool call and produces its own verdict
artifact before the call runs — e.g. `GuardrailResult` in
[`microsoft/autogen#7881`](https://github.com/microsoft/autogen/pull/7881), which today
carries `decision`/`reason`/`modified_args`/`metadata: dict[str, Any]` but no dedicated slot
tying that verdict back to the call it evaluated. Raised by babyblueviper1
([`autogen#8008`](https://github.com/microsoft/autogen/issues/8008), comment
[`5131127564`](https://github.com/microsoft/autogen/issues/8008#issuecomment-5131127564)),
who independently derives a structurally identical correlation key on their own side
(`decision_ref = SHA-256(JCS({artifact_hash, artifact_type, policy_version, verdict,
source_class}))`) — an instance-identity key distinct from the full verdict payload, same
relationship `action_ref` has to `original_args_digest`/`effective_args_digest`.

This is a spec pattern, not code this repo ships into `autogen` or any other guardrail
implementation — the field belongs on the gate's own verdict type, wherever that lives:

| Field | Type | Semantics | When null |
|---|---|---|---|
| `verdict_ref` | `str \| None` | The `action_ref` (this repo's canonical form, `SHA-256(JCS({agent_id, action_type, scope, timestamp}))`, or a caller's own equivalent identity key) supplied as an input field into the gate's own verdict artifact at evaluation time, so the verdict's own correlation key (e.g. `decision_ref`) transitively commits to it. | The caller had no upstream `action_ref` to bind — most guardrails run standalone today. Absence is not an error; it is the same `no-observation-path` shape as `outcome_handle`, one stage earlier: the gate did evaluate, it just has nothing external to correlate against. |

A verifier holding both records — the gate's own verdict artifact (with its `verdict_ref`)
and this repo's `action_ref` trail — can correlate them on one shared key without either
system trusting the other's internal bookkeeping, the same non-null/null discipline
`outcome_handle` already establishes, applied to the input side of execution instead of the
output side. `verdict_ref` is deliberately not scoped to any single caller's wrapper: any
policy gate that accepts an external identity key as an input field to its own verdict can
adopt the same shape.

## Reliance policy is out of scope, by design

Everything above — `trail_status`/`outcome_handle`, `confirmation_predicate` per backend,
`verdict_ref` — preserves facts independently and lets a verifier correlate them on a shared
key. None of it prescribes which combination of confirmed facts is *sufficient* to authorize
a given downstream action. Raised directly by xsa520
([`A2A#1672`](https://github.com/a2aproject/A2A/issues/1672), comment
[`5161421422`](https://github.com/a2aproject/A2A/issues/1672#issuecomment-5161421422)):
preserving independently observable facts does not determine which combination is sufficient
for a particular downstream action — a card discovery flow, a low-risk message exchange, and
a delegated action with external consequence may reasonably require different limbs,
freshness windows, and assurance thresholds. Otherwise the boolean simply moves downstream:
the limbs stay separate in the receipt, but the consumer silently treats one fixed
combination as universally "verified."

This was already the shape of every guarantee above — "consumers can adopt either
independently based on their requirements" (Composing Layer 2 + Layer 4, above) — but it was
never named as a general principle. It is one now: **this spec defines and preserves facts;
it does not define a reliance policy over them.** Deciding which facts must be present, how
fresh they must be, and what assurance threshold applies for a given action class is the
responsibility of the receiving system, not the protocol. This mirrors the
`confirmation_predicate` gap closed above (also raised by xsa520) — the pattern was implicit
in how the repo's own integration behaves, and the fix there was the same: name the boundary
explicitly instead of leaving it to be inferred from behavior.

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

**Same boundary applies here:** DashClaw's dedup only fires if the same `action_ref` arrives
twice. If the caller recomputes `action_ref` per retry attempt (new `timestamp_ms` each
time, per the derivation above) rather than fixing it once before the first attempt, no two
attempts ever share a key and DashClaw never sees a duplicate to dedup — see the "What a
COMMITTED SafeAgent claim proves" boundary note above for the retry scenario where this
matters.

## References

- SafeAgent RFC: [`RFC_EXECUTION_GUARD.md`](https://github.com/azender1/SafeAgent/blob/main/RFC_EXECUTION_GUARD.md)
- Joint spec issue: [`giskard09/argentum-core#7`](https://github.com/giskard09/argentum-core/issues/7)
- DashClaw issue: [`ucsandman/DashClaw#105`](https://github.com/ucsandman/DashClaw/issues/105)

Co-authored-by: azender1 <azender1@users.noreply.github.com>
