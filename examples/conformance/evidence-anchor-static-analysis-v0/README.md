# evidence-anchor-static-analysis-v0

EvidenceAnchor conformance vectors for an **AgentGraph static-analysis scan event**, following
the `action-ref-v1` derivation and the `examples/conformance/` layout.

```
action_ref = SHA-256(JCS({agent_id, action_type, scope, timestamp}))
```

- `agent_id` — the scanner identity (`did:web:agentgraph.co`)
- `action_type` — `static_analysis.scan` (the scanner operation)
- `scope` — the target tool identity (MCP server URI / package ref)
- `timestamp` — RFC 3339 (ms), the logical scan time

The **verdict** (`grade` / `findings` / `cve_list` / `outcome`) is kept **out of the preimage** —
the load-bearing design choice: `action_ref` stays stable as the correlation key across re-scans of
the same target, while the evidence it points at can change, and a verifier confirms *identity*
(the anchor) and *evidence* (the verdict) independently.

## Invariants

1. **rescan_idempotency** — same `{agent_id, action_type, scope, timestamp}` → same `action_ref`
   (`POS-1` ≡ `INV-1`, even though the verdict differs).
2. **distinct_events** — a later `timestamp` → different `action_ref` (`INV-2`).
3. **evidence_independence** — the verdict is never in the `action_ref` preimage.

## Vectors

| Vector | Expectation | Notes |
|---|---|---|
| `POS-1_clean_mcp` | PASS | grade A, 0 critical/high → admit |
| `NEG-1_critical_mcp` | FAIL | 2 critical / 3 high + CVE → deny |
| `INV-1_rescan_stable_ref` | PASS | same preimage as POS-1 → identical `action_ref` |
| `INV-2_later_distinct_ref` | PASS | later timestamp → distinct `action_ref` |

## Reproduce

```bash
pip install rfc8785
python3 verify.py
```

`action_ref` uses the `rfc8785` package (true RFC 8785 JCS). For these flat preimages it is
byte-identical to `json.dumps(…, sort_keys=True)`; `rfc8785` additionally handles nested objects
and number canonicalization, so the same verifier holds for the full attestation envelope. The
AgentGraph source set is mirrored at
[agentgraph-co/agentgraph → docs/conformance/evidence-anchor-static-analysis-v0](https://github.com/agentgraph-co/agentgraph/tree/main/docs/conformance/evidence-anchor-static-analysis-v0).
