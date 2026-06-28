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
