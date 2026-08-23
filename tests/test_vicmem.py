import unittest

from infocarry.vicmem import (
    VICMEM_CATEGORY_RECORD_SIZE,
    VICMEM_HEADER_SIZE,
    VICMEM_SIGNATURE,
    VICMEM_TAIL_RECORD_SIZE,
    VicMemCategoryRecordView,
    VicMemFormatError,
    VicMemSection,
    VicMemTail,
    VicMemTailRecordView,
    build_vicmem,
    parse_vicmem,
    remove_vicmem_exact_path,
    replace_vicmem_exact_path,
)


class VicMemTests(unittest.TestCase):
    def test_empty_image_round_trip(self):
        data = build_vicmem((None, None, None, None), None)
        self.assertEqual(len(data), VICMEM_HEADER_SIZE)
        self.assertEqual(data[:10], VICMEM_SIGNATURE)
        parsed = parse_vicmem(data)
        self.assertEqual(parsed.header.section_mask, 0)
        self.assertEqual(parsed.sections, (None, None, None, None))
        self.assertIsNone(parsed.tail)
        self.assertEqual(parsed.to_bytes(), data)

    def test_all_sections_and_opaque_records_round_trip(self):
        category_record = bytes(range(256)) + bytes(range(4))
        tail_record = b"tail" + bytes([0xA5]) * (VICMEM_TAIL_RECORD_SIZE - 4)
        sections = (
            VicMemSection(auxiliary=b"AUX0", records=(category_record,)),
            None,
            VicMemSection(auxiliary=b"AUX2", records=(b"B" * VICMEM_CATEGORY_RECORD_SIZE,)),
            None,
        )
        data = build_vicmem(sections, VicMemTail(records=(tail_record,)))
        parsed = parse_vicmem(data)
        self.assertEqual(parsed.header.section_mask, 0b10101)
        self.assertEqual(parsed.sections[0].auxiliary, b"AUX0")
        self.assertEqual(parsed.sections[0].records[0], category_record)
        self.assertEqual(parsed.sections[2].records[0], b"B" * VICMEM_CATEGORY_RECORD_SIZE)
        self.assertEqual(parsed.tail.records, (tail_record,))
        self.assertEqual(parsed.to_bytes(), data)

    def test_preserves_reserved_and_unknown_mask_bits(self):
        data = (
            VICMEM_SIGNATURE
            + b"\x12\x34"
            + (1).to_bytes(4, "little")
            + (0x80000000).to_bytes(4, "little")
        )
        parsed = parse_vicmem(data)
        self.assertEqual(parsed.header.reserved, b"\x12\x34")
        self.assertEqual(parsed.header.section_mask, 0x80000000)
        self.assertEqual(parsed.to_bytes(), data)

    def test_zero_count_selected_sections_are_preserved(self):
        sections = (VicMemSection(auxiliary=b"zero", records=()), None, None, None)
        data = build_vicmem(sections, None, section_mask=1)
        parsed = parse_vicmem(data)
        self.assertEqual(parsed.sections[0].count, 0)
        self.assertEqual(parsed.sections[0].auxiliary, b"zero")
        self.assertEqual(parsed.to_bytes(), data)

    def test_rejects_bad_header_and_partial_payload(self):
        valid = build_vicmem((None, None, None, None), None)
        with self.assertRaises(VicMemFormatError):
            parse_vicmem(b"short")
        with self.assertRaises(VicMemFormatError):
            parse_vicmem(b"bad-sign!!" + valid[10:])
        with self.assertRaises(VicMemFormatError):
            parse_vicmem(VICMEM_SIGNATURE + b"\x00\x00" + (2).to_bytes(4, "little") + b"\x00" * 4)
        with self.assertRaises(VicMemFormatError):
            parse_vicmem(valid + b"x")

        selected_header = (
            VICMEM_SIGNATURE
            + b"\x00\x00"
            + (1).to_bytes(4, "little")
            + (1).to_bytes(4, "little")
        )
        with self.assertRaises(VicMemFormatError):
            parse_vicmem(selected_header + b"\x01\x00\x00\x00")

    def test_rejects_unsafe_counts_and_invalid_record_sizes(self):
        selected_header = (
            VICMEM_SIGNATURE
            + b"\x00\x00"
            + (1).to_bytes(4, "little")
            + (1).to_bytes(4, "little")
        )
        oversized = selected_header + (21).to_bytes(4, "little")
        with self.assertRaises(VicMemFormatError):
            parse_vicmem(oversized)
        with self.assertRaises(VicMemFormatError):
            VicMemSection(auxiliary=b"123", records=())
        with self.assertRaises(VicMemFormatError):
            VicMemSection(auxiliary=b"1234", records=(b"x",))
        with self.assertRaises(VicMemFormatError):
            VicMemTail(records=(b"x",))

    def test_category_record_view_preserves_raw_path_storage(self):
        path = "memo\\テスト.vnw".encode("cp932")
        raw = path + b"\x00" + b"\xa5" * (
            VICMEM_CATEGORY_RECORD_SIZE - len(path) - 1
        )
        view = VicMemCategoryRecordView(raw)
        self.assertEqual(view.raw, raw)
        self.assertEqual(view.path_bytes, path)
        self.assertTrue(view.path_is_terminated)
        self.assertEqual(view.decode_path("cp932"), "memo\\テスト.vnw")

    def test_unterminated_category_path_remains_inspectable(self):
        raw = b"A" * VICMEM_CATEGORY_RECORD_SIZE
        view = VicMemCategoryRecordView(raw)
        self.assertEqual(view.path_bytes, raw)
        self.assertFalse(view.path_is_terminated)

    def test_tail_record_view_exposes_only_verified_fields(self):
        path = b"memo\\bookmark.vnw"
        path_storage = path + b"\x00" + b"\xcc" * (
            VICMEM_CATEGORY_RECORD_SIZE - len(path) - 1
        )
        raw = (
            path_storage
            + (0x11223344).to_bytes(4, "little")
            + (40).to_bytes(4, "little")
        )
        view = VicMemTailRecordView(raw)
        self.assertEqual(view.raw, raw)
        self.assertEqual(view.path_bytes, path)
        self.assertTrue(view.path_is_terminated)
        self.assertEqual(view.field_3, 0x11223344)
        self.assertEqual(view.rendered_line_position, 40)

    def test_replaces_exact_category_and_tail_paths_preserving_unknown_bytes(self):
        old = b"root\\memo.txt"
        category = old + b"\x00" + b"\xa5" * (VICMEM_CATEGORY_RECORD_SIZE - len(old) - 1)
        tail_path = old + b"\x00" + b"\xcc" * (VICMEM_CATEGORY_RECORD_SIZE - len(old) - 1)
        tail = tail_path + (0x11223344).to_bytes(4, "little") + (40).to_bytes(4, "little")
        data = build_vicmem(
            (VicMemSection(auxiliary=b"AUX0", records=(category,)), None, None, None),
            VicMemTail(records=(tail,)),
        )
        parsed = parse_vicmem(data)
        rebuilt = replace_vicmem_exact_path(parsed, "root\\memo.txt", "root\\renamed.txt")
        result = parse_vicmem(rebuilt.to_bytes())
        self.assertEqual(
            VicMemCategoryRecordView(result.sections[0].records[0]).path_bytes,
            b"root\\renamed.txt",
        )
        self.assertEqual(
            VicMemTailRecordView(result.tail.records[0]).path_bytes,
            b"root\\renamed.txt",
        )
        self.assertEqual(result.tail.records[0][-8:], tail[-8:])
        self.assertNotEqual(result.to_bytes(), data)

    def test_record_views_reject_wrong_sizes(self):
        with self.assertRaises(VicMemFormatError):
            VicMemCategoryRecordView(b"short")
        with self.assertRaises(VicMemFormatError):
            VicMemTailRecordView(b"short")

    def test_removes_exact_category_and_tail_paths(self):
        old = b"root\\memo.txt"
        category = old + b"\x00" + b"\xa5" * (VICMEM_CATEGORY_RECORD_SIZE - len(old) - 1)
        other = b"root\\keep.txt" + b"\x00" + b"\xbb" * (
            VICMEM_CATEGORY_RECORD_SIZE - len(b"root\\keep.txt") - 1
        )
        tail = (
            old
            + b"\x00"
            + b"\xcc" * (VICMEM_CATEGORY_RECORD_SIZE - len(old) - 1)
            + b"\x00" * 8
        )
        data = build_vicmem(
            (VicMemSection(auxiliary=b"AUX0", records=(category, other)), None, None, None),
            VicMemTail(records=(tail,)),
        )
        rebuilt = parse_vicmem(data)
        result = parse_vicmem(remove_vicmem_exact_path(rebuilt, "root\\memo.txt").to_bytes())
        self.assertEqual(len(result.sections[0].records), 1)
        self.assertEqual(result.sections[0].records[0], other)
        self.assertEqual(len(result.tail.records), 0)


if __name__ == "__main__":
    unittest.main()
