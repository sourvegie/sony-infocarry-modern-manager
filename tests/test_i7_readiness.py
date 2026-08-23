import unittest

from infocarry.i7_readiness import (
    I7ReadinessError,
    TimestampFixedStateEvidence,
    VERIFIED_INDEPENDENT,
    assess_timestamp_fixed_state_eligibility,
)


class I7ReadinessTests(unittest.TestCase):
    def test_current_evidence_fails_closed(self):
        result = assess_timestamp_fixed_state_eligibility(
            TimestampFixedStateEvidence(
                timestamp_rule_status="unresolved",
                fixed_state_rule_status="observed_multiple",
                timestamp_independent_cases=4,
                fixed_state_independent_cases=2,
            )
        )

        self.assertFalse(result.eligible)
        self.assertFalse(result.checks["timestamp_rule_independently_verified"])
        self.assertFalse(result.checks["fixed_state_rule_independently_verified"])
        self.assertIn("timestamp +0x0c generation", " ".join(result.reasons))
        with self.assertRaisesRegex(I7ReadinessError, "not independently verified"):
            result.require_supported()

    def test_plausible_rules_do_not_become_eligible(self):
        result = assess_timestamp_fixed_state_eligibility(
            TimestampFixedStateEvidence(
                timestamp_rule_status="inferred",
                fixed_state_rule_status="verified",
                timestamp_independent_cases=2,
                fixed_state_independent_cases=3,
            )
        )
        self.assertFalse(result.eligible)

    def test_unresolved_reference_is_a_blocker(self):
        result = assess_timestamp_fixed_state_eligibility(
            TimestampFixedStateEvidence(
                timestamp_rule_status=VERIFIED_INDEPENDENT,
                fixed_state_rule_status=VERIFIED_INDEPENDENT,
                timestamp_independent_cases=2,
                fixed_state_independent_cases=2,
                unresolved_references=("0x001f.group-1",),
            )
        )
        self.assertFalse(result.eligible)
        self.assertFalse(result.checks["no_unresolved_references"])
        self.assertIn("0x001f.group-1", result.reasons[0])

    def test_verified_independent_rules_can_pass_assessment(self):
        result = assess_timestamp_fixed_state_eligibility(
            TimestampFixedStateEvidence(
                timestamp_rule_status=VERIFIED_INDEPENDENT,
                fixed_state_rule_status=VERIFIED_INDEPENDENT,
                timestamp_independent_cases=2,
                fixed_state_independent_cases=2,
            )
        )
        self.assertTrue(result.eligible)
        self.assertEqual(result.reasons, ())
        result.require_supported()
        self.assertTrue(result.to_dict()["checks"]["complete_fresh_backup"])

    def test_incomplete_backup_and_scope_are_reported(self):
        result = assess_timestamp_fixed_state_eligibility(
            TimestampFixedStateEvidence(
                timestamp_rule_status=VERIFIED_INDEPENDENT,
                fixed_state_rule_status=VERIFIED_INDEPENDENT,
                timestamp_independent_cases=2,
                fixed_state_independent_cases=2,
                fresh_backup_complete=False,
                exact_supported_scope=False,
            )
        )
        self.assertFalse(result.eligible)
        self.assertIn("complete fresh backup", " ".join(result.reasons))
        self.assertIn("exceeds the characterized operation", " ".join(result.reasons))


if __name__ == "__main__":
    unittest.main()
