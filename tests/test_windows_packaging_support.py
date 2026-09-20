import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import usb.core

from infocarry.execution_claim_store import PersistentExecutionClaimStore
from infocarry.write_protocol import AuthorizedWriteSender
from scripts.windows_manager_entry import (
    _read_safety_counters,
    _run_host_workflow_checks,
)


class WindowsPackagingSupportTests(unittest.TestCase):
    def test_packaged_smoke_uses_shared_paths_and_current_manager_title(self):
        entry = Path(__file__).parents[1] / "scripts" / "windows_manager_entry.py"
        source = entry.read_text(encoding="utf-8")

        self.assertIn("from infocarry.app_paths import application_paths", source)
        self.assertNotIn("_application_state_root", source)
        self.assertIn('window_state["title"] != "InfoCarry Manager"', source)

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

    def test_host_workflow_guards_against_device_enumeration_and_sender(self):
        with patch(
            "usb.core.find",
            side_effect=AssertionError("host workflow attempted USB enumeration"),
        ), patch.object(
            AuthorizedWriteSender,
            "send",
            side_effect=AssertionError("host workflow attempted to call the sender"),
        ):
            report = _run_host_workflow_checks()

        self.assertNotIn("device_enumeration_calls", report)
        self.assertNotIn("sender_calls", report)

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
