import hashlib
import unittest

from infocarry.backup_format import calculate_backup_checksum, parse_backup_blob
from infocarry.backup_repack import (
    BackupRepackError,
    delete_existing_file,
    rename_existing_record,
    repack_existing_records,
)

try:
    from test_backup_format import make_record, make_text_blob
except ModuleNotFoundError:
    from tests.test_backup_format import make_record, make_text_blob


def make_aligned_delete_blob(payload=b"abcde"):
    """Build a small fixture for the observed native delete alignment rules."""

    records = b"".join(
        (
            make_record(0xD0, "", 0x40, 0x100, "root"),
            make_record(0xD0, "", 0x40, 0x80, ".."),
            make_record(0xD0, "", 0x100, 0x80, "folder"),
            make_record(0xE0, "txt", 0, len(payload), "target", 0x200),
            make_record(0xD0, "", 0xC0, 0x100, ".."),
            make_record(0xE0, "txt", 40, 8, "source", 0x200),
            make_record(0xD0, "", 0xC0, 0x80, ".."),
        )
    )
    content = (
        b"\xff" * 32
        + payload
        + b"\xff" * (-(32 + len(payload)) % 4)
        + b"\xff" * 32
        + b"source!!"
    )
    content_start = 0x40 + len(records)
    content += b"\xff" * (-(content_start + len(content)) % 4)
    total_length = content_start + len(content) + 4
    header = bytearray(64)
    header[:14] = b"infoCarry 2.00"
    header[14:16] = b"\x01\x00"
    header[16:18] = (64).to_bytes(2, "big")
    header[0x14:0x18] = (0x20).to_bytes(4, "big")
    header[0x18:0x1C] = (total_length - 1).to_bytes(4, "big")
    header[0x28:0x2C] = (0x40).to_bytes(4, "big")
    header[0x2C:0x30] = len(records).to_bytes(4, "big")
    header[0x30:0x34] = content_start.to_bytes(4, "big")
    header[0x34:0x38] = len(content).to_bytes(4, "big")
    header[0x38:0x3C] = total_length.to_bytes(4, "big")
    header[0x3C:0x40] = b"\xff" * 4
    blob = bytearray(bytes(header) + records + content + b"\xff" * 4)
    blob[0x1C:0x20] = calculate_backup_checksum(blob).to_bytes(4, "big")
    return bytes(blob)


class BackupRepackTests(unittest.TestCase):
    def setUp(self):
        self.blob = make_text_blob(b"original")
        self.parsed = parse_backup_blob(self.blob)
        self.file_offset = 0xC0

    def test_empty_replacement_is_byte_identical(self):
        self.assertIs(repack_existing_records(self.parsed, {}), self.blob)

    def test_replaces_existing_payload_and_recomputes_checksum(self):
        rebuilt = repack_existing_records(self.parsed, {self.file_offset: b"changed"})
        parsed = parse_backup_blob(rebuilt)
        record = parsed.record_at(self.file_offset)
        _, payload = parsed.payload_parts(record)
        self.assertEqual(payload, b"changed")
        self.assertEqual(
            calculate_backup_checksum(rebuilt),
            int.from_bytes(rebuilt[0x1C:0x20], "big"),
        )
        self.assertEqual(parsed.paths, self.parsed.paths)
        self.assertNotEqual(
            hashlib.sha256(rebuilt).digest(), hashlib.sha256(self.blob).digest()
        )

    def test_length_change_updates_offsets_and_preserves_other_metadata(self):
        rebuilt = repack_existing_records(
            self.parsed, {self.file_offset: b"a longer replacement payload"}
        )
        parsed = parse_backup_blob(rebuilt)
        record = parsed.record_at(self.file_offset)
        _, payload = parsed.payload_parts(record)
        original = self.parsed.record_at(self.file_offset)
        self.assertEqual(payload, b"a longer replacement payload")
        self.assertEqual(record.flag, original.flag)
        self.assertEqual(record.extension, original.extension)
        self.assertEqual(record.timestamp_be32, original.timestamp_be32)
        self.assertEqual(record.field_10_be32, original.field_10_be32)
        self.assertEqual(record.field_14_be32, original.field_14_be32)

    def test_renames_existing_record_without_changing_payload_or_tree_shape(self):
        rebuilt = rename_existing_record(self.parsed, self.file_offset, "renamed")
        parsed = parse_backup_blob(rebuilt)
        record = parsed.record_at(self.file_offset)
        _, payload = parsed.payload_parts(record)
        self.assertEqual(record.name, "renamed")
        self.assertEqual(parsed.paths[self.file_offset], ("root", "renamed"))
        self.assertEqual(payload, b"original")
        self.assertEqual(parsed.header.stored_checksum, calculate_backup_checksum(rebuilt))
        self.assertEqual(len(parsed.records), len(self.parsed.records))
        self.assertEqual(set(parsed.paths) , set(self.parsed.paths))

    def test_rename_rejects_invalid_or_colliding_names(self):
        for name in ("", "bad/name", "..", "日本語\x00"):
            with self.subTest(name=name), self.assertRaises(BackupRepackError):
                rename_existing_record(self.parsed, self.file_offset, name)

    def test_delete_leaf_file_remaps_metadata_and_content(self):
        try:
            from test_backup_duplicate import make_nested_blob
        except ModuleNotFoundError:
            from tests.test_backup_duplicate import make_nested_blob

        nested = parse_backup_blob(make_nested_blob(b"source\r\n"))
        rebuilt = delete_existing_file(nested, 0x140)
        parsed = parse_backup_blob(rebuilt)
        self.assertNotIn(("root", "folder", "source.txt"), parsed.paths.values())
        self.assertEqual(len(parsed.records), len(nested.records) - 1)
        self.assertEqual(parsed.paths[0x40], ("root",))
        self.assertEqual(parsed.paths[0xC0], ("root", "folder"))
        self.assertEqual(parsed.record_at(0xC0).field_08_be32, 0x40)
        self.assertEqual(
            calculate_backup_checksum(rebuilt),
            int.from_bytes(rebuilt[0x1C:0x20], "big"),
        )

    def test_delete_uses_observed_alignment_and_exact_boundary_rebases(self):
        parsed = parse_backup_blob(make_aligned_delete_blob())
        original = parsed.data
        rebuilt = parse_backup_blob(delete_existing_file(parsed, 0x100))

        self.assertEqual(parsed.data, original)
        self.assertNotIn(("root", "target"), rebuilt.paths.values())
        self.assertEqual(rebuilt.header.content_length, 40)
        self.assertEqual(rebuilt.record_at(0xC0).field_04_be32, 0xC0)
        # This marker belongs to the folder at 0xc0, not the root parent of
        # the deleted record.  Its field 08 is preserved even though the old
        # value happened to equal the deleted record offset.
        self.assertEqual(rebuilt.record_at(0x100).field_08_be32, 0x100)
        source = rebuilt.record_at(0x140)
        self.assertEqual(source.field_04_be32, 0)
        self.assertEqual(rebuilt.payload_parts(source)[1], b"source!!")
        self.assertEqual(
            calculate_backup_checksum(rebuilt.data),
            rebuilt.header.stored_checksum,
        )

    def test_delete_rejects_directory_and_unreachable_record(self):
        with self.assertRaises(BackupRepackError):
            delete_existing_file(self.parsed, 0x40)
        with self.assertRaises(BackupRepackError):
            delete_existing_file(self.parsed, 0xDEAD)

    def test_rejects_unknown_or_non_file_targets(self):
        with self.assertRaises(BackupRepackError):
            repack_existing_records(self.parsed, {0xDEADBEEF: b"x"})
        with self.assertRaises(BackupRepackError):
            repack_existing_records(self.parsed, {"0xc0": b"x"})
        with self.assertRaises(BackupRepackError):
            repack_existing_records(self.parsed, {0x40: b"x"})
        with self.assertRaises(BackupRepackError):
            repack_existing_records(self.parsed, {self.file_offset: "not bytes"})


if __name__ == "__main__":
    unittest.main()
