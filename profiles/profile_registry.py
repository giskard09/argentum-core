"""
Profile registry for canonicalization profiles.

Each profile_id is SHA-256(JCS(profile_doc)). The registry loads profiles
from profiles/<profile_id>.json. A verifier reads canonicalization_profile_id
from the decision evidence, resolves it here before comparing any digests.
If the profile is absent or unrecognized, the verifier must return
UNSUPPORTED_CANONICAL_PROFILE — not DIGEST_MISMATCH.
"""

import hashlib
import json
import pathlib

_PROFILES_DIR = pathlib.Path(__file__).parent

# Human-readable aliases → canonical profile_id (SHA-256 of doc)
ALIASES: dict[str, str] = {
    "jcs-rfc8785-v1":            "82b5df2a487988d5ba773cf40ffa92a614769de6fbea6f4b2745794125e1c9fa",
    "jcs-rfc8785-action-ref-v1": "8c7f71754e3daae1a0390d5e0287d51097d011e40df36bf15cad5c0f47efa05a",
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
