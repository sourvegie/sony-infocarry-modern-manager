import hashlib
import unittest

from infocarry.backup_format import calculate_backup_checksum, parse_backup_blob
from infocarry.backup_repack import delete_existing_file
from infocarry.delete_evidence_compare import compare_delete_evidence
from infocarry.delete_model import DeleteModelError, build_one_txt_delete_model

try:
    from test_backup_format import make_record
    from test_backup_duplicate import make_nested_blob
    from test_backup_repack import make_aligned_delete_blob
except ModuleNotFoundError:
    from tests.test_backup_format import make_record
    from tests.test_backup_duplicate import make_nested_blob
    from tests.test_backup_repack import make_aligned_delete_blob


def _make_root_siblings(payloads):
    records = [
        make_record(0xD0, "", 0x40, (len(payloads) + 1) * 0x40, "root"),
        make_record(0xD0, "", 0, 0x40, ".."),
    ]
    content = bytearray()
    for index, payload in enumerate(payloads):
        start = len(content)
        content.extend(b"\xff" * 0x20)
        content.extend(payload)
        content.extend(b"\x00" * (-len(content) % 4))
        records.append(make_record(0xE0, "txt", start, len(payload), chr(97 + index), 0x200))
    records.append(make_record(0xD0, "", 0x40, (len(payloads) + 1) * 0x40, ".."))
    metadata = b"".join(records)
    content_start = 0x40 + len(metadata)
    content.extend(b"\x00" * (-(content_start + len(content)) % 4))
    total_length = content_start + len(content) + 4
    header = bytearray(64)
    header[:14] = b"infoCarry 2.00"
    header[14:16] = b"\x01\x00"
    header[16:18] = (64).to_bytes(2, "big")
    header[0x14:0x18] = (0x20).to_bytes(4, "big")
    header[0x18:0x1C] = (total_length - 1).to_bytes(4, "big")
    header[0x28:0x2C] = (0x40).to_bytes(4, "big")
    header[0x2C:0x30] = len(metadata).to_bytes(4, "big")
    header[0x30:0x34] = content_start.to_bytes(4, "big")
    header[0x34:0x38] = len(content).to_bytes(4, "big")
    header[0x38:0x3C] = total_length.to_bytes(4, "big")
    header[0x3C:0x40] = b"\xff" * 4
    blob = bytearray(bytes(header) + metadata + content + b"\xff" * 4)
    blob[0x1C:0x20] = calculate_backup_checksum(blob).to_bytes(4, "big")
    return bytes(blob)


def _rechecksum(data):
    rebuilt = bytearray(data)
    rebuilt[0x1C:0x20] = b"\x00" * 4
    rebuilt[0x1C:0x20] = calculate_backup_checksum(rebuilt).to_bytes(4, "big")
    return bytes(rebuilt)


class DeleteStructuralCoverageTests(unittest.TestCase):
    def test_target_at_beginning_middle_and_end_preserves_survivors(self):
        for index, target in enumerate(("a", "b", "c")):
            with self.subTest(target=target):
                parsed = parse_backup_blob(_make_root_siblings((b"A\r\n", b"B\r\n", b"C\r\n")))
                source = parsed.data
                target_offset = 0xC0 + index * 0x40
                model = build_one_txt_delete_model(parsed, f"root\\{target}.txt", target_offset)
                result = parse_backup_blob(model.candidate_blob)
                self.assertEqual(parsed.data, source)
                self.assertEqual(set(result.paths.values()), {
                    ("root",),
                    *( ("root", name) for name in ("a", "b", "c") if name != target),
                })
                for record in result.records:
                    if record.kind == "file" and record.offset in result.paths:
                        old_name = result.paths[record.offset][-1]
                        old = next(r for r in parsed.records if r.name == old_name)
                        self.assertEqual(record.timestamp_be32, old.timestamp_be32)
                        self.assertEqual(result.payload_parts(record)[1], parsed.payload_parts(old)[1])

    def test_nested_txt_and_multiple_surviving_siblings(self):
        parsed = parse_backup_blob(make_nested_blob(b"nested\r\n"))
        source = parsed.data
        model = build_one_txt_delete_model(parsed, "root\\folder\\source.txt", 0x140)
        candidate = parse_backup_blob(model.candidate_blob)
        self.assertEqual(parsed.data, source)
        self.assertEqual(candidate.paths[0xC0], ("root", "folder"))
        self.assertNotIn(("root", "folder", "source.txt"), candidate.paths.values())
        self.assertEqual(len(candidate.records), len(parsed.records) - 1)
        self.assertTrue(all(record.offset % candidate.header.record_size == candidate.header.metadata_start % candidate.header.record_size for record in candidate.records))

    def test_alignment_boundaries_and_large_payload(self):
        for length in (0, 1, 3, 4, 5, 4095, 4096, 4097):
            with self.subTest(length=length):
                parsed = parse_backup_blob(_make_root_siblings((b"T" * length, b"survivor\r\n")))
                source = parsed.data
                model = build_one_txt_delete_model(parsed, "root\\a.txt", 0xC0)
                result = parse_backup_blob(model.candidate_blob)
                self.assertEqual(parsed.data, source)
                self.assertNotIn(("root", "a"), result.paths.values())
                self.assertEqual(model.audit["candidate"]["record_count"], len(parsed.records) - 1)
                self.assertEqual(model.audit["timestamps"]["policy"], "preserve_surviving_timestamps")

    def test_overlapping_content_is_rejected_without_source_change(self):
        parsed = parse_backup_blob(make_aligned_delete_blob(b"target"))
        source = parsed.data
        altered = bytearray(source)
        altered[0x180 + 0x04 : 0x180 + 0x08] = (0x08).to_bytes(4, "big")
        malformed = parse_backup_blob(_rechecksum(altered))
        with self.assertRaisesRegex(DeleteModelError, "overlaps"):
            build_one_txt_delete_model(malformed, "root\\target.txt", 0x100)
        self.assertEqual(parsed.data, source)

    def test_unsupported_type_and_ambiguous_identity_fail_closed(self):
        parsed = parse_backup_blob(_make_root_siblings((b"A\r\n", b"B\r\n", b"C\r\n")))
        altered = bytearray(parsed.data)
        altered[0xC0] = 0xA0
        unsupported = parse_backup_blob(_rechecksum(altered))
        with self.assertRaises(DeleteModelError):
            build_one_txt_delete_model(unsupported, "root\\a.txt", 0xC0)
        with self.assertRaises(DeleteModelError):
            build_one_txt_delete_model(parsed, "root\\a.txt", 0xC1)
        with self.assertRaises(DeleteModelError):
            build_one_txt_delete_model(parsed, "root\\missing.txt", 0xC0)


class DeleteEvidenceComparisonTests(unittest.TestCase):
    def test_timestamp_only_difference_normalizes_and_preserves_source(self):
        baseline = parse_backup_blob(make_aligned_delete_blob(b"target"))
        candidate = parse_backup_blob(delete_existing_file(baseline, 0x100))
        changed = bytearray(candidate.data)
        for record in candidate.records:
            changed[record.offset + 0x0C : record.offset + 0x10] = (record.timestamp_be32 + 1).to_bytes(4, "big")
        post = parse_backup_blob(_rechecksum(changed))
        result = compare_delete_evidence(
            baseline, candidate, post, target_path="root\\target.txt"
        )
        self.assertTrue(result.normalized_structural_match)
        self.assertTrue(result.exact_supported_effect)
        self.assertEqual(result.remaining_non_timestamp_byte_count, 0)
        self.assertEqual(baseline.data, parse_backup_blob(make_aligned_delete_blob(b"target")).data)

    def test_non_timestamp_difference_remains_fail_closed(self):
        baseline = parse_backup_blob(make_aligned_delete_blob(b"target"))
        candidate = parse_backup_blob(delete_existing_file(baseline, 0x100))
        changed = bytearray(candidate.data)
        changed[0xC0 + 0x16] ^= 0x01
        post = parse_backup_blob(_rechecksum(changed))
        result = compare_delete_evidence(
            baseline, candidate, post, target_path="root\\target.txt"
        )
        self.assertFalse(result.normalized_structural_match)
        self.assertFalse(result.exact_supported_effect)
        self.assertGreater(result.remaining_non_timestamp_byte_count, 0)


if __name__ == "__main__":
    unittest.main()
