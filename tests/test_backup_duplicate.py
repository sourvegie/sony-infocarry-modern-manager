import unittest

from infocarry.backup_format import calculate_backup_checksum, parse_backup_blob
from infocarry.backup_duplicate import (
    BackupDuplicateError,
    DuplicateSpec,
    add_file_from_template,
    duplicate_existing_records,
)

try:
    from test_backup_format import make_record
except ModuleNotFoundError:
    from tests.test_backup_format import make_record


def make_nested_blob(payload=b"source\r\n"):
    # Root and one child directory. Each directory has the observed leading
    # parent marker, child records, and trailing self marker.
    records = b"".join(
        (
            make_record(0xD0, "", 0x40, 0x80, "root"),
            make_record(0xD0, "", 0x00, 0x80, ".."),
            make_record(0xD0, "", 0xC0, 0x80, "folder"),
            make_record(0xD0, "", 0x40, 0x80, ".."),
            make_record(0xE0, "txt", 0, len(payload), "source", 0x200),
            make_record(0xD0, "", 0xC0, 0x80, ".."),
            make_record(0xD0, "", 0x40, 0x80, ".."),
        )
    )
    prefix = b"\xff" * 0x20
    content_start = 0x40 + len(records)
    content = prefix + payload
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


class BackupDuplicateTests(unittest.TestCase):
    def setUp(self):
        self.blob = make_nested_blob()
        self.parsed = parse_backup_blob(self.blob)

    def test_duplicates_existing_file_offline(self):
        rebuilt = duplicate_existing_records(
            self.parsed,
            0xC0,
            [DuplicateSpec(0x140, "copy", timestamp_be32=9)],
            metadata_timestamp_be32=10,
        )
        parsed = parse_backup_blob(rebuilt)
        copied = next(
            record
            for record in parsed.records
            if record.name == "copy"
        )
        self.assertEqual(parsed.paths[copied.offset], ("root", "folder", "copy"))
        _, payload = parsed.payload_parts(copied)
        self.assertEqual(payload, b"source\r\n")
        self.assertEqual(copied.timestamp_be32, 9)
        self.assertEqual(parsed.record_at(0xC0).field_08_be32, 0xC0)
        self.assertEqual(parsed.record_at(0x1C0).field_08_be32, 0xC0)
        self.assertTrue(all(record.timestamp_be32 == 10 for record in parsed.records if record.offset != copied.offset))
        self.assertEqual(
            calculate_backup_checksum(rebuilt),
            int.from_bytes(rebuilt[0x1C:0x20], "big"),
        )

    def test_rejects_duplicate_destination_name(self):
        with self.assertRaises(BackupDuplicateError):
            duplicate_existing_records(
                self.parsed,
                0xC0,
                [DuplicateSpec(0x140, "source")],
            )

    def test_rejects_non_file_source(self):
        with self.assertRaises(BackupDuplicateError):
            duplicate_existing_records(
                self.parsed,
                0xC0,
                [DuplicateSpec(0xC0, "copy")],
            )

    def test_add_from_template_replaces_copied_payload(self):
        rebuilt = add_file_from_template(
            self.parsed,
            0xC0,
            0x140,
            "new.txt",
            b"arbitrary\r\ncontent",
            timestamp_be32=11,
        )
        parsed = parse_backup_blob(rebuilt)
        target = next(
            record
            for record in parsed.records
            if parsed.paths.get(record.offset) == ("root", "folder", "new.txt")
        )
        _, payload = parsed.payload_parts(target)
        self.assertEqual(payload, b"arbitrary\r\ncontent")
        self.assertEqual(target.timestamp_be32, 11)


if __name__ == "__main__":
    unittest.main()
