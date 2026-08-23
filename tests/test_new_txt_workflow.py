from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.new_txt_gate import NEW_ROOT_TXT_CONFIRMATION_PHRASE
from infocarry.new_txt_workflow import (
    GuardedNewTxtWorkflow,
    NewTxtWorkflowError,
    build_new_txt_preview,
)
from infocarry.protocol import TransferCancelledError
from infocarry.write_protocol import (
    AuthorizedWriteSender,
    REQUEST_COMPLETION,
    REQUEST_TRANSFER_STATE,
    WriteProtocolError,
)

try:
    from test_new_txt import _make_root_blob, _write_archive
except ModuleNotFoundError:
    from tests.test_new_txt import _make_root_blob, _write_archive


class WorkflowBackend:
    def __init__(self, *, fail_bulk_at=None, completion=(0,)):
        self.calls = []
        self.fail_bulk_at = fail_bulk_at
        self.completion = list(completion)

    def control_out(self, request_type, request, value, index, data, timeout_ms):
        self.calls.append(("control_out", request, bytes(data)))
        return len(data)

    def control_in(self, request_type, request, value, index, length, timeout_ms):
        self.calls.append(("control_in", request))
        if request == REQUEST_TRANSFER_STATE:
            return b"\x00\x00"
        if request == REQUEST_COMPLETION:
            value = self.completion.pop(0) if self.completion else 0
            return value.to_bytes(2, "little")
        raise AssertionError(request)

    def bulk_write(self, endpoint, data, timeout_ms):
        self.calls.append(("bulk_write", bytes(data)))
        count = sum(call[0] == "bulk_write" for call in self.calls)
        if self.fail_bulk_at is not None and count == self.fail_bulk_at:
            raise OSError("simulated workflow disconnect")
        return len(data)


class NewTxtWorkflowTests(unittest.TestCase):
    def _setup(self, *, backend=None):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        baseline_blob = _make_root_blob()
        preview_backup = _write_archive(root / "preview-baseline", baseline_blob, now)
        source = root / "source.txt"
        source.write_text("new text\n", encoding="utf-8")
        backend = backend or WorkflowBackend()
        current = {"blob": baseline_blob, "fixed": None, "after_mode": "normal"}
        send_calls = []

        def capture(destination, *, cancelled, progress):
            if destination.name == "after":
                if current["after_mode"] == "malformed":
                    _write_archive(
                        destination,
                        current["blob"][:-4] + b"BAD!",
                        now,
                        fixed_state=current["fixed"],
                    )
                    return
                if current["after_mode"] == "mismatch":
                    _write_archive(
                        destination,
                        baseline_blob,
                        now,
                        fixed_state=current["fixed"],
                    )
                    return
            _write_archive(
                destination,
                current["blob"],
                now,
                fixed_state=current["fixed"],
            )

        def send(transaction, authorization, *, cancelled, progress):
            send_calls.append((transaction, authorization))
            completion = AuthorizedWriteSender(backend, 0x01).send(
                transaction,
                authorization,
                cancelled=cancelled,
                progress=progress,
            )
            current["blob"] = transaction.ranges[4] + transaction.ranges[7]
            current["fixed"] = {
                0x001B: transaction.ranges[0][0x00:0x40],
                0x001C: transaction.ranges[0][0x40:0x80],
                0x001D: transaction.ranges[0][0x80:0xC0],
                0x001E: transaction.ranges[0][0xC0:0x100],
                0x001F: transaction.ranges[1],
            }
            return completion

        preview = build_new_txt_preview(
            preview_backup,
            source,
            "new.txt",
            source_template_offset=0xC0,
            available_capacity_bytes=10000,
            source_encoding="utf-8",
            now=now,
            max_age_seconds=None,
        )
        workflow = GuardedNewTxtWorkflow(capture, send)
        return temporary, root, source, now, current, backend, send_calls, preview, workflow

    def _run(self, setup, **kwargs):
        temporary, root, source, now, _current, _backend, _calls, preview, workflow = setup
        fake_transport = kwargs.pop("fake_transport", True)
        confirmation = kwargs.pop("confirmation", NEW_ROOT_TXT_CONFIRMATION_PHRASE)
        return workflow.run(
            backup_destination=root / "before",
            post_write_destination=root / "after",
            source_path=source,
            target_filename="new.txt",
            source_template_offset=0xC0,
            available_capacity_bytes=10000,
            confirmation=confirmation,
            preview=preview,
            fake_transport=fake_transport,
            now=now,
            max_age_seconds=None,
            **kwargs,
        )

    def test_utf8_preview_and_fake_workflow_produce_durable_verified_audit(self):
        setup = self._setup()
        self.addCleanup(setup[0].cleanup)
        result = self._run(setup)
        self.assertEqual(result.state, "readback_verified")
        self.assertEqual(result.audit["workflow"]["states"][-1], "readback_verified")
        self.assertTrue(result.audit["workflow"]["fake_transport"])
        self.assertIn("OFFLINE PREVIEW ONLY", result.preview.to_dict()["preview"]["notice"])
        self.assertEqual(result.audit["completion"], "0x0000")
        self.assertTrue(result.verification.dynamic_blob_matches)
        self.assertTrue(result.verification.unrelated_objects_unchanged)
        self.assertEqual(result.audit["source"]["source_encoding"], "utf-8")

    def test_fake_transport_requirement_blocks_any_capture(self):
        setup = self._setup()
        self.addCleanup(setup[0].cleanup)
        with self.assertRaisesRegex(NewTxtWorkflowError, "fake transport"):
            self._run(setup, fake_transport=False)
        self.assertFalse((setup[1] / "before").exists())
        self.assertEqual(setup[6], [])

    def test_cancellation_before_transaction_is_safe_and_durable(self):
        setup = self._setup()
        self.addCleanup(setup[0].cleanup)
        with self.assertRaises(NewTxtWorkflowError) as raised:
            self._run(setup, cancelled=lambda: True)
        self.assertEqual(raised.exception.state, "cancelled_before_transaction")
        self.assertFalse(raised.exception.write_started)
        self.assertEqual(raised.exception.audit["device_change"], "none_started")
        self.assertEqual(setup[6], [])

    def test_wrong_phrase_stops_before_fake_sender(self):
        setup = self._setup()
        self.addCleanup(setup[0].cleanup)
        with self.assertRaises(NewTxtWorkflowError) as raised:
            self._run(setup, confirmation="WRITE INFOCARRY")
        self.assertEqual(raised.exception.stage, "authorization")
        self.assertEqual(setup[6], [])

    def test_source_change_after_displayed_preview_stops_before_sender(self):
        setup = self._setup()
        self.addCleanup(setup[0].cleanup)
        source = setup[2]
        original_capture = setup[7]
        # Change the source during the fresh-backup callback, after the
        # displayed preview was created but before candidate revalidation.
        workflow = setup[8]
        current = setup[4]

        def capture(destination, *, cancelled, progress):
            _write_archive(destination, current["blob"], setup[3])
            source.write_text("changed\n", encoding="utf-8")

        replacement = GuardedNewTxtWorkflow(capture, workflow._send)
        with self.assertRaisesRegex(NewTxtWorkflowError, "no longer matches"):
            replacement.run(
                backup_destination=setup[1] / "before",
                post_write_destination=setup[1] / "after",
                source_path=source,
                target_filename="new.txt",
                source_template_offset=0xC0,
                available_capacity_bytes=10000,
                confirmation=NEW_ROOT_TXT_CONFIRMATION_PHRASE,
                preview=original_capture,
                fake_transport=True,
                now=setup[3],
                max_age_seconds=None,
            )
        self.assertEqual(setup[6], [])

    def test_disconnect_after_transaction_start_is_indeterminate_and_not_retried(self):
        setup = self._setup(backend=WorkflowBackend(fail_bulk_at=2))
        self.addCleanup(setup[0].cleanup)
        with self.assertRaises(NewTxtWorkflowError) as raised:
            self._run(setup)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertTrue(raised.exception.write_started)
        self.assertFalse(raised.exception.audit["automatic_retry_allowed"])
        self.assertEqual(len(setup[6]), 1)
        self.assertEqual(len([call for call in setup[5].calls if call[0] == "control_out"]), 1)

    def test_malformed_post_readback_is_terminal_without_retry(self):
        setup = self._setup()
        self.addCleanup(setup[0].cleanup)
        setup[4]["after_mode"] = "malformed"
        with self.assertRaises(NewTxtWorkflowError) as raised:
            self._run(setup)
        self.assertEqual(raised.exception.stage, "post_write_readback")
        self.assertEqual(raised.exception.state, "failed")
        self.assertTrue(raised.exception.write_started)
        self.assertEqual(len(setup[6]), 1)

    def test_candidate_readback_mismatch_is_terminal_without_retry(self):
        setup = self._setup()
        self.addCleanup(setup[0].cleanup)
        setup[4]["after_mode"] = "mismatch"
        with self.assertRaisesRegex(NewTxtWorkflowError, "no automatic retry"):
            self._run(setup)
        self.assertEqual(len(setup[6]), 1)

    def test_nonzero_completion_is_terminal_known_failure(self):
        setup = self._setup(backend=WorkflowBackend(completion=(1, 0)))
        self.addCleanup(setup[0].cleanup)
        with self.assertRaises(NewTxtWorkflowError) as raised:
            self._run(setup)
        self.assertEqual(raised.exception.state, "failed")
        self.assertTrue(raised.exception.write_started)
        self.assertEqual(raised.exception.audit["device_change"], "completed_with_error")
        self.assertEqual(len(setup[6]), 1)


if __name__ == "__main__":
    unittest.main()
