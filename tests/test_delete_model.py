import hashlib
import unittest

from infocarry.backup_format import parse_backup_blob
from infocarry.delete_model import DeleteModelError, build_one_txt_delete_model

try:
    from test_backup_format import make_text_blob
    from test_backup_repack import make_aligned_delete_blob
except ModuleNotFoundError:
    from tests.test_backup_format import make_text_blob
    from tests.test_backup_repack import make_aligned_delete_blob


class OfflineDeleteModelTests(unittest.TestCase):
    def test_preserves_surviving_timestamps_unknown_fields_and_payloads(self):
        blob = make_aligned_delete_blob(b"target\r\n")
        parsed = parse_backup_blob(blob)
        original = parsed.data
        model = build_one_txt_delete_model(parsed, "root\\target.txt", 0x100)
        candidate = parse_backup_blob(model.candidate_blob)

        self.assertEqual(parsed.data, original)
        self.assertEqual(model.audit["timestamps"]["policy"], "preserve_surviving_timestamps")
        self.assertEqual(model.audit["baseline"]["model_length"] - model.audit["candidate"]["model_length"], 104)
        self.assertEqual(model.audit["candidate"]["removed_paths"], ["root\\target.txt"])
        self.assertEqual(model.audit["candidate"]["added_paths"], [])
        self.assertEqual(model.audit["preservation"]["surviving_payload_count"], 1)
        self.assertEqual(
            model.audit["preservation"]["surviving_payload_sha256"]["root\\folder\\source.txt"],
            hashlib.sha256(b"source!!").hexdigest(),
        )
        self.assertNotIn(("root", "target.txt"), candidate.paths.values())
        self.assertEqual(candidate.record_at(0x140).timestamp_be32, parsed.record_at(0x180).timestamp_be32)

    def test_candidate_is_deterministic_and_source_is_not_mutated(self):
        parsed = parse_backup_blob(make_text_blob(b"keep\r\n"))
        source = parsed.data
        first = build_one_txt_delete_model(parsed, "root\\memo.txt", 0xC0)
        second = build_one_txt_delete_model(parsed, "root\\memo.txt", 0xC0)
        self.assertEqual(first.candidate_blob, second.candidate_blob)
        self.assertEqual(first.audit, second.audit)
        self.assertEqual(first.candidate_blob_sha256, second.candidate_blob_sha256)
        self.assertEqual(parsed.data, source)

    def test_rejects_root_directory_non_txt_and_wrong_identity(self):
        parsed = parse_backup_blob(make_text_blob())
        cases = (
            ("root", 0x40, "root record"),
            ("root\\memo.txt", 0x40, "path"),
            ("root\\memo.bmp", 0xC0, "path"),
            ("root\\wrong.txt", 0xC0, "path"),
        )
        for path, offset, message in cases:
            with self.subTest(path=path), self.assertRaisesRegex(DeleteModelError, message):
                build_one_txt_delete_model(parsed, path, offset)

    def test_rejects_malformed_or_ambiguous_target_identity(self):
        parsed = parse_backup_blob(make_text_blob())
        for path, offset in (("root\\memo.txt", 0xC1), ("root\\memo.txt", 0x80)):
            with self.subTest(offset=offset), self.assertRaises(DeleteModelError):
                build_one_txt_delete_model(parsed, path, offset)

    def test_reports_alignment_and_pointer_changes_without_experiment_constants(self):
        parsed = parse_backup_blob(make_aligned_delete_blob(b"x" * 5))
        model = build_one_txt_delete_model(parsed, "root\\target.txt", 0x100)
        allocation = model.audit["allocation"]
        self.assertEqual(allocation["record_size"], parsed.header.record_size)
        self.assertEqual(allocation["content_segment_start"], 0)
        self.assertEqual(allocation["removed_aligned_bytes"], 40)
        self.assertEqual(allocation["model_delta"], -104)
        self.assertIn("preserve_surviving_timestamps", model.audit["timestamps"]["policy"])


if __name__ == "__main__":
    unittest.main()
