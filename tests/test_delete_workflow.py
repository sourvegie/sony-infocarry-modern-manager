from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.delete_generalized import build_generalized_delete_candidate
from infocarry.delete_workflow import (
    GuardedGeneralizedDeleteWorkflow,
    GeneralizedDeleteWorkflowError,
)
from infocarry.protocol import TransferCancelledError, TransferTimeoutError
from infocarry.write_protocol import WriteFailureAssessment

try:
    from test_new_txt import _make_root_blob, _write_archive
except ModuleNotFoundError:
    from tests.test_new_txt import _make_root_blob, _write_archive


class CaptureSequence:
    def __init__(self, baseline_blob, candidate, now):
        self.baseline_blob = baseline_blob
        self.candidate = candidate
        self.now = now
        self.calls = 0

    def __call__(self, destination, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            fixed = {command: bytes(64) for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
            _write_archive(destination, self.baseline_blob, self.now, fixed_state=fixed)
            return
        fixed = dict(
            zip((0x001B, 0x001C, 0x001D, 0x001E, 0x001F), self.candidate.fixed_state.after)
        )
        _write_archive(destination, self.candidate.candidate_blob, self.now, fixed_state=fixed)


class DeleteWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 25, tzinfo=timezone.utc)

    def _case(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        baseline_blob = _make_root_blob(b"source\r\n")
        reference = _write_archive(
            root / "reference",
            baseline_blob,
            self.now,
            fixed_state={command: bytes(64) for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)},
        )
        candidate = build_generalized_delete_candidate(
            reference,
            "root\\source.txt",
            0xC0,
            now=self.now,
            max_age_seconds=None,
        )
        return temporary, root, baseline_blob, candidate

    def test_success_runs_capture_send_and_readback_once(self):
        temporary, root, baseline_blob, candidate = self._case()
        self.addCleanup(temporary.cleanup)
        capture = CaptureSequence(baseline_blob, candidate, self.now)
        sends = []

        def send(transaction, binding, **_kwargs):
            sends.append((transaction, binding))
            return 0

        result = GuardedGeneralizedDeleteWorkflow(capture, send).run(
            backup_destination=root / "before",
            post_delete_destination=root / "after",
            target_path="root\\source.txt",
            target_record_offset=0xC0,
            confirmation="DELETE ONE INFOCARRY ITEM",
            fake_transport=True,
            now=self.now,
            max_age_seconds=None,
        )
        self.assertEqual(capture.calls, 2)
        self.assertEqual(len(sends), 1)
        self.assertEqual(result.completion, 0)
        self.assertEqual(result.audit["workflow"]["device_change"], "simulated_only")

    def test_prestart_cancellation_does_not_capture_or_send(self):
        temporary, root, _baseline_blob, _candidate = self._case()
        self.addCleanup(temporary.cleanup)
        calls = []
        workflow = GuardedGeneralizedDeleteWorkflow(
            lambda *args, **kwargs: calls.append((args, kwargs)),
            lambda *args, **kwargs: calls.append((args, kwargs)),
        )
        with self.assertRaises(GeneralizedDeleteWorkflowError) as raised:
            workflow.run(
                backup_destination=root / "before",
                post_delete_destination=root / "after",
                target_path="root\\source.txt",
                target_record_offset=0xC0,
                confirmation="DELETE ONE INFOCARRY ITEM",
                fake_transport=True,
                cancelled=lambda: True,
                now=self.now,
                max_age_seconds=None,
            )
        self.assertEqual(raised.exception.state, "cancelled_before_transaction")
        self.assertEqual(calls, [])

    def test_disconnect_timeout_cancellation_and_nonzero_completion_are_terminal(self):
        for label, failure in (
            ("disconnect", OSError("disconnect")),
            ("timeout", TransferTimeoutError("timeout")),
            ("cancel", TransferCancelledError("cancel")),
        ):
            with self.subTest(label=label):
                temporary, root, baseline_blob, candidate = self._case()
                self.addCleanup(temporary.cleanup)
                capture = CaptureSequence(baseline_blob, candidate, self.now)
                sends = []

                def send(_transaction, _binding, error=failure, **_kwargs):
                    sends.append(True)
                    raise error

                with self.assertRaises(GeneralizedDeleteWorkflowError) as raised:
                    GuardedGeneralizedDeleteWorkflow(capture, send).run(
                        backup_destination=root / "before",
                        post_delete_destination=root / "after",
                        target_path="root\\source.txt",
                        target_record_offset=0xC0,
                        confirmation="DELETE ONE INFOCARRY ITEM",
                        fake_transport=True,
                        now=self.now,
                        max_age_seconds=None,
                    )
                self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
                self.assertTrue(raised.exception.write_started)
                self.assertEqual(len(sends), 1)

        temporary, root, baseline_blob, candidate = self._case()
        self.addCleanup(temporary.cleanup)
        capture = CaptureSequence(baseline_blob, candidate, self.now)
        with self.assertRaises(GeneralizedDeleteWorkflowError) as raised:
            GuardedGeneralizedDeleteWorkflow(capture, lambda *_args, **_kwargs: 1).run(
                backup_destination=root / "before",
                post_delete_destination=root / "after",
                target_path="root\\source.txt",
                target_record_offset=0xC0,
                confirmation="DELETE ONE INFOCARRY ITEM",
                fake_transport=True,
                now=self.now,
                max_age_seconds=None,
            )
        self.assertEqual(raised.exception.stage, "write")
        self.assertFalse(raised.exception.audit["automatic_retry_allowed"])

    def test_malformed_completion_and_readback_mismatch_never_retry(self):
        temporary, root, baseline_blob, candidate = self._case()
        self.addCleanup(temporary.cleanup)
        capture = CaptureSequence(baseline_blob, candidate, self.now)
        with self.assertRaises(GeneralizedDeleteWorkflowError) as raised:
            GuardedGeneralizedDeleteWorkflow(capture, lambda *_args, **_kwargs: None).run(
                backup_destination=root / "before",
                post_delete_destination=root / "after",
                target_path="root\\source.txt",
                target_record_offset=0xC0,
                confirmation="DELETE ONE INFOCARRY ITEM",
                fake_transport=True,
                now=self.now,
                max_age_seconds=None,
            )
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertEqual(capture.calls, 1)

        temporary2, root2, baseline_blob2, candidate2 = self._case()
        self.addCleanup(temporary2.cleanup)

        class MismatchCapture(CaptureSequence):
            def __call__(self, destination, **kwargs):
                if self.calls == 0:
                    super().__call__(destination, **kwargs)
                    return
                self.calls += 1
                _write_archive(
                    destination,
                    self.baseline_blob,
                    self.now,
                    fixed_state={command: bytes(64) for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)},
                )

        mismatch = MismatchCapture(baseline_blob2, candidate2, self.now)
        with self.assertRaises(GeneralizedDeleteWorkflowError) as raised:
            GuardedGeneralizedDeleteWorkflow(mismatch, lambda *_args, **_kwargs: 0).run(
                backup_destination=root2 / "before",
                post_delete_destination=root2 / "after",
                target_path="root\\source.txt",
                target_record_offset=0xC0,
                confirmation="DELETE ONE INFOCARRY ITEM",
                fake_transport=True,
                now=self.now,
                max_age_seconds=None,
            )
        self.assertEqual(raised.exception.stage, "post_delete_readback")
        self.assertFalse(raised.exception.audit["automatic_retry_allowed"])


if __name__ == "__main__":
    unittest.main()
