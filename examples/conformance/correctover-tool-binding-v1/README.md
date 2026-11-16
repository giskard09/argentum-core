# Correctover independent conformance set — runtime tool-binding (draft-etcheverry-action-ref -05)

Fourth independent author-set in the action-ref ecosystem (after trail, agentavow, agentgraph — the
latter two also contributed under `examples/conformance/`). This suite is contributed in parallel to
the `conformance/correctover/` directory of
[`giskard09/draft-etcheverry-action-ref`](https://github.com/giskard09/draft-etcheverry-action-ref/pull/12)
(PR #12, three commits) and is byte-identical to the head commit there (1e61664 + the layer-separation
README commit).

**Focus**: this author-set contributes what the JCS comparison-semantics suites deliberately do not cover — **runtime tool-binding cases that a digest-only pipeline cannot decide**. The preimage/anchor layer proves the record was not tampered with; these vectors decide whether the tool identity and parameter set behind the record still bind to the approved declaration at settlement time, including the freshness-layer optional fields (`authority_verified_at_ms` / `revocation_check_at_ms`) used as a settlement-time MUST, and delegation-resolved subject binding per the -05 delegation-resolution section.

## Layer separation (per -05 §5.2)

-05 §5.2 requires the signer of the Decision record to be independent of the actor/executor **before** the outcome is final, and excludes the after-the-fact referee role from satisfying it. This author-set does not contest that requirement — it states plainly which layer each artifact occupies:

- **Authorization-layer independence** is guaranteed at write time by the Receipt SDK: the signer of record is a party independent of the actor, established before the decision is executed. Nothing in this suite substitutes for that.
- **Integrity-layer verification** is what this suite and the Public Verifier claim: that a signed record, once written, has not been tampered with and that its digests are recomputable by anyone, after the fact, offline. Under -05 §5.2 this is verification of integrity, not of authorization — and it is not claimed as authorization.

The two layers compose: the write-time independent signature is what makes the post-hoc integrity verdict worth anything; the post-hoc verification is what makes the write-time claim auditable without trusting the producer.

## The claim, and how to falsify it

The claim is not that these records are malformed. Every anchor carries a real `effective_args_digest` = SHA-256(JCS(`effective_args`)). On five of the seven, that digest verifies and a digest-only pipeline therefore **passes** the record; binding refuses it. `verify.py` prints both verdicts side by side for exactly this reason — the `digest-only=` column is the falsification handle. If a reviewer can make a digest-only pipeline reject any of those five, the suite is wrong about the case it claims to cover.

## Contents
- `correctover-tool-binding-v1-vectors.json` — 7 fixed anchors, reason-classed (tool-identity / label-integrity / param-widening / stale-authority / delegation-unresolved), each with a real digest
- `verify.py` — the independent verifier, dependency-free, written from -05 alone with no reference to the other author-set implementations

## Reproduce
```
python3 examples/conformance/correctover-tool-binding-v1/verify.py
# 7/7 verdicts agree. Zero-disagreement is the author-set requirement.
# 5 of 7 anchors are decided by binding alone: a digest-only pipeline passes them and this verifier refuses them.
```

## Known gaps (declared, per house rule: no reproduction evidence = no finding)
1. The JCS implementation inside `verify.py` is `sorted keys + no whitespace + minimal escaping`, which is byte-exact for the fixed ASCII preimages here. It is not a general RFC 8785 implementation. Byte-level conformance for non-ASCII inputs belongs to the three JCS comparison-semantics author-sets and is intentionally not duplicated here.
2. `approved_action_type` is a local extension, not a field defined by -05. It models the approved-declaration side of the label check; without it the label comparison has nothing to compare against, since -05 fixes `action_type` as a single preimage field and says nothing about how a relying party learns what was approved.
3. A second independently written verifier (verifier-two) is in progress; until it lands, zero-disagreement is claimed within this single implementation only.

## Author
Correctover (github.com/DSHCorrectover). Independent of trail / agentavow / agentgraph author-sets.
