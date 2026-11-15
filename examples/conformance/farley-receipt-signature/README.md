# farley-receipt-signature — conformance vectors

Receipt-signature vectors for [draft-farley-acta-signed-receipts-03](https://datatracker.ietf.org/doc/draft-farley-acta-signed-receipts/03/). Each case is a reject paired with a conformant twin.

- **Profile:** envelope shape (§2.1). The signing input is `JCS(payload)`, with no pre-hash (§5.1, §6.6).
- **Verification mode:** archival (§9.1). A verifier that applies the live-presentation freshness window (24h is RECOMMENDED) would reject all four receipts as stale. That case is out of scope here.
- **Key source:** `jwks.json`, which is external to the receipts, as §9.5 requires. No key is read from inside a receipt.
- **Keys:** TEST ONLY. Each Ed25519 seed is `SHA-256("agent-evidence-vectors/test-only/" + label)`. The seeds are public on purpose, so nothing signed with these keys means anything outside this suite.

| File | Expected | Requirement | What it tests |
|------|----------|-------------|---------------|
| `signature-input-drift.reject.json` | REJECT `signature_invalid` | MUST (§5.1, §5.2, §6.6) | Signed over the pretty-printed payload bytes, not `JCS(payload)`. |
| `signature-input-drift.conformant.json` | ACCEPT | MUST | Same payload, signed over `JCS(payload)`. |
| `superseded-key.reject.json` | REJECT `key_outside_validity_window` | SHOULD (§9.2) | Valid signature under key A, but `issued_at` is after key A's `valid_until`. |
| `superseded-key.conformant.json` | ACCEPT | SHOULD (§9.2) | Minimal pair: same key A, `issued_at` inside the window. `issued_at` is the only difference. |

The two `superseded-key` vectors test a SHOULD, so `index.json` gives them a second outcome, `expected_if_not_honoured` (`ACCEPT` for both). `expected` is the verdict from a verifier that applies the §9.2 windows. `expected_if_not_honoured` is the verdict from one that does not implement the check or was not given the windows, which §9.2 permits ("when available"). A run declares which case it is in and is scored against that outcome. This keeps "does not implement §9.2" apart from "implements §9.2 and gets it wrong". The MUST vectors have one outcome only.

The window check has a limit. `issued_at` is asserted by the signer, so the check catches a key that is still in use after an honest rotation. It does not catch a compromised key whose holder backdates `issued_at` into the window.

## Run

```
python3 examples/conformance/farley-receipt-signature/verify.py                    # windows honoured; exit 0 iff all four match index.json
python3 examples/conformance/farley-receipt-signature/verify.py --no-key-windows   # windows withheld; SHOULD vectors scored against expected_if_not_honoured
python3 examples/conformance/farley-receipt-signature/build.py    # regenerates the files byte for byte
```

CI runs `tests/test_farley_receipt_vectors.py`. It checks six things:

- every vector matches `index.json`;
- every signature verifies over the `signed_input_hex` that `index.json` publishes for it, and only `signature-input-drift.reject` was signed over something other than `JCS(payload)` (Python `json.dumps(payload, indent=2)`), so a re-run can check why a reject fails, not only that it does;
- `build.py` regenerates the files byte for byte;
- the superseded-key pair differs only in `issued_at`;
- the SHOULD vectors pass in both runs, only they carry `expected_if_not_honoured`, and a verifier that skips the windows while the run declares them honoured still fails, on `superseded-key.reject` only;
- `verify.py` refuses mutated receipts: wrong envelope shape, `alg`, a signature inside the signing input, tampering, missing field, bad encoding, and a mismatch between `kid` and `issuer_id`.

## vector_verifier.py: the 29-vector corpus of probityai/agent-evidence-vectors

`vector_verifier.py` answers `<cmd> <receipt>` in the contract of the `vectors-receipt-signature` corpus
(`AEV_RECEIPT_JWKS`, optional `AEV_RECEIPT_CONTEXT`; last stdout line is `{"verdict", "code"}`; exit 0/1/2).
Its CI job, `.github/workflows/farley-receipt-signature-corpus.yml`, replays the corpus through it with
`probityai/agent-evidence-vectors`, pinned by commit `13247ea` (tag v0.36.3).

What it is: a verifier of `draft-farley-acta-signed-receipts-03` (envelope shape) written from the text of the draft and
the corpus's requirements table, then checked against the corpus. Only `jcs.py` is shared with this repository, and no
code of the corpus's reference reader is imported or copied. The result is **directed**, not blind: the expected verdicts
were visible while it was written.

Result with `agent-evidence-vectors==0.36.3`: 29 of 29 pass; 0 SHOULD not honoured; 0 gaps closed; 0 fail.
The 29 include the 4 `SHOULD` members (key validity window) and the 2 `gap` members (`RS-G-001` revocation, `RS-G-002`
commitment time), which the draft does not decide: they are answered as the draft does, valid.

Where the draft does not decide, it chooses (and the corpus's `rs-c-3` asks for the same): a key's `valid_until` is outside
its window and `valid_from` inside (RFC 7519 `nbf`/`exp`). It does not read `revoked_at` or a commitment's logging time.
It answers the flat receipt shape `undecidable` (`unsupported_shape`); the corpus has no flat member.

What it is not: not the corpus's reference reader, not an independent implementation in the sense of the
independence method (the expected outcomes were known), and not a certification of anything. The test keys are public.

`tests/test_farley_vector_verifier.py` pins rules the corpus has no member for (unsupported `alg`, unknown `kid`, a
receipt at chain position 2 with no link, uppercase hex in a link) and a fifth, a link or `issued_at` with a trailing
LF or CRLF, which must be refused (a `$`-anchored pattern accepts it). The corpus has no member for any of them; the trailing-LF
case was caught by this repository's own regex sweep (`tests/test_regex_anchor_sweep.py`), not by the corpus. Mutating the
verifier to skip any of them is not detected by the corpus; it is by these tests.

## Observed: @veritasacta/verify 0.10.19

Run with `--jwks ./jwks.json --mode receipt` (0.10.19 was the latest npm release on 2026-09-23):

| File | Result |
|------|--------|
| `signature-input-drift.reject.json` | `valid: false`, `invalid_signature` |
| `signature-input-drift.conformant.json` | `valid: true` |
| `superseded-key.reject.json` | **`valid: true`** |
| `superseded-key.conformant.json` | `valid: true` |

In the JWKS path for receipts (`src/util/jwks.js`, `resolveFromJwks`), the key is matched by `kid` and checked for `kty`/`crv`. `valid_from`/`valid_until` are not read. The same package does check validity windows in another path, the claims-v211 key registry (`src/engines/claims-v211.js:348`), so the concept exists in the package but not in the receipt JWKS path. §9.2 is a SHOULD, so this is a gap and not a violation of a MUST. Scored against `expected_if_not_honoured`, 0.10.19 matches all four verdicts (re-run 2026-09-24).
