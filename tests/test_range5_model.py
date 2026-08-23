import unittest

from infocarry.range5_model import (
    RANGE5_LENGTH,
    Range5SerializationError,
    recover_range5_source,
    serialize_range5_model,
)


class Range5ModelSerializerTests(unittest.TestCase):
    def test_helper_layout_is_reproduced_byte_for_byte(self):
        source = bytes(range(RANGE5_LENGTH))
        expected = bytes(
            [
                0, 1, 2, 3,
                4, 5, 6, 7,
                8,
                9, 10, 11, 12, 13,
                15, 14,
                17, 16,
                18, 19,
                23, 22, 21, 20,
                27, 26, 25, 24,
                31, 30, 29, 28,
                35, 34, 33, 32,
                39, 38, 37, 36,
                43, 42, 41, 40,
                47, 46, 45, 44,
                51, 50, 49, 48,
                55, 54, 53, 52,
                59, 58, 57, 56,
                60, 61, 62, 63,
            ]
        )
        result = serialize_range5_model(source)
        self.assertEqual(len(result), RANGE5_LENGTH)
        self.assertEqual(result, expected)

    def test_source_is_not_mutated_and_tail_is_deterministic(self):
        source = bytearray([0xA5] * RANGE5_LENGTH)
        original = bytes(source)
        result = serialize_range5_model(source)
        self.assertEqual(bytes(source), original)
        self.assertEqual(result[-4:], bytes(source[-4:]))

    def test_rejects_non_bytes_like_and_wrong_length(self):
        for value in ("x", None, 4, b"short", b"x" * (RANGE5_LENGTH + 1)):
            with self.subTest(value=value):
                with self.assertRaises(Range5SerializationError):
                    serialize_range5_model(value)

    def test_recovers_all_source_fields_at_fixed_length(self):
        source = bytearray(range(RANGE5_LENGTH))
        source[0x0D] = 0xA1
        source[0x3A:0x3C] = b"XY"
        wire = serialize_range5_model(source)

        recovery = recover_range5_source(wire)
        self.assertTrue(recovery.round_trip)
        self.assertEqual(recovery.unknown_offsets, ())
        self.assertEqual(recovery.source[0x0D], 0xA1)
        self.assertEqual(recovery.source[0x3A:0x3C], b"XY")
        self.assertEqual(serialize_range5_model(recovery.source), wire)

    def test_rejects_wrong_recovery_length(self):
        with self.assertRaises(Range5SerializationError):
            recover_range5_source(b"\x00" * (RANGE5_LENGTH - 1))

    def test_recovered_manager_blocks_round_trip(self):
        captured = (
            "696e666f436172727920322e303001000040ffff00000020001f6b2768d431b7"
            "00000000000000000000004000005ac000005b00001f1024001f6b28ffffffff",
            "696e666f436172727920322e303001000040ffff00000020001f77c7415167be"
            "00000000000000000000004000005b0000005b40001f1c84001f77c8ffffffff",
        )
        for wire_hex in captured:
            with self.subTest(wire_hex=wire_hex):
                recovery = recover_range5_source(bytes.fromhex(wire_hex))
                self.assertEqual(recovery.unknown_offsets, ())
                self.assertTrue(recovery.round_trip)
                self.assertEqual(
                    serialize_range5_model(recovery.source), bytes.fromhex(wire_hex)
                )
                source = recovery.source
                aggregate_m = int.from_bytes(source[0x38:0x3C], "little")
                record_bytes = int.from_bytes(source[0x2C:0x30], "little")
                self.assertEqual(
                    source[0x18:0x1C], (aggregate_m - 1).to_bytes(4, "little")
                )
                self.assertEqual(
                    source[0x28:0x2C], (0x40).to_bytes(4, "little")
                )
                self.assertEqual(
                    source[0x30:0x34], (record_bytes + 0x40).to_bytes(4, "little")
                )


if __name__ == "__main__":
    unittest.main()
