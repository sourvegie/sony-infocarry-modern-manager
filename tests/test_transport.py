import json
import unittest
from pathlib import Path
from unittest.mock import patch

from infocarry.transport import InfoCarrySession, PyUsbReadOnlyBackend, PyUsbWriteBackend
from infocarry.usb_access import DeviceAccessError


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "infocarry_usb_descriptors.json"


class FakeConfiguration:
    bConfigurationValue = 1


class FakeDevice:
    idVendor = 0x054C
    idProduct = 0x001E

    def __init__(self, active_alt=0):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.device_descriptor = bytes.fromhex(fixture["device_descriptor_hex"])
        self.configuration_descriptor = bytes.fromhex(fixture["configuration_descriptor_hex"])
        self.active_alt = active_alt
        self.set_configurations = []
        self.set_alternates = []

    def ctrl_transfer(self, request_type, request, value, index, data_or_length, timeout):
        if request == 0x06:
            descriptor = (
                self.device_descriptor if value >> 8 == 1 else self.configuration_descriptor
            )
            return descriptor[:data_or_length]
        if request == 0x0A:
            return bytes([self.active_alt])
        raise AssertionError(f"unexpected control request 0x{request:02x}")

    def get_active_configuration(self):
        return FakeConfiguration()

    def set_configuration(self, value):
        self.set_configurations.append(value)

    def set_interface_altsetting(self, *, interface, alternate_setting):
        self.set_alternates.append((interface, alternate_setting))
        self.active_alt = alternate_setting


class FakeBackendDevice:
    def __init__(self):
        self.calls = []

    def ctrl_transfer(self, request_type, request, value, index, data_or_length, timeout):
        self.calls.append(
            ("control", request_type, request, value, index, data_or_length, timeout)
        )
        if isinstance(data_or_length, int):
            return bytes.fromhex("34 12")[:data_or_length]
        return len(data_or_length)

    def read(self, endpoint, length, timeout):
        self.calls.append(("read", endpoint, length, timeout))
        return b"payload"[:length]

    def write(self, endpoint, data, timeout):
        self.calls.append(("write", endpoint, bytes(data), timeout))
        return len(data)


class TransportTests(unittest.TestCase):
    def test_pyusb_backend_exposes_only_read_operations(self):
        device = FakeBackendDevice()
        backend = PyUsbReadOnlyBackend(device)
        self.assertEqual(backend.control_out(0x40, 1, 0, 0, b"header", 1000), 6)
        self.assertEqual(backend.control_in(0xC0, 3, 0, 0, 2, 1000), b"\x34\x12")
        self.assertEqual(backend.bulk_read(0x82, 4, 5000), b"payl")
        self.assertFalse(hasattr(backend, "bulk_write"))
        self.assertEqual(device.calls[0], ("control", 0x40, 1, 0, 0, b"header", 1000))
        self.assertEqual(device.calls[1], ("control", 0xC0, 3, 0, 0, 2, 1000))
        self.assertEqual(device.calls[2], ("read", 0x82, 4, 5000))

    def test_opt_in_write_backend_exposes_bulk_out(self):
        device = FakeBackendDevice()
        backend = PyUsbWriteBackend(device)
        self.assertEqual(backend.bulk_write(0x01, b"candidate", 5000), 9)
        self.assertEqual(device.calls[-1], ("write", 0x01, b"candidate", 5000))

    @patch("infocarry.transport.usb.util.dispose_resources")
    @patch("infocarry.transport.usb.util.release_interface")
    @patch("infocarry.transport.usb.util.claim_interface")
    def test_open_discovers_endpoints_claims_and_releases(
        self, claim_interface, release_interface, dispose_resources
    ):
        device = FakeDevice(active_alt=0)
        with InfoCarrySession.open(device) as session:
            self.assertEqual(session.endpoints.bulk_out, 0x01)
            self.assertEqual(session.endpoints.bulk_in, 0x82)
            self.assertEqual(session.endpoints.max_packet_size, 64)
            self.assertFalse(hasattr(session.backend, "bulk_write"))
        claim_interface.assert_called_once_with(device, 0)
        release_interface.assert_called_once_with(device, 0)
        dispose_resources.assert_called_once_with(device)
        self.assertEqual(device.set_configurations, [])
        self.assertEqual(device.set_alternates, [])

    @patch("infocarry.transport.usb.util.dispose_resources")
    @patch("infocarry.transport.usb.util.release_interface")
    @patch("infocarry.transport.usb.util.claim_interface")
    def test_open_restores_verified_alternate_zero(
        self, claim_interface, release_interface, dispose_resources
    ):
        device = FakeDevice(active_alt=1)
        with InfoCarrySession.open(device):
            pass
        self.assertEqual(device.set_alternates, [(0, 0)])

    @patch("infocarry.transport.usb.util.claim_interface")
    def test_rejects_unrelated_device_before_claim(self, claim_interface):
        device = FakeDevice()
        device.idProduct = 0xFFFF
        with self.assertRaises(DeviceAccessError):
            InfoCarrySession.open(device)
        claim_interface.assert_not_called()

    @patch("infocarry.transport.usb.util.dispose_resources")
    @patch("infocarry.transport.usb.util.release_interface")
    @patch("infocarry.transport.usb.util.claim_interface")
    def test_claim_failure_disposes_without_release(
        self, claim_interface, release_interface, dispose_resources
    ):
        import usb.core

        device = FakeDevice()
        claim_interface.side_effect = usb.core.USBError("claim failed")
        with self.assertRaisesRegex(DeviceAccessError, "failed to open"):
            InfoCarrySession.open(device)
        release_interface.assert_not_called()
        dispose_resources.assert_called_once_with(device)

    @patch("infocarry.transport.usb.util.dispose_resources")
    @patch("infocarry.transport.usb.util.release_interface")
    @patch("infocarry.transport.usb.util.claim_interface")
    def test_close_is_idempotent(
        self, claim_interface, release_interface, dispose_resources
    ):
        session = InfoCarrySession.open(FakeDevice())
        session.close()
        session.close()
        release_interface.assert_called_once()
        dispose_resources.assert_called_once()


if __name__ == "__main__":
    unittest.main()
