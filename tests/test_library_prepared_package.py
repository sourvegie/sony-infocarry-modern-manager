import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from infocarry.library import (
    PREPARATION_PREPARED,
    STATE_READY,
    LibraryCatalog,
    LibraryImportError,
)
from infocarry.library_transfer_plan import build_library_transfer_queue_plan
from infocarry.prepared_media_package import (
    PreparedMediaPackageError,
    build_prepared_content_package,
    build_prepared_media_package,
    export_prepared_media_package,
    load_prepared_media_package,
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
        created_at_utc="2026-08-31T00:00:00+00:00",
        updated_at_utc="2026-08-31T00:00:00+00:00",
        object_count=8,
        verified_at_utc=datetime.now(timezone.utc).isoformat(),
        object_sha256_by_key=(("0x8004:backup-blob", digest),),
        object_filename_by_key=(("0x8004:backup-blob", filename),),
        device_identity=("0x054c", "0x001e"),
    )


class PreparedPackageLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.first = self.root / "intro.txt"
        self.image = self.root / "page.bmp"
        self.last = self.root / "ending.txt"
        self.first.write_text("Introduction\n日本語\n", encoding="utf-8")
        self.image.write_bytes(make_profile_bmp())
        self.last.write_text("The End\n", encoding="utf-8")
        package = build_prepared_media_package(
            ((self.first, "01-introduction.txt"), (self.image, "02-page.bmp"), (self.last, "03-ending.txt")),
            "Grouped Book",
        )
        self.package_root = export_prepared_media_package(package, self.root / "prepared-output")

    def tearDown(self):
        self.temporary.cleanup()

    def test_import_revalidates_manifest_archive_and_preserves_source(self):
        before = (self.first.read_bytes(), self.image.read_bytes(), self.last.read_bytes())
        imported = load_prepared_media_package(self.package_root)
        self.assertEqual(imported.manifest_sha256, imported.manifest["prepared_manifest_sha256"])
        self.assertEqual(
            [(item["order"], item["kind"], item["name"]) for item in imported.children],
            [(0, "txt", "01-introduction.txt"), (1, "bmp", "02-page.bmp"), (2, "txt", "03-ending.txt")],
        )
        self.assertEqual(
            [item["package_path"] for item in imported.children],
            ["source/0001_intro.txt", "source/0002_page.bmp", "source/0003_ending.txt"],
        )
        self.assertEqual((self.first.read_bytes(), self.image.read_bytes(), self.last.read_bytes()), before)

    def test_explicit_content_builder_accepts_txt_only_without_changing_mixed_default(self):
        package = build_prepared_content_package(
            ((self.first, "01-introduction.txt"), (self.last, "03-ending.txt")),
            "Text Collection",
        )
        destination = export_prepared_media_package(package, self.root / "txt-only-output")
        imported = load_prepared_media_package(destination)
        self.assertEqual(imported.manifest["content_kinds"], ["txt"])
        self.assertEqual([child.kind for child in imported.package.items], ["txt", "txt"])

    def test_import_rejects_prepared_payload_mutation(self):
        child = self.package_root / "prepared/Grouped Book/02-page.bmp"
        child.write_bytes(child.read_bytes() + b"tamper")
        with self.assertRaisesRegex(PreparedMediaPackageError, "prepared child bytes mismatch"):
            load_prepared_media_package(self.package_root)

    def test_import_rejects_source_mutation_and_reordered_children(self):
        source = self.package_root / "source/0001_intro.txt"
        source.write_bytes(b"changed\n")
        with self.assertRaisesRegex(PreparedMediaPackageError, "source hash/size mismatch"):
            load_prepared_media_package(self.package_root)

        # Restore the source, then change a signed manifest field.  The
        # manifest is deliberately rehashed so the order validator, rather
        # than only the manifest-integrity check, is exercised.
        source.write_bytes(self.first.read_bytes())
        manifest_path = self.package_root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["items"][1]["order"] = 2
        unsigned = dict(manifest)
        unsigned.pop("prepared_manifest_sha256")
        manifest["prepared_manifest_sha256"] = hashlib.sha256(
            json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(PreparedMediaPackageError, "child order"):
            load_prepared_media_package(self.package_root)

    def test_import_rejects_unsupported_or_duplicate_children(self):
        manifest_path = self.package_root / "manifest.json"
        original = json.loads(manifest_path.read_text(encoding="utf-8"))
        for mutation, message in (
            (lambda value: value["items"][1].update(kind="epub"), "unsupported kind"),
            (
                lambda value: (
                    value["items"][2].update(
                        name="01-introduction.txt",
                        path="root\\Grouped Book\\01-introduction.txt",
                    ),
                    value["target"].update(
                        item_paths=[
                            "root\\Grouped Book\\01-introduction.txt",
                            "root\\Grouped Book\\02-page.bmp",
                            "root\\Grouped Book\\01-introduction.txt",
                        ]
                    ),
                ),
                "unique",
            ),
        ):
            manifest = json.loads(json.dumps(original))
            mutation(manifest)
            unsigned = dict(manifest)
            unsigned.pop("prepared_manifest_sha256")
            manifest["prepared_manifest_sha256"] = hashlib.sha256(
                json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(PreparedMediaPackageError, message):
                load_prepared_media_package(self.package_root)

    def test_import_rejects_escaping_child_path_even_with_rehashed_manifest(self):
        manifest_path = self.package_root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["items"][0]["package_path"] = "../outside.txt"
        unsigned = dict(manifest)
        unsigned.pop("prepared_manifest_sha256")
        manifest["prepared_manifest_sha256"] = hashlib.sha256(
            json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(PreparedMediaPackageError, "escapes"):
            load_prepared_media_package(self.package_root)

    def test_library_import_is_one_item_idempotent_and_removal_is_non_destructive(self):
        catalog = LibraryCatalog(self.root / "app/library.json")
        item = catalog.import_prepared_package(
            self.package_root,
            now="2026-08-31T00:00:00+00:00",
        )
        self.assertEqual(item.state, STATE_READY)
        self.assertEqual(item.preparation_state, PREPARATION_PREPARED)
        self.assertIsNotNone(item.package)
        self.assertIsNone(item.target_child_name)
        self.assertEqual(len(item.package.children), 3)
        first_catalog = (catalog.path.read_bytes(), self.first.read_bytes(), self.image.read_bytes(), self.last.read_bytes())
        self.assertEqual(catalog.import_prepared_package(self.package_root), item)
        self.assertEqual(catalog.path.read_bytes(), first_catalog[0])
        self.assertTrue(catalog.remove(item.item_id))
        self.assertEqual((self.first.read_bytes(), self.image.read_bytes(), self.last.read_bytes()), first_catalog[1:])

    def test_legacy_source_item_remains_a_legacy_item_after_round_trip(self):
        source = self.root / "plain.txt"
        source.write_text("plain", encoding="utf-8")
        catalog = LibraryCatalog(self.root / "legacy-app/library.json")
        item = catalog.import_file(source)
        raw_item = catalog.to_dict()["items"][0]
        self.assertNotIn("item_kind", raw_item)
        self.assertNotIn("package", raw_item)
        self.assertEqual(LibraryCatalog(catalog.path).get(item.item_id), item)

    def test_changed_package_is_not_silently_replaced(self):
        catalog = LibraryCatalog(self.root / "app/library.json")
        item = catalog.import_prepared_package(self.package_root)
        manifest_path = self.package_root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["notice"] = "changed"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(LibraryImportError):
            catalog.import_prepared_package(self.package_root)
        self.assertEqual(catalog.get(item.item_id), item)

    def test_catalog_round_trip_and_grouped_queue_review(self):
        catalog = LibraryCatalog(self.root / "app/library.json")
        item = catalog.import_prepared_package(self.package_root)
        reloaded = LibraryCatalog(catalog.path).get(item.item_id)
        self.assertEqual(reloaded, item)
        plan = build_library_transfer_queue_plan(
            LibraryCatalog(catalog.path),
            selected_item_ids=[item.item_id],
            backup=_verified_backup(self.root / "backup", make_nested_blob()),
            available_capacity_bytes=100_000,
        )
        report = plan.to_dict()
        self.assertTrue(plan.review_ready)
        self.assertTrue(plan.queue_ready)
        self.assertFalse(plan.eligible)
        self.assertEqual(report["totals"]["selected_items"], 1)
        self.assertEqual(report["items"][0]["operation_type"], "prepared_flat_typed_package")
        self.assertEqual(
            [(child["kind"], child["name"]) for child in report["items"][0]["prepared_artifact"]["ordered_children"]],
            [("txt", "01-introduction.txt"), ("bmp", "02-page.bmp"), ("txt", "03-ending.txt")],
        )
        self.assertFalse(report["grouping"]["automatic_grouping"])
        self.assertIn("candidate construction", " ".join(report["eligibility"]["reasons"]))


if __name__ == "__main__":
    unittest.main()
