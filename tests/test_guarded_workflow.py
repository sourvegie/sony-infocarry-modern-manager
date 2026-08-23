import hashlib
from pathlib import Path
import tempfile
import unittest

from infocarry.backup import BackupObjectSpec, RawBackupArchive
from infocarry.text_authoring import preview_decoded_text_replacement
from infocarry.protocol import TransferCancelledError
from infocarry.guarded_workflow import (
    ExistingTextReplacementWorkflow,
    GuardedWorkflowError,
)

try:
    from test_backup_format import make_text_blob
except ModuleNotFoundError:
    from tests.test_backup_format import make_text_blob


def _make_archive(destination: Path, blob: bytes) -> None:
    archive = RawBackupArchive.create(destination)
    archive.save(BackupObjectSpec(0x0024, "response-0024"), bytes(64))
    for command in range(0x001B, 0x0020):
        archive.save(BackupObjectSpec(command, f"response-{command:04x}"), bytes(64))
    probe = bytearray(64)
    probe[0x38:0x3C] = len(blob).to_bytes(4, "big")
    archive.save(BackupObjectSpec(0x8004, "backup-blob-probe"), bytes(probe))
    archive.save(BackupObjectSpec(0x8004, "backup-blob", len(blob)), blob)
    archive.finalize()


def _preview(blob: bytes, source_path: Path):
    report = preview_decoded_text_replacement(blob, 0xC0, "new text\n")
    report["workflow"] = {
        "source_backup_blob_sha256": hashlib.sha256(blob).hexdigest(),
        "input_path": str(source_path.resolve()),
        "target_record_offset": report["target"]["record_offset_hex"],
        "target_path": "root\\memo.txt",
        "device_accessed": False,
        "candidate_bytes_included": False,
    }
    return report


class GuardedWorkflowTests(unittest.TestCase):
    def test_runs_backup_authorize_send_once_and_full_readback(self):
        before_blob = make_text_blob(b"old text\r\n")
        current_blob = [before_blob]
        capture_calls = []
        send_calls = []

        def capture(destination, *, cancelled, progress):
            capture_calls.append(destination)
            _make_archive(destination, current_blob[0])

        def send(transaction, authorization, *, cancelled, progress):
            send_calls.append((transaction, authorization))
            current_blob[0] = transaction.ranges[4] + transaction.ranges[7]
            return 0

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            workflow = ExistingTextReplacementWorkflow(capture, send)
            result = workflow.run(
                backup_destination=root / "before",
                post_write_destination=root / "after",
                preview_report=_preview(before_blob, source),
                text_path=source,
                cli_write_flag=True,
                confirmation="REPLACE INFOCARRY TEXT",
            )

        self.assertEqual(len(capture_calls), 2)
        self.assertEqual(len(send_calls), 1)
        self.assertEqual(result.completion, 0)
        self.assertTrue(result.verification.fixed_state_matches)
        self.assertTrue(result.verification.dynamic_blob_matches)
        self.assertTrue(result.verification.unrelated_objects_unchanged)
        self.assertFalse(result.authorization.to_dict()["usb_transmission_performed"])

    def test_wrong_phrase_stops_before_send(self):
        before_blob = make_text_blob(b"old text\r\n")
        send_calls = []

        def capture(destination, *, cancelled, progress):
            _make_archive(destination, before_blob)

        def send(*args, **kwargs):
            send_calls.append(True)
            return 0

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            with self.assertRaisesRegex(GuardedWorkflowError, "confirmation phrase"):
                ExistingTextReplacementWorkflow(capture, send).run(
                    backup_destination=root / "before",
                    post_write_destination=root / "after",
                    preview_report=_preview(before_blob, source),
                    text_path=source,
                    cli_write_flag=True,
                    confirmation="WRITE INFOCARRY",
                )
        self.assertEqual(send_calls, [])

    def test_cancellation_after_backup_stops_before_send(self):
        before_blob = make_text_blob(b"old text\r\n")
        send_calls = []
        checks = iter((False, True))

        def capture(destination, *, cancelled, progress):
            _make_archive(destination, before_blob)

        def send(*args, **kwargs):
            send_calls.append(True)
            return 0

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            with self.assertRaises(TransferCancelledError):
                ExistingTextReplacementWorkflow(capture, send).run(
                    backup_destination=root / "before",
                    post_write_destination=root / "after",
                    preview_report=_preview(before_blob, source),
                    text_path=source,
                    cli_write_flag=True,
                    confirmation="REPLACE INFOCARRY TEXT",
                    cancelled=lambda: next(checks, True),
                )
        self.assertEqual(send_calls, [])

    def test_failed_readback_is_terminal_and_does_not_retry(self):
        before_blob = make_text_blob(b"old text\r\n")
        current_blob = [before_blob]
        send_calls = []

        def capture(destination, *, cancelled, progress):
            _make_archive(destination, current_blob[0])

        def send(transaction, authorization, *, cancelled, progress):
            send_calls.append(True)
            current_blob[0] = make_text_blob(b"unexpected\r\n")
            return 0

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            with self.assertRaisesRegex(GuardedWorkflowError, "do not retry") as raised:
                ExistingTextReplacementWorkflow(capture, send).run(
                    backup_destination=root / "before",
                    post_write_destination=root / "after",
                    preview_report=_preview(before_blob, source),
                    text_path=source,
                    cli_write_flag=True,
                    confirmation="REPLACE INFOCARRY TEXT",
                )
        self.assertEqual(raised.exception.stage, "post_write_readback")
        self.assertTrue(raised.exception.write_started)
        self.assertEqual(len(send_calls), 1)


if __name__ == "__main__":
    unittest.main()
