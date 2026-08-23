import hashlib
import unittest

from infocarry.backup_format import calculate_backup_checksum, parse_backup_blob
from infocarry.prepared_folder import (
    PreparedFolderError,
    build_modern_root_folder_text_candidate,
    build_root_folder_text_candidate,
)

try:
    from test_backup_format import make_record
except ModuleNotFoundError:
    from tests.test_backup_format import make_record


def _blob(records: bytes, content: bytes) -> bytes:
    content_start = 0x40 + len(records)
    content = content + b"\xff" * (-(content_start + len(content)) % 4)
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
    result = bytearray(bytes(header) + records + content + b"\xff" * 4)
    result[0x1C:0x20] = calculate_backup_checksum(result).to_bytes(4, "big")
    return bytes(result)


def make_folder_fixtures() -> tuple[bytes, bytes]:
    old_payload = b"old\r\n"
    prefix = b"\x01" + b"\xff" * 31
    old_segment = prefix + old_payload
    old_aligned = old_segment + b"\xff" * ((-len(old_segment)) % 4)
    prepared_payload = b"template\r\n"
    prepared_segment = prefix + prepared_payload
    prepared_aligned = prepared_segment + b"\xff" * ((-len(prepared_segment)) % 4)

    baseline_records = b"".join(
        (
            make_record(0xD0, "", 0x40, 0x80, "root"),
            make_record(0xD0, "", 0x00, 0x40, ".."),
            make_record(0xE0, "txt", 0x00, len(old_payload), "old", 0x200),
            make_record(0xD0, "", 0x40, 0x80, ".."),
        )
    )
    template_records = b"".join(
        (
            make_record(0xD0, "", 0x40, 0xC0, "root"),
            make_record(0xD0, "", 0x00, 0x40, ".."),
            make_record(0xE0, "txt", 0x00, len(old_payload), "old", 0x200),
            make_record(0xD0, "", 0x100, 0x80, "IC_I_FOLDER_20260823_01"),
            make_record(0xD0, "", 0x40, 0x100, ".."),
            make_record(0xE0, "txt", len(old_aligned), len(prepared_payload), "chapter", 0x200),
            make_record(0xD0, "", 0x40, 0xC0, ".."),
        )
    )
    return (
        _blob(baseline_records, old_aligned),
        _blob(template_records, old_aligned + prepared_aligned),
    )


def _rechecksum(blob: bytearray) -> bytes:
    blob[0x1C:0x20] = b"\x00" * 4
    blob[0x1C:0x20] = calculate_backup_checksum(bytes(blob)).to_bytes(4, "big")
    return bytes(blob)


class PreparedFolderTests(unittest.TestCase):
    def setUp(self):
        baseline_blob, template_blob = make_folder_fixtures()
        self.baseline = parse_backup_blob(baseline_blob)
        self.template = parse_backup_blob(template_blob)
        self.baseline_bytes = self.baseline.data
        self.template_bytes = self.template.data
        self.timestamps = {record.offset: 11 for record in self.baseline.records}

    def test_builds_captured_three_record_shape_and_preserves_input(self):
        result = build_root_folder_text_candidate(
            self.baseline,
            self.template,
            "Package",
            "chapter.txt",
            "A\nB",
            timestamp_be32=22,
            metadata_timestamps=self.timestamps,
        )
        candidate = parse_backup_blob(result.candidate_blob)
        folder = next(record for offset, path in candidate.paths.items() if path == ("root", "Package") for record in (candidate.record_at(offset),))
        child = next(record for offset, path in candidate.paths.items() if path == ("root", "Package", "chapter") for record in (candidate.record_at(offset),))
        self.assertEqual(folder.field_04_be32, folder.offset)
        self.assertEqual(folder.field_08_be32, 0x80)
        self.assertEqual(child.field_04_be32, 0x28)
        self.assertEqual(candidate.payload_parts(child)[1], b"A\r\nB")
        self.assertEqual(len(candidate.records), len(self.baseline.records) + 3)
        self.assertEqual(self.baseline.data, self.baseline_bytes)
        self.assertEqual(result.audit["allocation"]["metadata_records_added"], 3)
        self.assertEqual(result.audit["preservation"]["unrelated_changes_verified"], True)
        self.assertEqual(result.audit["template_validation"]["shared_content_verified"], True)
        self.assertEqual(candidate.record_at(0x40).field_08_be32, 0xC0)
        self.assertEqual(candidate.record_at(0x1C0).name, "..")
        self.assertEqual(candidate.record_at(0x1C0).field_08_be32, 0xC0)

    def test_alignment_boundaries_are_explicit_and_deterministic(self):
        for text in ("", "A", "AB", "ABC", "ABCD"):
            with self.subTest(text=text):
                result = build_root_folder_text_candidate(
                    self.baseline,
                    self.template,
                    "Package",
                    "chapter.txt",
                    text,
                    timestamp_be32=22,
                    metadata_timestamps=self.timestamps,
                )
                candidate = parse_backup_blob(result.candidate_blob)
                child_offset = next(
                    offset
                    for offset, path in candidate.paths.items()
                    if path == ("root", "Package", "chapter")
                )
                child = candidate.record_at(child_offset)
                payload = candidate.payload_parts(child)[1]
                expected_padding = (-(0x20 + len(payload))) % 4
                self.assertEqual(child.field_08_be32, len(payload))
                self.assertEqual(
                    result.audit["allocation"]["alignment_padding_bytes"],
                    expected_padding,
                )
                self.assertEqual(
                    result.audit["allocation"]["candidate_growth_bytes"],
                    0x40 * 3 + 0x20 + len(payload) + expected_padding,
                )

    def test_output_is_deterministic(self):
        kwargs = dict(
            timestamp_be32=22,
            metadata_timestamps=self.timestamps,
        )
        first = build_root_folder_text_candidate(
            self.baseline, self.template, "Package", "chapter.txt", "A\nB", **kwargs
        )
        second = build_root_folder_text_candidate(
            self.baseline, self.template, "Package", "chapter.txt", "A\nB", **kwargs
        )
        self.assertEqual(first.candidate_blob, second.candidate_blob)
        self.assertEqual(first.audit_dict(), second.audit_dict())
        self.assertEqual(
            hashlib.sha256(first.candidate_blob).hexdigest(),
            hashlib.sha256(second.candidate_blob).hexdigest(),
        )

    def test_modern_policy_preserves_shared_timestamps_and_binds_three_new_records(self):
        result = build_modern_root_folder_text_candidate(
            self.baseline,
            self.template,
            "Package",
            "chapter.txt",
            "A\nB",
            new_record_timestamp_be32=22,
        )
        candidate = parse_backup_blob(result.candidate_blob)
        before_by_path = {
            path: self.baseline.record_at(offset)
            for offset, path in self.baseline.paths.items()
        }
        after_by_path = {
            path: candidate.record_at(offset)
            for offset, path in candidate.paths.items()
        }
        for path in before_by_path:
            with self.subTest(path=path):
                self.assertEqual(
                    after_by_path[path].timestamp_be32,
                    before_by_path[path].timestamp_be32,
                )
        folder = after_by_path[("root", "Package")]
        child = after_by_path[("root", "Package", "chapter")]
        leading = candidate.record_at(folder.offset + 0x40)
        self.assertEqual(folder.timestamp_be32, 22)
        self.assertEqual(leading.timestamp_be32, 22)
        self.assertEqual(child.timestamp_be32, 22)
        self.assertEqual(
            result.audit["timestamp_policy"],
            "modern_constrained_preserve_existing_explicit_new_records",
        )
        self.assertEqual(result.audit["new_record_timestamp_be32"], "0x00000016")
        self.assertEqual(result.audit["existing_record_timestamps"], "preserved")
        self.assertEqual(self.template.data, self.template_bytes)

    def test_modern_timestamp_change_only_changes_three_fields_and_checksum(self):
        first = build_modern_root_folder_text_candidate(
            self.baseline,
            self.template,
            "Package",
            "chapter.txt",
            "A\nB",
            new_record_timestamp_be32=22,
        )
        second = build_modern_root_folder_text_candidate(
            self.baseline,
            self.template,
            "Package",
            "chapter.txt",
            "A\nB",
            new_record_timestamp_be32=23,
        )
        differences = {
            index
            for index, (left, right) in enumerate(
                zip(first.candidate_blob, second.candidate_blob)
            )
            if left != right
        }
        allowed = set(range(0x1C, 0x20))
        allowed.update(range(0x100 + 0x0C, 0x100 + 0x10))
        allowed.update(range(0x140 + 0x0C, 0x140 + 0x10))
        allowed.update(range(0x180 + 0x0C, 0x180 + 0x10))
        self.assertTrue(differences)
        self.assertTrue(differences <= allowed)

    def test_modern_policy_rejects_non_capture_shape_and_duplicate_path(self):
        changed = bytearray(self.template.data)
        changed[0x108:0x10C] = (0xC0).to_bytes(4, "big")
        changed_template = parse_backup_blob(_rechecksum(changed))
        with self.assertRaises(PreparedFolderError):
            build_modern_root_folder_text_candidate(
                self.baseline,
                changed_template,
                "Package",
                "chapter.txt",
                "A",
                new_record_timestamp_be32=22,
            )

    def test_modern_policy_reuses_exact_capture_template_as_fresh_baseline(self):
        result = build_modern_root_folder_text_candidate(
            self.template,
            self.template,
            "Package",
            "chapter.txt",
            "A\nB",
            new_record_timestamp_be32=22,
        )
        candidate = parse_backup_blob(result.candidate_blob)
        self.assertTrue(result.audit["template_validation"]["template_baseline_exact"])
        self.assertEqual(len(candidate.records), len(self.template.records) + 3)
        self.assertIn(("root", "Package"), candidate.paths.values())
        self.assertIn(("root", "Package", "chapter"), candidate.paths.values())
        for path in self.template.paths.values():
            before = self.template.record_at(
                next(offset for offset, value in self.template.paths.items() if value == path)
            )
            after = candidate.record_at(
                next(offset for offset, value in candidate.paths.items() if value == path)
            )
            self.assertEqual(after.timestamp_be32, before.timestamp_be32)
        with self.assertRaisesRegex(PreparedFolderError, "already exists"):
            build_modern_root_folder_text_candidate(
                self.baseline,
                self.template,
                "old",
                "chapter.txt",
                "A",
                new_record_timestamp_be32=22,
            )

    def test_requires_explicit_timestamp_and_complete_timestamp_map(self):
        with self.assertRaises(PreparedFolderError):
            build_root_folder_text_candidate(
                self.baseline, self.template, "Package", "chapter.txt", "A", timestamp_be32=None
            )
        with self.assertRaises(PreparedFolderError):
            build_root_folder_text_candidate(
                self.baseline,
                self.template,
                "Package",
                "chapter.txt",
                "A",
                timestamp_be32=22,
                metadata_timestamps={},
            )

    def test_rejects_duplicate_or_unsafe_names_and_unmappable_text(self):
        cases = (
            (".", "chapter.txt", "A"),
            ("Package", "bad.bin", "A"),
            ("Package/child", "chapter.txt", "A"),
            ("Package", "chapter.txt", "😀"),
        )
        for folder, child, text in cases:
            with self.subTest(folder=folder, child=child, text=text):
                with self.assertRaises(PreparedFolderError):
                    build_root_folder_text_candidate(
                        self.baseline,
                        self.template,
                        folder,
                        child,
                        text,
                        timestamp_be32=22,
                        metadata_timestamps=self.timestamps,
                    )

    def test_rejects_template_without_the_captured_shape(self):
        with self.assertRaises(PreparedFolderError):
            build_root_folder_text_candidate(
                self.baseline,
                self.baseline,
                "Package",
                "chapter.txt",
                "A",
                timestamp_be32=22,
                metadata_timestamps=self.timestamps,
            )

    def test_rejects_template_that_changes_a_shared_payload(self):
        changed = bytearray(self.template.data)
        old = self.template.record_at(0xC0)
        prefix, _payload = self.template.payload_parts(old)
        payload_offset = self.template.header.content_start + old.field_04_be32 + len(prefix)
        changed[payload_offset] ^= 0x01
        changed_template = parse_backup_blob(_rechecksum(changed))
        with self.assertRaisesRegex(PreparedFolderError, "changed preserved payload"):
            build_root_folder_text_candidate(
                self.baseline,
                changed_template,
                "Package",
                "chapter.txt",
                "A",
                timestamp_be32=22,
                metadata_timestamps=self.timestamps,
            )


if __name__ == "__main__":
    unittest.main()
