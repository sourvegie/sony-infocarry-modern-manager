import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from infocarry.library import (
    LIBRARY_FORMAT,
    LIBRARY_VERSION,
    PREPARATION_PREPARED,
    PREPARATION_STALE,
    SOURCE_MISSING,
    STATE_BLOCKED,
    STATE_IMPORTED,
    STATE_READY,
    STATE_STALE,
    STATE_UNSUPPORTED,
    LibraryCatalog,
    LibraryCatalogError,
    LibraryImportError,
    default_catalog_path,
)


class LibraryCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.catalog_path = self.root / "app-data" / "library.json"
        self.source = self.root / "source.txt"
        self.source.write_bytes("first\n日本語\n".encode("utf-8"))

    def tearDown(self):
        self.temporary.cleanup()

    def test_default_catalog_is_per_user_application_data(self):
        path = default_catalog_path()
        self.assertEqual(path.name, "library.json")
        self.assertNotIn("modern-client-github-candidate", path.parts)

    def test_import_records_identity_hash_and_supported_state(self):
        catalog = LibraryCatalog(self.catalog_path)
        item = catalog.import_file(self.source, now="2026-08-23T10:00:00+00:00")

        self.assertTrue(item.item_id)
        self.assertEqual(item.source_path, str(self.source.resolve()))
        self.assertEqual(item.source_filename, "source.txt")
        self.assertEqual(
            item.source_sha256,
            hashlib.sha256(self.source.read_bytes()).hexdigest(),
        )
        self.assertEqual(item.source_size_bytes, self.source.stat().st_size)
        self.assertEqual(item.detected_format, "utf-8-txt")
        self.assertTrue(item.supported)
        self.assertEqual(item.state, STATE_IMPORTED)
        self.assertEqual(item.source_status, "present")
        self.assertEqual(item.preparation_state, "unprepared")
        self.assertIsNone(item.target_folder_name)
        self.assertIsNone(item.prepared_manifest_sha256)

    def test_import_is_idempotent_for_unchanged_source(self):
        catalog = LibraryCatalog(self.catalog_path)
        first = catalog.import_file(self.source, now="2026-08-23T10:00:00+00:00")
        first_bytes = self.catalog_path.read_bytes()
        second = catalog.import_file(self.source, now="2026-08-23T11:00:00+00:00")

        self.assertEqual(first, second)
        self.assertEqual(first_bytes, self.catalog_path.read_bytes())
        self.assertEqual(len(catalog.items), 1)

    def test_unsupported_format_is_visible_without_conversion(self):
        source = self.root / "notes.md"
        source.write_text("not a txt package", encoding="utf-8")
        catalog = LibraryCatalog(self.catalog_path)

        item = catalog.import_file(source)

        self.assertFalse(item.supported)
        self.assertEqual(item.state, STATE_UNSUPPORTED)
        self.assertIn("unsupported", item.last_validation_error)
        self.assertEqual(item.source_filename, "notes.md")

    def test_invalid_utf8_txt_is_blocked(self):
        source = self.root / "invalid.txt"
        source.write_bytes(b"bad\xff")
        catalog = LibraryCatalog(self.catalog_path)

        item = catalog.import_file(source)

        self.assertTrue(item.supported)
        self.assertEqual(item.state, STATE_BLOCKED)
        self.assertIn("UTF-8", item.last_validation_error)

    def test_changed_source_is_stale_and_original_catalog_identity_is_preserved(self):
        catalog = LibraryCatalog(self.catalog_path)
        item = catalog.import_file(self.source, now="2026-08-23T10:00:00+00:00")
        original_hash = item.source_sha256
        original_import_time = item.import_timestamp_utc
        self.source.write_bytes(b"changed\n")

        updated = catalog.refresh(item.item_id, now="2026-08-23T12:00:00+00:00")

        self.assertEqual(updated.item_id, item.item_id)
        self.assertEqual(updated.source_sha256, original_hash)
        self.assertEqual(updated.import_timestamp_utc, original_import_time)
        self.assertNotEqual(updated.observed_source_sha256, original_hash)
        self.assertEqual(updated.state, STATE_STALE)
        self.assertEqual(updated.source_status, "changed")
        self.assertIn("changed", updated.last_validation_error)
        self.assertEqual(len(updated.source_observations), 2)

    def test_missing_source_is_stale_without_deleting_catalog_information(self):
        catalog = LibraryCatalog(self.catalog_path)
        item = catalog.import_file(self.source)
        original_hash = item.source_sha256
        self.source.unlink()

        updated = catalog.refresh(item.item_id)

        self.assertEqual(updated.state, STATE_STALE)
        self.assertEqual(updated.source_status, SOURCE_MISSING)
        self.assertEqual(updated.source_sha256, original_hash)
        self.assertEqual(updated.source_filename, "source.txt")
        self.assertIn("missing", updated.last_validation_error)

    def test_remove_only_removes_catalog_entry_and_not_source(self):
        catalog = LibraryCatalog(self.catalog_path)
        item = catalog.import_file(self.source)
        self.assertTrue(catalog.remove(item.item_id))

        reloaded = LibraryCatalog(self.catalog_path)
        self.assertEqual(reloaded.items, ())
        self.assertTrue(self.source.exists())
        self.assertFalse(catalog.remove(item.item_id))

    def test_atomic_save_preserves_previous_catalog_version(self):
        catalog = LibraryCatalog(self.catalog_path)
        first = catalog.import_file(self.source)
        second_source = self.root / "second.txt"
        second_source.write_text("second", encoding="utf-8")
        catalog.import_file(second_source)

        previous = json.loads(catalog.previous_path.read_text(encoding="utf-8"))
        current = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        self.assertEqual(previous["format"], LIBRARY_FORMAT)
        self.assertEqual(previous["version"], LIBRARY_VERSION)
        self.assertEqual([value["item_id"] for value in previous["items"]], [first.item_id])
        self.assertEqual(len(current["items"]), 2)

    def test_malformed_catalog_is_rejected_without_repairing_it(self):
        self.catalog_path.parent.mkdir()
        original = b"{not json\n"
        self.catalog_path.write_bytes(original)

        with self.assertRaises(LibraryCatalogError):
            LibraryCatalog(self.catalog_path)

        self.assertEqual(self.catalog_path.read_bytes(), original)

    def test_wrong_version_and_duplicate_ids_are_rejected(self):
        catalog = LibraryCatalog(self.catalog_path)
        item = catalog.import_file(self.source)
        raw = catalog.to_dict()
        raw["version"] = 999
        self.catalog_path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaises(LibraryCatalogError):
            LibraryCatalog(self.catalog_path)

        raw["version"] = LIBRARY_VERSION
        raw["items"].append(raw["items"][0])
        self.catalog_path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaises(LibraryCatalogError):
            LibraryCatalog(self.catalog_path)
        self.assertTrue(item.item_id)

    def test_preparation_update_is_catalog_only(self):
        catalog = LibraryCatalog(self.catalog_path)
        item = catalog.import_file(self.source)
        prepared_hash = "a" * 64

        updated = catalog.update_preparation(
            item.item_id,
            preparation_state=PREPARATION_PREPARED,
            state=STATE_READY,
            target_folder_name="BOOK",
            target_child_name="chapter.txt",
            prepared_manifest_sha256=prepared_hash,
        )
        reloaded = LibraryCatalog(self.catalog_path).get(item.item_id)

        self.assertEqual(updated, reloaded)
        self.assertEqual(reloaded.state, STATE_READY)
        self.assertEqual(reloaded.prepared_manifest_sha256, prepared_hash)
        self.assertEqual(self.source.read_bytes(), "first\n日本語\n".encode("utf-8"))

        changed = self.source.with_name("changed.txt")
        self.source.rename(changed)
        stale = LibraryCatalog(self.catalog_path).refresh(item.item_id)
        self.assertEqual(stale.preparation_state, PREPARATION_STALE)

    def test_directory_import_is_rejected(self):
        directory = self.root / "folder.txt"
        directory.mkdir()
        with self.assertRaises(LibraryImportError):
            LibraryCatalog(self.catalog_path).import_file(directory)


if __name__ == "__main__":
    unittest.main()
