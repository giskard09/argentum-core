Both files in this directory are vendored verbatim from
https://github.com/MoltyCel/aae-conformance-vectors, tag `v1.0.0`, commit
`22a08d76ef76fda19274a687081523443e2ce7d0`:

- `05-single-use-replay.json` (source: `vectors/05-single-use-replay.json`)
- `11-delegation-cascade-revocation.json` (source: `vectors/11-delegation-cascade-revocation.json`)

Verified byte-identical to the GitHub blobs via `git hash-object` matching
the tree's recorded blob SHA, not re-serialized.

Original NOTICE (reproduced per Apache-2.0 §4(d)):

> AAE Conformance Vectors
> Copyright (c) 2026 CryptoKRI GmbH, Zurich (MolTrust)
>
> Licensed under the Apache License, Version 2.0 (see LICENSE).
>
> The test keys under testkeys/ are public and exist only to make the signed
> vectors reproducible. They are not secrets and MUST NOT be used in production.

No test keys from that repo are used or vendored here — see
`../translate.py`'s module docstring for why JWS signature verification is
out of scope for this translation.
