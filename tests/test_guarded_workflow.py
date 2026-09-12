import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from infocarry.backup import BackupObjectSpec, RawBackupArchive
from infocarry.text_authoring import preview_decoded_text_replacement
from infocarry.protocol import TransferCancelledError
from infocarry.execution_claim_store import PersistentExecutionClaimStore
from infocarry.guarded_workflow import (
    ExistingTextReplacementWorkflow,
    GuardedWorkflowError,
)
from infocarry.indeterminate_write_lock import PersistentIndeterminateWriteLock
from infocarry.write_safety_boundary import PersistentWriteSafetyOwner
from infocarry.write_protocol import WriteFailureAssessment

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


def _make_stale_archive(destination: Path, blob: bytes) -> None:
    _make_archive(destination, blob)
    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["created_at_utc"] = "2000-01-01T00:00:00+00:00"
    manifest["updated_at_utc"] = "2000-01-01T00:00:00+00:00"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _safety_owner(root: Path) -> PersistentWriteSafetyOwner:
    return PersistentWriteSafetyOwner(
        execution_claim_store=PersistentExecutionClaimStore(
            root / "installation-state" / "execution-claims.sqlite3"
        ),
        indeterminate_write_lock=PersistentIndeterminateWriteLock(
            root / "installation-state" / "indeterminate-write-lock.json"
        ),
    )


class GuardedWorkflowTests(unittest.TestCase):
    @staticmethod
    def _claim_count(owner: PersistentWriteSafetyOwner) -> int:
        connection = sqlite3.connect(owner.execution_claim_store.path)
        try:
            return connection.execute("SELECT COUNT(*) FROM execution_claims").fetchone()[0]
        finally:
            connection.close()

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
            owner = _safety_owner(root)
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            workflow = ExistingTextReplacementWorkflow(capture, send, owner)
            result = workflow.run(
                backup_destination=root / "before",
                post_write_destination=root / "after",
                preview_report=_preview(before_blob, source),
                text_path=source,
                cli_write_flag=True,
                confirmation="REPLACE INFOCARRY TEXT",
            )
            self.assertEqual(self._claim_count(owner), 1)
            self.assertIsNone(owner.execution_claim_store.read_sender_in_flight())
            self.assertIsNone(owner.indeterminate_write_lock.read())

        self.assertEqual(len(capture_calls), 2)
        self.assertEqual(len(send_calls), 1)
        self.assertEqual(result.completion, 0)
        self.assertTrue(result.verification.fixed_state_matches)
        self.assertTrue(result.verification.dynamic_blob_matches)
        self.assertTrue(result.verification.unrelated_objects_unchanged)
        self.assertFalse(result.authorization.to_dict()["usb_transmission_performed"])

    def test_missing_safety_owner_fails_closed_before_capture_or_sender(self):
        capture_calls = []
        send_calls = []

        def capture(*args, **kwargs):
            capture_calls.append(True)

        def send(*args, **kwargs):
            send_calls.append(True)
            return 0

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            with self.assertRaisesRegex(GuardedWorkflowError, "requires the shared"):
                ExistingTextReplacementWorkflow(capture, send).run(
                    backup_destination=root / "before",
                    post_write_destination=root / "after",
                    preview_report={},
                    text_path=source,
                    cli_write_flag=True,
                    confirmation="REPLACE INFOCARRY TEXT",
                )
        self.assertEqual(capture_calls, [])
        self.assertEqual(send_calls, [])

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
            owner = _safety_owner(root)
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            with self.assertRaisesRegex(GuardedWorkflowError, "confirmation phrase"):
                ExistingTextReplacementWorkflow(capture, send, owner).run(
                    backup_destination=root / "before",
                    post_write_destination=root / "after",
                    preview_report=_preview(before_blob, source),
                    text_path=source,
                    cli_write_flag=True,
                    confirmation="WRITE INFOCARRY",
                )
            self.assertEqual(self._claim_count(owner), 0)
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
            owner = _safety_owner(root)
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            with self.assertRaises(TransferCancelledError):
                ExistingTextReplacementWorkflow(capture, send, owner).run(
                    backup_destination=root / "before",
                    post_write_destination=root / "after",
                    preview_report=_preview(before_blob, source),
                    text_path=source,
                    cli_write_flag=True,
                    confirmation="REPLACE INFOCARRY TEXT",
                    cancelled=lambda: next(checks, True),
                )
            self.assertEqual(self._claim_count(owner), 0)
        self.assertEqual(send_calls, [])

    def test_stale_fresh_backup_stops_before_claim_or_send(self):
        before_blob = make_text_blob(b"old text\r\n")
        capture_calls = []
        send_calls = []

        def capture(destination, *, cancelled, progress):
            capture_calls.append(destination)
            _make_stale_archive(destination, before_blob)

        def send(*args, **kwargs):
            send_calls.append(True)
            return 0

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = _safety_owner(root)
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            with self.assertRaisesRegex(GuardedWorkflowError, "fresh backup failed"):
                ExistingTextReplacementWorkflow(capture, send, owner).run(
                    backup_destination=root / "before",
                    post_write_destination=root / "after",
                    preview_report=_preview(before_blob, source),
                    text_path=source,
                    cli_write_flag=True,
                    confirmation="REPLACE INFOCARRY TEXT",
                )
            self.assertEqual(self._claim_count(owner), 0)
        self.assertEqual(len(capture_calls), 1)
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
                ExistingTextReplacementWorkflow(capture, send, _safety_owner(root)).run(
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

    def test_active_global_lock_blocks_before_backup_or_sender(self):
        before_blob = make_text_blob(b"old text\r\n")
        capture_calls = []
        send_calls = []

        def capture(destination, *, cancelled, progress):
            capture_calls.append(destination)
            _make_archive(destination, before_blob)

        def send(*args, **kwargs):
            send_calls.append(True)
            return 0

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = _safety_owner(root)
            owner.indeterminate_write_lock.record_indeterminate(
                reason="prior ambiguous write",
                evidence_root=str(root),
                model_key=owner.device_model_profile.lock_key,
                incident_id="incident-prior",
                attempt_id="attempt-prior",
            )
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            with self.assertRaisesRegex(GuardedWorkflowError, "globally locked"):
                ExistingTextReplacementWorkflow(capture, send, owner).run(
                    backup_destination=root / "before",
                    post_write_destination=root / "after",
                    preview_report=_preview(before_blob, source),
                    text_path=source,
                    cli_write_flag=True,
                    confirmation="REPLACE INFOCARRY TEXT",
                )
            self.assertEqual(capture_calls, [])
            self.assertEqual(send_calls, [])
            self.assertEqual(self._claim_count(owner), 0)

    def test_active_sender_marker_blocks_and_promotes_global_lock(self):
        before_blob = make_text_blob(b"old text\r\n")
        capture_calls = []
        send_calls = []

        def capture(destination, *, cancelled, progress):
            capture_calls.append(destination)
            _make_archive(destination, before_blob)

        def send(*args, **kwargs):
            send_calls.append(True)
            return 0

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = _safety_owner(root)
            claim = owner.consume_execution_claim(
                {
                    "preflight_seal_sha256": "a" * 64,
                    "core_preflight_seal_sha256": "b" * 64,
                    "candidate_blob_sha256": "c" * 64,
                    "transaction_sha256": "d" * 64,
                    "authorization_sha256": "e" * 64,
                    "baseline_state_identity_sha256": "f" * 64,
                    "capacity_response_sha256": "0" * 64,
                }
            )
            owner.mark_sender_start(
                claim,
                attempt_id="attempt-active",
                evidence_root=str(root),
                operation_label="guarded-replacement",
            )
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            with self.assertRaisesRegex(GuardedWorkflowError, "globally locked"):
                ExistingTextReplacementWorkflow(capture, send, owner).run(
                    backup_destination=root / "before",
                    post_write_destination=root / "after",
                    preview_report=_preview(before_blob, source),
                    text_path=source,
                    cli_write_flag=True,
                    confirmation="REPLACE INFOCARRY TEXT",
                )
            self.assertEqual(capture_calls, [])
            self.assertEqual(send_calls, [])
            marker = owner.execution_claim_store.read_sender_in_flight()
            self.assertIsNotNone(marker)
            self.assertEqual(marker.state, "lock_recorded")
            self.assertIsNotNone(owner.indeterminate_write_lock.read())

    def test_corrupt_claim_store_blocks_before_backup_or_sender(self):
        before_blob = make_text_blob(b"old text\r\n")
        capture_calls = []
        send_calls = []

        def capture(destination, *, cancelled, progress):
            capture_calls.append(destination)
            _make_archive(destination, before_blob)

        def send(*args, **kwargs):
            send_calls.append(True)
            return 0

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = _safety_owner(root)
            owner.execution_claim_store.path.write_bytes(b"corrupt claim store")
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            with self.assertRaisesRegex(GuardedWorkflowError, "write safety"):
                ExistingTextReplacementWorkflow(capture, send, owner).run(
                    backup_destination=root / "before",
                    post_write_destination=root / "after",
                    preview_report=_preview(before_blob, source),
                    text_path=source,
                    cli_write_flag=True,
                    confirmation="REPLACE INFOCARRY TEXT",
                )
            self.assertEqual(capture_calls, [])
            self.assertEqual(send_calls, [])

    def test_started_indeterminate_send_persists_lock_and_marker_without_retry(self):
        before_blob = make_text_blob(b"old text\r\n")
        send_calls = []

        def capture(destination, *, cancelled, progress):
            _make_archive(destination, before_blob)

        def send(*args, **kwargs):
            send_calls.append(True)
            error = OSError("simulated disconnect after sender start")
            error.write_failure_assessment = WriteFailureAssessment(
                primary_error=str(error),
                write_started=True,
                device_outcome="indeterminate",
            )
            raise error

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = _safety_owner(root)
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            with self.assertRaisesRegex(GuardedWorkflowError, "do not retry") as raised:
                ExistingTextReplacementWorkflow(capture, send, owner).run(
                    backup_destination=root / "before",
                    post_write_destination=root / "after",
                    preview_report=_preview(before_blob, source),
                    text_path=source,
                    cli_write_flag=True,
                    confirmation="REPLACE INFOCARRY TEXT",
                )
            self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
            self.assertEqual(len(send_calls), 1)
            self.assertEqual(self._claim_count(owner), 1)
            self.assertIsNotNone(owner.indeterminate_write_lock.read())
            marker = owner.execution_claim_store.read_sender_in_flight()
            self.assertIsNotNone(marker)
            self.assertEqual(marker.state, "lock_recorded")

    def test_determinate_prestart_sender_failure_closes_marker_without_global_incident(self):
        before_blob = make_text_blob(b"old text\r\n")
        send_calls = []

        def capture(destination, *, cancelled, progress):
            _make_archive(destination, before_blob)

        def send(*args, **kwargs):
            send_calls.append(True)
            raise TransferCancelledError("cancelled before request 0x02")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = _safety_owner(root)
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            with self.assertRaises(GuardedWorkflowError) as raised:
                ExistingTextReplacementWorkflow(capture, send, owner).run(
                    backup_destination=root / "before",
                    post_write_destination=root / "after",
                    preview_report=_preview(before_blob, source),
                    text_path=source,
                    cli_write_flag=True,
                    confirmation="REPLACE INFOCARRY TEXT",
                )
            self.assertEqual(raised.exception.state, "failed")
            self.assertFalse(raised.exception.write_started)
            self.assertEqual(len(send_calls), 1)
            self.assertEqual(self._claim_count(owner), 1)
            self.assertIsNone(owner.execution_claim_store.read_sender_in_flight())
            self.assertIsNone(owner.indeterminate_write_lock.read())

    def test_replay_of_consumed_replacement_operation_is_rejected(self):
        before_blob = make_text_blob(b"old text\r\n")
        transaction_holder = {"transaction": None}
        send_calls = []

        def capture(destination, *, cancelled, progress):
            transaction = transaction_holder["transaction"]
            blob = (
                before_blob
                if Path(destination).name.startswith("before") or transaction is None
                else transaction.ranges[4] + transaction.ranges[7]
            )
            _make_archive(destination, blob)

        def send(transaction, authorization, *, cancelled, progress):
            send_calls.append(True)
            transaction_holder["transaction"] = transaction
            return 0

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = _safety_owner(root)
            source = root / "replacement.txt"
            source.write_text("new text\n", encoding="utf-8")
            workflow = ExistingTextReplacementWorkflow(capture, send, owner)
            workflow.run(
                backup_destination=root / "before-1",
                post_write_destination=root / "after-1",
                preview_report=_preview(before_blob, source),
                text_path=source,
                cli_write_flag=True,
                confirmation="REPLACE INFOCARRY TEXT",
            )
            with self.assertRaisesRegex(GuardedWorkflowError, "already consumed"):
                workflow.run(
                    backup_destination=root / "before-2",
                    post_write_destination=root / "after-2",
                    preview_report=_preview(before_blob, source),
                    text_path=source,
                    cli_write_flag=True,
                    confirmation="REPLACE INFOCARRY TEXT",
                )
            self.assertEqual(len(send_calls), 1)
            self.assertEqual(self._claim_count(owner), 1)


if __name__ == "__main__":
    unittest.main()
