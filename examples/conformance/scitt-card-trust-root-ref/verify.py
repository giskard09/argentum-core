"""
Verifier for scitt-card-trust-root-ref-v1 conformance vectors.

Two independent boundaries, each with its own named failure_mode — a
conformant verifier MUST NOT collapse them into a single boolean:

  class "card_authenticity":
    self_consistency (signature verifies against the embedded key) is NOT
    the same claim as authenticity (the key chains to a registry-known
    trust anchor). A card can be self_consistency=true and still be a
    forgery signed with a key generated for the occasion.
    -> failure_mode: TRUST_ANCHOR_UNRESOLVED

  class "envelope_preimage":
    the preimage field must be the actual {agent_id,action_type,scope,
    timestamp} object whose SHA-256(JCS(...)) reduces to
    canonical_envelope_ref — not a description of the rule, not any other
    non-recomputable stand-in.
    -> failure_mode: PREIMAGE_NOT_RECOMPUTABLE

Both are named-boundary rejections: the field that failed is named in the
result, never swallowed into a single valid:true/false.
"""

import hashlib
import json
import sys
from pathlib import Path

REQUIRED_PREIMAGE_KEYS = {"agent_id", "action_type", "scope", "timestamp"}


def jcs(obj: dict) -> bytes:
    return json.dumps(
        dict(sorted(obj.items())), separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def verify_card(card: dict, known_trust_anchors: set[str]) -> tuple[bool, str | None, str | None]:
    """Returns (ok, failure_mode, failure_detail)."""
    if not card.get("self_consistency"):
        return False, "SIGNATURE_INVALID", "card.self_consistency is false — signature does not verify against embedded key."

    anchor = card.get("trust_anchor_ref")
    if anchor not in known_trust_anchors:
        return (
            False,
            "TRUST_ANCHOR_UNRESOLVED",
            f"card.issuer_key_id={card.get('issuer_key_id')!r} is self_consistency=true but "
            f"trust_anchor_ref={anchor!r} is not in the known trust anchor registry. "
            "Signature validity proves the issuer signed its own claim, not that the issuer is trusted.",
        )

    return True, None, None


def verify_envelope(envelope: dict) -> tuple[bool, str | None, str | None]:
    """Returns (ok, failure_mode, failure_detail)."""
    preimage = envelope.get("preimage")
    canonical_envelope_ref = envelope.get("canonical_envelope_ref")

    if not isinstance(preimage, dict) or set(preimage.keys()) != REQUIRED_PREIMAGE_KEYS:
        return (
            False,
            "PREIMAGE_NOT_RECOMPUTABLE",
            f"envelope.preimage is {type(preimage).__name__}, not the required "
            f"{sorted(REQUIRED_PREIMAGE_KEYS)} object — cannot recompute SHA-256(JCS(preimage)).",
        )

    recomputed = hashlib.sha256(jcs(preimage)).hexdigest()
    if recomputed != canonical_envelope_ref:
        return (
            False,
            "PREIMAGE_DIGEST_MISMATCH",
            f"recomputed={recomputed[:16]}... != canonical_envelope_ref={str(canonical_envelope_ref)[:16]}...",
        )

    return True, None, None


def main():
    vectors_path = Path(__file__).parent / "vectors.json"
    data = json.loads(vectors_path.read_text())

    known_trust_anchors = set(data["trust_registry"]["known_trust_anchors"])
    vectors = data["vectors"]

    print(f"scitt-card-trust-root-ref-v1 conformance — {len(vectors)} vectors\n")

    passed = 0
    failed = 0
    seen_failure_modes = set()

    for v in vectors:
        vid = v["id"]
        expected = v["expected"]

        if v["class"] == "card_authenticity":
            conforms, failure_mode, failure_detail = verify_card(v["card"], known_trust_anchors)
        else:
            conforms, failure_mode, failure_detail = verify_envelope(v["envelope"])

        ok = conforms if expected == "PASS" else not conforms
        if failure_mode:
            seen_failure_modes.add(failure_mode)
            if expected == "FAIL" and failure_mode != v.get("failure_mode"):
                ok = False

        marker = "✓" if ok else "✗"
        status = "PASS" if ok else "FAIL"
        print(f"  {marker} [{status}] {vid}")
        if not ok:
            print(f"         expected failure_mode={v.get('failure_mode')!r}, got {failure_mode!r}: {failure_detail}")
        elif expected == "FAIL":
            print(f"         correctly rejected: {failure_mode} — {failure_detail}")

        if ok:
            passed += 1
        else:
            failed += 1

    # Named-boundary invariant: the two adversarial vectors must NOT share a failure_mode.
    if len(seen_failure_modes) < 2:
        print(f"\n  ✗ [FAIL] named-boundary-distinctness — expected 2 distinct failure_mode values, got {seen_failure_modes}")
        failed += 1

    print(f"\n{passed}/{len(vectors)} passed", end="")
    if failed:
        print(f", {failed} failed")
        sys.exit(1)
    else:
        print()


if __name__ == "__main__":
    main()
