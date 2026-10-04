# timestamp-grammar negative conformance set - v1

Negative vectors for the action-ref timestamp grammar gate. A conformant verifier
rejects any timestamp that is not canonical RFC 3339 UTC written with ASCII digits
`[0-9]`, before it hashes anything.

**Spec:** [`docs/spec/action-ref.md`](../../docs/spec/action-ref.md)
**Grammar reference:** `plugins/agt_evidence_anchor/action_ref.py` (`_TIMESTAMP_RE`), same
`[0-9]` pattern (PR #114, PR #115)
**Runner:** [`verify.py`](./verify.py) (stdlib only, deterministic, exit 0 on full pass)

## Why `[0-9]` and not `\d`

In Python 3, `\d` matches any Unicode decimal digit. A grammar written with `\d` accepts
timestamp strings that use non-ASCII digits, and two implementations can then disagree on
whether the same instant is valid. The grammar is pinned to `[0-9]`. `verify.py` asserts
that the pattern contains no shorthand classes.

## Files

| File | Vectors | What it holds |
|------|---------|---------------|
| [`timestamp-grammar-negative-v1.fixture.json`](./timestamp-grammar-negative-v1.fixture.json) | 0 | Negative vectors. One slot is reserved and open (see below). |
| [`verify.py`](./verify.py) | — | Runner. Checks the positive control and every vector present in the fixture. |

## Current coverage: none

This set has **no negative vectors yet**. The first vector (slot `0001`) is reserved and is
intentionally not written in this repository. It is to be contributed separately, with the
contributor's credit.

So the runner, for now, checks only a positive control: a canonical ASCII timestamp must be
accepted, so the grammar is not rejecting everything. A run with zero vectors is reported as
`no negative vectors present: 1 slot(s) open`. That output is not a pass for the open slot.

## Run

```
python3 verify.py
```

Exit `0` when the positive control is accepted and every present negative vector fails
closed. Exit `1` otherwise.

## What this set does NOT cover

- Timestamps that are well-formed but name an impossible date, such as month 13 or day 31
  in April. The grammar checks shape only.
- A trailing newline. The pattern follows `action_ref.py`, which uses `$` with `re.match`,
  and `$` also matches before a final newline. Tightening this is a separate change, not made
  here.
- Timestamps in the epoch-ms form accepted by `/nexus/trail`. Those are a different path.
- Any claim about whether an action happened. A grammar check says nothing about occurrence.
