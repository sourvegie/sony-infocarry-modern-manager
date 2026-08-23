from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from infocarry.backup import BackupObjectSpec, RawBackupArchive
from infocarry.capture import CaptureError
from infocarry.cli import (
    build_parser,
    command_backup,
    command_info,
    command_inventory,
    command_preview_text,
)
from infocarry.usb_access import DeviceAccessError

try:
    from test_backup_format import make_text_blob
except ModuleNotFoundError:
    from tests.test_backup_format import make_text_blob


class CliTests(unittest.TestCase):
    def test_info_requires_new_raw_destination_argument(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["info", "--query", "configuration"])

    @patch("infocarry.cli.InfoCarrySession.open")
    def test_existing_capture_is_rejected_before_device_open(self, open_session):
        with tempfile.TemporaryDirectory() as temporary:
            existing = Path(temporary)
            with self.assertRaises(CaptureError):
                command_info(False, "configuration", existing)
        open_session.assert_not_called()

    def test_backup_requires_destination_argument(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["backup"])

    def test_export_requires_source_and_destination_arguments(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["export", "backup-only"])

    def test_fixture_report_requires_fixture_and_destination(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["fixture-report", "fixture-only"])
        args = parser.parse_args(["fixture-report", "fixture", "report"])
        self.assertEqual(args.command, "fixture-report")
        self.assertEqual(args.fixture_root, Path("fixture"))
        self.assertEqual(args.destination, Path("report"))

    def test_offline_workflow_commands_parse_without_device_access(self):
        parser = build_parser()
        inventory = parser.parse_args(["inventory", "backup"])
        self.assertEqual(inventory.command, "inventory")
        preview = parser.parse_args(
            ["preview-text", "backup", "0xc0", "input.txt", "--max-bytes", "128"]
        )
        self.assertEqual(preview.command, "preview-text")
        self.assertEqual(preview.record_offset, 0xC0)
        self.assertEqual(preview.max_bytes, 128)
        desktop = parser.parse_args(["desktop"])
        self.assertEqual(desktop.command, "desktop")

    def test_offline_workflow_commands_use_backup_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backup = root / "backup"
            archive = RawBackupArchive.create(backup)
            blob = make_text_blob(b"old text")
            archive.save(BackupObjectSpec(0x8004, "backup-blob", len(blob)), blob)
            archive.finalize()
            inventory_report = root / "inventory-report"
            command_inventory(False, backup, inventory_report)
            self.assertTrue((inventory_report / "report.json").exists())
            text_file = root / "input.txt"
            text_file.write_text("new\ntext", encoding="utf-8")
            preview_report = root / "preview-report"
            command_preview_text(
                False, backup, 0xC0, text_file, 128, preview_report
            )
            self.assertTrue((preview_report / "report.json").exists())

    @patch("infocarry.cli.InfoCarrySession.open")
    def test_existing_backup_is_rejected_before_device_open(self, open_session):
        with tempfile.TemporaryDirectory() as temporary:
            existing = Path(temporary)
            with self.assertRaises(CaptureError):
                command_backup(False, existing)
        open_session.assert_not_called()

    @patch("infocarry.cli.InfoCarrySession.open")
    def test_backup_open_failure_marks_archive_incomplete(self, open_session):
        open_session.side_effect = DeviceAccessError("device disconnected")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "new-backup"
            with self.assertRaises(DeviceAccessError):
                command_backup(False, destination)
            manifest = (destination / "manifest.json").read_text()
            self.assertIn('"state": "incomplete"', manifest)
            self.assertIn('"type": "DeviceAccessError"', manifest)


if __name__ == "__main__":
    unittest.main()
