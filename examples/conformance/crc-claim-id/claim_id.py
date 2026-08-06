"""Independent implementation of crc.claim.v0 claim_id (trustless-ai/cross-reference-console CLAIM.md).

claim_id = "sha256:" + hex( SHA-256( JCS(ClaimPreimage) ) )

Written from the spec text in CLAIM.md, not from the reference implementation
at trustless-ai/cross-reference-console/reference/claim_id.py -- this repo's
own JCS canonicalizer (jcs.py, added 2026-08-06 for an unrelated RFC 8785
fix in argentum.py/mycelium_trails.py) is reused as-is, unmodified for this
purpose.
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from jcs import jcs_bytes

REQUIRED_FIELDS = (
    "schema", "profile_id", "policy_version", "artifact_hash", "artifact_type",
    "claim_body", "source_class", "verifier_profile", "as_of", "claimant",
)


def claim_id(preimage: dict) -> str:
    missing = [f for f in REQUIRED_FIELDS if f not in preimage]
    if missing:
        raise ValueError(f"ClaimPreimage missing required fields: {missing}")
    digest = hashlib.sha256(jcs_bytes(preimage, ensure_ascii=False)).hexdigest()
    return f"sha256:{digest}"


if __name__ == "__main__":
    import json
    preimage = json.load(sys.stdin)
    print(claim_id(preimage))
