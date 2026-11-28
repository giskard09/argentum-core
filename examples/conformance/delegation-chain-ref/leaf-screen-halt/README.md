# delegation-chain-ref · leaf-screen-halt

A reject vector for `delegation-chain-ref-v1`: a delegation chain that validly
authorizes a **payment** cannot anchor a **PII-screen halt** as its leaf action.

## What it exercises

The chain delegates payment authority, narrowing monotonically:

```
mycelium:*  ->  mycelium:payment  ->  mycelium:payment:route
```

Its `leaf_action_ref`, however, anchors a `PII_BLOCKED` presidio screen whose
preimage scope is `presidio:x402.screen:PII_BLOCKED:EMAIL_ADDRESS,US_SSN`.

Leaf-anchoring **recompute passes** — `leaf_action_ref` is exactly the screen's
own `action_ref` (`action-ref-v1`: `SHA-256(JCS({agent_id, action_type, scope,
timestamp}))`), and chain continuity, root anchoring, and monotonic narrowing all
hold. The chain is rejected on a single invariant, **`scope_mismatch_at_leaf`**:
the screen's scope is not the authorized leaf-hop scope. A payment authorization
does not cover a leaf whose identity is a different action.

## Layer boundary (why this is a *reject*, not a *halt*)

This verifier is **structural** — continuity, root, leaf-anchoring, narrowing. It
carries no verdict, so "`PII_BLOCKED` → composed halt" is not a property it can
express. The *halt* lives one level up, at the composed envelope, where the
`screen_ref` verdict `AND_PRESENT`-collapses the decision (see the comp-006
three-signer vector in `agentoracle-receipt-spec`). Two questions, two layers:

- **Chain layer** (here): *is this leaf the action the chain authorized?*
- **Envelope layer**: *does any sibling halt the composition?*

Whether the chain verifier should grow verdict-awareness so a leaf-halt is
checkable in-suite is an open question for the spec owner; either way the reject
below stands on the structural invariants alone.

## Canonicalization of this copy (declared limit)

This directory carries its own copy of the delegation-chain verifier, `verify.py`, written when the directory was added (`384e134`, 2026-06-28) and not updated with [`../verify.py`](../verify.py), which `../verify.py`'s docstring calls a frozen copy. Its `jcs()` is `json.dumps(sort_keys=True, ensure_ascii=False)`. That is **not** RFC 8785: it orders object keys outside the Basic Multilingual Plane by code point instead of by UTF-16 code unit, and writes numbers in Python's form (`1.0`, `1e-06`) instead of ECMAScript's (`1`, `0.000001`). The spec ([`delegation-chain-ref.md`](../../../../docs/spec/delegation-chain-ref.md), Derivation) requires RFC 8785. Nothing here claims otherwise: this copy is not an RFC 8785 implementation.

The copy is left as it is so that its bytes, which `../SHA256SUMS` lists, stay tied to the vectors of this directory. No object in this directory's JSON files has a key outside the BMP or a number whose two forms differ (every JSON subtree canonicalizes to the same bytes under this copy and under the repo's `jcs.py`); `tests/test_delegation_chain_frozen_jcs.py` checks that and fails if such data is added, so the choice between changing the copy and keeping it is made again then. For the current reference behaviour (RFC 8785 since 2026-11-26) see [`../verify.py`](../verify.py).

## Provenance

The `screen_ref` is `action-ref-v1`, produced by
[`presidio-hardened-x402`](https://github.com/presidio-v/presidio-hardened-x402)
`action_ref.py` (`compute_screen_ref`), and byte-matches the published
`presidio-x402-003/004/005` screen vectors.

## Run

```
python verify.py
```

Expected: `1/1 passed` — `leaf-screen-halt-001` correctly rejected with
`scope_mismatch_at_leaf`.
