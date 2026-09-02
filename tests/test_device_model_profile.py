from dataclasses import replace
import unittest

from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.device_info import RawInfoResponse
from infocarry.device_model_profile import (
    CapacityObservation,
    DeviceModelProfileError,
    MODEL_STATUS_UNCHARACTERIZED,
    VNW_V10_PROFILE,
    VNW_V15_PROFILE,
    reviewed_device_model_profile,
    validate_actionable_session,
)


class DeviceModelProfileTests(unittest.TestCase):
    @staticmethod
    def _native_evidence(baseline=700, candidate=800):
        raw = b"\x00" * 64
        raw = bytearray(raw)
        raw[0:2] = (237).to_bytes(2, "big")
        raw[2:4] = (320).to_bytes(2, "big")
        raw[8:12] = (3145728).to_bytes(4, "big")
        response = NativeCapacityResponse.from_hardware_response(
            RawInfoResponse(0x0019, "hardware", bytes(raw)),
            device_identity=(0x054C, 0x001E),
        )
        return response.bind_model_lengths(baseline, candidate)

    def _capacity(self, **overrides):
        values = {
            "native_evidence": self._native_evidence(),
            "model_profile_id": VNW_V15_PROFILE.profile_id,
            "capacity_response_sha256": self._native_evidence().raw_response_sha256,
            "total_model_bytes": 3145728,
            "baseline_model_bytes": 700,
            "candidate_model_bytes": 800,
            "candidate_growth_bytes": 100,
            "remaining_growth_bytes": 3145028,
            "remaining_after_transfer_bytes": 3144928,
        }
        values.update(overrides)
        return CapacityObservation(**values)

    def test_v15_is_the_only_verified_transfer_profile(self):
        self.assertEqual(VNW_V15_PROFILE.usb_identity, ("0x054c", "0x001e"))
        self.assertTrue(VNW_V15_PROFILE.transfer_capable)
        self.assertEqual(VNW_V15_PROFILE.capacity_query, "0x0019")
        self.assertEqual(
            VNW_V15_PROFILE.capacity_interpreter,
            "64-byte response; big-endian +0x08 total candidate-model capacity",
        )
        self.assertFalse(VNW_V10_PROFILE.transfer_capable)
        self.assertEqual(VNW_V10_PROFILE.capability_status, MODEL_STATUS_UNCHARACTERIZED)
        self.assertIsNone(VNW_V10_PROFILE.usb_identity)
        self.assertIsNone(VNW_V10_PROFILE.capacity_query)

    def test_unknown_model_profile_fails_closed(self):
        with self.assertRaises(DeviceModelProfileError):
            reviewed_device_model_profile("sony-vnw-unknown")

    def test_each_session_must_rediscover_exactly_one_actionable_model(self):
        first = validate_actionable_session([reviewed_device_model_profile("sony-vnw-v15")])
        second = validate_actionable_session([reviewed_device_model_profile("sony-vnw-v15")])
        self.assertIs(first, second)
        for detected in ([], [VNW_V15_PROFILE, VNW_V15_PROFILE], [VNW_V10_PROFILE]):
            with self.subTest(detected=detected):
                with self.assertRaises(DeviceModelProfileError):
                    validate_actionable_session(detected)

    def test_capacity_observation_enforces_session_arithmetic(self):
        native = self._native_evidence(700, 850)
        observation = self._capacity(
            native_evidence=native,
            capacity_response_sha256=native.raw_response_sha256,
            candidate_model_bytes=850,
            candidate_growth_bytes=150,
            remaining_growth_bytes=3145028,
            remaining_after_transfer_bytes=3144878,
        )
        self.assertEqual(observation.remaining_after_transfer_bytes, 3144878)
        self.assertEqual(observation.remaining_growth_bytes, 3145028)
        with self.assertRaises(DeviceModelProfileError):
            self._capacity(
                candidate_model_bytes=850,
                candidate_growth_bytes=149,
                remaining_growth_bytes=3145028,
                remaining_after_transfer_bytes=3144878,
            )
        with self.assertRaises(DeviceModelProfileError):
            self._capacity(remaining_growth_bytes=3145027)

    def test_v10_capacity_semantics_cannot_be_invented(self):
        with self.assertRaises(DeviceModelProfileError):
            self._capacity(model_profile_id=VNW_V10_PROFILE.profile_id)

        with self.assertRaises(DeviceModelProfileError):
            self._capacity(native_evidence=object())

    def test_v15_profile_cannot_be_rebound_to_another_usb_or_capacity_rule(self):
        with self.assertRaises(DeviceModelProfileError):
            replace(
                VNW_V15_PROFILE,
                usb_identity=("0x054c", "0x001e"),
                capacity_query="0x0024",
            )
        with self.assertRaises(DeviceModelProfileError):
            replace(VNW_V15_PROFILE, usb_identity=("0x054c", "0x0099"))


if __name__ == "__main__":
    unittest.main()
