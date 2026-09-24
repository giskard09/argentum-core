"""Builds vectors.json for host-capability-ref, byte-reproducible.

The signing key comes from a public seed and signs nothing outside this fixture.

    python3 build.py          # rewrites vectors.json
    python3 build.py --check  # exit 1 if the file on disk differs
"""
import hashlib
import json
import sys

from verify import HERE, SCHEME, bip340, jcs

SECKEY = hashlib.sha256(b"host-capability-ref bip340 test key").digest()
AUX = hashlib.sha256(b"host-capability-ref aux").digest()
OUT = HERE / "vectors.json"


def artifact(preimage: dict, signed_preimage: dict | None = None, corrupt_sig: bool = False) -> dict:
    """Signed over JCS(signed_preimage or preimage); preimage_jcs declares the signed bytes."""
    signed = jcs(signed_preimage or preimage)
    sig = bytearray(bip340.schnorr_sign(signed, SECKEY, AUX))
    if corrupt_sig:
        sig[0] ^= 1
    return {
        "preimage": preimage,
        "preimage_jcs": signed.decode("utf-8"),
        "signature": {"scheme": SCHEME, "pubkey_x_only": bip340.pubkey_gen(SECKEY).hex(), "sig": bytes(sig).hex()},
    }


def build() -> dict:
    base = {"schema": "host-capability-ref.v1", "subject": "example", "issued_at": "2026-09-24T12:00:00.000Z"}
    altered = dict(base, subject="example-altered")
    return {
        "spec_version": "host-capability-ref-v1",
        "description": (
            "A valid profile algorithm the host may lack. `expected` lists every verdict a "
            "conformant verifier may return on some host; `expected_by_host` is what the "
            "reference verifier returns with and without bip340-schnorr-secp256k1."
        ),
        "vectors": [
            {
                "id": "hc-001-valid-signature",
                "description": "Valid BIP-340 signature over the declared canonical bytes. A host "
                               "without the algorithm cannot confirm it and must not reject it.",
                "expected": ["PASS", "NOT_ASSESSED"],
                "expected_by_host": {"capable": "PASS", "incapable": "NOT_ASSESSED"},
                "artifact": artifact(base),
            },
            {
                "id": "hc-002-invalid-signature",
                "description": "Canonical bytes match, signature corrupted. Only a host with the "
                               "algorithm can see it; one without must not accept it.",
                "expected": ["FAIL", "NOT_ASSESSED"],
                "expected_by_host": {"capable": "FAIL", "incapable": "NOT_ASSESSED"},
                "failure_mode": "signature_invalid",
                "artifact": artifact(base, corrupt_sig=True),
            },
            {
                "id": "hc-003-mixed-preimage-mismatch",
                "description": "The preimage was altered after signing: JCS(preimage) no longer "
                               "matches preimage_jcs. Any host sees that without the algorithm, "
                               "so the missing capability does not soften it.",
                "expected": ["FAIL"],
                "expected_by_host": {"capable": "FAIL", "incapable": "FAIL"},
                "failure_mode": "preimage_jcs_mismatch",
                "artifact": artifact(altered, signed_preimage=base),
            },
        ],
    }


if __name__ == "__main__":
    text = json.dumps(build(), indent=2, ensure_ascii=False) + "\n"
    if "--check" in sys.argv[1:]:
        sys.exit(0 if OUT.read_text() == text else 1)
    OUT.write_text(text)
    print(f"wrote {OUT.name}")
