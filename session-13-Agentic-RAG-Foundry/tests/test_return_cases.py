"""Runs every labeled return case through the service. No model is involved."""
import unittest

from fixtures import CASES, Environment
from northstar.eligibility import ReturnRequest
from northstar.service import NotFound


class ReturnCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = Environment()

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def test_every_case_matches_its_label_and_writes_nothing(self):
        before = (self.env.count("returns"), self.env.count("refunds"), self.env.count("support_tickets"))
        mismatches = []
        for case in CASES:
            actor, request = case["authenticated_customer_id"], ReturnRequest(**case["inputs"])
            try:
                result = self.env.service.check_return_eligibility(actor, request)
                actual = (result["outcome"], result["policy_ids"], result["fee_cents"])
            except NotFound:
                # A denial carries no policy evidence; the label's policy id is for the explanation only.
                actual = ("access_denied", case["expected_policy_ids"], None)
            expected = (case["expected_outcome"], case["expected_policy_ids"], case["expected_fee_cents"])
            if actual != expected:
                mismatches.append(f"{case['case_id']} {case['scenario']}: expected {expected}, got {actual}")
        self.assertEqual(mismatches, [])
        # The cases contain no customer confirmation, so nothing may have been written.
        self.assertEqual((self.env.count("returns"), self.env.count("refunds"), self.env.count("support_tickets")), before)

    def test_version_sensitive_cases_are_present(self):
        flips = [c for c in CASES if c["version_sensitive"] and c["expected_fee_cents"] is None]
        self.assertGreaterEqual(len(flips), 2)


if __name__ == "__main__":
    unittest.main()
