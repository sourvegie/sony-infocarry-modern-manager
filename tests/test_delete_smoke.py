from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from infocarry.delete_smoke import (
    DELETE_SMOKE_OWNER_APPROVAL,
    DeleteSmokeDeviceIdentity,
    DeleteSmokeError,
    DeleteSmokeExecutionError,
    build_delete_smoke_preflight,
    create_delete_smoke_session,
    list_eligible_delete_targets,
    run_delete_smoke,
    seal_delete_smoke_preflight,
    verify_sealed_delete_smoke_preflight,
)
from infocarry.write_protocol import WriteFailureAssessment
from infocarry.write_gate import verify_fresh_backup

try:
    from test_new_txt import _make_root_blob, _write_archive
except ModuleNotFoundError:
    from tests.test_new_txt import _make_root_blob, _write_archive


class _OneShotSender:
    def __init__(self, completion=0):
        self.completion = completion
        self.calls = 0

    def send(self, _transaction, _authorization, **_kwargs):
        self.calls += 1
        return self.completion


class DeleteSmokeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 26, tzinfo=timezone.utc)
        self.device = DeleteSmokeDeviceIdentity(0x054C, 0x001E, bus=2, address=3)

    def _case(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        fixed = {command: bytes(64) for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
        backup_path = _write_archive(
            root / "before",
            _make_root_blob(b"source\r\n"),
            self.now,
            fixed_state=fixed,
        )
        backup = verify_fresh_backup(backup_path, now=self.now, max_age_seconds=None)
        return temporary, root, backup

    def _preflight(self):
        temporary, root, backup = self._case()
        preflight = build_delete_smoke_preflight(
            backup,
            self.device,
            target_path="root\\source.txt",
            target_record_offset=0xC0,
            now=self.now,
            max_age_seconds=None,
        )
        return temporary, root, preflight

    def test_listing_is_explicit_and_contains_only_eligible_root_txt(self):
        temporary, _root, backup = self._case()
        self.addCleanup(temporary.cleanup)
        targets = list_eligible_delete_targets(backup, now=self.now, max_age_seconds=None)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].path, "root\\source.txt")
        self.assertEqual(targets[0].record_offset, 0xC0)
        self.assertEqual(targets[0].read_state, "unread")
        self.assertEqual(targets[0].parent_path, "root")

    def test_session_skeleton_is_new_and_non_overwriting(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        session = create_delete_smoke_session(Path(temporary.name) / "session")
        self.assertTrue((session / "pre-delete-backup").is_dir())
        with self.assertRaises(DeleteSmokeError):
            create_delete_smoke_session(session)

    def test_sealed_artifact_contains_hashes_not_candidate_bytes_and_cannot_be_replaced(self):
        temporary, root, preflight = self._preflight()
        self.addCleanup(temporary.cleanup)
        sealed = seal_delete_smoke_preflight(preflight, root / "derived" / "preflight.json")
        verify_sealed_delete_smoke_preflight(sealed)
        document = json.loads(sealed.artifact_path.read_text(encoding="utf-8"))
        encoded = sealed.artifact_path.read_text(encoding="utf-8")
        self.assertEqual(document["preflight"]["target"]["path"], "root\\source.txt")
        self.assertEqual(
            document["preflight"]["candidate"]["dynamic_blob_sha256"],
            preflight.candidate.candidate_blob_sha256,
        )
        self.assertNotIn(preflight.candidate.candidate_blob.hex(), encoded)
        with self.assertRaises(DeleteSmokeError):
            seal_delete_smoke_preflight(preflight, sealed.artifact_path)

    def test_tampered_sealed_artifact_is_rejected_before_any_callback(self):
        temporary, root, preflight = self._preflight()
        self.addCleanup(temporary.cleanup)
        sealed = seal_delete_smoke_preflight(preflight, root / "preflight.json")
        document = json.loads(sealed.artifact_path.read_text(encoding="utf-8"))
        document["preflight"]["target"]["path"] = "root\\other.txt"
        sealed.artifact_path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(DeleteSmokeError):
            verify_sealed_delete_smoke_preflight(sealed)

    def test_execute_requires_sealed_preflight_before_detector_capture_or_sender(self):
        temporary, root, preflight = self._preflight()
        self.addCleanup(temporary.cleanup)
        sender = _OneShotSender()
        with self.assertRaises(DeleteSmokeExecutionError) as raised:
            run_delete_smoke(
                preflight=preflight,
                post_delete_destination=root / "after",
                detect_device=lambda: (_ for _ in ()).throw(AssertionError("detector called")),
                capture=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("capture called")),
                sender=sender,
                owner_approval=DELETE_SMOKE_OWNER_APPROVAL,
                confirmation="DELETE ONE INFOCARRY ITEM",
                now=self.now,
                max_age_seconds=None,
            )
        self.assertEqual(raised.exception.stage, "sealed_preflight")
        self.assertEqual(sender.calls, 0)

    def test_fake_execution_revalidates_seal_and_sends_once_then_verifies_readback(self):
        temporary, root, preflight = self._preflight()
        self.addCleanup(temporary.cleanup)
        sealed = seal_delete_smoke_preflight(preflight, root / "preflight.json")
        sender = _OneShotSender()

        def capture(destination, **_kwargs):
            fixed = dict(
                zip(
                    (0x001B, 0x001C, 0x001D, 0x001E, 0x001F),
                    preflight.candidate.fixed_state.after,
                )
            )
            _write_archive(destination, preflight.candidate.candidate_blob, self.now, fixed_state=fixed)

        result = run_delete_smoke(
            preflight=sealed,
            post_delete_destination=root / "after",
            detect_device=lambda: self.device,
            capture=capture,
            sender=sender,
            owner_approval=DELETE_SMOKE_OWNER_APPROVAL,
            confirmation="DELETE ONE INFOCARRY ITEM",
            now=self.now,
            max_age_seconds=None,
        )
        self.assertEqual(result.completion, 0)
        self.assertTrue(result.verification.target_removed)
        self.assertTrue(result.audit["live_transaction_performed"])
        self.assertEqual(sender.calls, 1)

    def test_nonzero_completion_is_terminal_and_never_retried(self):
        temporary, root, preflight = self._preflight()
        self.addCleanup(temporary.cleanup)
        sealed = seal_delete_smoke_preflight(preflight, root / "preflight.json")
        sender = _OneShotSender(completion=1)
        with self.assertRaises(DeleteSmokeExecutionError) as raised:
            run_delete_smoke(
                preflight=sealed,
                post_delete_destination=root / "after",
                detect_device=lambda: self.device,
                capture=lambda *_args, **_kwargs: self.fail("post-readback must not occur"),
                sender=sender,
                owner_approval=DELETE_SMOKE_OWNER_APPROVAL,
                confirmation="DELETE ONE INFOCARRY ITEM",
                now=self.now,
                max_age_seconds=None,
            )
        self.assertEqual(raised.exception.stage, "write_completion")
        self.assertTrue(raised.exception.write_started)
        self.assertFalse(raised.exception.audit["automatic_retry_allowed"])
        self.assertEqual(sender.calls, 1)

    def test_wrong_device_and_pre_start_cancellation_do_not_reach_sender(self):
        temporary, root, preflight = self._preflight()
        self.addCleanup(temporary.cleanup)
        sealed = seal_delete_smoke_preflight(preflight, root / "preflight.json")
        sender = _OneShotSender()
        with self.assertRaises(DeleteSmokeExecutionError) as wrong_device:
            run_delete_smoke(
                preflight=sealed,
                post_delete_destination=root / "wrong-after",
                detect_device=lambda: DeleteSmokeDeviceIdentity(0x054C, 0x001E, bus=8, address=9),
                capture=lambda *_args, **_kwargs: self.fail("capture must not run"),
                sender=sender,
                owner_approval=DELETE_SMOKE_OWNER_APPROVAL,
                confirmation="DELETE ONE INFOCARRY ITEM",
                now=self.now,
                max_age_seconds=None,
            )
        self.assertEqual(wrong_device.exception.stage, "preflight_revalidation")
        self.assertEqual(sender.calls, 0)

        with self.assertRaises(DeleteSmokeExecutionError) as cancelled:
            run_delete_smoke(
                preflight=sealed,
                post_delete_destination=root / "cancelled-after",
                detect_device=lambda: self.fail("detector must not run"),
                capture=lambda *_args, **_kwargs: self.fail("capture must not run"),
                sender=sender,
                owner_approval=DELETE_SMOKE_OWNER_APPROVAL,
                confirmation="DELETE ONE INFOCARRY ITEM",
                cancelled=lambda: True,
                now=self.now,
                max_age_seconds=None,
            )
        self.assertEqual(cancelled.exception.state, "cancelled_before_transaction")
        self.assertEqual(sender.calls, 0)

    def test_sender_failure_after_start_is_indeterminate_and_not_retried(self):
        temporary, root, preflight = self._preflight()
        self.addCleanup(temporary.cleanup)
        sealed = seal_delete_smoke_preflight(preflight, root / "preflight.json")

        class StartedFailureSender:
            calls = 0

            def send(self, _transaction, _authorization, **_kwargs):
                self.calls += 1
                error = TimeoutError("simulated timeout")
                error.write_failure_assessment = WriteFailureAssessment(
                    primary_error="simulated timeout",
                    write_started=True,
                    device_outcome="indeterminate",
                )
                raise error

        sender = StartedFailureSender()
        with self.assertRaises(DeleteSmokeExecutionError) as raised:
            run_delete_smoke(
                preflight=sealed,
                post_delete_destination=root / "after",
                detect_device=lambda: self.device,
                capture=lambda *_args, **_kwargs: self.fail("post-readback must not run"),
                sender=sender,
                owner_approval=DELETE_SMOKE_OWNER_APPROVAL,
                confirmation="DELETE ONE INFOCARRY ITEM",
                now=self.now,
                max_age_seconds=None,
            )
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertTrue(raised.exception.write_started)
        self.assertEqual(sender.calls, 1)

    def test_readback_mismatch_is_terminal_after_one_send(self):
        temporary, root, preflight = self._preflight()
        self.addCleanup(temporary.cleanup)
        sealed = seal_delete_smoke_preflight(preflight, root / "preflight.json")
        sender = _OneShotSender()

        def capture(destination, **_kwargs):
            _write_archive(destination, preflight.candidate.baseline.data, self.now)

        with self.assertRaises(DeleteSmokeExecutionError) as raised:
            run_delete_smoke(
                preflight=sealed,
                post_delete_destination=root / "after",
                detect_device=lambda: self.device,
                capture=capture,
                sender=sender,
                owner_approval=DELETE_SMOKE_OWNER_APPROVAL,
                confirmation="DELETE ONE INFOCARRY ITEM",
                now=self.now,
                max_age_seconds=None,
            )
        self.assertEqual(raised.exception.stage, "post_delete_readback")
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertEqual(sender.calls, 1)

    def test_runner_is_not_exposed_by_normal_cli_or_gui(self):
        package_root = Path(__file__).parents[1] / "src" / "infocarry"
        for filename in ("cli.py", "desktop.py", "desktop_ttk.py", "__init__.py"):
            with self.subTest(filename=filename):
                source = (package_root / filename).read_text(encoding="utf-8")
                self.assertNotIn("delete_smoke", source)


if __name__ == "__main__":
    unittest.main()
