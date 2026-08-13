"""JCS/RFC 8785 key ordering for stored trail preimages.

Python's json.dumps(sort_keys=True) sorts object keys by Unicode code point.
RFC 8785 requires sorting by UTF-16 code unit -- the two orders coincide for
ASCII/BMP keys but diverge for keys with characters outside the BMP (an
astral code point encodes as a UTF-16 surrogate pair, and the leading
surrogate can sort before or after a BMP character depending on its range).

Found via independent verification of a third-party correction
(flarenetworkflr / x402-foundation/x402#3000) to a canonicalization guide
of ours -- confirmed the same ordering bug existed in
mycelium_trails.set_trail_preimage and argentum.py's anchor_proof
recomputation.
"""
import json
import os
import sys
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mycelium_trails

EMOJI = "\U0001F600"  # outside the BMP
BMP_HIGH = "￿"   # inside the BMP, sorts after EMOJI's lead surrogate under UTF-16


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "trails.db")
    mycelium_trails.init_db(db_path)
    return db_path


def test_astral_key_sorts_before_bmp_key_utf16_order(db):
    """RFC 8785 (JCS) key order for a key pair straddling the BMP boundary.

    Python's default code-point sort gives [BMP_HIGH, EMOJI] (wrong for JCS).
    A JS-conformant (and thus JCS-conformant) sort gives [EMOJI, BMP_HIGH].
    """
    trail_id = mycelium_trails.record_trail(
        db, "agent-jcs-test", "oasis", "enter", uuid.uuid4().hex, karma_at_time=10,
    )
    preimage = {BMP_HIGH: "a", EMOJI: "b"}
    mycelium_trails.set_trail_preimage(db, trail_id, preimage)

    row = mycelium_trails.get_trail_by_id(db, trail_id)
    stored = row["preimage_json"]

    # ensure_ascii=False: RFC 8785 requires literal UTF-8 for non-ASCII
    # chars, not \uXXXX escapes (the other bug jcs.py fixed, see
    # test_jcs_rfc8785_a2a_vectors.py::test_c2_non_ascii_literal_utf8).
    expected = json.dumps(
        {EMOJI: "b", BMP_HIGH: "a"}, sort_keys=False, separators=(",", ":"), ensure_ascii=False
    )
    assert stored == expected, f"expected JCS/UTF-16 key order, got: {stored!r}"

    wrong_order = json.dumps({BMP_HIGH: "a", EMOJI: "b"}, sort_keys=True, separators=(",", ":"))
    assert stored != wrong_order, "regressed to Python code-point sort_keys=True order"
