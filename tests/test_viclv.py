import unittest

from infocarry.viclv import (
    VICLV_ENTRY_SIZE,
    VICLV_HEADER_SIZE,
    VICLV_SIGNATURE,
    VicLvEntry,
    VicLvFormatError,
    build_viclv,
    parse_viclv,
    remove_viclv_exact_path,
    replace_viclv_exact_path,
)


class VicLvTests(unittest.TestCase):
    def test_build_parse_and_exact_round_trip(self):
        entries = (
            VicLvEntry.from_path_bytes(1, b"manual\\first.txt"),
            VicLvEntry.from_cp932_path(2, "簡易マニュアル\\各部.txt"),
        )
        data = build_viclv(entries)

        self.assertEqual(data[:10], VICLV_SIGNATURE)
        self.assertEqual(data[10:12], b"\x00\x00")
        self.assertEqual(data[12:16], (1).to_bytes(4, "little"))
        self.assertEqual(len(data), VICLV_HEADER_SIZE + 2 * VICLV_ENTRY_SIZE)

        parsed = parse_viclv(data)
        self.assertEqual(tuple(parsed.entries), entries)
        self.assertEqual(parsed.entries[0].path_bytes, b"manual\\first.txt")
        self.assertEqual(parsed.entries[1].path_cp932, "簡易マニュアル\\各部.txt")
        self.assertEqual(parsed.to_bytes(), data)

    def test_parser_preserves_reserved_and_nonzero_padding(self):
        field = b"a\x00" + b"\xaa" * 258
        data = (
            VICLV_SIGNATURE
            + b"\x12\x34"
            + (1).to_bytes(4, "little")
            + bytes((7,))
            + field
        )
        parsed = parse_viclv(data)
        self.assertEqual(parsed.header.reserved, b"\x12\x34")
        self.assertEqual(parsed.entries[0].category, 7)
        self.assertEqual(parsed.entries[0].path_bytes, b"a")
        self.assertEqual(parsed.to_bytes(), data)

    def test_empty_path_represents_legacy_base_directory_entry(self):
        entry = VicLvEntry.from_path_bytes(1, b"")
        self.assertEqual(entry.path_field, bytes(260))
        self.assertEqual(parse_viclv(build_viclv((entry,))).entries[0], entry)

    def test_rejects_invalid_header_length_and_partial_entry(self):
        with self.assertRaises(VicLvFormatError):
            parse_viclv(b"short")
        with self.assertRaises(VicLvFormatError):
            parse_viclv(b"bad-sign!!" + b"\x00\x00" + (1).to_bytes(4, "little"))
        with self.assertRaises(VicLvFormatError):
            parse_viclv(VICLV_SIGNATURE + b"\x00\x00" + (2).to_bytes(4, "little"))
        with self.assertRaises(VicLvFormatError):
            parse_viclv(VICLV_SIGNATURE + b"\x00\x00" + (1).to_bytes(4, "little") + b"x")

    def test_rejects_unterminated_or_oversized_generated_path(self):
        with self.assertRaises(VicLvFormatError):
            VicLvEntry(category=1, path_field=b"x" * 260)
        with self.assertRaises(VicLvFormatError):
            VicLvEntry.from_path_bytes(1, b"x" * 260)
        with self.assertRaises(VicLvFormatError):
            VicLvEntry.from_path_bytes(1, b"a\x00b")

    def test_exact_path_mutations_preserve_categories_and_padding(self):
        field = b"root\\old.txt\x00" + b"\xaa" * (260 - len(b"root\\old.txt") - 1)
        image = parse_viclv(
            build_viclv(
                (
                    VicLvEntry(category=2, path_field=field),
                    VicLvEntry.from_cp932_path(1, "root"),
                ),
                reserved=b"\x12\x34",
            )
        )
        renamed = replace_viclv_exact_path(image, "root\\old.txt", "root\\new.txt")
        self.assertEqual(renamed.entries[0].category, 2)
        self.assertEqual(renamed.entries[0].path_bytes, b"root\\new.txt")
        self.assertEqual(renamed.entries[0].path_field[len(b"root\\new.txt") + 1 :],
                         field[len(b"root\\old.txt") + 1 :])
        self.assertEqual(renamed.entries[1], image.entries[1])
        removed = remove_viclv_exact_path(renamed, "root\\new.txt")
        self.assertEqual(len(removed.entries), 1)
        self.assertEqual(removed.entries[0], image.entries[1])
        self.assertEqual(removed.header, image.header)

    def test_exact_path_mutations_reject_invalid_paths(self):
        image = parse_viclv(build_viclv((VicLvEntry.from_path_bytes(1, b"a"),)))
        with self.assertRaises(VicLvFormatError):
            replace_viclv_exact_path(image, "", "b")
        with self.assertRaises(VicLvFormatError):
            replace_viclv_exact_path(image, "a", "\x00")


if __name__ == "__main__":
    unittest.main()
