import json
import unittest

from infocarry.vicdata import VicDataError, xor_vicdata
from infocarry.vicdata_audit import (
    VICDATA_AUDIT_FORMAT,
    build_replacement_audit,
)

try:
    from test_backup_format import make_text_blob
except ModuleNotFoundError:
    from tests.test_backup_format import make_text_blob


class VicDataAuditTests(unittest.TestCase):
    def setUp(self):
        self.encoded = xor_vicdata(make_text_blob(b"original"))

    def test_builds_deterministic_json_safe_audit(self):
        first = build_replacement_audit(self.encoded, 0xC0, b"longer replacement")
        second = build_replacement_audit(self.encoded, 0xC0, b"longer replacement")
        self.assertEqual(first, second)
        json.dumps(first, sort_keys=True)
        self.assertEqual(first["format"], VICDATA_AUDIT_FORMAT)
        self.assertEqual(first["target"]["record_offset_hex"], "0x000000c0")
        self.assertEqual(first["target"]["after_payload_bytes"], 18)
        self.assertTrue(first["target"]["native_prefix_preserved"])
        self.assertTrue(first["invariants"]["record_count_preserved"])
        self.assertTrue(first["invariants"]["paths_preserved"])
        self.assertTrue(first["invariants"]["target_payload_verified"])
        self.assertFalse(first["safety"]["usb_operation_performed"])
        self.assertFalse(first["safety"]["filesystem_output_performed"])
        self.assertFalse(first["regions"]["header"]["byte_identical"])
        self.assertTrue(first["regions"]["trailer"]["byte_identical"])

    def test_rejects_non_bytes_replacement(self):
        with self.assertRaises(VicDataError):
            build_replacement_audit(self.encoded, 0xC0, "text")


if __name__ == "__main__":
    unittest.main()
