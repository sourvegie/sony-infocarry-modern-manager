import unittest

from infocarry.delete_readiness import (
    DeleteReadinessError,
    SUPPORTED_DEVICE,
    assess_delete_eligibility,
)


_HASH = "a" * 64


def _complete(**overrides):
    values = {
        "device_identity": SUPPORTED_DEVICE,
        "baseline_manifest_sha256": _HASH,
        "baseline_blob_sha256": _HASH,
        "target_path": "root\\disposable.txt",
        "target_record_offset": 0xC0,
        "target_payload_sha256": _HASH,
        "target_is_root_txt": True,
        "disposable_target_confirmed": True,
        "unresolved_references": (),
        "timestamp_rule": "independently verified rule",
        "fixed_state_derivation": "fresh-state derivation",
        "candidate_blob_sha256": _HASH,
        "transaction_sha256": _HASH,
        "operation_phrase_bound": True,
        "exactly_one_removed": True,
        "no_added_paths": True,
        "unrelated_payloads_preserved": True,
        "storage_sufficient": True,
    }
    values.update(overrides)
    return values


class DeleteReadinessTests(unittest.TestCase):
    def test_opaque_timestamp_and_attempt_fixture_state_fail_closed(self):
        result = assess_delete_eligibility(
            **_complete(
                timestamp_rule=None,
                fixed_state_derivation=None,
                captured_fixture_only=True,
            )
        )

        self.assertFalse(result.eligible)
        self.assertFalse(result.checks["timestamp_rule"])
        self.assertFalse(result.checks["fixed_state_derivation"])
        self.assertFalse(result.checks["not_fixture_only"])
        self.assertIn("metadata +0x0c generation rule is unresolved", result.reasons)
        self.assertIn("fresh fixed-state derivation is unresolved", result.reasons)
        self.assertIn("captured-fixture reproduction is not live-delete eligibility", result.reasons)
        with self.assertRaisesRegex(DeleteReadinessError, "not eligible for live deletion"):
            result.require()

    def test_complete_narrow_inputs_can_be_assessed_without_authorizing_a_sender(self):
        result = assess_delete_eligibility(**_complete())

        self.assertTrue(result.eligible)
        self.assertEqual(result.reasons, ())
        result.require()
        self.assertTrue(result.to_dict()["checks"]["prospective_transaction"])

    def test_unknown_reference_and_missing_binding_are_indeterminate(self):
        result = assess_delete_eligibility(
            **_complete(
                unresolved_references=("0x001f.group-1",),
                operation_phrase_bound=False,
                no_added_paths=None,
            )
        )

        self.assertFalse(result.eligible)
        self.assertIn("target is referenced by unresolved state structure(s): 0x001f.group-1", result.reasons)
        self.assertIn("delete-specific confirmation phrase is not bound", result.reasons)
        self.assertIn("candidate adds an unexpected path or is unverified", result.reasons)

    def test_invalid_target_shape_and_hashes_are_rejected(self):
        result = assess_delete_eligibility(
            **_complete(
                target_path="root\\folder\\nested.txt",
                target_record_offset=0xC1,
                target_payload_sha256="not-a-hash",
                baseline_manifest_sha256=None,
            )
        )

        self.assertFalse(result.eligible)
        self.assertFalse(result.checks["exact_root_txt_target"])
        self.assertFalse(result.checks["record_offset"])
        self.assertFalse(result.checks["target_payload"])
        self.assertFalse(result.checks["complete_fresh_backup_manifest"])
