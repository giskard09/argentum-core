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
| [`timestamp-grammar-negative-v1.fixture.json`](./timestamp-grammar-negative-v1.fixture.json) | 1 | Negative vectors. Slot `0001` is filled (see below). |
| [`verify.py`](./verify.py) | — | Runner. Checks the positive control and every vector present in the fixture. |

## Current coverage: one vector

Slot `0001` holds `neg-0001-arabic-indic-digits`, contributed by aeoess as the follow-up to
PR #115. It is the canonical instant of `recompute-drift-v1` `neg-b01`,
`2026-06-11T08:30:00.123Z`, written with Arabic-Indic digits (U+0660 to U+0669). A grammar
written with `\d` accepts it and the `[0-9]` grammar rejects it. Its `claimed_action_ref` is
the real digest of the drifted payload, and its `correct_action_ref` equals the `neg-b01`
digest of the canonical form.

The runner also checks a positive control: a canonical ASCII timestamp must be accepted, so
the grammar is not rejecting everything.

## Run

```
python3 verify.py
```

Exit `0` when the positive control is accepted and every present negative vector fails
closed. Exit `1` otherwise.

## What this set does NOT cover

- Timestamps that are well-formed but name an impossible date, such as month 13 or day 31
  in April. The grammar checks shape only.
- A trailing newline. This set's gate anchors with `\Z`, so it rejects one, but no vector
  here tests that case yet.
- Timestamps in the epoch-ms form accepted by `/nexus/trail`. Those are a different path.
- Any claim about whether an action happened. A grammar check says nothing about occurrence.
