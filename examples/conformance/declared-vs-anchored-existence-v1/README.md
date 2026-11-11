# declared-vs-anchored-existence-v1

CC0-1.0. Vectors that keep two claims apart:

1. **Declared**: the `timestamp` inside the `action_ref` preimage is stated by the emitter.
2. **Anchored existence**: an `Anchored` event for the same digest, from a contract the emitter does not control, bounds when the digest existed. It does not show the declared time was true, that the signing key was uncompromised at that time, or that the set of anchored actions is complete.

Plus a **declared binding** field: a record states which identifier ties it to a payment (`authorization_nonce`, `tx_hash`, `amount_payto`), and the verifier reads strength from the declared kind. In the amount+payTo case, two same-price calls are not distinguishable.

## Run

```
python3 verify.py                 # vectors, no network
python3 -m unittest test_verify   # properties, no network
python3 verify.py --live          # optional: re-reads the anchor from Base mainnet
python3 build_vectors.py          # regenerate vectors.json
```

## The tension, stated

Verifying an anchor needs a chain read. Offline, `verify.py` only checks the *captured* evidence for internal consistency; vector `K1` shows a fabricated but internally consistent capture is accepted offline, and only `--live` (a lookup of the transaction and block) catches it. Anchor checking is therefore an optional layer or an explicit carve-out from a "bytes plus standard library" bar, not part of it. `draft-etcheverry-action-ref-04` section 10.1 already presents on-chain anchoring as informative.

## Real and synthetic

- Real: the P1/P2 preimage (from `giskard09/delivery-receipt-anchor`) and its Base mainnet anchor, block 51345144, tx `0xb1144ee8777262b0d3ac2cd6ea342f14daa300cb5a4401f082e070ae18aed125`.
- Synthetic: the tampered captures N3 to N7 and K1, and every binding vector (nonces, hashes and addresses are placeholders).

No claim of adoption, endorsement or third-party independence. See `REQUIREMENTS_MAP.md` for the spec-by-spec map.
