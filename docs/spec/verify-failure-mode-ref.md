# verify-failure-mode-ref-v1 — Specification

**Stable tag:** `verify-failure-mode-ref-v1`
**Status:** stable
**Canonical vectors:** [`examples/conformance/verify-failure-mode-ref-v1/vectors.json`](../../examples/conformance/verify-failure-mode-ref-v1/vectors.json)
**Reference verifier:** [`examples/conformance/verify-failure-mode-ref-v1/verify.py`](../../examples/conformance/verify-failure-mode-ref-v1/verify.py)

---

## What is verify-failure-mode-ref

`verify-failure-mode-ref-v1` generalizes the fail-open/fail-closed distinction found in
azender1/SafeAgent#12 (`attestation_unreachable` vs. `attestation_stale`) into a
mechanism-neutral spec: any pre-action gate that consumes external verification evidence
(signed attestation, scan finding, revocation check) must classify a failed verify step into
exactly one of four DISTINCT reason codes before applying policy. Collapsing any two of them
into a single generic "denied" bucket loses information an operator needs to respond
correctly — "the source was down" and "the evidence was actively wrong" require different
remediation (retry infra vs. investigate compromise).

**What it enables:** an external implementer who reproduces `classify_verify_attempt()`
byte-identical from the stated inputs has a conformant implementation. `verify_mode` is
explicit config (`fail_closed` default | `fail_open` opt-in) and composes with any existing
policy gate (e.g. a grade/score threshold) without replacing it — the verify-failure
classification runs before the gate evaluates its own policy.

**What it does not do:** it does not define the evidence format itself (attestation,
revocation record, scan finding) — it defines how a verify *attempt* against that evidence is
classified and gated. It does not replace a gate's own policy logic (e.g. a karma/score
threshold) — `PROCEED_TO_GATE_POLICY` hands control back to that logic once the verify step
itself succeeded.

---

## The four reason codes

| Code | Meaning |
|------|---------|
| `verify_ok` | Evidence source reachable, signature valid, digest matches, within freshness bound. |
| `verify_unreachable` | The evidence source could not be reached (network error, timeout, DNS failure) before any content was received. No claim about the evidence's validity can be made — this is an availability fact, not a safety fact. |
| `verify_stale` | The evidence source responded and returned a signed, structurally valid record, but the record's freshness bound (`issued_at + ttl_seconds`, or explicit `expires_at`) has passed. The evidence exists and may have been valid once, but cannot be trusted as current. |
| `verify_invalid` | The evidence source responded with a record that is fresh (within its freshness bound) but fails structural or cryptographic verification (signature does not verify against the declared key, or the canonical digest does not match the signed payload). The evidence is actively contradicted, not merely absent or expired. |

## Reference classification

```python
def classify_verify_attempt(fetch_ok, sig_valid, digest_match, issued_at_ms,
                             expires_at_ms, ttl_seconds, now_ms):
    if not fetch_ok:
        return "verify_unreachable"
    if expires_at_ms is not None and now_ms > expires_at_ms:
        return "verify_stale"
    if ttl_seconds is not None and (now_ms - issued_at_ms) > ttl_seconds * 1000:
        return "verify_stale"
    if not (sig_valid and digest_match):
        return "verify_invalid"
    return "verify_ok"


def policy_action(reason, verify_mode):
    if reason == "verify_ok":
        return "PROCEED_TO_GATE_POLICY"
    if reason == "verify_unreachable":
        return "SKIP" if verify_mode == "fail_open" else "DENY"
    return "DENY"
```

---

## Invariants

**1. reason codes must remain distinguishable**

A gate must never collapse two of the four codes into a single generic "denied"/"error"
value. An auditor reading the record needs to tell `verify_unreachable` (retry infra) from
`verify_invalid` (investigate compromise) from `verify_stale` (evidence aged out, re-fetch).
See `negative_vectors[0]` (`collapsed-unreachable-and-invalid`) in the canonical vectors for
the reference failure this invariant rules out.

**2. unknown reason code fails closed**

A verifier that receives a reason code it does not recognize (e.g. a future addition it has
not been updated to handle) MUST treat it as equivalent to `DENY`. It must never collapse an
unrecognized code to `PROCEED_TO_GATE_POLICY` or to `SKIP`. `verify_mode=fail_open` only
relaxes the `verify_unreachable` case explicitly — it grants no leniency to any other reason
code, known or unknown.

`policy_action()` above already satisfies this by construction: only `verify_ok` reaches
`PROCEED_TO_GATE_POLICY`, only `verify_unreachable` under `fail_open` reaches `SKIP`, and
every other input — including a reason code this function has never seen — falls through to
the final `return "DENY"`. No code change was required to state this invariant; it documents
behavior that already holds, so a future edit to `policy_action()` does not regress it
silently.

**3. the enum is append-only**

New reason codes may be added in a future minor revision (e.g. a fifth code for a mechanism
not yet covered). An existing code's semantics must never be redefined or repurposed — only
deprecated (documented as no longer emitted by conformant implementations, but still
recognized and still failing closed per invariant 2) and superseded by a new, distinct code.
A verifier's fail-closed handling of unrecognized codes (invariant 2) is what makes an
append-only enum safe to extend without a breaking change to consumers: an older verifier
that has not learned a new code denies by default rather than mis-classifying it as success.

---

## Cross-references

- Originating distinction: azender1/SafeAgent#12 (`attestation_unreachable` vs.
  `attestation_stale`), generalized here to mechanism-neutral verify-failure classification.
- `revocation_ref` / `revocation_check_at_ms` (a specific evidence type this mechanism can
  gate on): [`revocation-ref.md`](./revocation-ref.md)
- Fail-closed default framing consistent with `verifier-independence.md` and
  `guarantee-model.md`.
