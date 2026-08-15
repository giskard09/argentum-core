# composed-attestation-bip340-cell

Co-suite artifact requested by kenneives in
[giskard09/composed-attestation-3leg-worked-example#2](https://github.com/giskard09/composed-attestation-3leg-worked-example/issues/2)
(comment [5303696037](https://github.com/giskard09/composed-attestation-3leg-worked-example/issues/2#issuecomment-5303696037)):
a BIP-340 (Schnorr/secp256k1) cell whose signed preimage carries this suite's
real `action_ref` v2 value — `authority_ref` — as a top-level string, embedded
verbatim, so R3 (drop-one-signature) breaks validation on either side if
either suite's signature is removed.

## Files

- `bip340.py` — pure-Python BIP-340 sign/verify (no coincurve binding
  available in this environment). Cross-checked against `eth_keys` for
  `pubkey_gen` correctness and round-trip/tamper-tested against itself —
  see commit message for the verification steps run before trusting it.
- `generate.py` — builds `cell.json` deterministically (fixed seed + fixed
  `aux_rand`), so a reviewer regenerates and diffs rather than trusting
  committed bytes.
- `cell.json` — the artifact. `preimage.authority_ref` is
  `examples/conformance/action-ref-v2/action-ref-v2.fixture.json#arv2-001`,
  the same NEXUS oracle-signal example already published in
  `docs/spec/action-ref.md`.
- `verify.py` — independent verifier: recomputes JCS, checks the signature,
  confirms `authority_ref` is present verbatim in the signed bytes, and runs
  the R3 negative twice (corrupted signature, tampered `authority_ref`) —
  both must FAIL.

## Run

```
python3 generate.py   # writes cell.json (deterministic, diff against committed copy)
python3 verify.py     # ALL CHECKS PASS
```

## Handoff

Per kenneives' comment: send this cell (or point at it) once built, before
anyone on their side pins it. Not sent yet — awaiting estrategia's go-ahead.
