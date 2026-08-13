#!/usr/bin/env python3
"""Regression suite for admission_status()'s three-state fix (2026-08-13).

Written against the WG trustless-ai consensus spec (Merlini/BabyBlueViper1/
Pavlo), validated against two independent real incidents of the same
bug-shape: BabyBlueViper1's PQ companion-signature check (a retired key
collapsed "not determined" and "authorized" into the same True) and
Merlini's recompute-kit exit-code check (an environment failure collapsed
"verified false" and "environment broke" into the same False).

Covers all four required properties, not just the point fix:
  (a) genuinely indeterminate input names the third state, never the
      permissive one
  (b) the legacy bool is always a strict projection of the named state --
      no input can make them disagree
  (c) an impossible combination (two mutually-exclusive states both true)
      raises, it never silently resolves to one of them
  (d) the control inverse: every genuinely determinable input still lands
      on ADMITTED or REJECTED -- unresolved must not leak into cases that
      have a real answer, which is exactly the failure mode a lazy "always
      return unresolved" fix would pass (a)-(c) while fixing nothing.

Zero-dependency, offline. Run: python3 test_admission_status.py
"""
from __future__ import annotations

import unittest

from verify import (
    ADMISSION_ADMITTED,
    ADMISSION_REJECTED,
    ADMISSION_UNRESOLVED,
    _assert_exclusive,
    admission_status,
    admits,
)


def _vector(key_id=None, payment_signer=None, include_signer=True, include_actor=True):
    v = {"artifact": {"actor": {}}}
    if include_signer:
        v["signer"] = {} if key_id is None else {"key_id": key_id}
    if include_actor and payment_signer is not None:
        v["artifact"]["actor"]["payment_signer"] = payment_signer
    return v


DETERMINABLE_ADMITTED = [
    _vector(key_id="policy-issuer-a", payment_signer="wallet:0x1"),
    _vector(key_id="policy-issuer-b", payment_signer="wallet:0x2"),
    _vector(key_id="", payment_signer="wallet:0x3"),  # empty string != None: still determinable
]

DETERMINABLE_REJECTED = [
    _vector(key_id="wallet:0x1", payment_signer="wallet:0x1"),
    _vector(key_id="wallet:0x2", payment_signer="wallet:0x2"),
]

INDETERMINATE = [
    _vector(key_id=None, payment_signer="wallet:0x1"),  # signer key_id missing
    _vector(key_id="policy-issuer-a", payment_signer=None),  # payment_signer missing
    _vector(key_id=None, payment_signer=None),  # both missing
    _vector(include_signer=False, payment_signer="wallet:0x1"),  # no signer block at all
    {},  # empty vector entirely
]


class TestPropertyA_UnresolvedNeverPermissive(unittest.TestCase):
    """(a) A genuinely indeterminable input names the third state explicitly,
    and that state is never the permissive default (ADMITTED)."""

    def test_missing_fields_resolve_to_unresolved(self):
        for v in INDETERMINATE:
            with self.subTest(vector=v):
                self.assertEqual(admission_status(v), ADMISSION_UNRESOLVED)

    def test_unresolved_is_never_admitted(self):
        for v in INDETERMINATE:
            with self.subTest(vector=v):
                self.assertNotEqual(admission_status(v), ADMISSION_ADMITTED)
                # the permissive legacy value is True -- confirm unresolved
                # never projects to it.
                self.assertFalse(admits(v))


class TestPropertyB_BoolNeverContradictsNamedField(unittest.TestCase):
    """(b) admits() == (admission_status() == ADMITTED), for every input,
    with no exception -- the bool cannot diverge from the named field."""

    def test_bool_matches_named_state_across_all_cases(self):
        for v in DETERMINABLE_ADMITTED + DETERMINABLE_REJECTED + INDETERMINATE:
            with self.subTest(vector=v):
                self.assertEqual(admits(v), admission_status(v) == ADMISSION_ADMITTED)


class TestPropertyC_ImpossibleCombinationRaises(unittest.TestCase):
    """(c) Two mutually-exclusive states both true is a raise, not a silent
    resolution to one of them. Tested directly against _assert_exclusive
    with fabricated combinations, since _admission_raw_checks cannot
    currently produce one by construction -- this guards against a future
    edit that makes it possible."""

    def test_admitted_and_rejected_both_true_raises(self):
        with self.assertRaises(ValueError):
            _assert_exclusive(True, True, False)

    def test_admitted_and_unresolved_both_true_raises(self):
        with self.assertRaises(ValueError):
            _assert_exclusive(True, False, True)

    def test_rejected_and_unresolved_both_true_raises(self):
        with self.assertRaises(ValueError):
            _assert_exclusive(False, True, True)

    def test_all_three_true_raises(self):
        with self.assertRaises(ValueError):
            _assert_exclusive(True, True, True)

    def test_none_true_raises(self):
        with self.assertRaises(ValueError):
            _assert_exclusive(False, False, False)

    def test_exactly_one_true_does_not_raise(self):
        _assert_exclusive(True, False, False)
        _assert_exclusive(False, True, False)
        _assert_exclusive(False, False, True)


class TestPropertyD_UnresolvedDisappearsWhenDeterminable(unittest.TestCase):
    """(d) Control inverse. Every genuinely determinable input must land on
    ADMITTED or REJECTED -- never UNRESOLVED. Without this test, a lazy fix
    that always returns UNRESOLVED would pass (a)-(c) while having fixed
    nothing real; this is the check the WG itself flagged as missing from
    their own 4-case-by-hand coverage."""

    def test_determinable_admitted_never_unresolved(self):
        for v in DETERMINABLE_ADMITTED:
            with self.subTest(vector=v):
                status = admission_status(v)
                self.assertNotEqual(status, ADMISSION_UNRESOLVED)
                self.assertEqual(status, ADMISSION_ADMITTED)

    def test_determinable_rejected_never_unresolved(self):
        for v in DETERMINABLE_REJECTED:
            with self.subTest(vector=v):
                status = admission_status(v)
                self.assertNotEqual(status, ADMISSION_UNRESOLVED)
                self.assertEqual(status, ADMISSION_REJECTED)


if __name__ == "__main__":
    unittest.main()
