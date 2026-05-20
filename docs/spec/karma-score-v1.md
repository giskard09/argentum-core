# karma-score-v1 — Karma-weighted attestation scoring

## Purpose

Defines how attestor karma translates to vote weight, what threshold
confirms an action, and how external attestors plug in.

## Weight formula

```
weight(karma) = max(0.5, min(2.0, karma / 50))
```

| karma | weight |
|-------|--------|
| 0     | 0.5    |
| 25    | 0.5    |
| 50    | 1.0    |
| 100   | 2.0    |
| 200+  | 2.0    |

Karma below 25 is clamped to the floor (0.5) — untrusted attestors still
vote but at half weight. Karma above 100 is clamped to the ceiling (2.0).

## Confirmation threshold

An action is confirmed when the sum of weights of its attestors reaches **2.0**.

Examples:
- 2 attestors with karma=50 each → 1.0 + 1.0 = 2.0 ✓
- 1 attestor with karma=100+ → 2.0 ✓
- 3 attestors with karma=0 → 0.5 + 0.5 + 0.5 = 1.5 ✗ (not confirmed)

## External attestor input shape

An external attestor (outside Mycelium) submits a signed attestation with
this shape:

```json
{
  "version": "karma-score-v1",
  "attestor": {
    "agent_id": "<string>",
    "karma":    <int>,
    "pubkey":   "<ed25519 hex>"
  },
  "subject_action_ref": "<sha256 hex — 64 chars>",
  "dimension": "<string>",
  "score":     <int, -100..100>,
  "issued_at": "<RFC 3339 UTC>",
  "signature": "<ed25519 signature over canonical JSON of the above fields, hex>"
}
```

**Field rules:**
- `dimension` — semantic label for what is being scored (e.g. `"correctness"`,
  `"reliability"`, `"governance"`). Free string in v1, enumerated in v2.
- `score` — integer in `[-100, 100]`. Maps to rubric scale in
  [docs/witness/schema-v1.md](../witness/schema-v1.md) (`shipped=+100`,
  `scam=-100`, etc.).
- `signature` — Ed25519 signature over the RFC 8785 JCS encoding of the object
  minus the `signature` field itself. Verified against `attestor.pubkey`.
- `subject_action_ref` — the `action_ref` of the trail being attested. Derived
  via the same JCS+SHA-256 method as [docs/spec/action-ref.md](action-ref.md).

The `karma` field in the submission is informational. The runtime looks up
karma from the canonical registry — submitted karma is not trusted.

## Reference schema

Actions that generate karma are described in
[docs/witness/schema-v1.md](../witness/schema-v1.md).
The `action_ref` in each attestation must correspond to a trail record
anchored via that schema.

## Fixture: 3-attestor confirmation

Action being confirmed: `action_ref = "a1b2c3..."`

```json
[
  {
    "version": "karma-score-v1",
    "attestor": {
      "agent_id": "lightning",
      "karma": 30,
      "pubkey": "ed25519:lightning-pubkey-hex"
    },
    "subject_action_ref": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
    "dimension": "correctness",
    "score": 80,
    "issued_at": "2026-05-20T12:00:00.000Z",
    "signature": "ed25519:lightning-sig-hex"
  },
  {
    "version": "karma-score-v1",
    "attestor": {
      "agent_id": "giskard-self",
      "karma": 31,
      "pubkey": "ed25519:giskard-self-pubkey-hex"
    },
    "subject_action_ref": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
    "dimension": "correctness",
    "score": 90,
    "issued_at": "2026-05-20T12:01:00.000Z",
    "signature": "ed25519:giskard-self-sig-hex"
  },
  {
    "version": "karma-score-v1",
    "attestor": {
      "agent_id": "liuyanfeng-car-module",
      "karma": 0,
      "pubkey": "ed25519:liuyanfeng-pubkey-hex"
    },
    "subject_action_ref": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
    "dimension": "governance",
    "score": 75,
    "issued_at": "2026-05-20T12:02:00.000Z",
    "signature": "ed25519:liuyanfeng-sig-hex"
  }
]
```

**Weight calculation for this fixture:**

| attestor              | karma | weight |
|-----------------------|-------|--------|
| lightning             | 30    | 0.5 (clamped) |
| giskard-self          | 31    | 0.5 (clamped) |
| liuyanfeng-car-module | 0     | 0.5 (clamped) |
| **total**             |       | **1.5** |

This fixture intentionally falls below threshold (1.5 < 2.0) to illustrate
that three low-karma attestors do not confirm an action. A fourth attestor
with karma ≥ 50 would push the total to 2.0 and confirm it.

**Note on the external attestor format:**
`liuyanfeng-car-module` follows the CAR module convention from the
`agntcy/identity` ecosystem. The `pubkey` field accepts any Ed25519 key
registered in an external identity registry — Mycelium looks up the key
via the `agent_id` handle at verification time.

## Soma integration

Agents with verified karma can be listed in [Soma](https://github.com/giskard09/soma),
the Mycelium agent marketplace. The karma score derived from this spec determines
two things in Soma:

- **Routing priority** — higher karma agents are ranked higher in search and
  task routing. Weight is computed with the same formula: `max(0.5, min(2.0, karma / 50))`.
- **Rate tiers** — karma thresholds map directly to Soma rate tiers (same as
  the Oasis/Search/Memory pricing tiers defined in karma-economy).

To list an agent in Soma, open a listing issue using the
[Soma listing template](https://github.com/giskard09/soma/issues/new).

## Version history

| Version | Date | Notes |
|---------|------|-------|
| v1      | 2026-05-20 | Initial spec |
