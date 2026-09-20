from __future__ import annotations

from contextlib import AbstractContextManager
from types import SimpleNamespace
import unittest

from infocarry.constants import INFOCARRY_PRODUCT_ID, SONY_VENDOR_ID
from infocarry.device_home import (
    DeviceHomeService,
    classify_device_error,
    format_capacity_summary,
)
from infocarry.protocol import REQUEST_BEGIN_RECEIVE


class FakeReadOnlyBackend:
    """Only the existing receive operations; deliberately no bulk-write API."""

    def __init__(self, response: bytes):
        self.response = response
        self.headers: list[bytes] = []
        self.bulk_reads = 0

    def control_out(self, request_type, request, value, index, data, timeout_ms):
        self.headers.append(bytes(data))
        assert request == REQUEST_BEGIN_RECEIVE
        return len(data)

    def control_in(self, request_type, request, value, index, length, timeout_ms):
        return b"\x00\x00"

    def bulk_read(self, endpoint, length, timeout_ms):
        self.bulk_reads += 1
        result = self.response[:length]
        self.response = self.response[length:]
        return result


class FakeSession(AbstractContextManager):
    def __init__(self, backend):
        self.backend = backend
        self.endpoints = SimpleNamespace(bulk_in=0x81, bulk_out=0x02)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def hardware_response(capacity: int = 32 * 1024 * 1024) -> bytes:
    response = bytearray(64)
    response[8:12] = capacity.to_bytes(4, "big")
    return bytes(response)


class DeviceHomeTests(unittest.TestCase):
    def test_disconnected_state_does_not_open_a_session(self):
        opened = []
        service = DeviceHomeService(discover=lambda: (), open_session=lambda *_a: opened.append(1))

        snapshot = service.inspect()

        self.assertEqual(snapshot.state, "disconnected")
        self.assertEqual(snapshot.heading, "Device disconnected")
        self.assertIn("VNW-V15", snapshot.message)
        self.assertEqual(opened, [])

    def test_unsupported_sony_device_is_not_queried(self):
        opened = []
        unsupported = SimpleNamespace(
            idVendor=SONY_VENDOR_ID,
            idProduct=0x9999,
            bus=2,
            address=4,
        )
        service = DeviceHomeService(
            discover=lambda: (unsupported,),
            open_session=lambda *_a: opened.append(1),
        )

        snapshot = service.inspect()

        self.assertEqual(snapshot.state, "unsupported_device")
        self.assertIn("No InfoCarry query was sent", snapshot.message)
        self.assertIn("Physical-unit identity: not established", snapshot.technical_details)
        self.assertEqual(opened, [])

    def test_reviewed_v15_uses_only_read_only_0019_receive(self):
        backend = FakeReadOnlyBackend(hardware_response())
        session = FakeSession(backend)
        device = SimpleNamespace(
            idVendor=SONY_VENDOR_ID,
            idProduct=INFOCARRY_PRODUCT_ID,
            bus=3,
            address=7,
        )
        service = DeviceHomeService(
            discover=lambda: (device,), open_session=lambda selected: session
        )

        snapshot = service.inspect()

        self.assertEqual(snapshot.state, "connected")
        self.assertEqual(snapshot.capacity_bytes, 32 * 1024 * 1024)
        self.assertIn("Sony InfoCarry VNW-V15 connected", snapshot.heading)
        self.assertIn("Physical-unit identity: not established", snapshot.technical_details)
        self.assertEqual(backend.headers, [b"\x19\x00\x40\x00\x00\x00"])
        self.assertEqual(backend.bulk_reads, 1)
        self.assertFalse(hasattr(backend, "bulk_write"))

    def test_multiple_sony_devices_are_ambiguous_and_not_queried(self):
        v15 = SimpleNamespace(idVendor=SONY_VENDOR_ID, idProduct=INFOCARRY_PRODUCT_ID)
        other = SimpleNamespace(idVendor=SONY_VENDOR_ID, idProduct=0x9999)
        opened = []
        snapshot = DeviceHomeService(
            discover=lambda: (v15, other),
            open_session=lambda *_a: opened.append(1),
        ).inspect()
        self.assertEqual(snapshot.state, "ambiguous")
        self.assertEqual(opened, [])

    def test_error_classification_covers_usb_failure_categories(self):
        cases = (
            (OSError(13, "Permission denied"), "access_denied"),
            (RuntimeError("device busy"), "device_busy"),
            (RuntimeError("device disconnected"), "disconnected_during_read"),
            (RuntimeError("libusb backend unavailable"), "backend_unavailable"),
            (RuntimeError("malformed response; expected 64 bytes"), "unrecognized_response"),
        )
        for error, expected in cases:
            with self.subTest(expected=expected):
                state, message = classify_device_error(error)
                self.assertEqual(state, expected)
                self.assertTrue(message)

    def test_capacity_summary_preserves_baseline_and_growth_semantics(self):
        rendered = format_capacity_summary(
            total_model_bytes=1024,
            baseline_model_bytes=512,
            backup_timestamp="2026-09-20T01:02:03Z",
            required_candidate_growth_bytes=128,
            metadata_overhead_bytes=16,
        )
        self.assertIn("Total model capacity: 1,024 bytes", rendered)
        self.assertIn("Current baseline from loaded complete backup", rendered)
        self.assertIn("Remaining growth capacity against this snapshot: 512 bytes", rendered)
        self.assertIn("Required candidate growth: 128 bytes", rendered)
        self.assertIn("Candidate metadata overhead: 16 bytes", rendered)
        self.assertNotIn("free space", rendered.casefold())

    def test_no_baseline_does_not_invent_remaining_growth(self):
        rendered = format_capacity_summary(
            total_model_bytes=1024,
            baseline_model_bytes=None,
            backup_timestamp=None,
        )
        self.assertIn("Current baseline from a complete backup: Not evaluated", rendered)
        self.assertIn("Remaining growth capacity: Not evaluated", rendered)
        self.assertNotIn("free space", rendered.casefold())


if __name__ == "__main__":
    unittest.main()
