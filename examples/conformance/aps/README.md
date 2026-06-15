# AEOESS independent conformance set for action-ref-v1

An independent implementation of the `action-ref-v1` wire format from
[`agent-passport-system`](https://github.com/aeoess/agent-passport-system)
(APS by AEOESS). This directory mirrors the published set at
`agent-passport-system/conformance/action-ref-v1`.

`action_ref` is `SHA-256(JCS(preimage))` over the four-field preimage
`{agent_id, action_type, scope, timestamp}`, with JCS per RFC 8785 and the
timestamp pinned to RFC 3339 UTC with exactly three fractional digits and a
`Z` suffix (`YYYY-MM-DDTHH:MM:SS.mmmZ`).

## Files

- `vectors.json` — the vector set. Accept vectors carry the expected
  lowercase-hex SHA-256 and the canonical JCS string. Reject vectors carry
  `reject: true` and must fail the timestamp grammar rather than be coerced.
- `verify.py` — standalone runner, Python 3 stdlib only. Vendored JCS
  serializer, independent recomputation.
- `verify.mjs` — standalone runner, Node.js built-ins only (`node:crypto`,
  `node:fs`). Independent recomputation in a second language.

Neither runner wraps the SDK. Each recomputes from the preimage, so a pass
cross-checks the hashes against two independent implementations.

## Run

```
python3 verify.py
node verify.mjs
```

Both exit 0 on a full pass and print:

```
PASS: 13 vectors (8 accept recomputed byte-identical, 5 reject correctly refused)
```

## Relationship to the baseline

The same AEOESS implementation reproduces the argentum-core
`action-ref-v1-baseline.fixture.json` vectors byte-identical, including the
`0003` namespace-collision pair, satisfying criterion (a) in
[`../README.md`](../README.md): an independent implementation of the
action-ref-v1 wire format validating against this conformance directory.

The vectors here are AEOESS's own, so the two sets together give independent
recomputation on independent inputs.
