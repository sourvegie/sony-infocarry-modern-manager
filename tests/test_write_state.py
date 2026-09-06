from types import SimpleNamespace
import unittest

from infocarry.write_state import (
    StateSerializationError,
    rebase_fixed_state_responses,
    serialize_grouped_values_state,
    serialize_offset_list_ranges,
    serialize_offset_list_state,
)


def offset_state(count=2, first=0x10203040):
    return SimpleNamespace(
        count=count,
        value_04_be16=0x1234,
        value_06_be16=0xABCD,
        record_offsets=tuple(first + index for index in range(count)),
    )


class FixedWriteStateSerializerTests(unittest.TestCase):
    def test_rebase_changes_only_counted_offsets_and_bookmark_group_dword_one(self):
        ranges = []
        for index in range(4):
            raw = bytearray([0xA0 + index] * 64)
            raw[0:8] = b"\x00" * 8
            if index == 0:
                raw[0:4] = (2).to_bytes(4, "big")
                raw[8:12] = (0x80).to_bytes(4, "big")
                raw[12:16] = (0x140).to_bytes(4, "big")
            ranges.append(bytes(raw))
        grouped = bytearray([0xEE] * 64)
        values = (0x140, 0xC00, 0, 0x14, 0xFFF101C5, 0, 0, 0, 0, 0)
        grouped[:40] = b"".join(value.to_bytes(4, "big") for value in values)
        rebased_ranges, rebased_grouped = rebase_fixed_state_responses(
            ranges, bytes(grouped), insertion_offset=0x100, metadata_delta=0x140
        )
        self.assertEqual(rebased_ranges[0][8:16], (0x80).to_bytes(4, "big") + (0x280).to_bytes(4, "big"))
        self.assertEqual(rebased_ranges[0][16:], ranges[0][16:])
        self.assertEqual(rebased_ranges[1:], tuple(ranges[1:]))
        self.assertEqual(rebased_grouped[:4], (0x280).to_bytes(4, "big"))
        self.assertEqual(rebased_grouped[4:], bytes(grouped[4:]))

    def test_offset_list_is_big_endian_and_zero_fills_unused_tail(self):
        result = serialize_offset_list_state(offset_state())
        expected = (
            b"\x00\x00\x00\x02"
            b"\x12\x34\xab\xcd"
            b"\x10\x20\x30\x40\x10\x20\x30\x41"
            + b"\x00" * (0x40 - 16)
        )
        self.assertEqual(result, expected)
        self.assertEqual(len(result), 0x40)

    def test_four_offset_records_form_the_0x100_first_range(self):
        responses = [
            offset_state(count=index, first=index * 0x100) for index in range(4)
        ]
        result = serialize_offset_list_ranges(responses)
        self.assertEqual(len(result), 0x100)
        for index, response in enumerate(responses):
            start = index * 0x40
            self.assertEqual(result[start : start + 0x40], serialize_offset_list_state(response))

    def test_grouped_values_are_ten_big_endian_dwords_and_zero_tail(self):
        response = SimpleNamespace(groups=(tuple(range(5)), tuple(5 + index for index in range(5))))
        result = serialize_grouped_values_state(response)
        expected = b"".join(value.to_bytes(4, "big") for value in range(10))
        self.assertEqual(result, expected + b"\x00" * 24)
        self.assertEqual(len(result), 0x40)

    def test_rejects_shape_and_numeric_overflow(self):
        with self.assertRaises(StateSerializationError):
            serialize_offset_list_state(offset_state(count=14))
        with self.assertRaises(StateSerializationError):
            serialize_offset_list_state(SimpleNamespace(
                count=1,
                value_04_be16=0,
                value_06_be16=0,
                record_offsets=(),
            ))
        with self.assertRaises(StateSerializationError):
            serialize_offset_list_ranges([offset_state()] * 3)
        with self.assertRaises(StateSerializationError):
            serialize_grouped_values_state(SimpleNamespace(groups=((1, 2, 3, 4, 5),)))
        with self.assertRaises(StateSerializationError):
            serialize_grouped_values_state(
                SimpleNamespace(
                    groups=((1, 2, 3, 4, 5), (6, 7, 8, 9, 0x100000000))
                )
            )


if __name__ == "__main__":
    unittest.main()
