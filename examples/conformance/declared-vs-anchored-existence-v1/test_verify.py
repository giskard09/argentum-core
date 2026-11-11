"""Offline tests (no network): vectors plus the properties the vectors are about."""
import copy
import json
import unittest
from pathlib import Path

from verify import compute_action_ref, verify_binding_pair, verify_existence

DATA = json.loads((Path(__file__).parent / "vectors.json").read_text())
EXI = {v["id"]: v for v in DATA["existence_vectors"]}
BIN = {v["id"]: v for v in DATA["binding_vectors"]}


class VectorTests(unittest.TestCase):
    def test_every_existence_vector(self):
        for vid, v in EXI.items():
            with self.subTest(vid=vid):
                got = verify_existence(v["input"])
                self.assertEqual(got["verdict"], v["expected"]["verdict"])
                if "existed_by_utc" in v["expected"]:
                    self.assertEqual(got["existence"]["existed_by_utc"], v["expected"]["existed_by_utc"])

    def test_every_binding_vector(self):
        for vid, v in BIN.items():
            with self.subTest(vid=vid):
                got = verify_binding_pair(v["input"]["record_a"], v["input"]["record_b"])
                for k, want in v["expected"].items():
                    self.assertEqual(got[k], want, k)


class ClaimClassSeparation(unittest.TestCase):
    def test_declared_time_is_never_reported_as_bounded(self):
        for vid, v in EXI.items():
            got = verify_existence(v["input"])
            with self.subTest(vid=vid):
                self.assertEqual(got["declared"]["claim_class"], "signer_declared")
                self.assertFalse(got["declared"]["independently_bounded"])

    def test_anchor_never_claims_key_validity_or_truth_or_completeness(self):
        for vid, v in EXI.items():
            got = verify_existence(v["input"])
            with self.subTest(vid=vid):
                self.assertEqual(got["not_established"], DATA["constants"]["not_established"])
                self.assertIn("key_uncompromised_at_bound", got["not_established"])

    def test_no_anchor_means_no_existence_bound(self):
        got = verify_existence(EXI["P1-declared-only-no-anchor"]["input"])
        self.assertFalse(got["existence"]["established"])
        self.assertIsNone(got["existence"]["existed_by_utc"])

    def test_offline_evidence_is_labelled_unauthenticated(self):
        got = verify_existence(EXI["P2-anchored-existence-established"]["input"])
        self.assertEqual(got["existence"]["evidence_authenticity"], "captured_not_chain_verified")

    def test_p2_declared_precedes_bound_by_the_stated_gap(self):
        got = verify_existence(EXI["P2-anchored-existence-established"]["input"])
        self.assertEqual(got["declared"]["seconds_before_bound"], 6035)

    def test_declared_time_is_bound_into_the_digest_but_not_verified(self):
        pre = EXI["P2-anchored-existence-established"]["input"]["preimage"]
        later = dict(pre, timestamp="2026-09-15T12:00:00.001Z")
        self.assertNotEqual(compute_action_ref(pre), compute_action_ref(later))

    def test_known_limit_fabricated_capture_is_accepted_offline(self):
        # Documents the limit: only a chain read catches this, so the vector pins it.
        got = verify_existence(EXI["K1-fabricated-capture-passes-offline"]["input"])
        self.assertEqual(got["verdict"], "EXISTENCE_BOUND_ESTABLISHED")
        self.assertEqual(got["existence"]["evidence_authenticity"], "captured_not_chain_verified")

    def test_out_of_profile_preimage_stops_before_any_anchor_read(self):
        bad = copy.deepcopy(EXI["P2-anchored-existence-established"]["input"])
        bad["preimage"]["scope"] = "café"
        self.assertEqual(verify_existence(bad)["verdict"], "OUT_OF_PROFILE_DOMAIN")


class BindingProperties(unittest.TestCase):
    def test_same_price_same_payto_are_not_distinguished_by_amount_payto(self):
        v = BIN["B1-amount-payto-cannot-tell-two-same-price-calls-apart"]["input"]
        self.assertFalse(verify_binding_pair(v["record_a"], v["record_b"])["distinguishable"])

    def test_nonce_distinguishes_what_amount_payto_cannot(self):
        a = BIN["B2-authorization-nonce-distinguishes-same-price-calls"]["input"]
        self.assertEqual(a["record_a"]["payment"], a["record_b"]["payment"])
        self.assertTrue(verify_binding_pair(a["record_a"], a["record_b"])["distinguishable"])

    def test_kind_is_never_inferred_from_present_fields(self):
        a = copy.deepcopy(BIN["B2-authorization-nonce-distinguishes-same-price-calls"]["input"])
        del a["record_a"]["binding"]["kind"]
        self.assertEqual(verify_binding_pair(a["record_a"], a["record_b"])["verdict"], "BINDING_UNDECLARED")

    def test_unknown_kind_is_rejected(self):
        a = copy.deepcopy(BIN["B2-authorization-nonce-distinguishes-same-price-calls"]["input"])
        a["record_a"]["binding"]["kind"] = "vibes"
        self.assertEqual(verify_binding_pair(a["record_a"], a["record_b"])["verdict"], "BINDING_KIND_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
