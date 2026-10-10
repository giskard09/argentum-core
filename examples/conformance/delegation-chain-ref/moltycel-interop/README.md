# MoltyCel AAE vector interop (delegation-chain-ref-v1)

Runs two real conformance vectors from [MoltyCel/aae-conformance-vectors](
https://github.com/MoltyCel/aae-conformance-vectors) (tag `v1.0.0`, commit
`22a08d76ef76fda19274a687081523443e2ce7d0`, Apache-2.0) through this repo's
own verifier, after translating each vector's AAE/VC2 encoding into a
delegation-chain-ref-v1 `chain_artifact`. The two source files are vendored
verbatim in `source-vectors/` (byte-identical to the GitHub blobs — verified
by git blob SHA, not just re-serialized JSON) for independent reproduction
without depending on GitHub being reachable.

**Why these two, and not the rest of the set:** `vectors/11-delegation-
cascade-revocation.json` is the vector that actually exercises the same
real-world scenario as this repo's own AAE-02 §7.5 enforcement layer
(`revoked-ancestor/verify_enforcement.py`, commit `617cb8c`): a delegated
grant whose ancestor is revoked. `vectors/05-single-use-replay.json` tests a
different invariant (replay of an already-consumed credential), which maps
to `verify.py`'s `replay_detected`/`SeenRegistry`, not to §7.5 — it was
built in parallel because it is the same kind of cheap, already-supported
cross-implementation check, not because MoltyCel or anyone else asked for
it specifically.

The `vectors/enforce/` folder in MoltyCel's repo (26 vectors, unreleased —
on `main`, not tagged) is **out of scope here on purpose**: those vectors
test an ABAC-style constraint/policy engine (`type_fields`, exact/enum/range
constraints, forbid-outranks-grant, ratification by issuing principal).
Nothing in delegation-chain-ref-v1 implements or claims that model.
Building an adapter for it would mean implementing MoltyCel's policy engine
from scratch to satisfy its own schema — that tests MoltyCel's engine
against itself, not this repo's verifier against anything. Translating
those 26 vectors is not on this repo's roadmap.

## What this proves and what it does not

What it proves: `verify.py` + `verify_enforcement.py`, run unmodified
against a translated version of MoltyCel's own scenario, reach the same
REJECT verdict MoltyCel's AAE verifier reaches, for both vectors. That is a
real cross-implementation agreement on two concrete scenarios.

What it does not prove: that delegation-chain-ref-v1 implements AAE, or
that this translation is the only reasonable one. `docs/spec/delegation-
chain-ref.md:17` already states "no vector in this repository is an AAE
conformance test" — this folder does not change that. `translate.py`'s
module docstring lists every translation choice made and why, including
three places where the two formats genuinely check different things (see
"Structural differences found" below) — those are not bugs in the
translation, they are what the comparison was for.

## Running it

```
pip install -r ../../../../requirements.txt   # PyNaCl, for verify.py's Ed25519 check
python run_interop.py
```

Exits 0 if both translated vectors agree with MoltyCel's declared `expected`
result. Prints a report and `REPORT_SHA256` last; `main()` runs the report
twice in-process and asserts the digest matches before printing, so a
reviewer does not have to run it twice by hand to check determinism (though
they can — repeated runs across separate processes were also checked while
building this and produced the same digest).

## Structural differences found (not translation artifacts)

1. **Narrowing dimension.** delegation-chain-ref-v1 narrows authority via a
   colon-namespaced `scope` string (parent-prefix matching). AAE-02 narrows
   via action-set subset (vector 11's depth-1 mandate drops "book", keeps
   only "read") and constraint tightening (`max_transaction_value` 500 →
   300) — and has no `scope` field at the delegated hop at all. AAE's model
   is more expressive here (it can narrow *which actions* and *by how
   much*, not just a namespace path); ours is simpler to check
   mechanically. Carrying the parent's scope forward unchanged for the
   translated hop (equal, which `scope_is_narrower_or_equal` allows) is the
   most faithful mapping available, not evidence we checked AAE's actual
   narrowing.

2. **Replay protection is opt-in in AAE, unconditional here.** AAE's
   `single_use` is a flag the issuer sets per credential; absent or false,
   presumably reuse is allowed. `verify.py`'s `SeenRegistry` has no such
   flag — every accepted `chain_id`/`delegation_ref` is protected against
   resubmission, always. The vector-05 translation reproduces the concrete
   scenario (same id presented after being recorded as consumed), not the
   opt-in/opt-out semantics.

3. **Revocation evidence shape.** AAE's `revocation_responses` in vector 11
   is a boolean (`revoked: true`) with no timestamp, checked against a live
   `revocation_check` URI in general use. This repo's `revocation-ref-v1`
   convention carries a `revoked_at` timestamp. `enforce_7_5()` does not
   read `revoked_at` for its decision (only revoked-id membership), so this
   is inert for the verdict — but `translate.py` had to supply *something*
   syntactically, and used the vector's own `context.current_time` as an
   explicitly-labeled stand-in, not data MoltyCel supplied.

## Credit

Vectors: MoltyCel/CryptoKRI GmbH, Apache-2.0 (see `source-vectors/` for the
vendored files; original `NOTICE` text at the source repo applies to them).
Framing that connecting our PR#123 + babyblueviper1's reproduction to a
MoltyCel vector run would give AAE-02 §7.5 its first cross-implementation
check: goun7, in x402#2332.
