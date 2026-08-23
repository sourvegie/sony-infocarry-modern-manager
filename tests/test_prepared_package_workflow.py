from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import parse_backup_blob
from infocarry.prepared_package import build_prepared_text_package
from infocarry.prepared_package_candidate import build_prepared_package_candidate
from infocarry.prepared_package_workflow import (
    GuardedPreparedPackageWorkflow,
    PreparedPackageOfflinePreview,
    PreparedPackageWorkflowError,
)
from infocarry.protocol import TransferCancelledError, TransferTimeoutError
from infocarry.write_gate import verify_fresh_backup
from infocarry.write_protocol import (
    AuthorizedWriteSender,
    REQUEST_COMPLETION,
    REQUEST_TRANSFER_STATE,
    WritePolicy,
)

try:
    from test_new_txt import _write_archive
    from test_prepared_folder import make_folder_fixtures
except ModuleNotFoundError:
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_folder import make_folder_fixtures


class PackageWorkflowBackend:
    def __init__(self, *, partial=False, bulk_error=None, completions=(0,)):
        self.calls = []
        self.partial = partial
        self.bulk_error = bulk_error
        self.completions = list(completions)

    def control_out(self, request_type, request, value, index, data, timeout_ms):
        self.calls.append(("control_out", request, bytes(data)))
        return len(data)

    def control_in(self, request_type, request, value, index, length, timeout_ms):
        self.calls.append(("control_in", request))
        if request == REQUEST_TRANSFER_STATE:
            return b"\x00\x00"
        if request == REQUEST_COMPLETION:
            value = self.completions.pop(0) if self.completions else 0
            return value.to_bytes(2, "little")
        raise AssertionError(request)

    def bulk_write(self, endpoint, data, timeout_ms):
        self.calls.append(("bulk_write", bytes(data)))
        if self.bulk_error is not None:
            raise self.bulk_error
        return max(1, len(data) // 2) if self.partial else len(data)


class PreparedPackageWorkflowTests(unittest.TestCase):
    def _setup(self, *, backend=None, after_mode="normal", preview_timestamp=0x6A8ABA6F):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        now = datetime(2026, 8, 23, tzinfo=timezone.utc)
        baseline_blob, template_blob = make_folder_fixtures()
        zero_state = {command: b"\x00" * 64 for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
        preview_backup_path = _write_archive(root / "preview", baseline_blob, now, fixed_state=zero_state)
        before = verify_fresh_backup(preview_backup_path, now=now, max_age_seconds=None)
        source = root / "source.txt"
        source.write_text("A\nB", encoding="utf-8")
        package = build_prepared_text_package(source, "Package", "chapter.txt")
        template = parse_backup_blob(template_blob)
        preview_candidate = build_prepared_package_candidate(
            package,
            before,
            template,
            new_record_timestamp_be32=preview_timestamp,
            available_capacity_bytes=10_000,
        )
        backend = backend or PackageWorkflowBackend()
        current = {"blob": baseline_blob, "fixed": zero_state}
        send_calls = []

        def capture(destination, *, cancelled, progress):
            if destination.name == "after":
                if after_mode == "malformed":
                    _write_archive(
                        destination,
                        current["blob"][:-4] + b"BAD!",
                        now,
                        fixed_state=current["fixed"],
                    )
                    return
                if after_mode == "mismatch":
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
            completion = AuthorizedWriteSender(
                backend,
                0x01,
                policy=WritePolicy(busy_timeout_seconds=0.25, busy_poll_interval_seconds=0.01),
            ).send(transaction, authorization, cancelled=cancelled, progress=progress)
            current["blob"] = transaction.ranges[4] + transaction.ranges[7]
            current["fixed"] = {
                0x001B: transaction.ranges[0][0x00:0x40],
                0x001C: transaction.ranges[0][0x40:0x80],
                0x001D: transaction.ranges[0][0x80:0xC0],
                0x001E: transaction.ranges[0][0xC0:0x100],
                0x001F: transaction.ranges[1],
            }
            return completion

        workflow = GuardedPreparedPackageWorkflow(capture, send, template)
        return {
            "temporary": temporary,
            "root": root,
            "now": now,
            "zero_state": zero_state,
            "package": package,
            "preview": PreparedPackageOfflinePreview(preview_candidate),
            "workflow": workflow,
            "backend": backend,
            "current": current,
            "send_calls": send_calls,
            "source": source,
        }

    def _run(self, setup, **kwargs):
        arguments = {
            "backup_destination": setup["root"] / "before",
            "post_operation_destination": setup["root"] / "after",
            "package": setup["package"],
            "preview": setup["preview"],
            "new_record_timestamp_be32": 0x6A8ABA6F,
            "available_capacity_bytes": 10_000,
            "confirmation": "ADD ONE INFOCARRY TEXT PACKAGE",
            "fake_transport": True,
            "now": setup["now"],
            "max_age_seconds": None,
        }
        arguments.update(kwargs)
        return setup["workflow"].run(**arguments)

    def test_partial_fake_transfer_completes_once_and_readback_verifies(self):
        setup = self._setup(backend=PackageWorkflowBackend(partial=True))
        self.addCleanup(setup["temporary"].cleanup)
        result = self._run(setup)
        self.assertEqual(result.state, "readback_verified")
        self.assertEqual(result.completion, 0)
        self.assertTrue(result.audit["workflow"]["fake_transport"])
        self.assertFalse(result.audit["workflow"]["automatic_retry_allowed"])
        self.assertEqual(len(setup["send_calls"]), 1)
        self.assertEqual(len([call for call in setup["backend"].calls if call[0] == "control_out"]), 1)

    def test_disconnect_and_timeout_after_transaction_start_are_indeterminate_once(self):
        for error in (OSError("simulated disconnect"), TransferTimeoutError("simulated timeout")):
            with self.subTest(error=type(error).__name__):
                setup = self._setup(backend=PackageWorkflowBackend(bulk_error=error))
                self.addCleanup(setup["temporary"].cleanup)
                with self.assertRaisesRegex(PreparedPackageWorkflowError, "no automatic retry") as raised:
                    self._run(setup)
                self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
                self.assertTrue(raised.exception.write_started)
                self.assertFalse(raised.exception.audit["automatic_retry_allowed"])
                self.assertEqual(len(setup["send_calls"]), 1)
                self.assertEqual(len([call for call in setup["backend"].calls if call[0] == "control_out"]), 1)

    def test_cancellation_before_send_is_safe_and_after_start_is_indeterminate(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaises(PreparedPackageWorkflowError) as raised:
            self._run(setup, cancelled=lambda: True)
        self.assertEqual(raised.exception.state, "cancelled_before_transaction")
        self.assertFalse(raised.exception.write_started)
        self.assertEqual(setup["send_calls"], [])

        started = {"value": False}

        def cancelled_after_start():
            return started["value"]

        original_send = setup["workflow"]._send

        def send_after_start(transaction, authorization, *, cancelled, progress):
            started["value"] = True
            return original_send(transaction, authorization, cancelled=cancelled, progress=progress)

        setup["workflow"] = GuardedPreparedPackageWorkflow(
            setup["workflow"]._capture,
            send_after_start,
            setup["workflow"]._template,
        )
        with self.assertRaises(PreparedPackageWorkflowError) as raised:
            self._run(setup, cancelled=cancelled_after_start)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertTrue(raised.exception.write_started)
        self.assertEqual(len(setup["send_calls"]), 1)

    def test_nonzero_and_missing_completion_are_terminal_without_retry(self):
        for completions in ((1, 0),):
            setup = self._setup(backend=PackageWorkflowBackend(completions=completions))
            self.addCleanup(setup["temporary"].cleanup)
            with self.assertRaisesRegex(PreparedPackageWorkflowError, "unacceptable completion|no automatic retry") as raised:
                self._run(setup)
            self.assertEqual(raised.exception.state, "failed")
            self.assertTrue(raised.exception.write_started)
            self.assertEqual(len(setup["send_calls"]), 1)

        setup = self._setup(backend=PackageWorkflowBackend())
        self.addCleanup(setup["temporary"].cleanup)
        original_send = setup["workflow"]._send

        def missing_completion(transaction, authorization, *, cancelled, progress):
            original_send(transaction, authorization, cancelled=cancelled, progress=progress)
            return None

        setup["workflow"] = GuardedPreparedPackageWorkflow(
            setup["workflow"]._capture,
            missing_completion,
            setup["workflow"]._template,
        )
        with self.assertRaisesRegex(PreparedPackageWorkflowError, "unacceptable completion") as raised:
            self._run(setup)
        self.assertEqual(raised.exception.state, "failed")
        self.assertEqual(len(setup["send_calls"]), 1)

    def test_malformed_or_mismatched_readback_is_terminal_and_not_retried(self):
        for mode in ("malformed", "mismatch"):
            setup = self._setup(after_mode=mode)
            self.addCleanup(setup["temporary"].cleanup)
            with self.assertRaisesRegex(PreparedPackageWorkflowError, "no automatic retry") as raised:
                self._run(setup)
            self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
            self.assertTrue(raised.exception.write_started)
            self.assertEqual(len(setup["send_calls"]), 1)

    def test_preview_source_phrase_and_fake_transport_gates_stop_before_sender(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaisesRegex(PreparedPackageWorkflowError, "fake transport"):
            setup["workflow"].run(
                backup_destination=setup["root"] / "no-before",
                post_operation_destination=setup["root"] / "no-after",
                package=setup["package"],
                preview=setup["preview"],
                new_record_timestamp_be32=0x6A8ABA6F,
                available_capacity_bytes=10_000,
                confirmation="ADD ONE INFOCARRY TEXT PACKAGE",
                fake_transport=False,
                now=setup["now"],
                max_age_seconds=None,
            )
        self.assertEqual(setup["send_calls"], [])

        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaisesRegex(PreparedPackageWorkflowError, "confirmation"):
            self._run(setup, confirmation="ADD INFOCARRY TXT")
        self.assertEqual(setup["send_calls"], [])

        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        setup["source"].write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(PreparedPackageWorkflowError, "candidate"):
            self._run(setup)
        self.assertEqual(setup["send_calls"], [])


if __name__ == "__main__":
    unittest.main()
