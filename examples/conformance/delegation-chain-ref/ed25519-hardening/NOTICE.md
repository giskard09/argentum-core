`novifinancial-ed25519-speccheck-cases.json` in this directory is vendored
verbatim from https://github.com/novifinancial/ed25519-speccheck, commit
`65519336fda78a3d016e947df6d82848aca0c9da` (file: `cases.json`).

Verified byte-identical to that commit's GitHub blob via `git hash-object`
matching the recorded blob SHA `8686dcb7eef8b6abe36ca8fa9bb10de112e63774`
for that path at that commit, not re-serialized.

That repository is licensed under the Apache License, Version 2.0 (no
separate NOTICE file exists upstream to reproduce). Per its README:

> The authors of this code are Kostas Chalkias ([@kchalkias]), François
> Garillot ([@huitseeker]) and Valeria Nikolaenko ([@valerini]).
>
> Special thanks go to Yolan Romailler, Rajath Shanbag and Rob Starkey for
> contributing test vector results.

The `EXPECTED_LIBSODIUM_ACCEPTS` set in `check_hardening.py` is transcribed
from that same commit's `results.md` condition table (the "LibSodium"
row) — not re-derived by us. This directory tests whether this repo's own
pinned PyNaCl (`../requirements.txt`) still matches that published,
third-party-audited result; it is not a claim about the test vectors'
own correctness, which is novifinancial's work.
