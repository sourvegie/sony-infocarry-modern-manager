import unittest

from infocarry.protocol import (
    CommandNotAllowedError,
    DeviceStatusError,
    ReadOnlyReceiver,
    ReceivePolicy,
    TransferCancelledError,
    TransferLengthError,
    TransferTimeoutError,
    build_command_header,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeBackend:
    def __init__(self, *, states=(), completions=(0,), bulk_chunks=()):
        self.states = list(states)
        self.completions = list(completions)
        self.bulk_chunks = list(bulk_chunks)
        self.calls = []
        self.header_result = None

    def control_out(self, request_type, request, value, index, data, timeout_ms):
        self.calls.append(("control_out", request_type, request, value, index, data, timeout_ms))
        return len(data) if self.header_result is None else self.header_result

    def control_in(self, request_type, request, value, index, length, timeout_ms):
        self.calls.append(("control_in", request_type, request, value, index, length, timeout_ms))
        queue = self.states if request == 3 else self.completions
        value = queue.pop(0)
        return value if isinstance(value, bytes) else value.to_bytes(2, "little")

    def bulk_read(self, endpoint, length, timeout_ms):
        self.calls.append(("bulk_read", endpoint, length, timeout_ms))
        return self.bulk_chunks.pop(0)


class ProtocolTests(unittest.TestCase):
    def make_receiver(self, backend, *, clock=None, **policy_values):
        clock = clock or FakeClock()
        policy = ReceivePolicy(**policy_values)
        return ReadOnlyReceiver(
            backend,
            0x82,
            allowed_commands=frozenset({0x18}),
            policy=policy,
            clock=clock,
            sleep=clock.sleep,
        )

    def test_command_header_is_exactly_six_little_endian_bytes(self):
        self.assertEqual(build_command_header(0x18, 64), bytes.fromhex("18 00 40 00 00 00"))
        with self.assertRaises(ValueError):
            build_command_header(0x10000, 1)
        with self.assertRaises(ValueError):
            build_command_header(1, 0x100000000)

    def test_unknown_command_is_rejected_before_usb_access(self):
        backend = FakeBackend()
        receiver = self.make_receiver(backend)
        with self.assertRaises(CommandNotAllowedError):
            receiver.receive(0x99, 64)
        self.assertEqual(backend.calls, [])

    def test_busy_partial_reads_and_chunking(self):
        backend = FakeBackend(
            states=(3, 0, 0),
            completions=(0,),
            bulk_chunks=(b"ab", b"cde"),
        )
        clock = FakeClock()
        receiver = self.make_receiver(
            backend,
            clock=clock,
            max_bulk_chunk=3,
            busy_timeout_seconds=1.0,
            busy_poll_interval_seconds=0.1,
        )
        self.assertEqual(receiver.receive(0x18, 5), b"abcde")
        self.assertEqual(clock.sleeps, [0.1])
        bulk_calls = [call for call in backend.calls if call[0] == "bulk_read"]
        self.assertEqual([call[2] for call in bulk_calls], [3, 3])
        self.assertEqual(backend.calls[0][5], bytes.fromhex("18 00 05 00 00 00"))
        self.assertEqual(backend.calls[-1][2], 4)

    def test_failure_state_queries_completion_then_raises(self):
        backend = FakeBackend(states=(1,), completions=(7,))
        receiver = self.make_receiver(backend)
        with self.assertRaises(DeviceStatusError) as raised:
            receiver.receive(0x18, 1)
        self.assertEqual(raised.exception.stage, "transfer-state")
        self.assertEqual(backend.calls[-1][2], 4)

    def test_unexpected_state_is_not_treated_as_ready(self):
        backend = FakeBackend(states=(4,), completions=(0,))
        receiver = self.make_receiver(backend)
        with self.assertRaises(DeviceStatusError):
            receiver.receive(0x18, 1)

    def test_nonzero_completion_fails(self):
        backend = FakeBackend(states=(0,), completions=(2,), bulk_chunks=(b"x",))
        receiver = self.make_receiver(backend)
        with self.assertRaises(DeviceStatusError) as raised:
            receiver.receive(0x18, 1)
        self.assertEqual(raised.exception.stage, "completion")

    def test_busy_deadline_is_finite(self):
        backend = FakeBackend(states=(3,) * 20, completions=(0,))
        clock = FakeClock()
        receiver = self.make_receiver(
            backend,
            clock=clock,
            busy_timeout_seconds=0.25,
            busy_poll_interval_seconds=0.1,
        )
        with self.assertRaises(TransferTimeoutError):
            receiver.receive(0x18, 1)
        self.assertAlmostEqual(sum(clock.sleeps), 0.25)
        self.assertEqual(backend.calls[-1][2], 4)

    def test_cancellation_queries_completion(self):
        backend = FakeBackend(completions=(0,))
        receiver = self.make_receiver(backend)
        with self.assertRaises(TransferCancelledError):
            receiver.receive(0x18, 1, cancelled=lambda: True)
        self.assertEqual(backend.calls[-1][2], 4)

    def test_short_control_and_empty_bulk_are_rejected(self):
        backend = FakeBackend()
        backend.header_result = 5
        receiver = self.make_receiver(backend)
        with self.assertRaises(TransferLengthError):
            receiver.receive(0x18, 1)
        self.assertEqual(len(backend.calls), 1)

        backend = FakeBackend(states=(0,), completions=(0,), bulk_chunks=(b"",))
        receiver = self.make_receiver(backend)
        with self.assertRaises(TransferLengthError):
            receiver.receive(0x18, 1)
        self.assertEqual(backend.calls[-1][2], 4)


if __name__ == "__main__":
    unittest.main()
