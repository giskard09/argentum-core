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
PASS: 15 vectors (10 accept recomputed byte-identical, 5 reject correctly refused)
```

## Relationship to the draft and the baseline

The set includes the two test vectors from Appendix A of
[`draft-giskard-aeoess-action-ref-00`](https://github.com/giskard09/draft-giskard-aeoess-action-ref)
(`draft-appendix-a-v1`, `draft-appendix-a-v2`). The implementation reproduces
the draft's Vector 1 (`fdd7f810...`) byte-for-byte and derives Vector 2, which
the draft leaves as an exercise.

The same implementation also reproduces the argentum-core
`action-ref-v1-baseline.fixture.json` vectors byte-identical, including the
`0003` namespace-collision pair, satisfying criterion (a) in
[`../README.md`](../README.md).

The remaining vectors are AEOESS's own, so the sets together give independent
recomputation on both the normative draft inputs and independent inputs.
