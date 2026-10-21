from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import calculate_backup_checksum, parse_backup_blob
from infocarry.backup_duplicate import add_file_from_template
from infocarry.delete_workflow import ROOT_BMP_DELETE_FIXTURE_BYTES, ROOT_BMP_DELETE_FIXTURE_FILENAME
from infocarry.new_bmp import NewBmpAddResult, build_new_root_bmp_add
from infocarry.new_txt import NewTxtAddError
from infocarry.write_state import rebase_fixed_state_responses

try:
    from test_backup_duplicate import make_nested_blob
    from test_new_txt import _write_archive
except ModuleNotFoundError:
    from tests.test_backup_duplicate import make_nested_blob
    from tests.test_new_txt import _write_archive


def _bmp_baseline():
    blob = bytearray(make_nested_blob(ROOT_BMP_DELETE_FIXTURE_BYTES, prefix_length=16))
    # P16's captured BMP record shape: replace the synthetic helper's TXT type,
    # retaining its observed 0xe0 / 0x100 / all-ff 16-byte BMP profile.
    blob[0x141:0x144] = b"bmp"
    blob[0x1c:0x20] = b"\x00" * 4
    blob[0x1c:0x20] = calculate_backup_checksum(blob).to_bytes(4, "big")
    return bytes(blob)


class NewRootBmpCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.baseline_blob = _bmp_baseline()
        # These established test-state records point to the reachable nested
        # BMP at relative record offset 0x100, after the root insertion point.
        self.fixed = {
            0x001B: (1).to_bytes(4, "big") + bytes(4) + (0x100).to_bytes(4, "big") + bytes(52),
            0x001C: bytes(64), 0x001D: bytes(64), 0x001E: bytes(64),
            0x001F: (0x100).to_bytes(4, "big") + bytes(60),
        }
        self.backup = _write_archive(self.root / "backup", self.baseline_blob,
                                     self.now, fixed_state=self.fixed)
        self.source = self.root / ROOT_BMP_DELETE_FIXTURE_FILENAME
        self.source.write_bytes(ROOT_BMP_DELETE_FIXTURE_BYTES)

    def build(self, **changes):
        args = dict(backup_directory=self.backup, source_path=self.source,
                    target_filename=ROOT_BMP_DELETE_FIXTURE_FILENAME,
                    source_template_offset=0x140, available_capacity_bytes=20_000,
                    record_timestamp_be32=0x6A900000, now=self.now,
                    max_age_seconds=None)
        args.update(changes)
        return build_new_root_bmp_add(**args)

    def test_root_bmp_candidate_reuses_observed_nested_record_and_rebases_structure(self):
        before = parse_backup_blob(self.baseline_blob)
        candidate = self.build()
        self.assertIsInstance(candidate, NewBmpAddResult)
        after = parse_backup_blob(candidate.candidate_blob)
        target_path = ("root", ROOT_BMP_DELETE_FIXTURE_FILENAME[:-4])
        self.assertEqual(set(after.paths.values()), set(before.paths.values()) | {target_path})
        target_offset = next(o for o, p in after.paths.items() if p == target_path)
        target = after.record_at(target_offset)
        template = before.record_at(0x140)
        self.assertEqual(target_offset, 0x100)  # appended to root child order
        self.assertEqual((target.kind, target.extension, target.flag), ("file", "bmp", 0xE0))
        self.assertEqual((target.field_10_be32, target.field_14_be32),
                         (template.field_10_be32, 0x100))
        self.assertEqual(target.timestamp_be32, 0x6A900000)
        self.assertEqual(after.payload_parts(target),
                         (b"\xff" * 16, ROOT_BMP_DELETE_FIXTURE_BYTES))

        root_before, root_after = before.record_at(0x40), after.record_at(0x40)
        self.assertEqual(root_after.field_08_be32, root_before.field_08_be32 + 0x40)
        # The new leaf is immediately before the root's moved trailing marker;
        # its parent is root, not the existing folder.
        root_marker = after.record_at(target_offset + 0x40)
        self.assertEqual((root_marker.kind, root_marker.name), ("directory", ".."))
        self.assertEqual(root_marker.field_04_be32, 0x40)
        self.assertEqual(after.paths[0xC0], ("root", "folder"))
        self.assertEqual(after.paths[0x180], ("root", "folder", "source"))
        self.assertEqual(candidate.transaction.ranges[0][8:12], (0x140).to_bytes(4, "big"))
        self.assertEqual(candidate.transaction.ranges[1][:4], (0x140).to_bytes(4, "big"))

        # All existing records keep their semantic fields/timestamps and file
        # bytes; established pointers are shifted by the serializer/parser.
        for old_offset, path in before.paths.items():
            new_offset = next(o for o, p in after.paths.items() if p == path)
            old, new = before.record_at(old_offset), after.record_at(new_offset)
            self.assertEqual((old.kind, old.extension, old.flag, old.timestamp_be32,
                              old.field_10_be32, old.field_14_be32),
                             (new.kind, new.extension, new.flag, new.timestamp_be32,
                              new.field_10_be32, new.field_14_be32))
            if old.kind == "file":
                self.assertEqual(before.payload_parts(old), after.payload_parts(new))

        rebased, grouped = rebase_fixed_state_responses(
            tuple(self.fixed[c] for c in (0x001B, 0x001C, 0x001D, 0x001E)),
            self.fixed[0x001F], insertion_offset=0xC0, metadata_delta=0x40)
        self.assertEqual(candidate.transaction.ranges[0], b"".join(rebased))
        self.assertEqual(candidate.transaction.ranges[1], grouped)
        self.assertEqual(after.header.stored_checksum,
                         calculate_backup_checksum(candidate.candidate_blob))
        audit = candidate.audit
        self.assertEqual(audit["target"]["payload_sha256"],
                         __import__("hashlib").sha256(ROOT_BMP_DELETE_FIXTURE_BYTES).hexdigest())
        self.assertEqual(audit["allocation"]["metadata_delta"], 64)
        self.assertEqual(audit["preservation"]["unrelated_changes_verified"], True)

    def test_malformed_name_target_template_and_payload_fail_closed(self):
        for name in ("../bad.bmp", "bad/name.bmp", "bad\\name.bmp", "bad.name.bmp", " bad.bmp"):
            with self.subTest(name=name), self.assertRaises(NewTxtAddError):
                self.build(target_filename=name)
        with self.assertRaises(NewTxtAddError):
            self.build(source_template_offset=0x40)
        changed = bytearray(self.baseline_blob)
        content_start = parse_backup_blob(self.baseline_blob).header.content_start
        changed[content_start] = 0x00
        changed[0x1c:0x20] = bytes(4)
        changed[0x1c:0x20] = calculate_backup_checksum(changed).to_bytes(4, "big")
        altered_backup = _write_archive(self.root / "changed", bytes(changed), self.now,
                                        fixed_state=self.fixed)
        with self.assertRaisesRegex(NewTxtAddError, "all-ff 16-byte form"):
            self.build(backup_directory=altered_backup)
        self.source.write_bytes(b"not a bitmap")
        with self.assertRaisesRegex(NewTxtAddError, "image profile"):
            self.build()

    def test_capacity_and_timestamp_bounds_are_rejected(self):
        with self.assertRaisesRegex(NewTxtAddError, "capacity"):
            self.build(available_capacity_bytes=1)
        with self.assertRaisesRegex(NewTxtAddError, "timestamp"):
            self.build(record_timestamp_be32=-1)

    def test_existing_target_is_not_replaced_or_overwritten(self):
        candidate = self.build()
        backup = _write_archive(self.root / "target-present", candidate.candidate_blob,
                                self.now, fixed_state=self.fixed)
        with self.assertRaisesRegex(NewTxtAddError, "already exists or is ambiguous"):
            self.build(backup_directory=backup, source_template_offset=0x180)

    def test_dangling_protected_reference_fails_closed(self):
        invalid_state = dict(self.fixed)
        invalid_state[0x001B] = (1).to_bytes(4, "big") + bytes(4) + (0x400000).to_bytes(4, "big") + bytes(52)
        backup = _write_archive(self.root / "dangling-state", self.baseline_blob,
                                self.now, fixed_state=invalid_state)
        with self.assertRaisesRegex(NewTxtAddError, "dangling"):
            self.build(backup_directory=backup)

    def test_overlapping_baseline_file_segments_fail_closed(self):
        before = parse_backup_blob(self.baseline_blob)
        duplicated = add_file_from_template(
            before, before.header.metadata_start, 0x140, "other", ROOT_BMP_DELETE_FIXTURE_BYTES,
            timestamp_be32=0x6A800000, fresh_new_allocation=True)
        overlapping = bytearray(duplicated)
        after_duplicate = parse_backup_blob(duplicated)
        other_offset = next(offset for offset, path in after_duplicate.paths.items()
                            if path == ("root", "other"))
        nested_offset = next(offset for offset, path in after_duplicate.paths.items()
                             if path == ("root", "folder", "source"))
        nested_record = after_duplicate.record_at(nested_offset)
        overlapping[other_offset + 4:other_offset + 8] = nested_record.field_04_be32.to_bytes(4, "big")
        overlapping[0x1C:0x20] = bytes(4)
        overlapping[0x1C:0x20] = calculate_backup_checksum(overlapping).to_bytes(4, "big")
        overlap_backup = _write_archive(self.root / "overlapping", bytes(overlapping),
                                        self.now, fixed_state=self.fixed)
        with self.assertRaisesRegex(NewTxtAddError, "segments overlap"):
            self.build(backup_directory=overlap_backup, source_template_offset=other_offset)


if __name__ == "__main__":
    unittest.main()
