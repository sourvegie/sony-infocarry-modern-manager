from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from infocarry.backup_state_identity import (
    BackupStateIdentityError,
    compare_verified_backups,
    derive_backup_state_identity,
)
from infocarry.write_gate import verify_fresh_backup

try:
    from test_new_txt import _make_root_blob, _write_archive
except ModuleNotFoundError:
    from tests.test_new_txt import _make_root_blob, _write_archive


class BackupStateIdentityTests(unittest.TestCase):
    def _archive(self, root: Path, timestamp: datetime):
        return _write_archive(root, _make_root_blob(), timestamp)

    def test_capture_path_and_timestamps_are_provenance_only(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_path = self._archive(root / "capture-a", now)
            second_path = self._archive(root / "capture-b", now - timedelta(seconds=3))
            second_manifest_path = second_path / "manifest.json"
            second_manifest = json.loads(second_manifest_path.read_text(encoding="utf-8"))
            second_manifest["created_at_utc"] = (now - timedelta(seconds=7)).isoformat()
            second_manifest["updated_at_utc"] = (now - timedelta(seconds=6)).isoformat()
            for sequence, entry in enumerate(second_manifest["objects"], start=1):
                entry["received_at_utc"] = (
                    now - timedelta(seconds=sequence)
                ).isoformat()
            second_manifest_path.write_text(
                json.dumps(second_manifest), encoding="utf-8"
            )

            first = verify_fresh_backup(first_path, now=now, max_age_seconds=None)
            second = verify_fresh_backup(second_path, now=now, max_age_seconds=None)
            comparison = compare_verified_backups(first, second)

            self.assertEqual(derive_backup_state_identity(first), derive_backup_state_identity(second))
            self.assertTrue(comparison.raw_state_equal)
            self.assertEqual(comparison.raw_state_differences, ())
            self.assertTrue(comparison.provenance_differences)
            self.assertIn(
                "archive_directory",
                {entry["field"] for entry in comparison.provenance_differences},
            )
            self.assertIn(
                "manifest_sha256",
                {entry["field"] for entry in comparison.provenance_differences},
            )
            self.assertIn(
                "object_received_at_utc",
                {entry["field"] for entry in comparison.provenance_differences},
            )

    def test_each_material_identity_change_fails_closed(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline_path = self._archive(root / "baseline", now)

            cases = (
                "protocol",
                "protocol_extra",
                "role",
                "command",
                "object_set",
                "filename",
                "requested_length",
            )
            for case in cases:
                with self.subTest(case=case):
                    changed_path = Path(temporary) / case
                    shutil.copytree(baseline_path, changed_path)
                    manifest_path = changed_path / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if case == "protocol":
                        manifest["protocol"]["direction"] = "host-to-device"
                    elif case == "protocol_extra":
                        manifest["protocol"]["unexpected"] = "not-supported"
                    elif case == "role":
                        manifest["objects"][0]["kind"] = "response-0025"
                    elif case == "command":
                        manifest["objects"][0]["command"] = "0x0025"
                    elif case == "object_set":
                        manifest["objects"].pop(0)
                    elif case == "filename":
                        old_name = manifest["objects"][0]["filename"]
                        new_name = "object-99.bin"
                        (changed_path / old_name).rename(changed_path / new_name)
                        manifest["objects"][0]["filename"] = new_name
                    elif case == "requested_length":
                        manifest["objects"][0]["requested_length"] += 1
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                    verified = verify_fresh_backup(
                        changed_path, now=now, max_age_seconds=None
                    )
                    with self.assertRaises(BackupStateIdentityError):
                        derive_backup_state_identity(verified)

            raw_path = Path(temporary) / "raw"
            shutil.copytree(baseline_path, raw_path)
            raw_object = raw_path / "object-08.bin"
            raw_object.write_bytes(raw_object.read_bytes() + b"x")
            with self.assertRaises(Exception):
                verified = verify_fresh_backup(
                    raw_path, now=now, max_age_seconds=None
                )
                derive_backup_state_identity(verified)

    def test_dynamic_and_fixed_state_changes_make_raw_identity_unequal(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline_path = self._archive(root / "baseline", now)
            dynamic_path = self._archive(
                root / "different-dynamic", now
            )
            dynamic_manifest = json.loads(
                (dynamic_path / "manifest.json").read_text(encoding="utf-8")
            )
            blob_path = dynamic_path / dynamic_manifest["objects"][-1]["filename"]
            blob_path.write_bytes(_make_root_blob(b"different\r\n"))
            dynamic_manifest["objects"][-1]["received_length"] = blob_path.stat().st_size
            dynamic_manifest["objects"][-1]["requested_length"] = blob_path.stat().st_size
            dynamic_manifest["objects"][-1]["sha256"] = hashlib.sha256(
                blob_path.read_bytes()
            ).hexdigest()
            (dynamic_path / "manifest.json").write_text(
                json.dumps(dynamic_manifest), encoding="utf-8"
            )

            fixed_state = {
                command: b"\x00" * 64
                for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)
            }
            fixed_path = _write_archive(
                root / "different-fixed", _make_root_blob(), now, fixed_state=fixed_state
            )
            baseline = verify_fresh_backup(baseline_path, now=now, max_age_seconds=None)
            dynamic = verify_fresh_backup(dynamic_path, now=now, max_age_seconds=None)
            fixed = verify_fresh_backup(fixed_path, now=now, max_age_seconds=None)
            dynamic_comparison = compare_verified_backups(baseline, dynamic)
            fixed_comparison = compare_verified_backups(baseline, fixed)
            self.assertFalse(dynamic_comparison.raw_state_equal)
            self.assertFalse(fixed_comparison.raw_state_equal)
            self.assertTrue(
                any(
                    entry["field"].endswith("sha256")
                    for entry in dynamic_comparison.raw_state_differences
                )
            )
            self.assertTrue(
                any(
                    entry["field"].startswith("fixed_state_sha256")
                    for entry in fixed_comparison.raw_state_differences
                )
            )

    def test_device_and_length_changes_are_rejected_by_integrity_gate(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        with tempfile.TemporaryDirectory() as temporary:
            baseline_path = self._archive(Path(temporary) / "baseline", now)
            for field, value in (("device", {"vendor_id": "0x0000", "product_id": "0x001e"}),):
                changed_path = Path(temporary) / field
                shutil.copytree(baseline_path, changed_path)
                manifest_path = changed_path / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest[field] = value
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(Exception):
                    derive_backup_state_identity(
                        verify_fresh_backup(changed_path, now=now, max_age_seconds=None)
                    )

            length_path = Path(temporary) / "length"
            shutil.copytree(baseline_path, length_path)
            manifest_path = length_path / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["objects"][0]["received_length"] += 1
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(Exception):
                derive_backup_state_identity(
                    verify_fresh_backup(length_path, now=now, max_age_seconds=None)
                )


if __name__ == "__main__":
    unittest.main()
