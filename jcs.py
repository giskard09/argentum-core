"""RFC 8785 (JCS)-compatible JSON canonicalization helper.

Python's json.dumps(sort_keys=True) sorts object keys by Unicode code point.
JCS mandates the same key order as JS Array.prototype.sort(), which compares
by UTF-16 code unit. The two orders diverge only for keys with characters
outside the Basic Multilingual Plane (astral code points encode as surrogate
pairs in UTF-16), but any byte-exact cross-implementation verifier needs the
correct order regardless of whether today's payloads happen to be ASCII.

RFC 8785 also mandates: (1) non-ASCII characters serialize as literal UTF-8,
never as \\uXXXX escapes, and (2) numbers serialize per the ECMAScript
Number::toString algorithm (ECMA-262 7.1.12.1), which picks fixed vs.
exponential notation by different thresholds than Python's float repr (e.g.
0.000001 is "0.000001" in JCS/JS, "1e-06" under plain json.dumps).

This module is the single place that ordering/formatting lives -- every site
in this repo that needs a JCS-stable serialization (for hashing or signing)
should call jcs_dumps/jcs_bytes instead of json.dumps(sort_keys=True)
directly.
"""
import json
import math
from typing import Any


def _canonicalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        sorted_keys = sorted(obj.keys(), key=lambda k: k.encode("utf-16-be", "surrogatepass"))
        return {k: _canonicalize(obj[k]) for k in sorted_keys}
    if isinstance(obj, list):
        return [_canonicalize(item) for item in obj]
    return obj


def _ecma_number_string(x: float) -> str:
    """Format a float per ECMA-262 Number::toString (7.1.12.1).

    Relies on Python's float repr for the shortest round-trip digit
    sequence (CPython's dtoa gives the same minimal digit set the
    ECMAScript algorithm requires), then re-derives (sign, digits, n) from
    that string and re-applies JS's fixed-vs-exponential placement rules,
    which differ from Python's own repr formatting.
    """
    if math.isnan(x) or math.isinf(x):
        raise ValueError(f"JCS numbers must be finite: {x!r}")
    if x == 0.0:
        return "0"  # covers -0.0 too: Number::toString(-0) == "0"

    sign = "-" if x < 0 else ""
    text = repr(abs(x))
    mantissa, _, exp_part = text.partition("e")
    exp = int(exp_part) if exp_part else 0
    int_part, _, frac_part = mantissa.partition(".")

    raw_digits = int_part + frac_part
    stripped_leading = raw_digits.lstrip("0")
    leading_zeros = len(raw_digits) - len(stripped_leading)
    # value == 0.<stripped_leading> * 10**point_pos
    point_pos = len(int_part) - leading_zeros + exp

    digits = stripped_leading.rstrip("0") or "0"
    k = len(digits)
    n = point_pos

    if k <= n <= 21:
        s = digits + "0" * (n - k)
    elif 0 < n <= 21:
        s = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        s = "0." + "0" * (-n) + digits
    else:
        exp_str = f"e{'+' if n - 1 >= 0 else ''}{n - 1}"
        s = (digits if k == 1 else f"{digits[0]}.{digits[1:]}") + exp_str

    return sign + s


def _encode(obj: Any, ensure_ascii: bool) -> str:
    if obj is None:
        return "null"
    if obj is True:
        return "true"
    if obj is False:
        return "false"
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=ensure_ascii)
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, float):
        return _ecma_number_string(obj)
    if isinstance(obj, dict):
        items = ",".join(f"{_encode(k, ensure_ascii)}:{_encode(v, ensure_ascii)}" for k, v in obj.items())
        return "{" + items + "}"
    if isinstance(obj, list):
        return "[" + ",".join(_encode(item, ensure_ascii) for item in obj) + "]"
    raise TypeError(f"Object of type {type(obj).__name__} is not JCS-serializable")


def jcs_dumps(obj: Any, ensure_ascii: bool = False) -> str:
    """Serialize obj as JCS-ordered, whitespace-free JSON.

    ensure_ascii defaults to False: RFC 8785 requires literal UTF-8 output
    for non-ASCII characters, never \\uXXXX escapes. For ASCII-only payloads
    (every preimage in this repo today) this default is a no-op -- escaping
    only changes output for non-ASCII input, so no previously-anchored hash
    is affected by this default flip.
    """
    return _encode(_canonicalize(obj), ensure_ascii)


def jcs_bytes(obj: Any, ensure_ascii: bool = False) -> bytes:
    return jcs_dumps(obj, ensure_ascii=ensure_ascii).encode("utf-8")
