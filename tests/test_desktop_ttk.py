import errno
import unittest

from infocarry.backup_format import BackupFormatError
from infocarry.desktop_ttk import (
    format_library_preparation_audit,
    format_offline_conversion_report,
    format_offline_page_preview,
    format_post_write_verification,
    format_text_replacement_preview,
    friendly_error_message,
)
from infocarry.guarded_workflow import GuardedWorkflowError
from infocarry.offline_conversion import PageLayout, load_utf8_text_document


class DesktopTtkMessageTests(unittest.TestCase):
    def test_library_prepare_summary_is_explicitly_offline(self):
        summary = format_library_preparation_audit(
            {
                "device_operation": "none",
                "usb_accessed": False,
                "source": {"sha256": "a" * 64},
                "prepared": {"child_path": "root\\Book\\chapter.txt"},
            }
        )
        self.assertIn("OFFLINE LIBRARY PREPARE", summary)
        self.assertIn("no device change occurred", summary)
        self.assertIn("root\\\\Book\\\\chapter.txt", summary)
        self.assertIn('"usb_accessed": false', summary)

    def test_recovery_messages_cover_common_read_only_failures(self):
        self.assertIn("not enough free disk space", friendly_error_message(OSError(errno.ENOSPC, "full")))
        self.assertIn("not writable", friendly_error_message(PermissionError("denied")))
        malformed = friendly_error_message(BackupFormatError("bad checksum"))
        self.assertIn("incomplete or malformed", malformed)
        self.assertIn("fresh read-only backup", malformed)
        disconnected = friendly_error_message(RuntimeError("USB timeout while reading"))
        self.assertIn("Reconnect the device", disconnected)

    def test_replacement_preview_summary_is_explicitly_offline(self):
        report = {
            "authoring": {
                "input_characters": 5,
                "input_utf8_bytes": 7,
                "normalized_characters": 6,
                "encoded_payload_bytes": 6,
            },
            "target": {
                "path": "root\\memo",
                "record_offset_hex": "0x000000c0",
                "native_prefix": {"length_bytes": 32, "preserved_exactly": True},
            },
            "workflow": {
                "target_path": "root\\memo.txt",
                "target_record_offset": "0x000000c0",
                "input_path": "/tmp/replacement.txt",
            },
            "capacity": {
                "limit_applied": False,
                "limit_bytes": None,
                "encoded_payload_within_limit": True,
            },
        }
        summary = format_text_replacement_preview(report)
        self.assertIn("OFFLINE REPLACEMENT PREVIEW", summary)
        self.assertIn("no device change occurred", summary)
        self.assertIn("root\\memo.txt", summary)
        self.assertIn("0x000000c0", summary)
        self.assertIn("Source UTF-8 bytes: 7", summary)
        self.assertIn("Encoded payload (strict CP932): 6 bytes", summary)
        self.assertIn("Candidate bytes included: no", summary)
        self.assertIn("USB operation performed: no", summary)

    def test_post_write_summary_shows_all_independent_checks_and_no_retry(self):
        summary = format_post_write_verification(
            {
                "before_backup": {"directory": "/tmp/before"},
                "after_backup": {"directory": "/tmp/after"},
                "fixed_state_matches": True,
                "dynamic_blob_matches": True,
                "unrelated_objects_unchanged": True,
            }
        )
        self.assertIn("POST-WRITE READ-BACK VERIFICATION — VERIFIED", summary)
        self.assertIn("Fixed state matches candidate: yes", summary)
        self.assertIn("Dynamic content matches candidate: yes", summary)
        self.assertIn("Unrelated backup objects unchanged: yes", summary)
        self.assertIn("Automatic retry: no", summary)

    def test_guarded_write_error_explains_terminal_recovery(self):
        message = friendly_error_message(
            GuardedWorkflowError(
                "read-back did not match", stage="post_write_readback", write_started=True
            )
        )
        self.assertIn("Do not retry automatically", message)
        self.assertIn("post_write_readback", message)

    def test_conversion_and_renderer_summaries_are_explicitly_offline(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "notes.txt"
            source.write_text("hello\nworld", encoding="utf-8")
            document = load_utf8_text_document(
                source, layout=PageLayout(columns=5, lines_per_page=1)
            )
            report = format_offline_conversion_report(document)
            self.assertIn("OFFLINE TEXT CONVERSION", report)
            self.assertIn("Device accessed: no", report)
            self.assertIn("Candidate device bytes included: no", report)
            page = format_offline_page_preview(document, 1)
            self.assertIn("Page 1 / 2", page)
            self.assertIn("hello", page)


if __name__ == "__main__":
    unittest.main()
