"""RFC 8785 (JCS)-compatible JSON canonicalization helper.

Python's json.dumps(sort_keys=True) sorts object keys by Unicode code point.
JCS mandates the same key order as JS Array.prototype.sort(), which compares
by UTF-16 code unit. The two orders diverge only for keys with characters
outside the Basic Multilingual Plane (astral code points encode as surrogate
pairs in UTF-16), but any byte-exact cross-implementation verifier needs the
correct order regardless of whether today's payloads happen to be ASCII.

This module is the single place that ordering lives — every site in this
repo that needs a JCS-stable serialization (for hashing or signing) should
call jcs_dumps/jcs_bytes instead of json.dumps(sort_keys=True) directly.
"""
import json
from typing import Any


def _canonicalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        sorted_keys = sorted(obj.keys(), key=lambda k: k.encode("utf-16-be", "surrogatepass"))
        return {k: _canonicalize(obj[k]) for k in sorted_keys}
    if isinstance(obj, list):
        return [_canonicalize(item) for item in obj]
    return obj


def jcs_dumps(obj: Any, ensure_ascii: bool = True) -> str:
    """Serialize obj as JCS-ordered, whitespace-free JSON.

    ensure_ascii defaults to True to match json.dumps' own default (and thus
    preserve byte output at call sites that never set it explicitly). Pass
    False where the site already relied on literal non-ASCII output.
    """
    return json.dumps(_canonicalize(obj), sort_keys=False, separators=(",", ":"), ensure_ascii=ensure_ascii)


def jcs_bytes(obj: Any, ensure_ascii: bool = True) -> bytes:
    return jcs_dumps(obj, ensure_ascii=ensure_ascii).encode("utf-8")
