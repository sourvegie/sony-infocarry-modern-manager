from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.new_txt_gate import (
    NEW_ROOT_TXT_CONFIRMATION_PHRASE,
    NewTxtGateError,
    authorize_new_txt_add,
    bind_new_txt_sender,
)
from infocarry.protocol import (
    DeviceStatusError,
    TransferCancelledError,
    TransferTimeoutError,
)
from infocarry.write_protocol import (
    AuthorizedWriteSender,
    REQUEST_COMPLETION,
    REQUEST_TRANSFER_STATE,
    WritePolicy,
    WriteProtocolError,
    WriteTransferLengthError,
    assess_write_failure,
)

try:
    from test_new_txt import _make_root_blob, _write_archive
except ModuleNotFoundError:
    from tests.test_new_txt import _make_root_blob, _write_archive


class ScenarioBackend:
    def __init__(
        self,
        *,
        completion=(0,),
        fail_bulk_at=None,
        partial=False,
        state_default=0,
        completion_bytes=None,
    ):
        self.calls = []
        self.completion = list(completion)
        self.fail_bulk_at = fail_bulk_at
        self.partial = partial
        self.state_default = state_default
        self.completion_bytes = completion_bytes

    def control_out(self, request_type, request, value, index, data, timeout_ms):
        self.calls.append(("control_out", request, bytes(data)))
        return len(data)

    def control_in(self, request_type, request, value, index, length, timeout_ms):
        self.calls.append(("control_in", request))
        if request == REQUEST_TRANSFER_STATE:
            return self.state_default.to_bytes(2, "little")
        if request == REQUEST_COMPLETION:
            if self.completion_bytes is not None:
                return self.completion_bytes
            value = self.completion.pop(0) if self.completion else 0
            return value.to_bytes(2, "little")
        raise AssertionError(request)

    def bulk_write(self, endpoint, data, timeout_ms):
        self.calls.append(("bulk_write", bytes(data)))
        count = sum(call[0] == "bulk_write" for call in self.calls)
        if self.fail_bulk_at is not None and count == self.fail_bulk_at:
            raise OSError("simulated fake cable disconnect")
        if self.partial:
            return max(1, len(data) // 2)
        return len(data)


class NewTxtTransportIntegrationTests(unittest.TestCase):
    def _candidate(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        backup = _write_archive(root / "backup", _make_root_blob(), now)
        source = root / "source.txt"
        source.write_bytes(b"new\r\n")
        from infocarry.new_txt import build_new_root_txt_add

        result = build_new_root_txt_add(
            backup,
            source,
            "new.txt",
            source_template_offset=0xC0,
            available_capacity_bytes=10000,
            now=now,
            max_age_seconds=None,
        )
        binding = authorize_new_txt_add(
            result, confirmation=NEW_ROOT_TXT_CONFIRMATION_PHRASE
        )
        sender_binding = bind_new_txt_sender(
            binding,
            result,
            backup,
            source,
            now=now,
            max_age_seconds=None,
        )
        return temporary, backup, source, result, binding, sender_binding, now

    @staticmethod
    def _calls(backend, name):
        return [call for call in backend.calls if call[0] == name]

    def _send(self, backend, sender_binding, result, **kwargs):
        return AuthorizedWriteSender(
            backend,
            0x01,
            policy=kwargs.pop("policy", WritePolicy()),
            clock=kwargs.pop("clock", None) or __import__("time").monotonic,
            sleep=kwargs.pop("sleep", None) or __import__("time").sleep,
        ).send(result.transaction, sender_binding, **kwargs)

    def test_bound_candidate_completes_and_independent_readback_verifies(self):
        temporary, backup, source, result, binding, sender_binding, now = self._candidate()
        self.addCleanup(temporary.cleanup)
        backend = ScenarioBackend()
        completion = self._send(backend, sender_binding, result)
        self.assertEqual(completion, 0)
        post = _write_archive(
            Path(temporary.name) / "post",
            result.candidate_blob,
            now,
            fixed_state={
                0x001B: result.transaction.ranges[0][0x00:0x40],
                0x001C: result.transaction.ranges[0][0x40:0x80],
                0x001D: result.transaction.ranges[0][0x80:0xC0],
                0x001E: result.transaction.ranges[0][0xC0:0x100],
                0x001F: result.transaction.ranges[1],
            },
        )
        verification = binding.verify_post_add_backup(
            result, backup, source, post, now=now, max_age_seconds=None
        )
        self.assertTrue(verification.fixed_state_matches)
        self.assertTrue(verification.dynamic_blob_matches)
        self.assertTrue(verification.unrelated_objects_unchanged)
        self.assertEqual(len(self._calls(backend, "control_out")), 1)

    def test_partial_transfer_completes_without_duplicate_transaction(self):
        temporary, _backup, _source, result, _binding, sender_binding, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        backend = ScenarioBackend(partial=True)
        completion = self._send(
            backend,
            sender_binding,
            result,
            policy=WritePolicy(max_bulk_chunk=0x40),
        )
        self.assertEqual(completion, 0)
        self.assertGreater(len(self._calls(backend, "bulk_write")), 5)
        self.assertEqual(len(self._calls(backend, "control_out")), 1)

    def test_disconnect_after_start_is_indeterminate_and_not_retried(self):
        temporary, _backup, _source, result, _binding, sender_binding, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        backend = ScenarioBackend(fail_bulk_at=2)
        with self.assertRaises(WriteProtocolError) as raised:
            self._send(backend, sender_binding, result)
        assessment = assess_write_failure(raised.exception)
        self.assertTrue(assessment.write_started)
        self.assertEqual(assessment.device_outcome, "indeterminate")
        self.assertFalse(assessment.automatic_retry_allowed)
        self.assertEqual(len(self._calls(backend, "bulk_write")), 2)
        self.assertEqual(len(self._calls(backend, "control_out")), 1)
        self.assertEqual(
            len([call for call in self._calls(backend, "control_in") if call[1] == REQUEST_COMPLETION]),
            1,
        )

    def test_timeout_after_start_is_indeterminate_without_bulk_retry(self):
        temporary, _backup, _source, result, _binding, sender_binding, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        backend = ScenarioBackend(state_default=3)
        clock = [0.0]
        policy = WritePolicy(busy_timeout_seconds=0.25, busy_poll_interval_seconds=0.1)
        with self.assertRaises(TransferTimeoutError) as raised:
            self._send(
                backend,
                sender_binding,
                result,
                policy=policy,
                clock=lambda: clock[0],
                sleep=lambda value: clock.__setitem__(0, clock[0] + value),
            )
        assessment = assess_write_failure(raised.exception)
        self.assertTrue(assessment.write_started)
        self.assertEqual(assessment.device_outcome, "indeterminate")
        self.assertEqual(len(self._calls(backend, "bulk_write")), 0)
        self.assertEqual(len(self._calls(backend, "control_out")), 1)
        self.assertEqual(
            len([call for call in self._calls(backend, "control_in") if call[1] == REQUEST_COMPLETION]),
            1,
        )

    def test_cancellation_before_header_is_safe_and_does_not_query_completion(self):
        temporary, _backup, _source, result, _binding, sender_binding, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        backend = ScenarioBackend()
        with self.assertRaises(TransferCancelledError) as raised:
            self._send(
                backend,
                sender_binding,
                result,
                cancelled=lambda: True,
            )
        assessment = assess_write_failure(raised.exception)
        self.assertFalse(assessment.write_started)
        self.assertEqual(assessment.device_outcome, "not_started")
        self.assertEqual(backend.calls, [])

    def test_cancellation_after_first_chunk_is_indeterminate_and_not_retried(self):
        temporary, _backup, _source, result, _binding, sender_binding, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        backend = ScenarioBackend()
        checks = iter((False, False, False, True))
        with self.assertRaises(TransferCancelledError) as raised:
            self._send(
                backend,
                sender_binding,
                result,
                cancelled=lambda: next(checks, True),
            )
        assessment = assess_write_failure(raised.exception)
        self.assertTrue(assessment.write_started)
        self.assertEqual(assessment.device_outcome, "indeterminate")
        self.assertEqual(len(self._calls(backend, "bulk_write")), 1)
        self.assertEqual(len(self._calls(backend, "control_out")), 1)
        self.assertEqual(
            len([call for call in self._calls(backend, "control_in") if call[1] == REQUEST_COMPLETION]),
            1,
        )

    def test_nonzero_completion_is_terminal_known_failure_without_retry(self):
        temporary, _backup, _source, result, _binding, sender_binding, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        backend = ScenarioBackend(completion=(1, 0))
        with self.assertRaises(DeviceStatusError) as raised:
            self._send(backend, sender_binding, result)
        assessment = assess_write_failure(raised.exception)
        self.assertTrue(assessment.write_started)
        self.assertEqual(assessment.device_outcome, "completed_with_error")
        self.assertFalse(assessment.automatic_retry_allowed)
        self.assertEqual(len(self._calls(backend, "control_out")), 1)
        self.assertEqual(len(self._calls(backend, "bulk_write")), 5)
        self.assertEqual(
            len([call for call in self._calls(backend, "control_in") if call[1] == REQUEST_COMPLETION]),
            2,
        )

    def test_missing_completion_is_indeterminate_and_not_retried(self):
        temporary, _backup, _source, result, _binding, sender_binding, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        backend = ScenarioBackend(completion_bytes=b"\x00")
        with self.assertRaises(WriteTransferLengthError) as raised:
            self._send(backend, sender_binding, result)
        assessment = assess_write_failure(raised.exception)
        self.assertTrue(assessment.write_started)
        self.assertEqual(assessment.device_outcome, "indeterminate")
        self.assertEqual(len(self._calls(backend, "control_out")), 1)
        self.assertEqual(len(self._calls(backend, "bulk_write")), 5)
        self.assertEqual(
            len([call for call in self._calls(backend, "control_in") if call[1] == REQUEST_COMPLETION]),
            2,
        )

    def test_changed_source_is_rejected_before_any_fake_usb_call(self):
        temporary, _backup, source, result, _binding, sender_binding, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        source.write_bytes(b"changed\r\n")
        backend = ScenarioBackend()
        with self.assertRaises(WriteProtocolError):
            self._send(backend, sender_binding, result)
        self.assertEqual(backend.calls, [])

    def test_malformed_post_readback_is_terminal_and_sender_is_not_recalled(self):
        temporary, backup, source, result, binding, sender_binding, now = self._candidate()
        self.addCleanup(temporary.cleanup)
        backend = ScenarioBackend()
        self.assertEqual(self._send(backend, sender_binding, result), 0)
        bad_post = _write_archive(
            Path(temporary.name) / "bad-post",
            result.candidate_blob[:-4] + b"BAD!",
            now,
            fixed_state={
                0x001B: result.transaction.ranges[0][0x00:0x40],
                0x001C: result.transaction.ranges[0][0x40:0x80],
                0x001D: result.transaction.ranges[0][0x80:0xC0],
                0x001E: result.transaction.ranges[0][0xC0:0x100],
                0x001F: result.transaction.ranges[1],
            },
        )
        with self.assertRaisesRegex(NewTxtGateError, "no retry attempted"):
            binding.verify_post_add_backup(
                result, backup, source, bad_post, now=now, max_age_seconds=None
            )
        self.assertEqual(len(self._calls(backend, "control_out")), 1)

    def test_candidate_readback_mismatch_is_terminal_and_not_retried(self):
        temporary, backup, source, result, binding, sender_binding, now = self._candidate()
        self.addCleanup(temporary.cleanup)
        backend = ScenarioBackend()
        self.assertEqual(self._send(backend, sender_binding, result), 0)
        mismatch = _write_archive(
            Path(temporary.name) / "mismatch-post",
            _make_root_blob(),
            now,
            fixed_state={
                0x001B: result.transaction.ranges[0][0x00:0x40],
                0x001C: result.transaction.ranges[0][0x40:0x80],
                0x001D: result.transaction.ranges[0][0x80:0xC0],
                0x001E: result.transaction.ranges[0][0xC0:0x100],
                0x001F: result.transaction.ranges[1],
            },
        )
        with self.assertRaisesRegex(NewTxtGateError, "no retry attempted"):
            binding.verify_post_add_backup(
                result, backup, source, mismatch, now=now, max_age_seconds=None
            )
        self.assertEqual(len(self._calls(backend, "control_out")), 1)


if __name__ == "__main__":
    unittest.main()
