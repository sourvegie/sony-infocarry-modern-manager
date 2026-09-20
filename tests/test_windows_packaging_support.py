import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from infocarry.execution_claim_store import PersistentExecutionClaimStore
from scripts.windows_manager_entry import (
    _read_safety_counters,
    _run_host_workflow_checks,
)


class WindowsPackagingSupportTests(unittest.TestCase):
    def test_packaged_host_workflow_covers_content_and_keeps_exact_profiles(self):
        report = _run_host_workflow_checks()

        self.assertTrue(report["add_content"])
        self.assertEqual(report["preparation"][".txt"], "txt")
        self.assertEqual(report["preparation"][".bmp"], "bmp")
        self.assertEqual(report["preparation"][".epub"], "txt")
        self.assertEqual(set(report["readiness_review"]), {".txt", ".bmp", ".epub"})

        three = report["verified_shapes"]["txt-bmp-txt"]
        self.assertEqual(three["shape"], ["txt", "bmp", "txt"])
        self.assertEqual(three["profile"], "experimental-flat-root-folder-txt-bmp-v1")
        self.assertTrue(three["eligible"])
        self.assertFalse(three["blocked"])
        self.assertFalse(three["transfer_enabled"])

        four = report["verified_shapes"]["txt-bmp-txt-txt"]
        self.assertEqual(four["shape"], ["txt", "bmp", "txt", "txt"])
        self.assertEqual(four["profile"], "verified-vnw-v15-four-leaf-direct-v1")
        self.assertTrue(four["eligible"])
        self.assertFalse(four["blocked"])
        self.assertFalse(four["transfer_enabled"])

        unsupported = report["unsupported_shape_blocked"]
        self.assertEqual(unsupported["shape"], ["txt", "txt", "bmp", "txt"])
        self.assertFalse(unsupported["eligible"])
        self.assertTrue(unsupported["blocked"])
        self.assertFalse(unsupported["transfer_enabled"])
        self.assertFalse(report["vnw_v10_transfer_capable"])

    def test_host_workflow_does_not_enter_a_device_or_write_path(self):
        report = _run_host_workflow_checks()
        self.assertEqual(report["device_enumeration_calls"], 0)
        self.assertEqual(report["sender_calls"], 0)
        self.assertEqual(report["claims_consumed"], 0)
        self.assertEqual(report["sender_marker_mutations"], 0)
        self.assertEqual(report["installation_lock_mutations"], 0)

    def test_fresh_packaged_profile_reports_zero_persistent_write_activity(self):
        with TemporaryDirectory(prefix="infocarry-windows-safety-smoke-") as temporary:
            state_root = Path(temporary)
            PersistentExecutionClaimStore(state_root / "execution-claims.sqlite3")
            counters = _read_safety_counters(state_root)

        self.assertEqual(
            counters,
            {
                "claims_consumed": 0,
                "sender_marker_rows": 0,
                "installation_lock_mutations": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
