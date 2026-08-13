"""Regression vectors for the RFC 8785 (JCS) bugs reported against
a2a-python in a2aproject/A2A#2122 and referenced publicly by us in
a2a-tck#227 (2026-08-13) as "still open on our end, not yet patched".

Verified independently against RFC 8785's own worked examples plus the
log output in A2A#2122 (rfc8785.py / gowebpki-jcs both agree on the
expected bytes below). These are the exact three axes the issue found
diverging between a2a-python and @a2a-js/sdk:

  C2 -- non-ASCII string must serialize as literal UTF-8, not \\uXXXX
  C3 -- object key order is UTF-16 code unit order, not code point order
  C4 -- numbers serialize per ECMAScript Number::toString, not Python repr
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from jcs import jcs_dumps


def test_c2_non_ascii_literal_utf8():
    assert jcs_dumps({"name": "Café Agent"}) == '{"name":"Café Agent"}'


def test_c3_astral_key_sorts_before_bmp_e000():
    # U+1F600 (astral) encodes as UTF-16 surrogate pair D83D DE00.
    # U+E000 (BMP, private-use area) encodes as the single unit E000.
    # D83D < E000, so the astral key sorts first -- opposite of code-point
    # order, where U+E000 < U+1F600 would sort it first instead.
    astral_key = "\U0001F600"
    bmp_key = ""
    assert jcs_dumps({bmp_key: 1, astral_key: 2}) == '{"\U0001F600":2,"":1}'


def test_c4_ecmascript_number_serialization():
    assert jcs_dumps({"tolerance": 0.000001}) == '{"tolerance":0.000001}'


def test_c4_ecmascript_number_large_and_small_exponents():
    assert jcs_dumps({"a": 1e21}) == '{"a":1e+21}'
    assert jcs_dumps({"a": 1e20}) == '{"a":100000000000000000000}'
    assert jcs_dumps({"a": 1e-7}) == '{"a":1e-7}'
    assert jcs_dumps({"a": 100.0}) == '{"a":100}'
    assert jcs_dumps({"a": 0.1}) == '{"a":0.1}'
    assert jcs_dumps({"a": 0.0}) == '{"a":0}'
    assert jcs_dumps({"a": -0.0}) == '{"a":0}'
    assert jcs_dumps({"a": -1.5}) == '{"a":-1.5}'


def test_c1_ascii_control_unaffected_regression():
    assert jcs_dumps({"name": "Example Agent", "ok": True, "n": 1}) == (
        '{"n":1,"name":"Example Agent","ok":true}'
    )
