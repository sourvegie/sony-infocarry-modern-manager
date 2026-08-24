import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import calculate_backup_checksum
from infocarry.i7_experiment import (
    I7_SESSION_STAGES,
    I7_TARGET_FILENAME,
    I7ExperimentError,
    compare_i7_backups,
    create_i7_session,
    create_synthetic_fixture,
    hash_manager_snapshot,
    ingest_snoopy_log,
    record_host_clock,
    synthetic_i7_fixture_bytes,
    validate_complete_backup,
    validate_synthetic_fixture,
    write_manager_snapshot_manifest,
)

try:
    from test_backup_format import make_text_blob
    from test_usblog import _synthetic_101b
except ModuleNotFoundError:
    from tests.test_backup_format import make_text_blob
    from tests.test_usblog import _synthetic_101b


def _write_complete_backup(root: Path, blob: bytes) -> None:
    root.mkdir()
    objects = []
    raw_objects = [
        (0x0024, "response-0024", b"A" * 64),
        (0x001B, "response-001b", b"\x00" * 64),
        (0x001C, "response-001c", b"\x00" * 64),
        (0x001D, "response-001d", b"\x00" * 64),
        (0x001E, "response-001e", b"\x00" * 64),
        (0x001F, "response-001f", b"\x00" * 64),
        (0x8004, "backup-blob-probe", b"B" * 64),
        (0x8004, "backup-blob", blob),
    ]
    for ordinal, (command, kind, data) in enumerate(raw_objects, start=1):
        filename = f"object-{ordinal:02d}.bin"
        (root / filename).write_bytes(data)
        objects.append(
            {
                "sequence": ordinal,
                "command": f"0x{command:04x}",
                "kind": kind,
                "filename": filename,
                "received_length": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    timestamp = datetime.now(timezone.utc).isoformat()
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "format": "infocarry-raw-backup-v1",
                "state": "complete",
                "created_at_utc": timestamp,
                "updated_at_utc": timestamp,
                "device": {"vendor_id": "0x054c", "product_id": "0x001e"},
                "objects": objects,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


class I7ExperimentTests(unittest.TestCase):
    def test_fixture_is_exact_ascii_cp932_source_and_non_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / I7_TARGET_FILENAME
            report = create_synthetic_fixture(source)
            self.assertEqual(report.size_bytes, 1863)
            self.assertEqual(
                report.sha256,
                "3aa626dc1e0dbd2fe13b59fbea7eddf43358a522b9f55ed15ac18556b2a69d4b",
            )
            self.assertEqual(report.encoding, "UTF-8 (ASCII subset; strict)")
            self.assertEqual(report.line_ending, "CRLF")
            self.assertEqual(report.line_count, 56)
            self.assertEqual(validate_synthetic_fixture(source), report)
            with self.assertRaises(I7ExperimentError):
                create_synthetic_fixture(source)

    def test_fixture_rejects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / I7_TARGET_FILENAME
            source.write_bytes(synthetic_i7_fixture_bytes() + b"changed")
            with self.assertRaises(I7ExperimentError):
                validate_synthetic_fixture(source)

    def test_session_is_new_and_contains_only_preparation_stages(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / I7_TARGET_FILENAME
            fixture = create_synthetic_fixture(source)
            session = create_i7_session(Path(temporary) / "session", fixture=fixture)
            manifest = json.loads((session / "session-manifest.json").read_text())
            self.assertFalse(manifest["usb_operation_performed"])
            self.assertEqual(manifest["stages"], list(I7_SESSION_STAGES))
            for stage in I7_SESSION_STAGES:
                self.assertTrue((session / stage).is_dir())
            with self.assertRaises(I7ExperimentError):
                create_i7_session(session)

    def test_clock_record_is_explicitly_host_only_and_non_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "macos-clock.json"
            record_host_clock(destination, "macOS")
            payload = json.loads(destination.read_text())
            self.assertEqual(payload["host_label"], "macOS")
            self.assertFalse(payload["device_clock_read"])
            self.assertEqual(payload["supported_device_identity"]["product_id"], "0x001e")
            with self.assertRaises(I7ExperimentError):
                record_host_clock(destination, "macOS")

    def test_backup_inventory_validates_objects_and_fixed_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            backup = Path(temporary) / "backup"
            _write_complete_backup(backup, make_text_blob())
            report = validate_complete_backup(backup)
            self.assertEqual(report["object_count"], 8)
            self.assertEqual(report["record_count"], 3)
            self.assertEqual(report["fixed_state"]["0x001b"]["parsed"]["count"], 0)
            self.assertEqual(report["fixed_state"]["0x001f"]["parsed"]["groups"], [[0] * 5, [0] * 5])
            self.assertEqual(report["device"]["vendor_id"], "0x054c")

    def test_backup_inventory_rejects_incomplete_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            backup = Path(temporary) / "backup"
            backup.mkdir()
            (backup / "manifest.json").write_text(
                json.dumps({"format": "infocarry-raw-backup-v1", "state": "incomplete"}),
                encoding="utf-8",
            )
            with self.assertRaises(I7ExperimentError):
                validate_complete_backup(backup)

    def test_manager_snapshot_preserves_nested_order_path_and_hashes_all_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "manager-before"
            (root / "Backup").mkdir(parents=True)
            (root / "Memo").mkdir()
            order = root / "ICM" / "転送元フォルダ" / "order.vnw"
            order.parent.mkdir(parents=True)
            (root / "Backup" / "VICDATA.bin").write_bytes(b"vicdata")
            (root / "Memo" / "VICMEM.bin").write_bytes(b"vicmem")
            (root / "Memo" / "VICLV.bin").write_bytes(b"viclv")
            order.write_bytes(b"order")
            (root / I7_TARGET_FILENAME).write_bytes(b"source")
            report = hash_manager_snapshot(root)
            self.assertEqual(
                report["required_files"]["order.vnw"]["relative_path"],
                "ICM/転送元フォルダ/order.vnw",
            )
            self.assertIn("filesystem_created_at_utc", report["files"][0])
            self.assertIn("filesystem_modified_at_utc", report["files"][0])
            self.assertEqual(report["file_count"], 5)
            manifest = write_manager_snapshot_manifest(root)
            self.assertTrue(manifest.is_file())
            with self.assertRaises(I7ExperimentError):
                write_manager_snapshot_manifest(root)

    def test_snoopy_ingestion_is_hash_only_and_does_not_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            native = Path(temporary) / "01-add.usblog"
            native.write_bytes(_synthetic_101b())
            report = ingest_snoopy_log(native)
            self.assertEqual(report["ordinary_101b_transaction_count"], 1)
            self.assertEqual(report["native_log_sha256"], hashlib.sha256(native.read_bytes()).hexdigest())
            self.assertEqual(report["completion"]["status"], "not_decoded_by_offline_101b_parser")

    def test_backup_comparison_is_deterministic_and_reports_no_delta(self):
        with tempfile.TemporaryDirectory() as temporary:
            before = Path(temporary) / "before"
            after = Path(temporary) / "after"
            blob = make_text_blob()
            _write_complete_backup(before, blob)
            _write_complete_backup(after, blob)
            report = compare_i7_backups(before, after)
            self.assertEqual(report["paths"]["added"], [])
            self.assertEqual(report["paths"]["removed"], [])
            self.assertEqual(report["model_growth_bytes"], 0)
            self.assertTrue(report["unrelated_file_payloads_unchanged"])
            self.assertTrue(all(item["byte_identical"] for item in report["fixed_state"].values()))


if __name__ == "__main__":
    unittest.main()
