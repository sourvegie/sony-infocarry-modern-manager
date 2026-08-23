import json
import unittest
from pathlib import Path

from infocarry.descriptors import (
    DescriptorError,
    parse_configuration_descriptor,
    parse_descriptor_set,
    parse_device_descriptor,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "infocarry_usb_descriptors.json"


class DescriptorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.device_data = bytes.fromhex(fixture["device_descriptor_hex"])
        cls.configuration_data = bytes.fromhex(fixture["configuration_descriptor_hex"])
        cls.active_alt = fixture["active_alternate_setting"]

    def test_device_descriptor(self):
        descriptor = parse_device_descriptor(self.device_data)
        self.assertEqual(descriptor.vendor_id, 0x054C)
        self.assertEqual(descriptor.product_id, 0x001E)
        self.assertEqual(descriptor.usb_version_bcd, 0x0100)
        self.assertEqual(descriptor.endpoint_zero_max_packet_size, 8)
        self.assertEqual(descriptor.configuration_count, 1)

    def test_configuration_and_alternate_settings(self):
        descriptor = parse_configuration_descriptor(self.configuration_data)
        self.assertEqual(descriptor.total_length, 55)
        self.assertEqual(descriptor.interface_count, 1)
        self.assertEqual(descriptor.max_power_ma, 100)
        self.assertEqual(len(descriptor.interfaces), 2)

        alt_zero, alt_one = descriptor.interfaces
        self.assertEqual((alt_zero.number, alt_zero.alternate_setting), (0, 0))
        self.assertEqual(
            [(ep.address, ep.direction, ep.transfer_type_name, ep.max_packet_size) for ep in alt_zero.endpoints],
            [(0x01, "out", "bulk", 64), (0x82, "in", "bulk", 64)],
        )
        self.assertEqual((alt_one.number, alt_one.alternate_setting), (0, 1))
        self.assertEqual(
            [(ep.address, ep.direction, ep.transfer_type_name, ep.max_packet_size) for ep in alt_one.endpoints],
            [(0x81, "in", "bulk", 64), (0x02, "out", "bulk", 64)],
        )

    def test_descriptor_set_records_active_setting(self):
        descriptors = parse_descriptor_set(
            self.device_data, self.configuration_data, self.active_alt
        )
        self.assertEqual(descriptors.active_alternate_setting, 0)

    def test_rejects_truncated_device_descriptor(self):
        with self.assertRaises(DescriptorError):
            parse_device_descriptor(self.device_data[:-1])

    def test_rejects_inconsistent_configuration_length(self):
        damaged = bytearray(self.configuration_data)
        damaged[2:4] = (56).to_bytes(2, "little")
        with self.assertRaises(DescriptorError):
            parse_configuration_descriptor(bytes(damaged))


if __name__ == "__main__":
    unittest.main()
