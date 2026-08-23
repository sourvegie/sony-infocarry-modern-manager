from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest

from infocarry.prepared_package import build_prepared_text_package
from infocarry.prepared_transfer_plan import (
    PreparedTransferPlanError,
    build_prepared_transfer_plan,
)
from infocarry.write_gate import VerifiedBackup

try:
    from test_backup_duplicate import make_nested_blob
except ModuleNotFoundError:
    from tests.test_backup_duplicate import make_nested_blob


def _verified_backup(root: Path, blob: bytes) -> VerifiedBackup:
    root.mkdir()
    filename = "object-08-command-8004.bin"
    (root / filename).write_bytes(blob)
    digest = hashlib.sha256(blob).hexdigest()
    return VerifiedBackup(
        directory=root,
        manifest_sha256="a" * 64,
        blob_sha256=digest,
        created_at_utc="2026-08-23T00:00:00+00:00",
        updated_at_utc="2026-08-23T00:00:00+00:00",
        object_count=8,
        verified_at_utc=datetime.now(timezone.utc).isoformat(),
        object_sha256_by_key=(("0x8004:backup-blob", digest),),
        object_filename_by_key=(("0x8004:backup-blob", filename),),
        device_identity=("0x054c", "0x001e"),
    )


class PreparedTransferPlanTests(unittest.TestCase):
    def test_preview_reports_paths_capacity_and_blocked_primitives(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_text("short\n", encoding="utf-8")
            package = build_prepared_text_package(source, "New Book", "chapter.txt")
            backup = _verified_backup(root / "backup", make_nested_blob())
            plan = build_prepared_transfer_plan(
                package, backup, available_capacity_bytes=10_000
            )
            report = plan.to_dict()
            self.assertFalse(plan.eligible)
            self.assertEqual(
                report["proposed"]["destination_paths"],
                ["root\\New Book", "root\\New Book\\chapter.txt"],
            )
            self.assertEqual(report["conflicts"]["status"], "none")
            self.assertEqual(report["size"]["capacity"]["status"], "sufficient_for_lower_bound_only")
            self.assertFalse(report["proven_primitives"]["new_root_folder_creation"])
            self.assertTrue(report["proven_primitives"]["capture7_one_folder_one_txt_fixture_reproduction"])
            self.assertTrue(report["eligibility"]["exact_capture7_fixture_reproduction_scope"])
            self.assertIn("fresh_folder_timestamp_generation", report["blocked_primitives"])
            self.assertIn("live_folder_package_transaction", report["blocked_primitives"])
            self.assertFalse(report["eligibility"]["candidate_eligible"])
            self.assertFalse(report["usb_accessed"])
            self.assertFalse(report["safety"]["candidate_bytes_included"])

    def test_existing_folder_is_a_conflict_and_unknown_capacity_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_text("short", encoding="utf-8")
            package = build_prepared_text_package(source, "folder", "chapter.txt")
            backup = _verified_backup(root / "backup", make_nested_blob())
            plan = build_prepared_transfer_plan(package, backup)
            report = plan.to_dict()
            self.assertEqual(report["conflicts"]["status"], "conflict")
            self.assertEqual(report["size"]["capacity"]["status"], "unknown")
            self.assertIn("root\\folder", [entry["path"] for entry in report["conflicts"]["entries"]])
            self.assertFalse(plan.eligible)

    def test_rejects_changed_verified_blob(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_text("short", encoding="utf-8")
            package = build_prepared_text_package(source, "Book", "chapter.txt")
            backup = _verified_backup(root / "backup", make_nested_blob())
            (backup.directory / "object-08-command-8004.bin").write_bytes(b"changed")
            with self.assertRaises(PreparedTransferPlanError):
                build_prepared_transfer_plan(package, backup)


if __name__ == "__main__":
    unittest.main()
