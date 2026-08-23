import unittest

from infocarry.view_wrapper import (
    ViewWrapperError,
    calculate_text_view_checksum,
    parse_text_view_wrapper,
    serialize_legacy_prefix,
)


class ViewWrapperTests(unittest.TestCase):
    def test_parses_legacy_unread_wrapper(self):
        raw = bytes.fromhex(
            "01fffffffdffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        )
        wrapper = parse_text_view_wrapper(raw)
        self.assertEqual(wrapper.checksum_be32, 0x01FFFFFF)
        self.assertEqual(wrapper.state_byte_internal_50, 0xFD)
        self.assertEqual(wrapper.field_44_internal_byte, 0xFF)
        self.assertEqual(wrapper.field_46_internal_be16, 0xFFFF)
        self.assertEqual(wrapper.field_48_internal_be32, 0xFFFFFFFF)
        self.assertEqual(wrapper.field_4c_internal_be32, 0xFFFFFFFF)
        self.assertTrue(wrapper.checksum_valid)

    def test_parses_observed_current_view_wrapper(self):
        raw = bytes.fromhex(
            "018cff0dfdff0000007400f0ffffffffffffffffffffffffffffffffffffffff"
        )
        wrapper = parse_text_view_wrapper(raw)
        self.assertEqual(wrapper.checksum_be32, 0x018CFF0D)
        self.assertEqual(wrapper.state_byte_internal_50, 0xFD)
        self.assertEqual(wrapper.field_44_internal_byte, 0xFF)
        self.assertEqual(wrapper.field_46_internal_be16, 0)
        self.assertEqual(wrapper.field_48_internal_be32, 0x007400F0)
        self.assertEqual(wrapper.field_4c_internal_be32, 0xFFFFFFFF)
        self.assertTrue(wrapper.checksum_valid)

    def test_checksum_is_the_complement_of_remaining_words(self):
        raw = bytearray(b"\xff" * 32)
        raw[4] = 0xFD
        raw[6:8] = (0x1234).to_bytes(2, "big")
        raw[8:12] = (0x007400F0).to_bytes(4, "big")
        raw[0:4] = calculate_text_view_checksum(raw).to_bytes(4, "big")
        self.assertEqual(sum(int.from_bytes(raw[i : i + 4], "big") for i in range(0, 32, 4)) & 0xFFFFFFFF, 0xFFFFFFF8)
        self.assertTrue(parse_text_view_wrapper(bytes(raw)).checksum_valid)

    def test_rejects_non_32_byte_prefix(self):
        with self.assertRaises(ViewWrapperError):
            parse_text_view_wrapper(b"\xff" * 16)

    def test_serializes_fixed_legacy_prefix_with_checksum(self):
        source = bytearray(b"\x00" * 0x60)
        source[0x44] = 0x12
        source[0x46:0x48] = (0x3456).to_bytes(2, "little")
        source[0x48:0x4C] = (0x007400F0).to_bytes(4, "little")
        source[0x4C:0x50] = (0x89ABCDEF).to_bytes(4, "little")
        source[0x50] = 0x00

        result = serialize_legacy_prefix(source, 0x20)
        self.assertEqual(result[4:16], bytes.fromhex("00123456007400f089abcdef"))
        self.assertTrue(parse_text_view_wrapper(result).checksum_valid)

    def test_serializes_gated_prefix_without_optional_fields(self):
        source = bytearray(b"\x00" * 0x60)
        source[0x44] = 0x12
        source[0x46:0x48] = b"\x56\x34"
        source[0x50] = 0x01
        result = serialize_legacy_prefix(source, 0x10)
        self.assertEqual(result[4:16], bytes.fromhex("01ffffffffffffffffffffff"))
        self.assertEqual(sum(int.from_bytes(result[i : i + 4], "big") for i in range(0, 16, 4)) & 0xFFFFFFFF, 0xFFFFFFFC)

    def test_rejects_invalid_legacy_prefix_arguments(self):
        with self.assertRaises(ViewWrapperError):
            serialize_legacy_prefix(b"\x00" * 0x50, 0x20)
        with self.assertRaises(ViewWrapperError):
            serialize_legacy_prefix(b"\x00" * 0x60, 0x12)


if __name__ == "__main__":
    unittest.main()
