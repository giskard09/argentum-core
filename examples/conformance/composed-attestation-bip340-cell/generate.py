"""
Builds the BIP-340 co-suite cell requested by kenneives in
giskard09/composed-attestation-3leg-worked-example#2 (comment 5303696037):

  "the BIP340 cell carries `authority_ref` as a single top-level string
  field in its *signed preimage*, value embedded verbatim ... the only
  invariant is that the signed bytes contain the verbatim string."

authority_ref is arv2-001 from examples/conformance/action-ref-v2/ —
already published in docs/spec/action-ref.md, not re-derived here.

Deterministic: fixed aux_rand so the output is reproducible byte-for-byte
(same posture as generate_fixtures.py in the paired repo — a reviewer
regenerates and diffs rather than trusting committed bytes).
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bip340

AUTHORITY_REF = "v2:a978a3fe6858ac212091304c618f8ce40d024f2b9bb8e26cfaddf73a8812bf76"
AUTHORITY_REF_SOURCE = (
    "examples/conformance/action-ref-v2/action-ref-v2.fixture.json#arv2-001 "
    "(argentum-core) -- same preimage as the worked v1 example published in "
    "docs/spec/action-ref.md ('Serialization -- JCS' section)"
)
SECKEY_SEED = b"mycelium.bip340-cell.composed-attestation-3leg.v1"
AUX_RAND = hashlib.sha256(b"mycelium.bip340-cell.aux.deterministic.v1").digest()
ISSUED_AT = "2026-08-15T00:00:00.000Z"


def jcs(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def derive_seckey() -> bytes:
    # Deterministic derivation, not randomness -- reduces this artifact's
    # generation to "re-run the script", same as the fixture's own posture.
    candidate = hashlib.sha256(SECKEY_SEED).digest()
    d0 = int.from_bytes(candidate, "big")
    if not (1 <= d0 < bip340.N):
        raise RuntimeError("deterministic seed landed out of range -- pick a new seed")
    return candidate


def build_cell() -> dict:
    seckey = derive_seckey()
    pubkey = bip340.pubkey_gen(seckey)

    preimage = {
        "schema": "mycelium.bip340-cell.v1",
        "authority_ref": AUTHORITY_REF,
        "co_suite_ref": "trustless-ai/composed-attestation-note#R3",
        "issued_at": ISSUED_AT,
    }
    preimage_bytes = jcs(preimage)
    signature = bip340.schnorr_sign(preimage_bytes, seckey, AUX_RAND)

    assert bip340.schnorr_verify(preimage_bytes, pubkey, signature), "self-check failed"

    return {
        "cell_schema": "mycelium.bip340-cell.v1",
        "preimage": preimage,
        "preimage_jcs": preimage_bytes.decode("utf-8"),
        "authority_ref_source": AUTHORITY_REF_SOURCE,
        "signature": {
            "scheme": "bip340-schnorr-secp256k1",
            "note": (
                "msg = raw JCS preimage bytes above (variable length, not a "
                "pre-hashed 32-byte digest) -- BIP-340's challenge tagged-hash "
                "handles arbitrary-length msg internally; see bip340.py docstring."
            ),
            "pubkey_x_only": pubkey.hex(),
            "sig": signature.hex(),
            "aux_rand": AUX_RAND.hex(),
        },
        "verify": (
            "recompute preimage_jcs = JCS(preimage) with sort_keys/no-space "
            "separators/utf-8; bip340.schnorr_verify(preimage_jcs.encode(), "
            "bytes.fromhex(pubkey_x_only), bytes.fromhex(sig)) must be True; "
            "preimage.authority_ref must equal, byte-for-byte, the v2 action_ref "
            "string emitted by this suite -- drop this cell's signature and the "
            "co-suite leg's own signed preimage (which embeds the identical "
            "authority_ref string) is what R3 checks fails without it."
        ),
    }


if __name__ == "__main__":
    cell = build_cell()
    out_path = os.path.join(os.path.dirname(__file__), "cell.json")
    with open(out_path, "w") as f:
        json.dump(cell, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {out_path}")
    print(f"pubkey_x_only: {cell['signature']['pubkey_x_only']}")
