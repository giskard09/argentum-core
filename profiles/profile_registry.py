"""
Profile registry for canonicalization profiles.

Each profile_id is SHA-256(JCS(profile_doc)). The registry loads profiles
from profiles/<profile_id>.json. A verifier reads canonicalization_profile_id
from the decision evidence, resolves it here before comparing any digests.
If the profile is absent or unrecognized, the verifier must return
UNSUPPORTED_CANONICAL_PROFILE — not DIGEST_MISMATCH.

Profile docs are immutable once minted: same profile_id implies same doc,
byte-for-byte, verified by construction. Closing a gap in a profile's schema
(pinning a field that was previously unpinned) is never an in-place edit --
it mints a new doc with a new profile_id and the alias is repointed to it.
The old doc stays on disk and stays resolvable, so evidence that already
named the old profile_id remains verifiable exactly as it always was.
"""

import hashlib
import json
import pathlib

_PROFILES_DIR = pathlib.Path(__file__).parent

# Human-readable aliases → canonical profile_id (SHA-256 of doc)
ALIASES: dict[str, str] = {
    "jcs-rfc8785-v1":            "f018a62879ab01f21e8fe5e9e7486dadba0b795e9358b32fd24d38d2c1f1f07d",
    "jcs-rfc8785-action-ref-v1": "bcf8ae8c1105b8b59f892935d076540f54813b0d87c30cab741e4c29847a0cf5",
}

# Superseded profile_ids -- no longer the alias target, but the doc stays on
# disk and stays resolvable by hash. Evidence minted before 2026-07-03 that
# names these hashes directly remains verifiable against the original,
# unpinned-schema doc. Superseded because duplicate_keys/numeric_domain were
# unpinned (see each new doc's "supersedes"/"superseded_reason" fields).
SUPERSEDED: dict[str, str] = {
    "82b5df2a487988d5ba773cf40ffa92a614769de6fbea6f4b2745794125e1c9fa": "f018a62879ab01f21e8fe5e9e7486dadba0b795e9358b32fd24d38d2c1f1f07d",
    "8c7f71754e3daae1a0390d5e0287d51097d011e40df36bf15cad5c0f47efa05a": "bcf8ae8c1105b8b59f892935d076540f54813b0d87c30cab741e4c29847a0cf5",
}

_cache: dict[str, dict] = {}


def _jcs(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def resolve(profile_id: str) -> dict | None:
    """Return the profile doc for a given profile_id (or alias), or None if not found."""
    canonical = ALIASES.get(profile_id, profile_id)
    if canonical in _cache:
        return _cache[canonical]
    path = _PROFILES_DIR / f"{canonical}.json"
    if not path.exists():
        return None
    doc = json.loads(path.read_text())
    # Verify content-addressing
    computed = hashlib.sha256(_jcs(doc)).hexdigest()
    if computed != canonical:
        raise ValueError(f"Profile integrity failure: {path.name} hashes to {computed}, expected {canonical}")
    _cache[canonical] = doc
    return doc


def is_supported(profile_id: str) -> bool:
    return resolve(profile_id) is not None


def verify_profile_integrity() -> dict[str, bool]:
    """Check all profiles in the directory. Returns {profile_id: ok}."""
    results = {}
    for p in _PROFILES_DIR.glob("*.json"):
        if p.name == "profile_registry.py":
            continue
        pid = p.stem
        try:
            doc = json.loads(p.read_text())
            computed = hashlib.sha256(_jcs(doc)).hexdigest()
            results[pid] = computed == pid
        except Exception:
            results[pid] = False
    return results
