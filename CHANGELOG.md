# Changelog

## [Unreleased]

### Changed — disclosure-scoped-ref: verifier canonicalizes with RFC 8785 (2026-11-26)

- `verify.py` computed JCS with `json.dumps(sort_keys=True)` from its first revision (`65ddd3c`, 2026-07-08) until now, which the spec says not to use in Python: it differs from RFC 8785 for object keys outside the BMP and for number forms. `verify.mjs` was not affected. It now calls the repo's `jcs.py`; a field value holding an integer outside ±(2^53−1) ends the run with a `ValueError` instead of being hashed exactly. Spec text unchanged; one note added.
- Compatibility, measured with the old and the new `verify.py`: all 94 JSON subtrees of `vectors.json` canonicalize to identical bytes, and the verifier output and exit code are identical. No published hash and no verdict changes.
- No vector was added: the fixture is one record with three scripted vectors, and a vector with such data needs a second fixture. `tests/test_jcs_disclosure_scoped_ref.py` (6 tests) pins the behaviour at function level, including a field digest checked against a hand-written canonical string; reverting `jcs()` to `sort_keys` fails 5 of the 6.
- Run from a checkout of the repository: `verify.py` now imports `jcs.py` from the repository root; before, the folder alone was enough. `verify.mjs` is still self-contained.

### Changed — recipient-allocation-ref: verifier canonicalizes with RFC 8785 (2026-11-26)

- `verify.py` computed JCS with `json.dumps(sort_keys=True)` from its first revision (`5aaa1f2`, 2026-06-27) until now, which the spec says not to use: it differs from RFC 8785 for object keys outside the BMP and for number forms. It now calls the repo's `jcs.py`; an integer outside ±(2^53−1) ends the run with a `ValueError` (the script has no per-vector error path) instead of being hashed. Spec text unchanged; one note added.
- Compatibility, measured with the old and the new `verify.py`: all 96 JSON subtrees of `vectors.json` canonicalize to identical bytes, and the script output and exit code are identical (2/2). No published hash and no verdict changes.
- No vector was added: the preimage has a fixed set of fields and the spec defines no extension field. `tests/test_jcs_recipient_allocation_ref.py` (5 tests) pins the behaviour at function level; reverting `jcs()` to `sort_keys` fails 4 of the 5.
- Not changed: the fixture's `reproduce_in_python` field in `vectors.json` still shows the `sort_keys` form, which is not the RFC 8785 recipe the spec gives. Left as published, because changing it changes the bytes of a file others cite.

### Changed — delegation-chain-ref: verifier canonicalizes with RFC 8785; 15 vectors for untested rules; mutants (2026-11-26)

- Spec (`docs/spec/delegation-chain-ref.md`, Derivation): one note says that from its first revision (`16e140a`, 2026-06-28) until now `verify.py` computed JCS with `json.dumps(sort_keys=True)`, which the spec says not to use, and that this differed from RFC 8785 for object keys outside the BMP and for number forms (`1.0`, `0.000001`). The spec text did not change; the verifier is brought to it.
- `verify.py`: `jcs()` now calls the repo's `jcs.py`. An integer outside ±(2^53−1) (out of the JCS profile) is reported as a failure of `delegation_chain_ref` instead of being hashed. The frozen copies in the subdirectories keep their own canonicalization and are not changed.
- Compatibility, measured with the old and the new `verify.py`: the 16 vectors of the five existing files give the same verdict and the same failure list; the 67 objects the verifier hashes or signs in them canonicalize to identical bytes. No published hash and no verdict changes. A `chain_artifact` that carried non-BMP keys or non-integer-form numbers would have got a different `delegation_chain_ref` from an RFC 8785 implementation; none of the published ones does.
- New: `coverage-vectors.json` (15 vectors, built by `build_coverage_vectors.py`, expected results written by hand): scope narrowing not declared (the 2026-10-10 erratum, which had no vector), sibling prefix, wildcard, equal scope; `delegation_chain_ref` mismatch, `root_anchoring`, `leaf_anchoring`, a chain break in the last pair; replay by `delegation_ref` and by `chain_id`; a NOT_ASSESSED submission that must not be recorded; RFC 8785 key order and number forms (hashes from a canonical string written by hand, checked against `jcs.py` and, once, against Node.js); an integer outside the JCS profile.
- New: `mutants.py` (32 mutants of `verify.py`, 32 caught). The five earlier files alone catch 18 of the 32. Not listed and not provable by a vector: the scoring in `run_file` (`ok = verdict in expected`, the `failure_mode` prefix check), since turning them off cannot fail a correct corpus.
- `SHA256SUMS`, `conformance-export.json` and `conformance-vectors.json` regenerated (the first lists the three new files and the changed `verify.py`).

### Fixed — delegation-chain-ref/SHA256SUMS was out of date since 2026-09-28; now complete and tested (2026-11-26)

- `examples/conformance/delegation-chain-ref/SHA256SUMS` was published on 2026-07-30 (`ede2529`) "for third-party vector grading" and last written in `a1dfc63` (2026-09-24). Its five hashes matched the files at that commit and no later one: `sha256sum -c` failed on all five from 2026-09-28 until this change, and nothing in the repository checked it. What changed after it, per file: `vectors.json` (`0a41ee7`, 2026-09-28, provenance declared; `7c2b226`, 2026-10-10, scope narrowing opt-in), `cross-org-vectors.json`, `replay-vectors.json` and `key-completeness-vectors.json` (`0a41ee7`, 2026-09-28), `verify.py` (`7c2b226`, 2026-10-10; `0d53350`, 2026-10-18, Ed25519 hardening). A third party that pinned the old hashes was grading the 2026-09-24 files, not the current ones.
- This change does not touch any vector file or `verify.py`. It regenerates the sums for the bytes on `main` as they are, so it states what is there now; it does not say those bytes are correct.
- Scope: the file covered 5 of the 33 other tracked files of the directory (it left out `small-order-key-vectors.json`, `build_key_completeness.py`, `requirements.txt` and all subdirectories: `ed25519-hardening`, `leaf-screen-halt`, `mid-hop-revocation`, `moltycel-interop`, `partial-chain-recovery`, `revoked-ancestor`). It now lists every tracked file under the directory except itself (34 lines: those 33 plus the new script, sorted by path, `sha256sum -c`-compatible, run from that directory), including the new `build_sha256sums.py` that writes it.
- `tests/test_delegation_chain_sha256sums.py` (6 tests) fails when a file of the set changes, is added or is removed without regenerating (`python3 build_sha256sums.py`). Checked by mutation: appending one byte to `vectors.json` fails 4 of the 6.
- Sweep for other published checksums: no other checksum file exists; in tracked `.md`/`.txt`/`.yml` the 25 lines that carry a 64-hex value and the word hash/sha256/digest/checksum name no file digest; the six `"sha256"` fields inside the vector sets are content digests of objects, not file hashes. Not covered: a stale file hash written in some other form.

### Changed — peer-reconciliation-ref-v1.3.1: negative vectors must be rejected for their own reason; eleven vectors (2026-11-26)

- `docs/spec/peer-reconciliation-ref-v1.md` (v1.3.1, no rule changes): new section "Conformance: what a negative vector must show". A negative vector counts as passed only if the verifier rejects it, reports a failure under the vector's `failure_mode`, and does not report that its computed result differs from the vector's declared `checks`. `observed` is stated to be a JSON boolean (the reference verifier already treated anything else as structurally invalid).
- `examples/conformance/peer-reconciliation-ref/verify.py`: `score()` applies that scoring; `verify_vector` and the check functions keep their signatures. Before, any rejection counted, including the verifier disagreeing with the declared value, so a verifier with a rule removed still passed most negative vectors (a 38-mutant run: 28 survived under the old scoring).
- New: `vectors-v1.3.1.json` (11 negative vectors, built by `build_v131.py`, expected results written by hand from the spec) and `mutants.py` (29 mutants, 29 caught; 11 of 29 under the old scoring; the 26 earlier vectors catch 20 under the new scoring, the new ones the other 9). `vectors.json` is byte-identical.
- Compatibility: all 26 earlier vectors give the same verdict and the same failure list under the old and the new verifier, and pass under both scorings. The 11 new vectors are also rejected by the old verifier code: the rules were enforced, no vector exercised them. No third-party use of this `verify.py` was found (GitHub code search shows only this repository; not proof of absence).
- `conformance-export.json` and `conformance-vectors.json` regenerated (75 sets; `vectors-v1.3.1.json` added to `peer-reconciliation-ref`).

### Changed — trail-head-ref-v1: shape rules written down, shape failures are verdicts (2026-11-26)

- `docs/spec/trail-head-ref-v1.md`: new "Shape rules" subsection under Verification. It says what "well formed" means in checks 1, 2e and 5 (types, lowercase hex, boolean is not an integer, `period_end` required and parseable, null is not absent for `prev_head` and `agent_seq`, unknown keys), which a verifier written from the document alone could not know.
- `plugins/agt_evidence_anchor/trail_head.py`: checkpoint and window-anchor shape now share one check. Inputs that were accepted or crashed now return a verdict: a checkpoint with a boolean `seq` (was `complete`); `period_end` null (was `complete`), missing (was `KeyError`) or unparseable (was `ValueError` with the age check, `complete` without it); an anchor with a missing `period_end` (was accepted); `prev_head: null` at seq 1 (was `continuity_only`); `agent_seq: null` (was `agent_gap` or, with heads computed over the field, `head_mismatch`).
- Compatibility: every `verify_trail` input of the published `trail-head-window-ref` vectors (11) and of `test_trail_head.py` (44 calls) gives the same verdict before and after. No trail-head chain from a third party is published in this repository.
- New: `examples/conformance/trail-head-shape-ref/` (15 vectors, hand-written expected results, two mutants that must fail) and `tests/test_trail_head_shape.py`.

### Changed — verifier-key-source-ref-v1.2: invariant 3 says what it checks; rules written down (2026-11-26)

- `docs/spec/verifier-key-source-ref-v1.md` (v1.2): invariant 3 no longer promises that `signer_id` is "verifiably linked to the declared verifier role". The reference verifier never checked that: it rejected the single sentinel `anonymous-key-holder`. The spec now says so, adds the optional `role_registry` input (with `verifier_role` on the record) and reports `identity_binding: declared_only` or `registry_checked`. New section "Rules a verifier must apply": timestamps compared as UTC instants, absent/null/empty `key_resolution_time` and absent certification time fail closed, closed sets for `key_source` and `verification_result`, key material per `key_source`, 64-lowercase-hex hashes, `out_of_scope` does not satisfy independence.
- `examples/conformance/verifier-key-source-ref/verify.py` applies those rules. Before: timestamps were compared as strings (half a second after certification passed with mixed precision), an absent `key_resolution_time` passed, any `key_source` string and any non-empty `public_key_hash` passed, an `embedded` key with only an evidence hash passed.
- Compatibility: the six published vectors keep their verdict (all FAIL). Five of them now also report `fixture_certification_time_missing` because they declare no certification time; the reason each was written for is still reported (the verifier now checks it). No PASS vector was published before; `vectors-v1.2.json` adds 19 (4 PASS) and `mutants.py` removes eleven rules one at a time, each caught. The end anchor of the timestamp regex is not among them: no vector can catch its removal, because `datetime.fromisoformat` also rejects trailing text.
- Published text corrected, same bytes elsewhere: the `description` and `failure_detail` of vector `signer-identity-unbound` said the signer was "not linked to any declared verifier role" / "not bound to a declared verifier role"; no role is declared in that vector. Changed in `vectors.json` and in its copies inside `conformance-vectors.json` and `conformance-export.json`.

### Changed — JCS integer profile (2026-10-07)

- `jcs.py` refuses integers outside `[-(2^53-1), 2^53-1]` with a `ValueError` that names the profile. Before, it emitted their exact value, which RFC 8785 (IEEE-754 doubles) does not reproduce: `2^53+1` came out as `9007199254740993` where a conformant verifier gives `9007199254740992`. Implemented in PR #121 (commit badcd25). Tests in `tests/test_jcs_integer_profile.py`.
- Impact: in-range preimages are unchanged. Integers beyond the safe range are now refused, so a signed payload that carries one is rejected by our verifiers instead of being hashed as a different value. The repository, the local databases and the production databases contained no such integers at the time of the change (read-only scan).
- Spec: `docs/spec/action-ref.md` carries a dated note in its Domain section.

### Fixed — EU AI Act Art. 12 application date (2026-09-24)

- `docs/compliance/regulatory-compliance.md` (v1.3) and `examples/conformance/art12-log-integrity-notes/README.md`: both said Art. 12 "has been in force since 2 August 2026". The AI Act entered into force on 1 August 2024; after the AI Omnibus (Regulation (EU) 2026/1744) the high-risk obligations apply from 2 December 2027 (Annex III) and 2 August 2028 (Annex I). Corrected with a visible correction note, in the same style as Correction (v1.2). Source: European Commission, "Regulatory framework on AI". Pending Legal review.

### Added — idempotency-ref-v1.1: the four cases through crewAI (2026-09-24)

- `examples/conformance/crewai-unguarded-retry/`: the v1.1 four-case test through crewAI's real `ToolUsage.use()`, not only replayed at spec level. Case 2 is crewAI's own re-dispatch after a lost acknowledgement; case 4 is a separate re-proposal. Effects are read from the independent effect store; `idempotency_ref` and `admitted_payload_digest` match `idempotency-ref-v1.1/vectors.json` byte for byte. The three negatives run on the same path and each diverges where its vector declares. Runner: `verify_logical_identity.py`; details in `LOGICAL_IDENTITY_V1_1.md`.

### Added — farley-receipt-signature: signed input published per vector (2026-09-23)

- `examples/conformance/farley-receipt-signature/index.json`: `signed_input_hex` per vector, the exact bytes each signature was made over. Without it, a re-run could confirm that `signature-input-drift.reject` fails, but not that it fails for the stated reason (signed over pretty-printed bytes rather than `JCS(payload)`). The four receipts and `jwks.json` are byte-identical; only `index.json` changes.
- `tests/test_farley_receipt_vectors.py`: every signature verifies over its published input, and only the drift reject's input differs from `JCS(payload)`.

### Added — trail-head-ref-v1: completeness of an agent's trail (2026-09-23)

- `docs/spec/trail-head-ref-v1.md` (draft): per-agent hash chain (`seq`, `prev_head`) for continuity, plus a checkpoint per agent per period, sealed under one Merkle root (batch-anchor construction, unchanged) and anchored with `AnchorRegistry.anchor(bytes32)`, for completeness. Empty periods still seal. Optional agent-signed `agent_seq` shows actions dropped at ingest between the first and last presented (a tail drop is visible only against the agent's own last counter). Distinct verdicts per failure; no checkpoint → completeness `not_evaluated`, never a pass. `action_ref` unchanged. Not yet emitted by the production trail pipeline.
- `plugins/agt_evidence_anchor/trail_head.py` + `tests/test_trail_head.py` (22 tests): removal, reorder, tampered record, renumbered removal, tail truncation (passes continuity alone, caught by the checkpoint), full re-chain after the fact, foreign or unproven checkpoint, stale checkpoint, agent-counter gap — each caught by a different check.
- Credit: the property split and the attacks come from [microsoft/autogen#7353](https://github.com/microsoft/autogen/issues/7353) — Yarmoluk (records included vs. every action recorded; removal/reorder test), babyblueviper1 (tail truncation against a live chain; a count signed by the log's own key adds no independence), TKCollective (gapless per-session sequence). Empty-period sealing: stillmarcus24, [x402-foundation/x402#2887](https://github.com/x402-foundation/x402/issues/2887).

### Added — vector key gate in CI (2026-09-23)

- `tools/check_vector_keys.py` + `tools/vector_key_gate.json`: every JSON key in a vector set that declares an external schema must appear in that spec as a field (quoted, `key (REQUIRED|…)`, or identifier-shaped in prose). Runs as its own CI step and as `tests/test_vector_key_gate.py`. Opt-in per set, against a vendored, hash-pinned spec (`docs/spec/vendor/`), so a new draft revision is an explicit commit. First set: `farley-receipt-signature` against draft-farley-acta-signed-receipts-03 (vendored unmodified under BCP 78). It would have stopped the `"tool"` / `tool_name` error that both verifiers passed in #96 (reported by robertolocatelli81-dev, Noûs).

### Added — idempotency-ref-v1.1: logical identity vs payload identity (2026-09-23)

- `docs/spec/idempotency-ref.md` failed two of the four cases of the logical-identity test: (3) a second intentional payment with a byte-identical payload was deduplicated as a retry, because Invariant 5 accepted "a hash of the caller's own pre-execution request" as a key source; (4) a drifted retry ($100 → $125) under the same key passed silently as a duplicate, because nothing bound the key to the admitted payload. v1.1, additive: the key is the logical action id minted at admission (Invariant 6: distinct intentional actions MUST carry distinct keys; content-derived keys only under a declared domain invariant); new `admitted_payload_digest` carried next to `idempotency_ref`, outside the artifact (Invariant 7: same key + different digest → CONFLICT, fail closed). Every v1.0 artifact and `idempotency_ref` is unchanged.
- `examples/conformance/idempotency-ref-v1.1/`: the four cases plus three negatives, each failing on a different check (content-derived key, no digest check, digest inside the artifact); `tests/test_idempotency_ref_v1_1.py`. `idempotency-ref-v1.fixture.json` `idem-002` gains a `v1_1_note` (hashed fields untouched).
- Four-case test defined by impartshadow/agent-contracts, [crewAIInc/crewAI#5802](https://github.com/crewAIInc/crewAI/issues/5802) (comment [5790417981](https://github.com/crewAIInc/crewAI/issues/5802#issuecomment-5790417981)); pinned as a regression by stringsofthemind-oss, [stringsofthemind-oss/once#45](https://github.com/stringsofthemind-oss/once/pull/45).

### Added — farley-receipt-signature conformance vectors (2026-09-23)

- `examples/conformance/farley-receipt-signature/`: 4 vectors, each a reject with a conformant twin, for [draft-farley-acta-signed-receipts-03](https://datatracker.ietf.org/doc/draft-farley-acta-signed-receipts/03/), envelope shape, archival mode. The first case, `signature-input-drift` (MUST), signs pretty-printed bytes instead of `JCS(payload)`. The second, `superseded-key` (SHOULD, §9.2), uses a key after its `valid_until`. It is a minimal pair: only `issued_at` differs. The key comes from an external `jwks.json` (§9.5), and the keys are TEST ONLY, with public seeds. Includes a reference `verify.py` (pynacl), a deterministic `build.py`, and the observed result for `@veritasacta/verify` 0.10.19, which accepts the superseded-key reject because its receipt JWKS path does not read validity windows.
- `tests/test_farley_receipt_vectors.py`: the vectors match `index.json`, the build is byte-deterministic, the pair is minimal, and mutated receipts are refused.
- Fixed (same day): the payloads carried `"tool"`, which no revision of the draft defines; §3.1.1 makes `tool_name` REQUIRED for `protectmcp:decision`, so the two conformant twins did not conform to the type they declare and could not serve as ACCEPT cases for a verifier that checks §3.1.1. `build.py` now emits `tool_name` and the four receipts are regenerated; `jwks.json`, both kids and every verdict are unchanged. Reported by robertolocatelli81-dev (Noûs) in [#96](https://github.com/giskard09/argentum-core/pull/96).

### Changed — verifier-key-source-ref-v1.1: recomputable is not anchored (2026-09-23)

- `docs/spec/verifier-key-source-ref-v1.md`: the `key_source` table said `embedded` was "Yes — no external fetch required", and the column-split table gave "one signer, embedded key" ✓/✓. Both are right about recomputability, but the spec did not say that recomputability is not authenticity. An embedded key is chosen by the fixture's producer, so on its own it gives no authenticity guarantee ([draft-farley-acta-signed-receipts-03 §9.5](https://datatracker.ietf.org/doc/draft-farley-acta-signed-receipts/03/)). This change adds an "Anchored by this record?" column, a normative "Recomputable vs anchored" section, invariant 6 (`recomputable_not_anchored`) and a note under the scenario table. Existing rows, columns, fixture and verifier are unchanged. It is additive for boards, which still report the same two columns. Self-audit.

### Fixed — idempotency-ref-v1 orphaned-PENDING sweeper unsafe on unconditional timer (2026-08-23)

- `docs/spec/idempotency-ref.md`: the orphaned-PENDING rule stated an unconditional `SHOULD` treating a PENDING record older than `window_ms` as equivalent to FAILED. That inference is unsound whenever the provider call has no idempotency key of its own (`send_email`, `place_trade`) — a crash between the provider call succeeding and the anchor write is indistinguishable from a call that never landed, so sweeping to FAILED on a timer authorizes the exact duplicate the artifact exists to prevent. Corrected: default resolution is now a provider-confirmed query (no timer-based clearing); treating `window_ms` alone as sufficient requires an explicit `provider_idempotent: true` declaration, not an assumed default. `examples/conformance/idempotency-ref-v1.fixture.json`'s `window_semantics` invariant updated to match. Reported by impartshadow/agent-contracts, [crewAIInc/crewAI#5802](https://github.com/crewAIInc/crewAI/issues/5802).

### Fixed — strict RFC 8785 canonicalization in agenttrust-v1 conformance suite (2026-07-08)

- `examples/conformance/agenttrust-v1/verify.mjs` replaced its hand-rolled `jcs()` helper (sort keys + `JSON.stringify`, self-consistent with the fixtures but not spec-compliant) with the `canonicalize` npm package (strict RFC 8785). Reported by TKCollective, [#32](https://github.com/giskard09/argentum-core/issues/32).
- With strict canonicalization, `jws-002.json` (vector `at-002`) now correctly fails `canonical_mismatch` — its embedded payload's `skill_results` key order isn't RFC 8785 canonical. Fixing it requires AgentTrust to regenerate and re-sign `jws-002.json`/`jws-003.json`; we don't hold the `agenttrust-ed25519-v1` signing key. Tracked in #32, pending their PR.
- `at-r01` also needs an AgentTrust re-sign to demonstrate actual semantic tampering (its embedded verdict doesn't currently differ from the sidecar).

### Added — AnchorRegistry on Ink mainnet (2026-07-07)

- `AnchorRegistry` deployed on Ink mainnet (chain_id 57073) at the same canonical CREATE2 address `0x49fEcA52bC634a9Ab773226D16619deC547794aa` as Arbitrum One and Base. Deploy tx `0xcbd2d137e14287a13168eb14a75d4cad44456d94a78946ef72170d3f3723a895`, source verified on the Ink explorer.
- `counterparty_ref_anchor.chain_id: 57073` is now a conformant target. Additive — existing integrators unaffected.

### Added — Accountability primitives & multi-chain anchor (2026-06)

- `counterparty_ref` (`docs/spec/counterparty-ref.md`) — content-addressed pointer to a counterparty snapshot at action time. JCS-canonical preimage with timestamp.
- `counterparty_ref_anchor` (optional extension on `counterparty_ref`) — verifiable on-chain pointer to the `markUsed(bytes32)` transaction that anchored the preimage. Chain-agnostic via `chain_id`. `GiskardPayments` deployed on Base mainnet (`0x90Fa32a9568c6aE6BEa915DF8737acfd7EEA97De`, chain_id 8453) alongside the existing Arbitrum deployment.
- `signing_trust_ref` (`docs/spec/signing-trust-ref.md`) — signer-type pointer (`operator_key` / `agent_keypair` / `multi_party`) for composed multi-signer envelopes.
- `verification_mode` (`docs/spec/verification-semantics.md`) — distinguishes producer-`asserted` from independently-`enforced` records.
- All fields optional and backward-compatible; existing consumers unaffected.

### Added — Schema v2 (2026-05-12)

- `scope` (string | null): optional field on TrailRecord — what the agent was authorized to do
- `delegation_ref` (string | null): optional opaque pointer to the delegation chain that originated the action
- Both fields are nullable and backward-compatible; existing consumers are unaffected
- `init_db` runs idempotent ALTER TABLE migrations for existing databases
- Affected: `record_trail()` signature, `_row_to_dict()` output, all SELECT queries

**Integrators:** `scope` and `delegation_ref` appear as `null` in all responses until explicitly supplied at write time. No action required to stay compatible.

## [v0.4.0] — 2026-04-30

- Auditoría v0.4 GREEN (FINDING-001 through FINDING-004 resolved)
- giskard-self agentId canonical #3249 (Eth Sepolia)
- pioneer-agent-001 in ARGENTUM (karma=20)

## [v0.3.0] — 2026-04-13

- Mycelium Trails v0 integrated in argentum-core
- `/trails/verify` endpoint live at `argentum.rgiskard.xyz`
- AgentKit action provider (TypeScript)
- Cross-rail fixture published in x402-foundation/x402
