# RFC 002 — action_ref v2: domain separation

- **Status**: Draft — design only, NOT for implementation until adopter coordination completes
- **Author(s)**: giskard09 (dept-código, per dept-estrategia request 2026-07-29)
- **Date**: 2026-07-29
- **Related**: `docs/spec/action-ref.md`, `plugins/agt_evidence_anchor/action_ref.py`, `ADOPTERS.md`
- **Supersedes**: —
- **Does NOT commit to**: changing `docs/spec/action-ref.md`'s preimage, tagging a new spec version, or notifying any adopter. This document exists to make the coordination decision possible, not to pre-empt it.

## Summary

`docs/spec/action-ref.md` (frozen at tag `action-ref-v1.0`, currently text
version 1.1) derives `action_ref` as a bare `SHA-256(JCS({agent_id,
action_type, scope, timestamp}))` — no domain or version tag in the hashed
bytes. This means any other protocol that independently arrives at the same
four-field JCS shape and SHA-256 produces colliding references: identical
bytes hash identically regardless of which system, spec, or version emitted
them. This was surfaced indirectly by an AEOESS comment in
`a2aproject/A2A#2028` — a general point about preimage domain separation,
not directed at us, but it applies to our frozen spec exactly as described.

This RFC proposes a **v2** preimage with an explicit domain/version tag,
and — the part that actually needs a decision, not just a format — a plan
for v1 and v2 to coexist without verifier ambiguity, given that v1 hashes
are already anchored on-chain by named production adopters who cannot be
retroactively changed.

## Why this cannot be a silent replace

`action_ref` is content-addressed: the guarantee is that anyone holding the
four preimage fields can recompute the same hash independently, without
trusting the emitter (`verifier-independence.md`, Model B). That guarantee
is only real if the preimage format a verifier assumes matches the one the
original anchor used. If we changed the preimage in place, every hash
already anchored under v1 — including ones already on Base mainnet — would
silently stop being recomputable by anyone using an updated verifier. The
record would still exist on-chain, immutable as promised, but no longer
independently reproducible from the fields without knowing which historical
format version applied. That failure mode is worse than the collision risk
this RFC is trying to close.

## Proposed v2 preimage

```
action_ref_v2 = SHA-256("action-ref:v2:" + JCS({
  "agent_id":     "<string>",
  "action_type":  "<string>",
  "scope":        "<string>",
  "timestamp":    "<RFC 3339 UTC, 3-digit ms precision>"
}))
```

The four fields, their types, and the JCS canonicalization rules are
**unchanged** from v1 — only a fixed ASCII prefix (`"action-ref:v2:"`) is
prepended to the canonical JSON bytes before hashing. This is a minimal
diff specifically so that v1 implementations can be upgraded to emit v2 by
adding one string concatenation, not by re-deriving canonicalization logic.

The prefix string itself is the open design question — `"action-ref:v2:"`
is the direct analogue of the example estrategia gave, not a final choice.
Alternatives worth weighing before this is implemented:
- A prefix that names the **spec**, not just a version number (e.g.
  `"mycelium.action-ref:v2:"`), so the domain tag itself states which
  document defines the hash — closes the AEOESS point more directly, since
  the whole risk is cross-protocol collision, not just cross-version
  collision within our own spec.
- Whether the tag belongs as a raw string prefix (cheapest, matches the
  estrategia example) or as a field inside the JCS object itself (e.g.
  `"schema": "action-ref-v2"` as a fifth sorted key) — a field-based tag is
  self-describing in the JSON but changes what "the four canonical fields"
  means, which cuts against `action-ref.md`'s explicit claim that the
  preimage is exactly four fields. Recommendation, not decision: prefix
  string, not a fifth field — preserves the "four fields, always" property
  that adopters like AURA cite when explaining portability.

## How v1 and v2 coexist without verifier ambiguity

The core problem to solve: given a 64-hex-char `action_ref` and the four
source fields, how does a verifier know whether to recompute it as v1 or
v2? Two hashes for the same four fields will differ, so a verifier that
guesses wrong gets `HASH_MISMATCH` on a perfectly valid record.

Proposed resolution — **the record must carry its own version, the hash
never has to be guessed**:

1. Every record that includes `action_ref` also includes a companion field,
   `action_ref_version` (or equivalent — e.g. an `"action-ref:v2"` scheme
   prefix on the hash string itself, `"v2:<hex>"`, so the tag travels with
   the value instead of needing a separate field). A conformant verifier
   reads the version marker first, then recomputes using the matching
   derivation. This mirrors how `signing-trust-ref.md`'s `signer_type` and
   `custody-ref.md`'s `custody_type` already work — a typed field the
   verifier branches on, not an assumption.
2. `action-ref.md` gets a new top section, "Version negotiation," stating
   explicitly: v1 preimage remains valid and permanently verifiable for any
   `action_ref` computed before the v2 cutover; v1 is not deprecated, not
   retired, not marked for future removal. New implementations SHOULD emit
   v2; verifiers MUST support recomputing both, keyed off the version
   marker.
3. `action-ref-v1.0` the git tag stays exactly as is (immutable, as tags
   should be). A new tag, `action-ref-v2.0`, marks the version-negotiation
   update. The stable-ref table at the top of `action-ref.md` gains a row
   for both.
4. Conformance fixtures: `examples/conformance/` gets a new fixture set
   (`action-ref-v2/`) alongside the existing v1 vectors — not a replacement
   of them. A verifier claiming v2 conformance must still pass the v1
   vectors to prove it did not silently drop v1 support.

This is the same shape as `custody-ref.md`'s enum-plus-cross-check pattern
and `signing-trust-ref.md`'s `signer_type`: don't make the verifier guess,
make the record self-describing.

## Per-adopter impact (ADOPTERS.md, named individually)

| Adopter | Current dependency | What v2 changes for them | Risk if uncoordinated |
|---|---|---|---|
| **SafeAgent (azender1)** | Production, `action_ref` derivation + x402 settlement live on Base mainnet (block 45907183). Real money movement tied to this hash. | Nothing forced — their existing v1 anchors stay valid under the "v1 permanently verifiable" rule. If/when they adopt v2 for new records, they add the version marker + prefix to their derivation code. | **Highest** — this is the one adopter with live financial settlement on top of `action_ref`. Any ambiguity in version negotiation directly risks a payment-verification mismatch. Must be the first adopter briefed, not the last. |
| **AURA (luisllaver)** | Production, `action_ref` carried in reputation records; explicitly documents portability — "a downstream auditor can recompute SHA-256(JCS(...)) and match it independently." | Their own marketing claim ("independently reproduced action-ref.md v1.0 fixture verbatim") is a v1-specific claim. If we ship v2 without the version-negotiation rule, their documented portability property silently breaks for anyone verifying against v2 assumptions. | High — reputational risk for them if their own README goes stale against the live spec without notice. |
| **CTEF (kenneives)** | PR open (agentgraph-co/agentgraph#20), not yet merged, 3 conformance vectors byte-matched to v1. | Pre-merge — lowest-friction adopter to coordinate with, since nothing is locked in yet. Could plausibly be the first to adopt v2 vectors directly if timing lines up before merge. | Low, but worth an explicit heads-up before their PR merges so they don't lock in v1-only vectors right as v2 ships. |
| **Vauban Pay (seritalien)** | IETF draft active (`draft-vauban-x402-stark-receipts-01`), conformance alignment in progress against `action-ref-v1.0` specifically (named tag). | Their draft cites the tag by name. A v2 tag doesn't invalidate their draft's v1 citation, but if they're still aligning conformance vectors, they should know a v2 exists before finalizing draft language that might read as "the" current version. | Medium — IETF draft process is slow-moving and citation-sensitive; better to tell them early than have them re-cite later. |
| **Agent OS / Trust Ledger (Liuyanfeng1234)** | Production data verified; first external contributor to argentum-core; PR for `negotiation_ref` in progress. | Real adopter with an active PR — gets the same standard technical notice as AURA/Vauban Pay/CTEF (fact stated, no rush, no ask). **Correction (2026-07-29, creador + estrategia):** does NOT get reviewer standing or early-access treatment on the v2 design. Classified WATCHLIST in `lab_external_intel.md` (outside `ADOPTERS.md`) — fabricated a cross-verification claim about a third party that does not exist (confirmed via `gh api`, the cited cross-check is not real) to lend legitimacy to a cluster already flagged as problematic. Not a reason to exclude them from the notice; is a reason not to hand them authority over spec design. | Low risk of breakage from the schema change itself. The risk this row tracks is process, not code: no elevated trust position, standard notice only. |

**General note applying to all five:** none of them are broken by this RFC
existing or by v1 continuing to be valid. The risk is entirely in the
sequencing of the announcement — if v2 ships without the version-marker
rule landing first, or without SafeAgent specifically being briefed before
public announcement (given live financial settlement), a verifier upgrade
race could produce a window where some verifiers assume v2-by-default and
mismatch a v1 record that has no version marker. The version-negotiation
mechanism (§ above) is a prerequisite for shipping anything, not an
optional refinement.

## Sequencing — final (creador + estrategia, 2026-07-29)

1. Land the version-negotiation mechanism in `action-ref.md` first —
   version-marker syntax, "v1 remains valid" language, new fixture set —
   with zero adopters affected, since this step only adds documentation
   and a fixture set, changes no existing hash. **DONE**, commit `72c414c`.
2. Brief SafeAgent directly (highest financial stakes) before anyone else.
   **In progress** — brief sent by email, awaiting response; step 3 does
   not proceed until that response lands or an explicit go-ahead is given.
3. Brief AURA, Vauban Pay, and Agent OS/Liuyanfeng1234 with the same
   standard technical notice, adapted per adopter — no differential
   treatment between the three, and no reviewer/early-access standing for
   Agent OS specifically (see corrected row above).
4. Offer CTEF the chance to adopt v2 vectors directly, given their PR is
   still unmerged — lowest-friction adopter to move first since nothing is
   locked in yet.
5. Only after 1-4: tag `action-ref-v2.0`, update `ADOPTERS.md` entries that
   confirm v2 adoption.

## Open questions for estrategia / creador

- Final domain-tag string — `"action-ref:v2:"` vs a spec-named variant.
- Whether `action_ref_version` is a sibling field or a `"v2:<hex>"` prefix
  on the hash string itself (affects every downstream schema that stores
  `action_ref`, including our own `trails.db`).
- Timing: is there a reason to move on this now (AEOESS's public comment
  creates soft pressure) or is coordination-first strictly required before
  any public v2 signal, given SafeAgent's live settlement exposure?
