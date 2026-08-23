import unittest

from infocarry.capacity import (
    CapacityAssessment,
    CapacitySemanticsError,
    assess_legacy_remaining_budget,
    assess_total_capacity,
)


class CapacitySemanticsTests(unittest.TestCase):
    def test_exact_total_capacity_boundary(self):
        result = assess_total_capacity(100, 80, 100, source="fixture")
        self.assertEqual(result.candidate_growth_bytes, 20)
        self.assertEqual(result.remaining_growth_bytes, 20)
        self.assertEqual(result.to_dict()["candidate_within_total_limit"], True)

    def test_one_byte_over_total_capacity_is_rejected(self):
        with self.assertRaisesRegex(CapacitySemanticsError, "exceeds the total capacity"):
            assess_total_capacity(99, 80, 100, source="fixture")

    def test_missing_or_malformed_capacity_evidence_is_rejected(self):
        with self.assertRaises(CapacitySemanticsError):
            assess_total_capacity(None, 80, 100, source="fixture")
        with self.assertRaises(CapacitySemanticsError):
            assess_total_capacity(True, 80, 100, source="fixture")
        with self.assertRaises(CapacitySemanticsError):
            assess_legacy_remaining_budget(None, 80, 100)

    def test_inconsistent_lengths_are_rejected(self):
        with self.assertRaisesRegex(CapacitySemanticsError, "candidate growth"):
            CapacityAssessment(100, 80, 100, 19, 20, "fixture")
        with self.assertRaisesRegex(CapacitySemanticsError, "remaining growth"):
            CapacityAssessment(100, 80, 100, 20, 19, "fixture")


if __name__ == "__main__":
    unittest.main()
