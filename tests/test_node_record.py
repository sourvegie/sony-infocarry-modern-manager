import unittest

from infocarry.node_record import NodeRecordError, serialize_internal_node_prefix


def internal_node(name_storage=None):
    source = bytearray(0x40)
    source[0:4] = b"\xe0txt"
    fields = (0x11223344, 0x55667788, 0x99AABBCC, 0xDDEEFF00, 0x01020304)
    for index, value in enumerate(fields):
        offset = 4 + index * 4
        source[offset : offset + 4] = value.to_bytes(4, "little")
    if name_storage is None:
        encoded = "日本語メモ".encode("cp932")
        source[0x18 : 0x18 + len(encoded)] = encoded
    else:
        if len(name_storage) != 0x28:
            raise AssertionError("test name storage must be exactly 40 bytes")
        source[0x18:0x40] = name_storage
    return bytes(source)


class NodeRecordSerializerTests(unittest.TestCase):
    def test_serializes_verified_record_layout(self):
        result = serialize_internal_node_prefix(internal_node())
        self.assertEqual(len(result), 0x40)
        self.assertEqual(result[0:4], b"\xe0txt")
        self.assertEqual(
            result[4:0x18],
            bytes.fromhex(
                "11223344 55667788 99aabbcc ddeeff00 01020304"
            ),
        )
        self.assertEqual(
            result[0x18:].split(b"\x00", 1)[0], "日本語メモ".encode("cp932")
        )

    def test_zeroes_a_dangling_final_legacy_shift_jis_lead_byte(self):
        storage = b"A" * 39 + b"\x82"
        result = serialize_internal_node_prefix(internal_node(storage))
        self.assertEqual(result[0x18:0x3F], b"A" * 39)
        self.assertEqual(result[0x3F], 0)

    def test_preserves_final_byte_when_penultimate_is_also_a_lead_byte(self):
        storage = b"A" * 38 + b"\x82\x82"
        result = serialize_internal_node_prefix(internal_node(storage))
        self.assertEqual(result[0x3E:0x40], b"\x82\x82")

    def test_rejects_wrong_length_and_non_bytes_input(self):
        for value in (b"\x00" * 63, b"\x00" * 65, "not bytes"):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(NodeRecordError):
                    serialize_internal_node_prefix(value)


if __name__ == "__main__":
    unittest.main()
