# mycelium.feedback.v1 — JSON schema

Format for the content pointed to by `feedbackURI` in a canonical
ERC-8004 `giveFeedback` call.

## Minimal object

```json
{
  "version": "mycelium.feedback.v1",
  "rater": {
    "address": "0x...",
    "agent_handle": "string"
  },
  "subject": {
    "agent_id": 3249,
    "agent_handle": "string"
  },
  "issued_at": "2026-04-24T00:00:00Z",
  "claim": {
    "type": "shipped|partial|review|neutral|miss|regression|scam",
    "summary": "short natural language claim (<= 240 chars)",
    "evidence": [
      {"kind": "github_pr", "url": "...", "sha": "..."},
      {"kind": "tx", "chain": "arbitrum-one|eth-sepolia|...", "hash": "0x..."},
      {"kind": "endpoint", "url": "..."},
      {"kind": "ipfs", "cid": "Qm..."}
    ]
  },
  "rubric_version": "mycelium.rubric.v1",
  "nonce": "hex-or-uuid"
}
```

## Field rules

- `rater.address` must match `msg.sender` of the on-chain `giveFeedback` call.
- `subject.agent_id` must match the `agentId` argument.
- `issued_at` must be within 24h of the on-chain tx block timestamp.
- `claim.type` must match `tag1` of the on-chain call.
- `evidence` must contain at least one item. Empty arrays are invalid.
- `nonce` protects against replay when the same rater scores the same subject
  repeatedly with identical content.

## Hash commitment

`feedbackHash` on-chain = `keccak256(utf8_bytes(canonical_json))` where
canonical form is the file as published (no whitespace normalization
prescribed in v1 — future versions may tighten this).

## Version bump policy

Breaking changes bump the major version. The `version` field in the JSON
must match the rubric referenced via `rubric_version`.
