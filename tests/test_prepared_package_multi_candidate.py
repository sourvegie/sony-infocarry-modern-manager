from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import calculate_backup_checksum, parse_backup_blob
from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.device_info import RawInfoResponse
from infocarry.prepared_media_package import build_prepared_media_package
from infocarry.prepared_multi_text import build_prepared_text_package_set
from infocarry.prepared_package_multi_candidate import (
    PreparedMultiCandidateError,
    build_prepared_multi_package_candidate,
)
from infocarry.write_gate import verify_fresh_backup

try:
    from test_backup_format import make_record
    from test_new_txt import _write_archive
    from test_prepared_media_package import make_profile_bmp
except ModuleNotFoundError:
    from tests.test_backup_format import make_record
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_media_package import make_profile_bmp


def _blob(records: bytes, content: bytes) -> bytes:
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
    result = bytearray(bytes(header) + records + content + b"\xff" * 4)
    result[0x1C:0x20] = calculate_backup_checksum(bytes(result)).to_bytes(4, "big")
    return bytes(result)


def _template_blobs() -> tuple[bytes, bytes]:
    old = b"old\r\n"
    first = b"template one\r\n"
    second = b"template two\r\n"
    bmp = make_profile_bmp()
    text_prefix = b"\x01" + b"\xff" * 31
    bmp_prefix = b"\xff" * 16
    old_segment = text_prefix + old
    first_segment = text_prefix + first
    second_segment = text_prefix + second
    bmp_segment = bmp_prefix + bmp
    old_aligned = old_segment + b"\xff" * ((-len(old_segment)) % 4)
    first_aligned = first_segment + b"\xff" * ((-len(first_segment)) % 4)
    second_aligned = second_segment + b"\xff" * ((-len(second_segment)) % 4)
    bmp_aligned = bmp_segment + b"\xff" * ((-len(bmp_segment)) % 4)
    baseline_records = b"".join(
        (
            make_record(0xD0, "", 0x40, 0x80, "root"),
            make_record(0xD0, "", 0x00, 0x40, ".."),
            make_record(0xE0, "txt", 0x00, len(old), "old", 0x200),
            make_record(0xD0, "", 0x40, 0x80, ".."),
        )
    )
    template_records = b"".join(
        (
            make_record(0xD0, "", 0x40, 0xC0, "root"),
            make_record(0xD0, "", 0x00, 0x40, ".."),
            make_record(0xE0, "txt", 0x00, len(old), "old", 0x200),
            make_record(0xD0, "", 0x100, 0xC0, "Template"),
            make_record(0xD0, "", 0x40, 0x100, ".."),
            make_record(0xE0, "txt", len(old_aligned), len(first), "chapter", 0x200),
            make_record(
                0xE0,
                "bmp",
                len(old_aligned) + len(first_aligned),
                len(bmp),
                "page",
                0x100,
            ),
            make_record(0xD0, "", 0x40, 0xC0, ".."),
        )
    )
    return _blob(baseline_records, old_aligned), _blob(
        template_records, old_aligned + first_aligned + bmp_aligned
    )


class PreparedMultiCandidateTests(unittest.TestCase):
    def _response(self) -> NativeCapacityResponse:
        fixture = json.loads(
            (Path(__file__).parent / "fixtures" / "infocarry_info_responses.json").read_text()
        )
        return NativeCapacityResponse.from_hardware_response(
            RawInfoResponse(0x0019, "hardware", bytes.fromhex(fixture["hardware"]["response_hex"])),
            device_identity=(0x054C, 0x001E),
        )

    def _case(self, *, mixed=False):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        baseline_blob, template_blob = _template_blobs()
        state = {command: b"\x00" * 64 for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        backup_path = _write_archive(root / "backup", baseline_blob, now, fixed_state=state)
        one = root / "one.txt"
        two = root / "two.txt"
        one.write_text("one\n", encoding="utf-8")
        two.write_text("two\n", encoding="utf-8")
        if mixed:
            image = root / "page.bmp"
            image.write_bytes(make_profile_bmp())
            package = build_prepared_media_package(
                ((one, "one.txt"), (image, "page.bmp"), (two, "two.txt")),
                "NewBook",
            )
        else:
            package = build_prepared_text_package_set(
                ((one, "one.txt"), (two, "two.txt")), "NewBook"
            )
        backup = verify_fresh_backup(backup_path, now=now, max_age_seconds=None)
        candidate = build_prepared_multi_package_candidate(
            package,
            backup,
            parse_backup_blob(template_blob),
            new_record_timestamp_be32=0x6A8ABA6F,
            native_capacity_response=self._response(),
            template_folder_path=("root", "Template"),
            template_item_paths={
                "txt": ("root", "Template", "chapter"),
                "bmp": ("root", "Template", "page"),
            },
        )
        return temporary, package, backup, candidate, parse_backup_blob(template_blob)

    def test_multiple_txt_candidate_preserves_shared_records_and_order(self):
        temporary, package, backup, candidate, _template = self._case()
        self.addCleanup(temporary.cleanup)
        self.assertEqual(
            candidate.audit["candidate"]["added_paths"],
            ["root\\NewBook", "root\\NewBook\\one.txt", "root\\NewBook\\two.txt"],
        )
        self.assertEqual(candidate.audit["package"]["ordered_items"][1]["order"], 1)
        self.assertEqual(len(candidate.candidate.records), len(candidate.baseline.records) + 4)
        self.assertEqual(candidate.candidate.record_at(0x40).field_08_be32, 0xC0)
        for path in candidate.baseline.paths.values():
            old = next(candidate.baseline.record_at(offset) for offset, value in candidate.baseline.paths.items() if value == path)
            new = next(candidate.candidate.record_at(offset) for offset, value in candidate.candidate.paths.items() if value == path)
            self.assertEqual(old.timestamp_be32, new.timestamp_be32)
        self.assertTrue(candidate.audit["preservation"]["unknown_record_bytes_preserved"])
        repeat = build_prepared_multi_package_candidate(
            package,
            backup,
            _template,
            new_record_timestamp_be32=0x6A8ABA6F,
            native_capacity_response=self._response(),
            template_folder_path=("root", "Template"),
            template_item_paths={
                "txt": ("root", "Template", "chapter"),
                "bmp": ("root", "Template", "page"),
            },
        )
        self.assertEqual(candidate.candidate_blob, repeat.candidate_blob)

    def test_mixed_candidate_preserves_exact_bmp_payload_and_types(self):
        temporary, package, _backup, candidate, _template = self._case(mixed=True)
        self.addCleanup(temporary.cleanup)
        self.assertEqual([entry["kind"] for entry in candidate.audit["package"]["ordered_items"]], ["txt", "bmp", "txt"])
        bmp_record = next(
            candidate.candidate.record_at(offset)
            for offset, path in candidate.candidate.paths.items()
            if path == ("root", "NewBook", "page")
        )
        self.assertEqual(candidate.candidate.payload_parts(bmp_record)[1], make_profile_bmp())
        self.assertEqual(len(candidate.candidate.payload_parts(bmp_record)[0]), 16)
        self.assertEqual(candidate.audit["allocation"]["metadata_records_added"], 5)

    def test_requires_each_kind_template_and_native_capacity(self):
        temporary, package, backup, _candidate, template = self._case()
        self.addCleanup(temporary.cleanup)
        image = Path(temporary.name) / "page.bmp"
        image.write_bytes(make_profile_bmp())
        mixed = build_prepared_media_package(
            ((Path(temporary.name) / "one.txt", "one.txt"), (image, "page.bmp"), (Path(temporary.name) / "two.txt", "two.txt")),
            "NewBook2",
        )
        with self.assertRaisesRegex(PreparedMultiCandidateError, "native BMP"):
            build_prepared_multi_package_candidate(
                mixed,
                backup,
                template,
                new_record_timestamp_be32=1,
                native_capacity_response=self._response(),
                template_folder_path=("root", "Template"),
                template_item_paths={"txt": ("root", "Template", "chapter")},
            )
        with self.assertRaisesRegex(PreparedMultiCandidateError, "native 0x0019"):
            build_prepared_multi_package_candidate(
                package,
                backup,
                template,
                new_record_timestamp_be32=1,
                native_capacity_response=None,
                template_folder_path=("root", "Template"),
                template_item_paths={"txt": ("root", "Template", "chapter")},
            )

    def test_source_change_and_duplicate_target_fail_closed(self):
        temporary, package, backup, _candidate, template = self._case()
        self.addCleanup(temporary.cleanup)
        package.items[0].source_path.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(PreparedMultiCandidateError, "source changed"):
            build_prepared_multi_package_candidate(
                package,
                backup,
                template,
                new_record_timestamp_be32=1,
                native_capacity_response=self._response(),
                template_item_paths={"txt": ("root", "Template", "chapter")},
            )


if __name__ == "__main__":
    unittest.main()
