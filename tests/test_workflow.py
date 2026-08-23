import json
import tempfile
import unittest
from pathlib import Path

from infocarry.backup_format import (
    BackupBlobHeader,
    BackupRecord,
    ParsedBackupBlob,
    parse_backup_blob,
)
from infocarry.vicdata import xor_vicdata
from infocarry.workflow import (
    WORKFLOW_INVENTORY_FORMAT,
    WorkflowError,
    build_backup_inventory,
    save_json_report,
)

try:
    from test_backup_format import make_text_blob
except ModuleNotFoundError:
    from tests.test_backup_format import make_text_blob


class WorkflowTests(unittest.TestCase):
    def test_inventory_preserves_encoded_child_order(self):
        records = tuple(
            BackupRecord(
                offset=offset,
                flag=0xD0,
                extension="",
                field_04_be32=0,
                field_08_be32=0,
                timestamp_be32=0,
                field_10_be32=0,
                field_14_be32=0,
                name=name,
                raw_hex="00" * 64,
            )
            for offset, name in ((0x40, "root"), (0x80, "alpha"), (0xC0, "zeta"))
        )
        header = BackupBlobHeader(
            version_major=2,
            version_minor=0,
            record_size=64,
            checksum_start=32,
            last_byte_offset=0,
            stored_checksum=0,
            optional_region_start=0,
            optional_region_end=0,
            metadata_start=64,
            metadata_length=192,
            content_start=256,
            content_length=0,
            total_length=256,
            trailer_hex="",
        )
        parsed = ParsedBackupBlob(
            data=b"",
            header=header,
            records=records,
            paths={
                0x40: ("root",),
                0xC0: ("root", "zeta"),
                0x80: ("root", "alpha"),
            },
            parent_record_offsets=(),
            orphan_record_offsets=(),
        )
        report = build_backup_inventory(parsed, "a" * 64)
        self.assertEqual(
            [entry["name"] for entry in report["records"]],
            ["root", "zeta", "alpha"],
        )

    def test_inventory_is_json_safe_and_contains_hashes_not_payloads(self):
        parsed = parse_backup_blob(make_text_blob(b"hello"))
        report = build_backup_inventory(parsed, "a" * 64)
        json.dumps(report, sort_keys=True)
        self.assertEqual(report["format"], WORKFLOW_INVENTORY_FORMAT)
        self.assertEqual(report["summary"]["files"], 1)
        file_entry = next(item for item in report["records"] if item["kind"] == "file")
        self.assertEqual(file_entry["payload_bytes"], 5)
        self.assertNotIn("payload_hex", file_entry)
        self.assertFalse(report["safety"]["device_accessed"])

    def test_report_writer_is_exclusive(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "report"
            target = save_json_report(destination, {"ok": True})
            self.assertEqual(target.read_text(), '{\n  "ok": true\n}\n')
            with self.assertRaises(WorkflowError):
                save_json_report(destination, {"changed": True})

    def test_inventory_rejects_invalid_digest(self):
        parsed = parse_backup_blob(make_text_blob(b"hello"))
        with self.assertRaises(WorkflowError):
            build_backup_inventory(parsed, "not-a-digest")


if __name__ == "__main__":
    unittest.main()
