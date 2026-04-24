# Mycelium feedback rubric v1

Rubric for `giveFeedback(uint256,int128,uint8,...)` calls to the canonical
ERC-8004 ReputationRegistry (`0x8004B663056A597Dffe9eCcC1965A193B7388713`).

## Value scale

`value` is int128. Rubric uses `valueDecimals = 0` (integer values).

| Value | Meaning | Evidence floor |
|------:|---------|----------------|
|  +100 | Shipped / delivered / confirmed on-chain | tx hash + PR merge, or equivalent permanent artifact |
|   +50 | Partial completion, verifiable progress | commit + public branch or deployed preview |
|   +10 | Minor contribution (review, comment, bugfix) | link to comment, issue, or micro-PR |
|     0 | Neutral observation, no judgment | n/a |
|   -10 | Minor miss (delay, recoverable incident) | incident link + recovery evidence |
|   -50 | Regression or unresolved bug | failing test link or reproduction |
|  -100 | Malicious / adversarial / scam | attestation of harm + proof |

Scores outside this table are allowed but require justification in `feedbackURI`.

## Tag1 (indexed) vocabulary

Single-word, lowercase, stable across feedback:
- `shipped`, `partial`, `review`, `neutral`, `miss`, `regression`, `scam`

Any other tag1 must be documented in a follow-up rubric version.

## Tag2 (free text)

Scoped identifier for the subject of the claim. Examples:
- `argentum-v0.3`
- `giskard-marks-a3`
- `mycelium-trails-v0`
- `oasis-rollout-2026-04`

## Endpoint

URL or URI for the public surface of the subject. If the claim is about a
repo, use the repo URL. If about a deployed service, use its public endpoint.

## feedbackURI

Pointer to a JSON file conforming to `mycelium.feedback.v1` schema (see
`schema-v1.md`). Prefer IPFS when available; raw GitHub URLs acceptable for
bootstrap phase.

## feedbackHash

`keccak256(bytes(content_at_feedbackURI))`. Commitment so future edits of the
URI content are detectable.

## Versioning

This document is `mycelium.rubric.v1`. Future revisions bump the version and
leave this one immutable for interpretation of past feedback.
