from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
import unittest

from infocarry.protocol import (
    DeviceStatusError,
    STATUS_BUSY,
    TransferCancelledError,
    TransferTimeoutError,
)
from infocarry.write_gate import WriteGateError
from infocarry.write_artifact import ProspectiveWriteTransaction, build_staging_range
from infocarry.write_protocol import (
    AuthorizedWriteSender,
    REQUEST_BEGIN_TRANSMIT,
    REQUEST_COMPLETION,
    REQUEST_TRANSFER_STATE,
    WritePolicy,
    WriteProtocolError,
)


def transaction():
    range5 = b"m" * 0x40
    range8 = b"model"
    variable_m = len(range5) + len(range8)
    return ProspectiveWriteTransaction(
        ranges=(
            b"a" * 0x100,
            b"b" * 0x40,
            build_staging_range(0, variable_m),
            b"",
            range5,
            b"",
            b"",
            range8,
        ),
        variable_n=0,
        variable_m=variable_m,
    )


class FakeWriteBackend:
    def __init__(
        self,
        completion=(0,),
        partial=False,
        fail_bulk_at=None,
        state_default=0,
    ):
        self.calls = []
        self.completion = list(completion)
        self.partial = partial
        self.fail_bulk_at = fail_bulk_at
        self.state_default = state_default

    def control_out(self, request_type, request, value, index, data, timeout_ms):
        self.calls.append(("control_out", request_type, request, bytes(data)))
        return len(data)

    def control_in(self, request_type, request, value, index, length, timeout_ms):
        self.calls.append(("control_in", request_type, request))
        if request == REQUEST_TRANSFER_STATE:
            return self.state_default.to_bytes(2, "little")
        if request == REQUEST_COMPLETION:
            value = self.completion.pop(0) if self.completion else 0
            return value.to_bytes(2, "little")
        raise AssertionError(request)

    def bulk_write(self, endpoint, data, timeout_ms):
        self.calls.append(("bulk_write", endpoint, bytes(data)))
        if self.fail_bulk_at is not None and sum(
            call[0] == "bulk_write" for call in self.calls
        ) == self.fail_bulk_at:
            raise OSError("simulated cable disconnect")
        return max(1, len(data) // 2) if self.partial else len(data)


class FakeAuthorization:
    def __init__(self, failure=None):
        self.calls = []
        self.failure = failure

    def revalidate(self, candidate):
        self.calls.append(candidate)
        if self.failure is not None:
            raise self.failure


class AuthorizedWriteSenderTests(unittest.TestCase):
    def test_sends_header_ranges_and_completion_only_after_revalidation(self):
        backend = FakeWriteBackend()
        authorization = FakeAuthorization()
        candidate = transaction()
        result = AuthorizedWriteSender(backend, 0x01).send(candidate, authorization)
        self.assertEqual(result, 0)
        self.assertEqual(authorization.calls, [candidate])
        self.assertEqual(backend.calls[0][1:3], (0x40, REQUEST_BEGIN_TRANSMIT))
        self.assertEqual(
            backend.calls[0][3], candidate.command_header
        )
        self.assertEqual(
            sum(call[0] == "bulk_write" for call in backend.calls), 5
        )
        self.assertEqual(backend.calls[-1][2], REQUEST_COMPLETION)

    def test_handles_partial_bulk_writes_and_polls_each_chunk(self):
        backend = FakeWriteBackend(partial=True)
        policy = WritePolicy(max_bulk_chunk=0x40)
        AuthorizedWriteSender(backend, 0x01, policy=policy).send(
            transaction(), FakeAuthorization()
        )
        bulk_calls = [call for call in backend.calls if call[0] == "bulk_write"]
        state_calls = [
            call for call in backend.calls
            if call[0] == "control_in" and call[2] == REQUEST_TRANSFER_STATE
        ]
        self.assertGreater(len(bulk_calls), 5)
        self.assertEqual(len(state_calls), len(bulk_calls))

    def test_reports_monotonic_bounded_payload_progress(self):
        backend = FakeWriteBackend(partial=True)
        progress = []
        candidate = transaction()
        AuthorizedWriteSender(backend, 0x01, policy=WritePolicy(max_bulk_chunk=0x40)).send(
            candidate,
            FakeAuthorization(),
            progress=lambda label, completed, total: progress.append(
                (label, completed, total)
            ),
        )
        self.assertEqual(progress[0], ("Write authorized", 0, candidate.payload_length))
        self.assertEqual(progress[1], ("Header sent", 0, candidate.payload_length))
        self.assertEqual(progress[-1], ("Write complete", candidate.payload_length, candidate.payload_length))
        values = [entry[1] for entry in progress]
        self.assertEqual(values, sorted(values))
        self.assertTrue(all(0 <= value <= candidate.payload_length for value in values))

    def test_busy_timeout_is_finite_and_does_not_retry_bulk_write(self):
        backend = FakeWriteBackend(state_default=STATUS_BUSY)
        now = [0.0]
        policy = WritePolicy(
            busy_timeout_seconds=0.25,
            busy_poll_interval_seconds=0.1,
        )
        with self.assertRaises(TransferTimeoutError):
            AuthorizedWriteSender(
                backend,
                0x01,
                policy=policy,
                clock=lambda: now[0],
                sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
            ).send(transaction(), FakeAuthorization())
        self.assertEqual(
            len([call for call in backend.calls if call[0] == "bulk_write"]), 0
        )
        self.assertEqual(
            len([
                call for call in backend.calls
                if call[0] == "control_in" and call[2] == REQUEST_COMPLETION
            ]),
            1,
        )

    def test_cancellation_queries_best_effort_completion_and_preserves_error(self):
        backend = FakeWriteBackend()
        with self.assertRaises(TransferCancelledError):
            AuthorizedWriteSender(backend, 0x01).send(
                transaction(), FakeAuthorization(), cancelled=lambda: True
            )
        self.assertEqual(backend.calls, [])

    def test_nonzero_completion_is_reported(self):
        backend = FakeWriteBackend(completion=(1, 0))
        with self.assertRaises(DeviceStatusError):
            AuthorizedWriteSender(backend, 0x01).send(
                transaction(), FakeAuthorization()
            )
        self.assertEqual(
            [call[2] for call in backend.calls if call[0] == "control_in"][-2:],
            [REQUEST_COMPLETION, REQUEST_COMPLETION],
        )

    def test_authorization_is_required_before_any_usb_access(self):
        backend = FakeWriteBackend()
        with self.assertRaises(WriteProtocolError):
            AuthorizedWriteSender(backend, 0x01).send(transaction(), SimpleNamespace())
        self.assertEqual(backend.calls, [])

    def test_mid_write_disconnect_queries_completion_once_for_recovery(self):
        backend = FakeWriteBackend(fail_bulk_at=2)
        with self.assertRaises(WriteProtocolError):
            AuthorizedWriteSender(backend, 0x01).send(
                transaction(), FakeAuthorization()
            )
        bulk_calls = [call for call in backend.calls if call[0] == "bulk_write"]
        completion_calls = [
            call for call in backend.calls
            if call[0] == "control_in" and call[2] == REQUEST_COMPLETION
        ]
        self.assertEqual(len(bulk_calls), 2)
        self.assertEqual(len(completion_calls), 1)

    def test_cancellation_after_a_chunk_queries_completion_and_does_not_retry(self):
        backend = FakeWriteBackend()
        checks = iter((False, False, False, True))
        with self.assertRaises(TransferCancelledError):
            AuthorizedWriteSender(backend, 0x01).send(
                transaction(), FakeAuthorization(), cancelled=lambda: next(checks, True)
            )
        self.assertEqual(
            len([call for call in backend.calls if call[0] == "bulk_write"]), 1
        )
        self.assertEqual(
            len([
                call for call in backend.calls
                if call[0] == "control_in" and call[2] == REQUEST_COMPLETION
            ]),
            1,
        )

    def test_send_and_verify_requires_and_uses_post_write_archive(self):
        backend = FakeWriteBackend()
        authorization = FakeAuthorization()
        authorization.backup = "verified-before"
        with patch(
            "infocarry.write_protocol.verify_post_write_backup",
            return_value="verified-after",
        ) as verifier:
            result = AuthorizedWriteSender(backend, 0x01).send_and_verify(
                transaction(), authorization, Path("post-write")
            )
        self.assertEqual(result, "verified-after")
        verifier.assert_called_once_with(
            "verified-before", Path("post-write"), transaction()
        )

    def test_failed_post_write_verification_is_terminal_and_never_retries(self):
        backend = FakeWriteBackend()
        authorization = FakeAuthorization()
        authorization.backup = "verified-before"
        candidate = transaction()
        with patch(
            "infocarry.write_protocol.verify_post_write_backup",
            side_effect=WriteGateError("candidate was not present in read-back"),
        ) as verifier:
            with self.assertRaisesRegex(WriteProtocolError, "no retry attempted"):
                AuthorizedWriteSender(backend, 0x01).send_and_verify(
                    candidate, authorization, Path("post-write")
                )
        verifier.assert_called_once()
        self.assertEqual(
            len([call for call in backend.calls if call[0] == "control_out"]), 1
        )
        self.assertEqual(
            len([call for call in backend.calls if call[0] == "bulk_write"]), 5
        )


if __name__ == "__main__":
    unittest.main()
