import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from infocarry.library import LibraryCatalog
from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.device_info import RawInfoResponse
from infocarry.library_transfer_plan import (
    LIBRARY_TRANSFER_PLAN_FORMAT,
    LibraryTransferPlanError,
    SELECTION_ALL_READY,
    SELECTION_SELECTED,
    build_library_transfer_queue_plan,
)
from infocarry.library_prepare import prepare_library_item
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
        created_at_utc="2026-08-31T00:00:00+00:00",
        updated_at_utc="2026-08-31T00:00:00+00:00",
        object_count=8,
        verified_at_utc=datetime.now(timezone.utc).isoformat(),
        object_sha256_by_key=(("0x8004:backup-blob", digest),),
        object_filename_by_key=(("0x8004:backup-blob", filename),),
        device_identity=("0x054c", "0x001e"),
    )


def _native_capacity_response(limit: int = 3_145_728) -> NativeCapacityResponse:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "infocarry_info_responses.json").read_text()
    )
    raw = bytearray(bytes.fromhex(fixture["hardware"]["response_hex"]))
    raw[0x08:0x0C] = limit.to_bytes(4, "big")
    return NativeCapacityResponse.from_hardware_response(
        RawInfoResponse(0x0019, "test", bytes(raw)),
        device_identity=(0x054C, 0x001E),
    )


class LibraryTransferPlanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.catalog = LibraryCatalog(self.root / "app" / "library.json")
        self.source_one = self.root / "one.txt"
        self.source_two = self.root / "two.txt"
        self.source_one.write_text("first\n日本語\n", encoding="utf-8")
        self.source_two.write_text("second\n", encoding="utf-8")
        self.item_one = self.catalog.import_file(
            self.source_one, now="2026-08-31T00:00:00+00:00"
        )
        self.item_two = self.catalog.import_file(
            self.source_two, now="2026-08-31T00:00:00+00:00"
        )
        self.backup = _verified_backup(self.root / "backup", make_nested_blob())

    def tearDown(self):
        self.temporary.cleanup()

    def _prepare(self, item_id: str, folder: str, child: str):
        return prepare_library_item(
            self.catalog,
            item_id,
            folder,
            child,
            now="2026-08-31T00:01:00+00:00",
        )

    def test_selected_plan_rebuilds_prepared_artifact_and_remains_review_only(self):
        prepared = self._prepare(self.item_one.item_id, "Book One", "chapter.txt")

        plan = build_library_transfer_queue_plan(
            self.catalog,
            selected_item_ids=[self.item_one.item_id],
            selection_mode=SELECTION_SELECTED,
            backup=self.backup,
            available_capacity_bytes=10_000,
        )
        report = plan.to_dict()
        item = report["items"][0]

        self.assertEqual(report["format"], LIBRARY_TRANSFER_PLAN_FORMAT)
        self.assertTrue(plan.review_ready)
        self.assertTrue(plan.queue_ready)
        self.assertFalse(plan.eligible)
        self.assertEqual(item["operation_type"], "prepared_root_txt_package")
        self.assertEqual(
            item["prepared_artifact"]["manifest_sha256"],
            prepared.package.prepared_manifest_sha256,
        )
        self.assertEqual(
            item["destination"]["paths"],
            ["root\\Book One", "root\\Book One\\chapter.txt"],
        )
        self.assertEqual(report["capacity"]["status"], "sufficient_for_lower_bound_only")
        self.assertFalse(report["safety"]["candidate_constructed"])
        self.assertFalse(report["safety"]["authorization_created"])
        self.assertFalse(report["safety"]["sender_called"])
        self.assertFalse(report["usb_accessed"])

    def test_all_ready_excludes_unprepared_items_without_mutating_catalog(self):
        self._prepare(self.item_one.item_id, "Book One", "chapter.txt")
        before = self.catalog.to_dict()

        plan = build_library_transfer_queue_plan(
            self.catalog,
            selection_mode=SELECTION_ALL_READY,
            backup=self.backup,
            available_capacity_bytes=10_000,
        )

        self.assertEqual(plan.to_dict()["selection"]["mode"], SELECTION_ALL_READY)
        self.assertEqual(len(plan.to_dict()["items"]), 1)
        self.assertEqual(
            plan.to_dict()["selection"]["excluded_items"][0]["item_id"],
            self.item_two.item_id,
        )
        self.assertEqual(self.catalog.to_dict(), before)

    def test_missing_backup_is_reviewable_but_not_queue_ready(self):
        self._prepare(self.item_one.item_id, "Book One", "chapter.txt")

        plan = build_library_transfer_queue_plan(
            self.catalog,
            selected_item_ids=[self.item_one.item_id],
        )
        report = plan.to_dict()

        self.assertTrue(plan.review_ready)
        self.assertFalse(plan.queue_ready)
        self.assertEqual(
            report["capacity"]["status"],
            "not_evaluated_without_verified_backup",
        )
        self.assertIn("verified device backup", " ".join(report["eligibility"]["reasons"]))
        self.assertFalse(report["safety"]["candidate_bytes_included"])

    def test_missing_capacity_is_not_presented_as_capacity_cleared(self):
        self._prepare(self.item_one.item_id, "Book One", "chapter.txt")

        plan = build_library_transfer_queue_plan(
            self.catalog,
            selected_item_ids=[self.item_one.item_id],
            backup=self.backup,
        )
        report = plan.to_dict()

        self.assertTrue(plan.review_ready)
        self.assertFalse(plan.queue_ready)
        self.assertEqual(report["capacity"]["status"], "unknown")
        self.assertIn("capacity was not supplied", " ".join(report["eligibility"]["reasons"]))

    def test_typed_native_capacity_evidence_is_provenance_bound_in_plan(self):
        self._prepare(self.item_one.item_id, "Book One", "chapter.txt")
        evidence = _native_capacity_response()

        plan = build_library_transfer_queue_plan(
            self.catalog,
            selected_item_ids=[self.item_one.item_id],
            selection_mode=SELECTION_SELECTED,
            backup=self.backup,
            capacity_evidence=evidence,
        )
        report = plan.to_dict()

        self.assertTrue(plan.queue_ready)
        self.assertEqual(report["capacity"]["status"], "sufficient_for_lower_bound_only")
        self.assertEqual(report["capacity"]["source"], "fresh_native_0x0019")
        self.assertEqual(
            report["capacity"]["native_response_sha256"],
            evidence.raw_response_sha256,
        )
        self.assertEqual(report["capacity"]["available_bytes"], 3_145_728)

    def test_typed_native_capacity_evidence_must_match_verified_backup(self):
        self._prepare(self.item_one.item_id, "Book One", "chapter.txt")
        evidence = _native_capacity_response()
        mismatched_backup = VerifiedBackup(
            directory=self.backup.directory,
            manifest_sha256=self.backup.manifest_sha256,
            blob_sha256=self.backup.blob_sha256,
            created_at_utc=self.backup.created_at_utc,
            updated_at_utc=self.backup.updated_at_utc,
            object_count=self.backup.object_count,
            verified_at_utc=self.backup.verified_at_utc,
            object_sha256_by_key=self.backup.object_sha256_by_key,
            object_filename_by_key=self.backup.object_filename_by_key,
            device_identity=("0x054c", "0x001f"),
        )

        with self.assertRaisesRegex(LibraryTransferPlanError, "identity differs"):
            build_library_transfer_queue_plan(
                self.catalog,
                selected_item_ids=[self.item_one.item_id],
                selection_mode=SELECTION_SELECTED,
                backup=mismatched_backup,
                capacity_evidence=evidence,
            )

    def test_existing_backup_folder_and_extensionful_child_are_conflicts(self):
        prepared = self._prepare(self.item_one.item_id, "Folder", "Source.txt")
        conflict_backup = _verified_backup(
            self.root / "conflict-backup", make_nested_blob()
        )

        plan = build_library_transfer_queue_plan(
            self.catalog,
            selected_item_ids=[self.item_one.item_id],
            backup=conflict_backup,
            available_capacity_bytes=10_000,
        )
        report = plan.to_dict()
        item = report["items"][0]

        self.assertFalse(plan.queue_ready)
        self.assertEqual(
            {entry["path"].casefold() for entry in item["conflicts"]},
            {"root\\folder", "root\\folder\\source.txt"},
        )
        self.assertEqual(
            item["prepared_artifact"]["manifest_sha256"],
            prepared.package.prepared_manifest_sha256,
        )

    def test_changed_verified_backup_is_rejected_before_queue_ready(self):
        self._prepare(self.item_one.item_id, "Book One", "chapter.txt")
        backup_blob = self.backup.directory / "object-08-command-8004.bin"
        backup_blob.write_bytes(backup_blob.read_bytes() + b"tampered")

        with self.assertRaisesRegex(
            LibraryTransferPlanError, "dynamic model changed after verification"
        ):
            build_library_transfer_queue_plan(
                self.catalog,
                selected_item_ids=[self.item_one.item_id],
                backup=self.backup,
                available_capacity_bytes=10_000,
            )

    def test_catalog_prepared_manifest_tampering_is_rejected(self):
        self._prepare(self.item_one.item_id, "Book One", "chapter.txt")
        self.catalog.update_preparation(
            self.item_one.item_id,
            preparation_state="prepared",
            state="ready",
            target_folder_name="Book One",
            target_child_name="chapter.txt",
            prepared_manifest_sha256="c" * 64,
            prepared_manifest_path=None,
            last_validation_error=None,
        )

        plan = build_library_transfer_queue_plan(
            self.catalog,
            selected_item_ids=[self.item_one.item_id],
            backup=self.backup,
            available_capacity_bytes=10_000,
        )
        item = plan.to_dict()["items"][0]

        self.assertFalse(plan.queue_ready)
        self.assertIn("prepared manifest hash does not match", " ".join(item["reasons"]))

    def test_malformed_verified_backup_is_rejected_fail_closed(self):
        self._prepare(self.item_one.item_id, "Book One", "chapter.txt")
        malformed_backup = _verified_backup(self.root / "malformed-backup", b"not a backup")

        with self.assertRaises(LibraryTransferPlanError):
            build_library_transfer_queue_plan(
                self.catalog,
                selected_item_ids=[self.item_one.item_id],
                backup=malformed_backup,
                available_capacity_bytes=10_000,
            )

    def test_source_change_is_blocked_by_rebuild_hash_check(self):
        prepared = self._prepare(self.item_one.item_id, "Book One", "chapter.txt")
        self.source_one.write_text("changed\n", encoding="utf-8")

        plan = build_library_transfer_queue_plan(
            self.catalog,
            selected_item_ids=[self.item_one.item_id],
            backup=self.backup,
            available_capacity_bytes=10_000,
        )
        item = plan.to_dict()["items"][0]

        self.assertFalse(plan.queue_ready)
        self.assertIn("source hash changed", " ".join(item["reasons"]))
        self.assertEqual(
            item["prepared_artifact"]["manifest_sha256"],
            prepared.package.prepared_manifest_sha256,
        )

    def test_overlapping_destinations_fail_closed_without_automatic_grouping(self):
        self._prepare(self.item_one.item_id, "Same Book", "one.txt")
        self._prepare(self.item_two.item_id, "Same Book", "two.txt")

        plan = build_library_transfer_queue_plan(
            self.catalog,
            selected_item_ids=[self.item_one.item_id, self.item_two.item_id],
            backup=self.backup,
            available_capacity_bytes=20_000,
        )
        report = plan.to_dict()

        self.assertFalse(plan.queue_ready)
        self.assertEqual(report["grouping"]["automatic_grouping"], False)
        self.assertEqual(report["grouping"]["overlap_status"], "conflict")
        self.assertIn("root\\Same Book", report["grouping"]["overlap_paths"])
        self.assertTrue(
            all(
                "automatic grouping is disabled" in " ".join(item["reasons"])
                for item in report["items"]
            )
        )

    def test_invalid_selection_is_rejected_without_catalog_access_side_effects(self):
        with self.assertRaises(LibraryTransferPlanError):
            build_library_transfer_queue_plan(
                self.catalog,
                selected_item_ids=["missing"],
                backup=self.backup,
            )
        with self.assertRaises(LibraryTransferPlanError):
            build_library_transfer_queue_plan(
                self.catalog,
                selected_item_ids=[self.item_one.item_id],
                selection_mode=SELECTION_ALL_READY,
                backup=self.backup,
            )


if __name__ == "__main__":
    unittest.main()
