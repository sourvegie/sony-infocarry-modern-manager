import unittest
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from infocarry.device_info import (
    COMMAND_CONFIGURATION_INFO,
    COMMAND_HARDWARE_INFO,
    DeviceInfoClient,
    parse_configuration_info,
    parse_hardware_info,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "infocarry_info_responses.json"


class FakeInfoBackend:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def control_out(self, request_type, request, value, index, data, timeout_ms):
        self.calls.append(("out", request_type, request, value, index, data, timeout_ms))
        return len(data)

    def control_in(self, request_type, request, value, index, length, timeout_ms):
        self.calls.append(("in", request_type, request, value, index, length, timeout_ms))
        return b"\x00\x00"

    def bulk_read(self, endpoint, length, timeout_ms):
        self.calls.append(("bulk", endpoint, length, timeout_ms))
        return self.payload[:length]


class DeviceInfoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def make_client(self, payload):
        backend = FakeInfoBackend(payload)
        session = SimpleNamespace(
            backend=backend,
            endpoints=SimpleNamespace(bulk_in=0x82),
        )
        return DeviceInfoClient(session), backend

    def test_configuration_query_is_exact_and_allowlisted(self):
        payload = bytes(range(64))
        client, backend = self.make_client(payload)
        response = client.read_configuration()
        self.assertEqual(response.command, COMMAND_CONFIGURATION_INFO)
        self.assertEqual(response.kind, "configuration")
        self.assertEqual(response.data, payload)
        self.assertEqual(backend.calls[0][5], bytes.fromhex("18 00 40 00 00 00"))
        self.assertEqual(backend.calls[1][2], 3)
        self.assertEqual(backend.calls[2], ("bulk", 0x82, 64, 5000))
        self.assertEqual(backend.calls[3][2], 4)

    def test_hardware_query_is_exact_and_allowlisted(self):
        payload = bytes(reversed(range(64)))
        client, backend = self.make_client(payload)
        response = client.read_hardware()
        self.assertEqual(response.command, COMMAND_HARDWARE_INFO)
        self.assertEqual(response.kind, "hardware")
        self.assertEqual(response.data, payload)
        self.assertEqual(backend.calls[0][5], bytes.fromhex("19 00 40 00 00 00"))

    def test_observed_response_fixtures_match_preserved_hashes(self):
        for fixture in self.fixture.values():
            data = bytes.fromhex(fixture["response_hex"])
            self.assertEqual(len(data), 64)
            self.assertEqual(hashlib.sha256(data).hexdigest(), fixture["sha256"])

    def test_configuration_parser_preserves_unknown_settings(self):
        data = bytes.fromhex(self.fixture["configuration"]["response_hex"])
        parsed = parse_configuration_info(data)
        self.assertEqual(parsed.leading_value, 11)
        self.assertEqual(parsed.settings_hex, "00 01 04 03 02 00 00 00 00 00 01")
        self.assertEqual(parsed.reserved_hex, "00 " * 51 + "00")

    def test_hardware_parser_decodes_verified_big_endian_fields(self):
        data = bytes.fromhex(self.fixture["hardware"]["response_hex"])
        parsed = parse_hardware_info(data)
        self.assertEqual(parsed.display_width_pixels, 240)
        self.assertEqual(parsed.display_height_pixels, 320)
        self.assertEqual(parsed.field_04_be16, 12)
        self.assertEqual(parsed.field_06_be16, 12)
        self.assertEqual(parsed.field_08_be32, 0x00300000)
        self.assertEqual(parsed.field_10_be32, 0x00004000)
        self.assertEqual(parsed.field_14_be32, 0x00400000)


if __name__ == "__main__":
    unittest.main()
