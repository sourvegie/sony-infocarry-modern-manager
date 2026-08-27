from datetime import datetime, timezone
from pathlib import Path
import unittest

from infocarry.desktop_ttk import format_prepared_package_readiness_preview
from infocarry.prepared_multi_text import build_prepared_text_package_set
from infocarry.prepared_package_readiness import (
    PreparedPackageReadinessError,
    build_prepared_package_readiness_preview,
)
from infocarry.write_gate import verify_fresh_backup

try:
    import test_prepared_package_multi_candidate as _fixture
except ModuleNotFoundError:
    import tests.test_prepared_package_multi_candidate as _fixture
    from tests.test_new_txt import _write_archive
else:
    from test_new_txt import _write_archive


class PreparedPackageReadinessTests(unittest.TestCase):
    def test_candidate_preview_reports_order_types_capacity_hashes_and_no_device(self):
        temporary, package, _backup, candidate, _template = _fixture.PreparedMultiCandidateTests()._case(mixed=True)
        self.addCleanup(temporary.cleanup)
        preview = build_prepared_package_readiness_preview(package, candidate=candidate)
        report = preview.to_dict()
        self.assertTrue(preview.candidate_available)
        self.assertEqual(
            [item["kind"] for item in report["package"]["ordered_items"]],
            ["txt", "bmp", "txt"],
        )
        self.assertEqual(report["package"]["paths"], [
            "root\\NewBook",
            "root\\NewBook\\one.txt",
            "root\\NewBook\\page.bmp",
            "root\\NewBook\\two.txt",
        ])
        self.assertEqual(report["capacity"]["status"], "sufficient")
        self.assertEqual(report["candidate"]["candidate_blob_sha256"], candidate.candidate_blob_sha256)
        self.assertEqual(report["candidate"]["transaction_sha256"], candidate.transaction_sha256)
        self.assertFalse(report["usb_accessed"])
        self.assertEqual(report["safety"]["sender_called"], False)
        rendered = format_prepared_package_readiness_preview(report)
        self.assertIn("OFFLINE PACKAGE READINESS PREVIEW", rendered)
        self.assertIn("TXT root\\NewBook\\one.txt", rendered)
        self.assertIn("BMP root\\NewBook\\page.bmp", rendered)
        self.assertIn("USB operation performed: no", rendered)

    def test_logical_preview_without_candidate_is_explicitly_blocked(self):
        temporary, package, backup, _candidate, _template = _fixture.PreparedMultiCandidateTests()._case(mixed=False)
        self.addCleanup(temporary.cleanup)
        preview = build_prepared_package_readiness_preview(package, backup=backup)
        report = preview.to_dict()
        self.assertFalse(preview.candidate_available)
        self.assertEqual(report["candidate"]["candidate_blob_sha256"], None)
        self.assertEqual(report["capacity"]["status"], "not_evaluated_without_candidate")
        self.assertFalse(report["eligibility"]["live_transfer_eligible"])
        self.assertTrue(any("candidate" in reason for reason in report["eligibility"]["reasons"]))

    def test_existing_casefold_path_is_reported_as_conflict(self):
        temporary, _package, _backup, _candidate, _template = _fixture.PreparedMultiCandidateTests()._case(mixed=False)
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        _baseline_blob, template_blob = _fixture._template_blobs()
        zero_state = {command: b"\x00" * 64 for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
        conflict_backup_path = _write_archive(
            root / "conflict-backup",
            template_blob,
            datetime(2026, 8, 27, tzinfo=timezone.utc),
            fixed_state=zero_state,
        )
        backup = verify_fresh_backup(
            conflict_backup_path,
            now=datetime(2026, 8, 27, tzinfo=timezone.utc),
            max_age_seconds=None,
        )
        one = root / "one.txt"
        two = root / "two.txt"
        package = build_prepared_text_package_set(((one, "one.txt"), (two, "two.txt")), "template")
        preview = build_prepared_package_readiness_preview(package, backup=backup)
        self.assertEqual(preview.report["conflicts"], ["root\\template"])
        self.assertFalse(preview.report["eligibility"]["offline_preview_ready"])

    def test_unsupported_package_input_is_rejected_without_usb(self):
        with self.assertRaisesRegex(PreparedPackageReadinessError, "ordered TXT or TXT/BMP"):
            build_prepared_package_readiness_preview(object())


if __name__ == "__main__":
    unittest.main()
