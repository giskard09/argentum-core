# action-ref near-miss conformance vectors — v1

Near-miss conformance vectors for the `action_ref` spec. Each vector represents a failure mode that a verifier **MUST** reject (fail-closed). An implementation that returns the correct `expected_error_code` for each input satisfies the near-miss boundary of `action-ref-v1`.

**Source:** [`agentgraph-co/agentgraph`](https://github.com/agentgraph-co/agentgraph) @ commit `a07cdf8`  
**Published at:** `https://agentgraph.co/.well-known/action-ref-near-miss-vectors.json`  
**Spec:** `draft-giskard-aeoess-action-ref`  
**Canonicalization:** RFC 8785 (JCS)

## Failure modes

| Vector | Failure mode | Description |
|--------|-------------|-------------|
| `ambiguous_issuer_binding` | `AMBIGUOUS_ISSUER_BINDING` | Same `action_ref` bound to two issuers with disjoint verdicts — injectivity violation |
| `rescoped_replay` | `RESCOPED_REPLAY` | Attestation issued for `read` scope presented against `write` scope — `action_ref` mismatch |
| `semantic_drift` | `SEMANTIC_DRIFT` | `action_type` differs between issuance (`behavioral_eval`) and verification (`behavioral`) — vocabulary drift |
| `same_action_ref_different_state` | `KNOWN_DESIGN_PROPERTY` | Same preimage, different execution state (in-progress vs terminal) → same `action_ref`. Correct by design; a verifier MUST NOT reject on this basis |

## Verification

All three `canonical_sha256` values are byte-match verifiable against the JCS preimage:

```python
import hashlib, json

def jcs(obj):
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

action_ref = "sha256:" + hashlib.sha256(jcs(preimage).encode()).hexdigest()
```

A conformant verifier **MUST**:
1. Recompute `action_ref` over the presented tuple before accepting any attestation.
2. Reject with `RESCOPED_REPLAY` if embedded and recomputed `action_ref` diverge.
3. Reject with `AMBIGUOUS_ISSUER_BINDING` if `(claim_type, evidenceType, source_provider_did)` does not uniquely select a verdict.
4. Reject with `SEMANTIC_DRIFT` if `action_type` is not from the closed canonical vocabulary at both issuance and verification.

## Attribution

Vectors authored by [agentgraph-co/agentgraph](https://github.com/agentgraph-co/agentgraph), incorporated per [A2A discussion #1734](https://github.com/a2aproject/A2A/discussions/1734#discussioncomment-17124409).
