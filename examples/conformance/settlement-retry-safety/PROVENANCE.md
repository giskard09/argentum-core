# PROVENANCE — settlement-retry-safety-v1

## What this is

A worked example implementing and verifying the seven-mode retry-safety
battery described by aurumflux20 in
[x402-foundation/x402#3208](https://github.com/x402-foundation/x402/issues/3208)
(comment at `2026-09-03T09:52:07Z`): `accept_then_timeout`, `5xx_after_settle`,
`double_402`, `slow_answer`, `reconcile_unavailable`, `declared_safe`, `clean`.
The rule under test: a settlement client must settle exactly once in every
mode, including `declared_safe`.

## What was actually built

**Everything in this directory is new code, written for this worked
example.** Unlike other worked examples in this series (Keycard, Binance,
Kraken, …), which model a synthetic-but-faithful envelope over a real
third party's *existing* production code, this one has no third-party code
to read from — the battery targets client-side retry behavior against an
x402 facilitator, and this repo had no x402 payment client before this work
(confirmed by grep: prior references to "x402" in this repo are all spec/
conformance documents citing the x402 wire schema for field names, never a
running payment flow). So the four files here are an original
implementation of the pattern the battery tests, not an extraction from
someone else's codebase:

- `pending_settlement_store.py` — a 3-way verdict store (`settled` /
  `refused-not-charged` / `indeterminate`), same PENDING/COMMITTED/FAILED
  vocabulary this repo already uses in
  [`idempotency-ref-v1`](../../../docs/spec/idempotency-ref.md), specialized
  to settlement outcomes.
- `facilitator_harness.py` — `MockFacilitator`, a fault-injecting facilitator
  with its own settlement ledger and its own signature-based idempotency
  (the safety net a client depends on when it re-presents an authorization
  instead of minting a new one).
- `execute_payment.py` — the client under test. Implements the receiver
  obligation whawk46 named in the same thread (comment at
  `2026-09-03T04:17:08Z`): an indeterminate verdict locks the authorization;
  the client re-presents the same signed payload rather than accepting a
  fresh `402` challenge.
- `run_battery.py` / `verify.py` — runners. `verify.py` is the one wired to
  `vectors.json`, matching the `verify.py` convention used elsewhere in
  `examples/conformance/`.

## What was verified, and how

Every vector in `vectors.json` is checked by **running the real code**
(`execute_payment()` driven through a bounded caller retry loop against
`MockFacilitator(mode)`), not by reading source and asserting it looks
correct. `verify.py` prints `ALL CHECKS PASS` only if all 8 vectors — the 7
battery modes plus `mutation-broken-client-001` — reproduce their declared
outcome:

```
$ python3 verify.py
settlement-retry-safety-v1 conformance — 8 vectors
...
ALL CHECKS PASS
```

**Mutation control (`mutation-broken-client-001`):** a deliberately broken
client that mints a *new* authorization signature on every retry, run
against the same `double_402` facilitator. It reproduces a real double
charge (`ledger_len > 1`) in the mock. This exists to rule out the failure
mode where a fixture set always reports success regardless of what the
client under test actually does — without this vector, 7/7 green would be
equally consistent with "the facilitator mock always settles once" and
"the client correctly avoids duplicate settlement." Confirmed manually
during construction that all five fault-injecting modes (not just
`double_402`) double-charge this broken client before the correct
`execute_payment()` client was finished — see session bitácora
`~/Downloads/BITACORA CODIGO 2026-09-03 settlement-retry-safety-v1.txt`.

## On-chain anchor

`ref = keccak256("settlement-retry-safety-v1:argentum-core@9cfbf67")` =
`0xd2d342d8221ac56cca286173b875d08a4723b8467565adc43ef76f149120a1dc`

Anchored via `anchor(bytes32)` on AnchorRegistry (Base mainnet,
`0x49fEcA52bC634a9Ab773226D16619deC547794aa`), permissionless — same
contract used across this repo's other worked examples.

- tx: `0x9caa800651433db570a8ac58085b834107640d1df6088386f9086ecbdb78a86f`
- block: `50824409`
- status: `0x1` (confirmed via direct `eth_getTransactionReceipt` against
  `mainnet.base.org`, not read back from the sender's own response)

**What this anchor claims and what it does not:** it timestamps the
existence of this artifact (commit `9cfbf67`) on Base mainnet at block
50824409 — a public, permissionless proof-of-existence, the same pattern
used for `negotiation_ref`/content-address anchors elsewhere in this repo.
It is **not** a conformance claim against aurumflux20's exact battery (she
has not published a runnable reference vector set as of this anchor), and
it is **not** a public "safe" claim — both of those remain separate,
un-taken decisions per the limits section below.

## Honest limits — what this does NOT establish

Same disclosure standard as this series' other worked examples
(`keycard-action-ref-anchor`, `binance-onchain-pay-action-ref-anchor`):

- **Single-process, in-memory.** `PendingSettlementStore` and
  `MockFacilitator` are plain Python objects with no persistence, no
  concurrency control, and no network boundary. This does not test what
  happens under concurrent retries (two threads/processes racing on the
  same `idempotency_key`), only sequential retry loops.
- **No real payment rail.** `MockFacilitator` is a hand-written model of
  the fault surface aurumflux20's battery names, not a wrapper around a
  real x402 facilitator or a real blockchain RPC. `0xATT`, `0xD402`, etc.
  are placeholder transaction references, not real transactions — unlike
  the anchored worked examples in this repo (Keycard, Binance, …), nothing
  here has been anchored on-chain yet.
- **The seven fault shapes are our own modeling of the battery's
  descriptions**, not vectors contributed directly by aurumflux20. The
  issue states the battery modes and the settle-exactly-once rule; it does
  not (as of this writing) publish a runnable reference harness we
  reproduced byte-for-byte. If aurumflux20 publishes concrete vectors
  later, this directory's modeling should be checked against them before
  any claim of conformance to *her* battery specifically, as opposed to
  conformance to the rule she described.
- **No claim of "safe" has been made publicly.** This PROVENANCE.md and the
  code it describes are not, by themselves, a citation-worthy artifact —
  per the session's operating rule, any public mention crediting
  aurumflux20's work or claiming this repo is retry-safe requires a
  separate decision after this artifact is reviewed.

## Source

- Issue: <https://github.com/x402-foundation/x402/issues/3208>
- Battery description: aurumflux20, comment `2026-09-03T09:52:07Z`
- Receiver obligation (no re-challenge on indeterminate): whawk46, comment
  `2026-09-03T04:17:08Z`
- Related spec in this repo: [`docs/spec/idempotency-ref.md`](../../../docs/spec/idempotency-ref.md)
  (PENDING/COMMITTED/FAILED lifecycle and orphaned-PENDING treatment this
  work reuses the vocabulary of)
