import json
from pathlib import Path
import unittest

from infocarry.capacity_evidence import (
    NATIVE_CAPACITY_EVIDENCE_SOURCE,
    NATIVE_CAPACITY_FIELD_OFFSET,
    NativeCapacityEvidenceError,
    NativeCapacityResponse,
)
from infocarry.device_info import RawInfoResponse


class NativeCapacityEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = json.loads(
            (Path(__file__).parent / "fixtures" / "infocarry_info_responses.json").read_text(
                encoding="utf-8"
            )
        )
        cls.raw = bytes.fromhex(fixture["hardware"]["response_hex"])

    def _response(self, data=None):
        return RawInfoResponse(
            command=0x0019,
            kind="hardware",
            data=self.raw if data is None else data,
        )

    def test_parsed_response_binds_raw_hash_and_total_limit(self):
        response = NativeCapacityResponse.from_hardware_response(
            self._response(), device_identity=(0x054C, 0x001E)
        )
        self.assertEqual(response.capacity_limit_bytes, 3_145_728)
        self.assertEqual(response.field_offset, NATIVE_CAPACITY_FIELD_OFFSET)
        self.assertEqual(response.evidence_source, NATIVE_CAPACITY_EVIDENCE_SOURCE)
        self.assertEqual(len(response.raw_response), 64)
        evidence = response.bind_model_lengths(2_050_848, 2_051_132)
        self.assertEqual(evidence.remaining_growth_bytes, 1_094_880)
        self.assertEqual(evidence.to_dict()["raw_response_sha256"], response.raw_response_sha256)

    def test_wrong_device_is_rejected(self):
        with self.assertRaisesRegex(NativeCapacityEvidenceError, "wrong device"):
            NativeCapacityResponse.from_hardware_response(
                self._response(), device_identity=(0x054C, 0x001F)
            )

    def test_truncated_or_wrong_command_response_is_rejected(self):
        with self.assertRaises(NativeCapacityEvidenceError):
            NativeCapacityResponse.from_hardware_response(
                self._response(self.raw[:-1]), device_identity=(0x054C, 0x001E)
            )
        with self.assertRaisesRegex(NativeCapacityEvidenceError, "0x0019"):
            NativeCapacityResponse.from_hardware_response(
                RawInfoResponse(0x0018, "configuration", self.raw),
                device_identity=(0x054C, 0x001E),
            )

    def test_tampered_hash_or_capacity_value_is_rejected(self):
        with self.assertRaisesRegex(NativeCapacityEvidenceError, "hash"):
            NativeCapacityResponse(
                device_identity=(0x054C, 0x001E),
                raw_response=self.raw,
                raw_response_sha256="0" * 64,
                response_command=0x0019,
                field_offset=0x08,
                capacity_limit_bytes=3_145_728,
            )
        with self.assertRaisesRegex(NativeCapacityEvidenceError, "differs"):
            NativeCapacityResponse(
                device_identity=(0x054C, 0x001E),
                raw_response=self.raw,
                raw_response_sha256=__import__("hashlib").sha256(self.raw).hexdigest(),
                response_command=0x0019,
                field_offset=0x08,
                capacity_limit_bytes=4_194_304,
            )

    def test_model_boundary_and_one_byte_over_fail_closed(self):
        response = NativeCapacityResponse.from_hardware_response(
            self._response(), device_identity=(0x054C, 0x001E)
        )
        response.bind_model_lengths(3_145_728 - 100, 3_145_728)
        with self.assertRaisesRegex(NativeCapacityEvidenceError, "exceeds"):
            response.bind_model_lengths(3_145_728 - 100, 3_145_728 + 1)


if __name__ == "__main__":
    unittest.main()
