# action-ref-v1-jcs-sha256 against two sets of stated requirements

Status: a working map for review, not a conformance claim, not an endorsement by anyone.

Sources read for this map (all re-read on 2026-11-11):

- **S** = `docs/spec/action-ref.md`, argentum-core `5fca1de` (file last changed in `623ee0a`), spec version 1.2.
- **D4** = `draft-etcheverry-action-ref-04`, the revision published on datatracker (rev 04, 2026-10-23). A `-05` file exists locally and is NOT published; nothing here relies on it.
- Requirements: imokokok in x402#2833 (comment 6789705166) and XFuel-Lab in tsc#4 (comment 6798531098).

Verdict values: CUMPLE / PARCIAL / NO CUMPLE / NO DECLARADO. "NO DECLARADO" means the source is silent; it does not mean the property is absent or present.

Framing point first: the `action_ref` preimage is four fields (`agent_id`, `action_type`, `scope`, `timestamp`; D4 section 3.1, S "Fields"). No request body or request parameters enter it. `action_ref` is therefore an action identifier, not a request-params hash. The rows below ask what the profile says about the properties imokokok lists for an interoperable request-hash field.

## A. imokokok (x402#2833, 6789705166): "explicit hash algorithm, canonicalization rule, domain separation rule, and a declared privacy mode"

| # | Requirement | Verdict | Where, and what it actually says |
|---|---|---|---|
| A1 | Explicit hash algorithm | CUMPLE | D4 3.3: `action_ref = SHA-256(JCS(preimage))`, lowercase hex, 64 chars. S "Derivation". The envelope also carries `hash_algo` (D4 4.1; the envelope fields are SHOULD, not MUST). |
| A2 | Explicit canonicalization rule | CUMPLE, with two unresolved differences between S and D4 | D4 3.2: RFC 8785 JCS. S "Serialization": RFC 8785. Differences: (1) outside the ASCII-only band, S "Domain" says the verifier MUST return `OUT_OF_PROFILE_DOMAIN` and that there is no "use a compliant library" fallback; D4 3.2 says implementations MUST use an RFC 8785-compliant library. (2) key order is "Unicode code point order" in D4 3.2 and "UTF-16 code unit order" in S; the four keys are ASCII so both give the same bytes. |
| A3 | Domain separation rule | NO CUMPLE (v1) | S "Version negotiation": v1 "has no domain tag: the raw JCS bytes of the four canonical fields are hashed directly", and S names the cross-protocol collision risk for that shape. The profile `action-ref-v1-jcs-sha256` is this v1 derivation (D4 section 11 uses the name for the frozen profile). |
| A3b | Domain separation, v2 | NO DECLARADO in D4 | S defines a separate v2 derivation: byte prefix `mycelium.action-ref:v2:` before the JCS bytes, string form `v2:<hex>` (S "v2 derivation"; tag `action-ref-v2.0`). D4 section 3 does not define it; D4 section 11 only mentions "6 domain-separated v2 vectors" in an implementation description. v2 is a different hash space, not a property of v1. |
| A4 | Declared privacy mode (unsalted / salted / not equality-testable) | NO DECLARADO | Neither S nor D4 contains a statement about salting, low-entropy inputs or equality testing for `action_ref` (grep for salt, privacy, equality, entropy: 0 hits in both). Not in the text but a consequence of it, and ours rather than the spec's: D4 9.4 requires the four preimage fields to be disclosed to verifiers for the operator-independence property, and nothing in the derivation is salted, so anyone holding the four fields can test equality. |
| A4b | Salted per-field commitment | Separate profile | `disclosure-scoped-ref` (`docs/spec/disclosure-scoped-ref.md`): per-field salt, at least 128 bits, REQUIRED. It is a sibling profile with its own digest, not part of `action_ref`. |

## B. XFuel-Lab (tsc#4, 6798531098)

| # | Requirement | Verdict | Where, and what it actually says |
|---|---|---|---|
| B1 | An existence bound the issuer does not control, named as a separate claim class | PARCIAL | D4 9.4 separates the *internally-consistent* case (recomputation is enough) from the *externally-witnessed* case (depends on "a timestamp or inclusion proof from a system the operator does not control (e.g. an on-chain anchor, or a SCITT receipt)"), and says this is "not an additional preimage field". D4 10: an anchor proves "one identifier existed, not that no other action occurred". D4 10.1: `anchoredBy` "is not evidence that the submitter is independent of the emitter". Missing: it is not named a claim class, and no sentence says an existence bound does not show the signing key was uncompromised (grep for "compromis": 0 hits in D4; 1 hit in S, at the revocation-authority paragraph about a stale or compromised registry, unrelated to signing keys). That part is NO DECLARADO. |
| B2 | `issuedAt` is signer-stated | PARCIAL | `issuedAt` is a field of the x402 draft XFuel-Lab cites, not of `action_ref`. The nearest field here is `timestamp`: S "Timestamp format" defines it as the moment the action was claimed; S "Boundary" says `agent_id`, `action_type` and `scope` are caller-supplied, that in the reference implementation `timestamp` is generated by the anchoring function (i.e. by the emitter), and that a well-formed `action_ref` "can still describe the wrong action". D4 9.3 only addresses format manipulation. No sentence says the `timestamp` is signer-declared and uncorroborated by itself. |
| B3 | Binding strength declared (which identifier ties the record to the payment) | NO CUMPLE / NO DECLARADO | No payment identifier is in the preimage and no field declares a binding kind. S "Boundary" says binding to an independently observable effect "is a sibling concern, not a member". `docs/spec/guarantee-model.md` ("Trail status states") describes an `outcome_handle` (a `tx_hash` is one instance) as a refetch handle, not as a declared binding strength. The vectors in this directory show a *declared* `binding.kind` with a stated strength; that is new material, not something the spec has today. |
| B4 | Recomputability bar needs a carve-out for anchor checks | CUMPLE, as declared | D4 10.1 is headed "(Informative)" and says checking whether the block is canonical "is a single lookup by block hash against any node"; D4 10 says a SCITT receipt MAY replace the on-chain anchor without changing the derivation. So anchoring is already an optional, chain-read layer in D4. The "bytes plus a standard-library verifier" bar is XFuel-Lab's proposal for the WG, not a statement in D4. |
| B5 | Canonicalization edge cases (duplicate keys, lone surrogates, control-character escapes, number forms) | PARCIAL | S "Domain" lists non-ASCII agent identifiers, surrogate-pair scope strings, malformed timestamp grammar and duplicate preimage keys as out-of-profile (`OUT_OF_PROFILE_DOMAIN`); vectors in `examples/conformance/action-ref-v1-domain-negative/`. Control-character escapes and number forms are not enumerated in S or D4, and the preimage contains no numbers. Not checked here: whether those vectors cover each case XFuel-Lab lists. |

## What these vectors add, and what they do not

- They keep the signer-declared `timestamp` and the anchored existence bound as two different claims in the output (`declared` vs `existence`), and always list what an anchor does not establish: that the declared time is true, that the key was uncompromised at the bound, that the set of actions is complete.
- The positive existence vector is a real anchor (Base mainnet). The declared timestamp in that preimage is 6035 seconds before the block time; nothing in the evidence says whether it was true.
- They make the binding kind a declared field and show amount+payTo failing to separate two same-price calls. All binding data is synthetic.
- They do not show adoption, independence of any third party, or endorsement. They show consistency under the evidence in `vectors.json`.
