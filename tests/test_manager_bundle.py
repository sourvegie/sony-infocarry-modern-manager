import unittest

from infocarry.manager_bundle import (
    ManagerBundleError,
    add_file_bundle,
    delete_file_bundle,
    rename_existing_file_bundle,
)
from infocarry.order_control import parse_order_control
from infocarry.vicdata import decode_vicdata, xor_vicdata
from infocarry.viclv import VicLvEntry, build_viclv, parse_viclv
from infocarry.vicmem import (
    VICMEM_CATEGORY_RECORD_SIZE,
    VicMemCategoryRecordView,
    VicMemSection,
    build_vicmem,
    parse_vicmem,
)

try:
    from test_backup_format import make_text_blob
except ModuleNotFoundError:
    from tests.test_backup_format import make_text_blob


class ManagerBundleTests(unittest.TestCase):
    def test_renames_vicdata_and_exact_vicmem_path_preserving_other_sidecars(self):
        decoded = make_text_blob(b"original")
        encoded = xor_vicdata(decoded)
        old_path = b"root\\memo.txt"
        raw_mem = old_path + b"\x00" + b"\xaa" * (
            VICMEM_CATEGORY_RECORD_SIZE - len(old_path) - 1
        )
        vicmem = build_vicmem(
            (VicMemSection(auxiliary=b"AUX0", records=(raw_mem,)), None, None, None),
            None,
        )
        viclv = build_viclv((VicLvEntry.from_cp932_path(2, "root"),))
        order = b";v1.0\nroot\r\n"

        bundle = rename_existing_file_bundle(
            encoded,
            0xC0,
            "renamed",
            vicmem=vicmem,
            viclv=viclv,
            order=order,
        )
        parsed = decode_vicdata(bundle.vicdata)
        self.assertEqual(parsed.paths[0xC0], ("root", "renamed"))
        mem = parse_vicmem(bundle.vicmem)
        self.assertEqual(
            VicMemCategoryRecordView(mem.sections[0].records[0]).path_bytes,
            b"root\\renamed.txt",
        )
        self.assertEqual(bundle.viclv, viclv)
        self.assertEqual(bundle.order, order)
        self.assertEqual(parse_order_control(bundle.order).to_bytes(), order)

    def test_rejects_directory_target(self):
        with self.assertRaises(ManagerBundleError):
            rename_existing_file_bundle(xor_vicdata(make_text_blob()), 0x40, "renamed")

    def test_adds_template_file_without_guessing_sidecars(self):
        try:
            from test_backup_duplicate import make_nested_blob
        except ModuleNotFoundError:
            from tests.test_backup_duplicate import make_nested_blob
        encoded = xor_vicdata(make_nested_blob(b"source\r\n"))
        order = b";v1.0\nroot\r\n"
        bundle = add_file_bundle(
            encoded,
            0xC0,
            0x140,
            "new.txt",
            b"new content",
            order=order,
        )
        parsed = decode_vicdata(bundle.vicdata)
        target = next(
            record
            for record in parsed.records
            if parsed.paths.get(record.offset) == ("root", "folder", "new.txt")
        )
        self.assertEqual(parsed.payload_parts(target)[1], b"new content")
        self.assertEqual(bundle.order, order)

    def test_deletes_file_and_exact_vicmem_path(self):
        encoded = xor_vicdata(make_text_blob(b"original"))
        old_path = b"root\\memo.txt"
        raw_mem = old_path + b"\x00" + b"\xaa" * (
            VICMEM_CATEGORY_RECORD_SIZE - len(old_path) - 1
        )
        vicmem = build_vicmem(
            (VicMemSection(auxiliary=b"AUX0", records=(raw_mem,)), None, None, None),
            None,
        )
        bundle = delete_file_bundle(encoded, 0xC0, vicmem=vicmem)
        self.assertNotIn(("root", "memo"), decode_vicdata(bundle.vicdata).paths.values())
        self.assertEqual(len(parse_vicmem(bundle.vicmem).sections[0].records), 0)

    def test_rename_and_delete_update_exact_viclv_file_paths(self):
        encoded = xor_vicdata(make_text_blob(b"original"))
        viclv = build_viclv((VicLvEntry.from_cp932_path(2, "root\\memo.txt"),))
        renamed = rename_existing_file_bundle(
            encoded, 0xC0, "renamed", viclv=viclv
        )
        self.assertEqual(
            parse_viclv(renamed.viclv).entries[0].path_cp932,
            "root\\renamed.txt",
        )
        deleted = delete_file_bundle(renamed.vicdata, 0xC0, viclv=renamed.viclv)
        self.assertEqual(parse_viclv(deleted.viclv).entries, ())


if __name__ == "__main__":
    unittest.main()
