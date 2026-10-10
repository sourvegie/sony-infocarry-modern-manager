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


def make_nested_blob(payload=b"source\r\n", prefix_length=32):
    # Root and one child directory. Each directory has the observed leading
    # parent marker, child records, and trailing self marker.
    records = b"".join(
        (
            make_record(0xD0, "", 0x40, 0x80, "root"),
            make_record(0xD0, "", 0x00, 0x80, ".."),
            make_record(0xD0, "", 0xC0, 0x80, "folder"),
            make_record(0xD0, "", 0x40, 0x80, ".."),
            make_record(0xE0, "txt", 0, len(payload), "source", 0x200 if prefix_length == 32 else 0x100),
            make_record(0xD0, "", 0xC0, 0x80, ".."),
            make_record(0xD0, "", 0x40, 0x80, ".."),
        )
    )
    prefix = b"\xff" * prefix_length
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

    def test_fresh_clone_allocation_preserves_complete_old_content_for_all_alignments(self):
        for prefix_length in (16, 32):
            for old_length in range(4):
                for new_length in range(4):
                    with self.subTest(prefix_length=prefix_length, old=old_length, new=new_length):
                        original = bytearray(make_nested_blob(b'O' * old_length, prefix_length))
                        parsed = parse_backup_blob(bytes(original))
                        # Retain opaque old padding plus a further four-byte trailing gap.
                        end = parsed.header.content_start + prefix_length + old_length
                        original[end:-4] = b'\xa5' * (len(original)-4-end)
                        original[-4:-4] = b'\x81\x92\xa3\xb4'
                        original[0x18:0x1C] = (len(original)-1).to_bytes(4, 'big')
                        original[0x34:0x38] = (parsed.header.content_length+4).to_bytes(4, 'big')
                        original[0x38:0x3C] = len(original).to_bytes(4, 'big')
                        original[0x1C:0x20] = calculate_backup_checksum(original).to_bytes(4, 'big')
                        before = parse_backup_blob(bytes(original))
                        payload = b'N' * new_length
                        candidate = add_file_from_template(before, 0xC0, 0x140, 'fresh', payload,
                            timestamp_be32=1234, fresh_new_allocation=True)
                        after = parse_backup_blob(candidate)
                        target = next(after.record_at(o) for o,p in after.paths.items() if p == ('root', 'folder', 'fresh'))
                        self.assertEqual(after.payload_parts(target), (b'\xff'*prefix_length, payload))
                        self.assertEqual(target.field_08_be32, new_length)
                        self.assertEqual(target.timestamp_be32, 1234)
                        old_content = before.data[before.header.content_start:before.header.content_start+before.header.content_length]
                        new_content = after.data[after.header.content_start:after.header.content_start+after.header.content_length]
                        allocation_length = prefix_length+new_length+(-new_length)%4
                        start = target.field_04_be32
                        self.assertEqual(new_content[:start]+new_content[start+allocation_length:], old_content)
                        self.assertEqual(new_content[start+prefix_length+new_length:start+allocation_length], b'\x00'*((-new_length)%4))
                        self.assertEqual(len(candidate)-len(original), 64+allocation_length)
                        for o,path in before.paths.items():
                            survivor = next(after.record_at(n) for n,p in after.paths.items() if p == path)
                            record = before.record_at(o)
                            self.assertEqual(survivor.timestamp_be32, record.timestamp_be32)
                            if record.kind == 'file': self.assertEqual(after.payload_parts(survivor), before.payload_parts(record))
                        # The explicit clone spec shares this exact structural path.
                        direct = duplicate_existing_records(before, 0xC0,
                            [DuplicateSpec(0x140, 'fresh', timestamp_be32=1234, replacement_payload=payload)])
                        self.assertEqual(direct, candidate)

    def test_default_add_stays_equal_to_original_duplicate_then_repack(self):
        from infocarry.backup_repack import repack_existing_records
        for old_length in range(4):
            before = parse_backup_blob(make_nested_blob(b'O'*old_length))
            duplicated = duplicate_existing_records(before, 0xC0, [DuplicateSpec(0x140, 'new', timestamp_be32=91)])
            parsed = parse_backup_blob(duplicated)
            target = next(o for o,p in parsed.paths.items() if p == ('root', 'folder', 'new'))
            expected = repack_existing_records(parsed, {target:b'new payload'})
            self.assertEqual(add_file_from_template(before, 0xC0, 0x140, 'new', b'new payload', timestamp_be32=91), expected)
            self.assertEqual(add_file_from_template(before, 0xC0, 0x140, 'new', b'new payload', timestamp_be32=91, fresh_new_allocation=False), expected)

    def test_fresh_allocation_options_reject_wrong_types(self):
        for invalid in (1, None, 'true'):
            with self.assertRaises(BackupDuplicateError):
                add_file_from_template(self.parsed, 0xC0, 0x140, 'new', b'txt', fresh_new_allocation=invalid)
        for payload in (False, 'txt', bytearray(b'txt')):
            with self.assertRaises(BackupDuplicateError):
                duplicate_existing_records(self.parsed, 0xC0, [DuplicateSpec(0x140, 'new', replacement_payload=payload)])


if __name__ == "__main__":
    unittest.main()
