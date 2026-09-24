# host-capability-ref

What a verifier reports when the host running it lacks an algorithm the
artifact's profile allows. Artifact-side corpora only exercise what the
artifact contains. Here the variable is the host, so a vector has no single
right answer: it has a set of verdicts a conformant verifier may return,
depending on what that verifier can run.

The gap was pointed out by Noûs (robertolocatelli81-dev) in the x402
Foundation TSC discussion of corpus requirements (comment 5808537300): with
artifact-side vectors only, a NOT_ASSESSED can hide a FAIL and no vector
detects it.

## Rules

- A missing capability is a property of the host, not of the artifact. A
  host without the algorithm returns `NOT_ASSESSED` with reason
  `capability_unavailable:<scheme>`. It is not `verify_invalid` in the sense
  of `docs/spec/verify-failure-mode-ref.md`: the evidence was not
  contradicted, it was not checked.
- An adverse finding the host can make without that capability is `FAIL` on
  every host. Here that is a preimage that no longer matches its declared
  canonical bytes (`preimage_jcs_mismatch`).
- Verdict precedence: `FAIL` > `NOT_ASSESSED` > `PASS`.

## Vectors

| id | expected (any conformant host) | with bip340 | without |
| --- | --- | --- | --- |
| `hc-001-valid-signature` | PASS, NOT_ASSESSED — FAIL not allowed | PASS | NOT_ASSESSED |
| `hc-002-invalid-signature` | FAIL, NOT_ASSESSED — PASS not allowed | FAIL `signature_invalid` | NOT_ASSESSED |
| `hc-003-mixed-preimage-mismatch` | FAIL | FAIL `preimage_jcs_mismatch` | FAIL `preimage_jcs_mismatch` |

The signature algorithm is BIP-340 Schnorr over secp256k1, using the
pure-Python implementation in `../composed-attestation-bip340-cell/bip340.py`
(imported, not copied; that corpus is unchanged). The key is derived from a
public seed and signs nothing outside this fixture.

## Run

```
python3 build.py --check   # vectors.json is byte-reproducible
python3 verify.py          # scores every vector on both hosts
```

`tests/test_host_capability_ref.py` also runs five mutants of the verifier.
It asserts the exact (vector, host) cases each mutant turns red, and each
vector is caught by at least one mutant.
