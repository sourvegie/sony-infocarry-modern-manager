import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from infocarry.library import LibraryCatalog, LibraryCatalogError, LibraryImportError
from infocarry.library_transfer_plan import (
    SELECTION_SELECTED,
    build_library_transfer_queue_plan,
)
from infocarry.prepared_media_package import (
    PreparedMediaPackageError,
    build_prepared_media_package,
    export_prepared_media_package,
)
from infocarry.write_gate import VerifiedBackup

try:
    from test_backup_duplicate import make_nested_blob
    from test_prepared_media_package import make_profile_bmp
except ModuleNotFoundError:
    from tests.test_backup_duplicate import make_nested_blob
    from tests.test_prepared_media_package import make_profile_bmp


def _verified_backup(root: Path, blob: bytes) -> VerifiedBackup:
    root.mkdir()
    filename = "object-08-command-8004.bin"
    (root / filename).write_bytes(blob)
    digest = hashlib.sha256(blob).hexdigest()
    return VerifiedBackup(
        directory=root,
        manifest_sha256="a" * 64,
        blob_sha256=digest,
        created_at_utc="2026-09-13T00:00:00+00:00",
        updated_at_utc="2026-09-13T00:00:00+00:00",
        object_count=8,
        verified_at_utc=datetime.now(timezone.utc).isoformat(),
        object_sha256_by_key=(("0x8004:backup-blob", digest),),
        object_filename_by_key=(("0x8004:backup-blob", filename),),
        device_identity=("0x054c", "0x001e"),
    )


class P18024CatalogPackageNameCollisionTests(unittest.TestCase):
    """Regression coverage for the P18-023 normal Library composition gate."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def _package(self, parent_name: str, target_name: str) -> Path:
        source_root = self.root / f"inputs-{parent_name}"
        source_root.mkdir()
        intro = source_root / "intro.txt"
        image = source_root / "page.bmp"
        ending = source_root / "ending.txt"
        intro.write_text("Introduction\n日本語\n", encoding="utf-8")
        image.write_bytes(make_profile_bmp())
        ending.write_text("The End\n", encoding="utf-8")
        package = build_prepared_media_package(
            (
                (intro, "01-introduction.txt"),
                (image, "02-page-01.bmp"),
                (ending, "03-ending.txt"),
            ),
            target_name,
        )
        # The P18-023 fixture's archive envelope is intentionally named
        # 00-package.  Its name is not the logical Library/package root.
        return export_prepared_media_package(
            package,
            self.root / parent_name / "00-package",
        )

    def test_p18_023_fixture_reproduces_legacy_00_package_failure(self):
        first = self._package("first", "P18-023 target A")
        second = self._package("second", "P18-023 target B")
        catalog = LibraryCatalog(self.root / "legacy" / "library.json")

        # This is the exact old projection seam: both canonical package nodes
        # took the physical archive basename instead of the manifest target.
        with patch(
            "infocarry.library._prepared_package_library_name",
            side_effect=lambda _folder_name: first.name,
        ):
            catalog.import_prepared_package(first)
            with self.assertRaisesRegex(
                LibraryCatalogError,
                r"duplicate sibling name in Library: 00-package",
            ):
                catalog.import_prepared_package(second)

    def test_corrected_package_projection_passes_normal_catalog_queue_gate(self):
        first = self._package("first", "P18-023 target A")
        second = self._package("second", "P18-023 target B")
        catalog = LibraryCatalog(self.root / "catalog" / "library.json")

        first_item = catalog.import_prepared_package(first)
        second_item = catalog.import_prepared_package(second)

        self.assertEqual(first_item.source_filename, "P18-023 target A")
        self.assertEqual(second_item.source_filename, "P18-023 target B")
        self.assertEqual([item.source_filename for item in catalog.roots], [
            "P18-023 target A",
            "P18-023 target B",
        ])

        plan = build_library_transfer_queue_plan(
            catalog,
            selected_item_ids=[first_item.item_id],
            selection_mode=SELECTION_SELECTED,
            backup=_verified_backup(self.root / "backup", make_nested_blob()),
            available_capacity_bytes=100_000,
        )
        self.assertTrue(plan.review_ready)
        self.assertTrue(plan.queue_ready)
        report = plan.to_dict()
        self.assertEqual(report["items"][0]["operation_type"], "prepared_flat_typed_package")
        self.assertEqual(
            [child["kind"] for child in report["items"][0]["prepared_artifact"]["ordered_children"]],
            ["txt", "bmp", "txt"],
        )
        self.assertEqual(
            report["items"][0]["destination"]["folder_path"],
            "root\\P18-023 target A",
        )

    def test_p18_025_exact_target_passes_00_package_projection(self):
        package = self._package("p18-025", "IC_P18_LIBRARY_20260913_03")
        catalog = LibraryCatalog(self.root / "p18-025" / "library.json")

        item = catalog.import_prepared_package(package)
        self.assertEqual(item.source_filename, "IC_P18_LIBRARY_20260913_03")
        self.assertEqual(item.package.folder_name, "IC_P18_LIBRARY_20260913_03")
        self.assertEqual(item.package.root_path, str(package))
        self.assertEqual(package.name, "00-package")

        plan = build_library_transfer_queue_plan(
            catalog,
            selected_item_ids=[item.item_id],
            selection_mode=SELECTION_SELECTED,
            backup=_verified_backup(self.root / "p18-025-backup", make_nested_blob()),
            available_capacity_bytes=100_000,
        )
        self.assertTrue(plan.review_ready)
        self.assertTrue(plan.queue_ready)
        report = plan.to_dict()
        self.assertEqual(
            report["items"][0]["destination"]["folder_path"],
            "root\\IC_P18_LIBRARY_20260913_03",
        )
        self.assertEqual(
            [child["kind"] for child in report["items"][0]["prepared_artifact"]["ordered_children"]],
            ["txt", "bmp", "txt"],
        )

    def test_true_duplicate_owner_visible_package_roots_still_fail_closed(self):
        first = self._package("first", "same owner root")
        second = self._package("second", "same owner root")
        catalog = LibraryCatalog(self.root / "catalog" / "library.json")
        catalog.import_prepared_package(first)

        with self.assertRaisesRegex(
            LibraryCatalogError,
            r"duplicate sibling name in Library: same owner root",
        ):
            catalog.import_prepared_package(second)

    def test_legacy_package_envelope_name_is_normalized_on_catalog_load(self):
        package = self._package("legacy", "logical target")
        catalog = LibraryCatalog(self.root / "catalog" / "library.json")
        item = catalog.import_prepared_package(package)
        raw = catalog.to_dict()
        raw["items"][0]["source_filename"] = "00-package"
        catalog.path.write_text(json.dumps(raw), encoding="utf-8")

        reloaded = LibraryCatalog(catalog.path)
        self.assertEqual(reloaded.get(item.item_id).source_filename, "logical target")

    def test_internal_envelopes_are_collision_safe_against_owner_visible_root(self):
        package = self._package("package", "owner-visible-root")
        catalog = LibraryCatalog(self.root / "catalog" / "library.json")
        owner_root = self.root / "owner-visible-root"
        owner_root.mkdir()
        (owner_root / "payload.txt").write_text("owner payload", encoding="utf-8")
        catalog.import_folder(owner_root)

        with self.assertRaisesRegex(
            LibraryCatalogError,
            r"duplicate sibling name in Library: owner-visible-root",
        ):
            catalog.import_prepared_package(package)

    def test_duplicate_payload_names_remain_rejected_by_package_composition(self):
        source_root = self.root / "duplicate-payload-input"
        source_root.mkdir()
        intro = source_root / "intro.txt"
        image = source_root / "page.bmp"
        ending = source_root / "ending.txt"
        intro.write_text("intro", encoding="utf-8")
        image.write_bytes(make_profile_bmp())
        ending.write_text("ending", encoding="utf-8")

        with self.assertRaisesRegex(PreparedMediaPackageError, "unique"):
            build_prepared_media_package(
                (
                    (intro, "same.txt"),
                    (image, "02-page.bmp"),
                    (ending, "same.txt"),
                ),
                "valid-root",
            )


if __name__ == "__main__":
    unittest.main()
