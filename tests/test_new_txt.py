import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import calculate_backup_checksum, parse_backup_blob
from infocarry.new_txt import (
    NewTxtAddError,
    build_new_root_txt_add,
    compare_new_txt_candidate,
)
from infocarry.write_state import StateSerializationError, rebase_fixed_state_responses

try:
    from test_backup_format import make_record
except ModuleNotFoundError:
    from tests.test_backup_format import make_record


def _make_root_blob(payload=b"source\r\n"):
    records = b"".join(
        (
            make_record(0xD0, "", 0x40, 0x80, "root"),
            make_record(0xD0, "", 0x00, 0x40, ".."),
            make_record(0xE0, "txt", 0x00, len(payload), "source", 0x200),
            make_record(0xD0, "", 0x40, 0x80, ".."),
        )
    )
    content_start = 0x40 + len(records)
    content = b"\xff" * 0x20 + payload
    content += b"\x00" * (-(content_start + len(content)) % 4)
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


def _write_archive(
    root: Path,
    blob: bytes,
    timestamp: datetime,
    *,
    fixed_state=None,
) -> Path:
    root.mkdir()
    if fixed_state is None:
        fixed_state = {
            0x001B: (1).to_bytes(4, "big") + b"\x00\x00\x00\x00" + (0xC0).to_bytes(4, "big") + b"\x00" * 52,
            0x001C: b"\x00" * 64,
            0x001D: b"\x00" * 64,
            0x001E: b"\x00" * 64,
            0x001F: (0xC0).to_bytes(4, "big") + b"\x00" * 60,
        }
    objects = [
        (0x0024, "response-0024", b"q" * 64),
        (0x001B, "response-001b", fixed_state[0x001B]),
        (0x001C, "response-001c", fixed_state[0x001C]),
        (0x001D, "response-001d", fixed_state[0x001D]),
        (0x001E, "response-001e", fixed_state[0x001E]),
        (0x001F, "response-001f", fixed_state[0x001F]),
        (0x8004, "backup-blob-probe", b"p" * 64),
        (0x8004, "backup-blob", blob),
    ]
    entries = []
    for sequence, (command, kind, data) in enumerate(objects, start=1):
        filename = f"object-{sequence:02d}.bin"
        (root / filename).write_bytes(data)
        entries.append(
            {
                "sequence": sequence,
                "command": f"0x{command:04x}",
                "kind": kind,
                "filename": filename,
                "requested_length": len(data),
                "received_length": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    manifest = {
        "format": "infocarry-raw-backup-v1",
        "state": "complete",
        "created_at_utc": timestamp.isoformat(),
        "updated_at_utc": timestamp.isoformat(),
        "device": {"vendor_id": "0x054c", "product_id": "0x001e"},
        "objects": entries,
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


class NewRootTxtBuilderTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc).replace(microsecond=0)

    def _case(self, source=b"new\r\n", target="new.txt"):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        backup = _write_archive(root / "backup", _make_root_blob(), self.now)
        source_path = root / "source.txt"
        source_path.write_bytes(source.encode("cp932") if isinstance(source, str) else source)
        return temporary, backup, source_path, target

    def _build(self, source=b"new\r\n", target="new.txt", capacity=10000):
        temporary, backup, source_path, target = self._case(source, target)
        result = build_new_root_txt_add(
            backup,
            source_path,
            target,
            source_template_offset=0xC0,
            available_capacity_bytes=capacity,
            now=self.now,
            max_age_seconds=None,
        )
        return temporary, backup, source_path, result

    def test_empty_and_alignment_boundary_payloads(self):
        for length in range(8):
            with self.subTest(length=length):
                temporary, _backup, _source, result = self._build(b"A" * length)
                self.addCleanup(temporary.cleanup)
                self.assertEqual(result.audit["target"]["payload_length"], length)
                self.assertEqual(result.audit["allocation"]["alignment_padding_bytes"], (-length) % 4)

    def test_long_valid_content_is_encoded_and_bounded(self):
        temporary, _backup, _source, result = self._build("日本語\n" * 500, capacity=20000)
        self.addCleanup(temporary.cleanup)
        self.assertGreater(result.audit["target"]["payload_length"], 1000)
        self.assertEqual(result.audit["source"]["newline_policy"], "crlf")

    def test_exact_capture04_golden_case(self):
        root = Path("${EVIDENCE_ROOT}/phase-12-new-txt-repeat-20260822-152959")
        if not root.is_dir():
            self.skipTest("stable capture 04 is not present")
        before = root / "00-pre-add-backup/repeat-pre-add-archive-20260822-152959"
        after = root / "04-post-add-backup/repeat-post-add-archive-20260822-152959"
        source = root / "01-manager-before-send/source/windows-host-copy/IC_E_ADD_20260822_04.txt"
        pre = parse_backup_blob((before / "object-08-command-8004.bin").read_bytes())
        post = parse_backup_blob((after / "object-08-command-8004.bin").read_bytes())
        timestamp_overrides = {
            record.offset: post.record_at(
                record.offset if record.offset < 0x2C0 else record.offset + 0x40
            ).timestamp_be32
            for record in pre.records
        }
        result = build_new_root_txt_add(
            before,
            source,
            "IC_E_ADD_20260822_04.txt",
            source_template_offset=0x280,
            available_capacity_bytes=152,
            record_timestamp_be32=post.record_at(0x2C0).timestamp_be32,
            metadata_timestamps=timestamp_overrides,
            max_age_seconds=None,
        )
        comparison = compare_new_txt_candidate(result, after, max_age_seconds=None)
        self.assertTrue(comparison.exact)
        self.assertTrue(comparison.normalized_equivalent)
        self.assertEqual(result.candidate_blob, post.data)
        self.assertEqual(result.audit["candidate"]["blob_sha256"], "153f446520f556cb0d0c93061e14230664833d1320c25c9f86acf5c0ff7bc8dd")

    def test_capture04_timestamp_variation_is_normalized_only(self):
        root = Path("${EVIDENCE_ROOT}/phase-12-new-txt-repeat-20260822-152959")
        if not root.is_dir():
            self.skipTest("stable capture 04 is not present")
        before = root / "00-pre-add-backup/repeat-pre-add-archive-20260822-152959"
        after = root / "04-post-add-backup/repeat-post-add-archive-20260822-152959"
        source = root / "01-manager-before-send/source/windows-host-copy/IC_E_ADD_20260822_04.txt"
        result = build_new_root_txt_add(
            before,
            source,
            "IC_E_ADD_20260822_04.txt",
            source_template_offset=0x280,
            available_capacity_bytes=152,
            max_age_seconds=None,
        )
        comparison = compare_new_txt_candidate(result, after, max_age_seconds=None)
        self.assertFalse(comparison.exact)
        self.assertTrue(comparison.normalized_equivalent)
        self.assertFalse(comparison.unexpected_differences)
        self.assertTrue(any(item["kind"] == "record_timestamp" for item in comparison.permitted_differences))

    def test_invalid_cp932_and_embedded_nul_are_rejected(self):
        for payload, pattern in ((b"\x81", "valid CP932"), (b"has\x00nul", "NUL")):
            with self.subTest(payload=payload):
                temporary, backup, source, target = self._case(payload)
                self.addCleanup(temporary.cleanup)
                with self.assertRaisesRegex(NewTxtAddError, pattern):
                    build_new_root_txt_add(
                        backup, source, target, source_template_offset=0xC0,
                        available_capacity_bytes=10000, now=self.now, max_age_seconds=None,
                    )

    def test_invalid_or_ambiguous_filenames_are_rejected(self):
        for target in ("😀.txt", "new.TXT", "a.b.txt", "folder\\new.txt", " new.txt"):
            with self.subTest(target=target):
                temporary, backup, source, _ = self._case()
                self.addCleanup(temporary.cleanup)
                with self.assertRaises(NewTxtAddError):
                    build_new_root_txt_add(
                        backup, source, target, source_template_offset=0xC0,
                        available_capacity_bytes=10000, now=self.now, max_age_seconds=None,
                    )

    def test_duplicate_target_and_ambiguous_capacity_fail_closed(self):
        temporary, backup, source, _ = self._case(target="source.txt")
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(NewTxtAddError, "duplicate"):
            build_new_root_txt_add(
                backup, source, "source.txt", source_template_offset=0xC0,
                available_capacity_bytes=10000, now=self.now, max_age_seconds=None,
            )
        temporary2, backup2, source2, _ = self._case()
        self.addCleanup(temporary2.cleanup)
        with self.assertRaisesRegex(NewTxtAddError, "cannot be established"):
            build_new_root_txt_add(
                backup2, source2, "new.txt", source_template_offset=0xC0,
                available_capacity_bytes=None, now=self.now, max_age_seconds=None,
            )

    def test_insufficient_capacity_is_checked_after_complete_size(self):
        temporary, backup, source, _ = self._case(b"A" * 20)
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(NewTxtAddError, "requires"):
            build_new_root_txt_add(
                backup, source, "new.txt", source_template_offset=0xC0,
                available_capacity_bytes=95, now=self.now, max_age_seconds=None,
            )

    def test_malformed_or_truncated_backup_is_rejected(self):
        temporary, backup, source, _ = self._case()
        self.addCleanup(temporary.cleanup)
        blob_path = backup / "object-08.bin"
        blob_path.write_bytes(blob_path.read_bytes()[:-1])
        with self.assertRaisesRegex(NewTxtAddError, "length does not match"):
            build_new_root_txt_add(
                backup, source, "new.txt", source_template_offset=0xC0,
                available_capacity_bytes=10000, now=self.now, max_age_seconds=None,
            )

    def test_state_rebase_preserves_unknown_bytes_and_rejects_invalid_offsets(self):
        first = bytearray(64)
        first[0:4] = (1).to_bytes(4, "big")
        first[8:12] = (0xC0).to_bytes(4, "big")
        first[30] = 0xA5
        grouped = bytearray(64)
        grouped[0:4] = (0xC0).to_bytes(4, "big")
        grouped[31] = 0x5A
        rebased, rebased_grouped = rebase_fixed_state_responses(
            (bytes(first), b"\x00" * 64, b"\x00" * 64, b"\x00" * 64),
            bytes(grouped), insertion_offset=0xC0, metadata_delta=0x40,
        )
        self.assertEqual(int.from_bytes(rebased[0][8:12], "big"), 0x100)
        self.assertEqual(int.from_bytes(rebased_grouped[0:4], "big"), 0x100)
        self.assertEqual(rebased[0][30], 0xA5)
        self.assertEqual(rebased_grouped[31], 0x5A)
        bad = bytearray(first)
        bad[8:12] = (0xC1).to_bytes(4, "big")
        with self.assertRaises(StateSerializationError):
            rebase_fixed_state_responses(
                (bytes(bad), b"\x00" * 64, b"\x00" * 64, b"\x00" * 64),
                bytes(grouped), insertion_offset=0xC0, metadata_delta=0x40,
            )
        with self.assertRaises(StateSerializationError):
            rebase_fixed_state_responses(
                (bytes(first), b"\x00" * 64, b"\x00" * 64, b"\x00" * 64),
                bytes(grouped), insertion_offset=0xC0, metadata_delta=0xFFFFFFC0,
            )

    def test_preserves_unrelated_records_and_input_and_hashes_are_deterministic(self):
        temporary, backup, source, result = self._build(b"deterministic\r\n")
        self.addCleanup(temporary.cleanup)
        before_blob = (backup / "object-08.bin").read_bytes()
        before_source = source.read_bytes()
        second = build_new_root_txt_add(
            backup, source, "new.txt", source_template_offset=0xC0,
            available_capacity_bytes=10000, now=self.now, max_age_seconds=None,
        )
        self.assertEqual(result.candidate_blob, second.candidate_blob)
        self.assertEqual(result.audit["audit_sha256"], second.audit["audit_sha256"])
        self.assertEqual((backup / "object-08.bin").read_bytes(), before_blob)
        self.assertEqual(source.read_bytes(), before_source)
        self.assertTrue(result.audit["preservation"]["unrelated_changes_verified"])

    def test_comparison_rejects_missing_new_record_as_unexpected(self):
        temporary, backup, source, result = self._build()
        self.addCleanup(temporary.cleanup)
        comparison = compare_new_txt_candidate(result, backup, now=self.now, max_age_seconds=None)
        self.assertFalse(comparison.exact)
        self.assertFalse(comparison.normalized_equivalent)
        self.assertIn("normalized_blob", comparison.unexpected_differences)


if __name__ == "__main__":
    unittest.main()
