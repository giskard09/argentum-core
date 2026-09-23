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

The window check has a limit. `issued_at` is asserted by the signer, so the check catches a key that is still in use after an honest rotation. It does not catch a compromised key whose holder backdates `issued_at` into the window.

## Run

```
python3 examples/conformance/farley-receipt-signature/verify.py   # exit 0 iff all four match index.json
python3 examples/conformance/farley-receipt-signature/build.py    # regenerates the files byte for byte
```

CI runs `tests/test_farley_receipt_vectors.py`. It checks four things:

- every vector matches `index.json`;
- `build.py` regenerates the files byte for byte;
- the superseded-key pair differs only in `issued_at`;
- the reference verifier refuses mutated receipts: wrong envelope shape, `alg`, a signature inside the signing input, tampering, missing field, bad encoding, and a mismatch between `kid` and `issuer_id`.

## Observed: @veritasacta/verify 0.10.19

Run with `--jwks ./jwks.json --mode receipt` (0.10.19 was the latest npm release on 2026-09-23):

| File | Result |
|------|--------|
| `signature-input-drift.reject.json` | `valid: false`, `invalid_signature` |
| `signature-input-drift.conformant.json` | `valid: true` |
| `superseded-key.reject.json` | **`valid: true`** |
| `superseded-key.conformant.json` | `valid: true` |

In the JWKS path for receipts (`src/util/jwks.js`, `resolveFromJwks`), the key is matched by `kid` and checked for `kty`/`crv`. `valid_from`/`valid_until` are not read. The same package does check validity windows in another path, the claims-v211 key registry (`src/engines/claims-v211.js:348`), so the concept exists in the package but not in the receipt JWKS path. §9.2 is a SHOULD, so this is a gap and not a violation of a MUST.
