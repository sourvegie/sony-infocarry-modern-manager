import hashlib
import tempfile
import unittest
from pathlib import Path

from infocarry.library import (
    PREPARATION_BLOCKED,
    PREPARATION_PREPARED,
    STATE_BLOCKED,
    STATE_READY,
    LibraryCatalog,
)
from infocarry.library_prepare import LibraryPreparationError, prepare_library_item


class LibraryPrepareTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.catalog = LibraryCatalog(self.root / "app" / "library.json")
        self.source = self.root / "source.txt"
        self.source.write_text("first\n日本語\n", encoding="utf-8")
        self.item = self.catalog.import_file(
            self.source,
            now="2026-08-23T10:00:00+00:00",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_prepare_reuses_canonical_package_and_records_no_device_audit(self):
        result = prepare_library_item(
            self.catalog,
            self.item.item_id,
            "Offline Book",
            "chapter.txt",
            now="2026-08-23T10:01:00+00:00",
        )

        self.assertEqual(result.item.state, STATE_READY)
        self.assertEqual(result.item.preparation_state, PREPARATION_PREPARED)
        self.assertEqual(result.item.target_folder_name, "Offline Book")
        self.assertEqual(result.item.target_child_name, "chapter.txt")
        self.assertEqual(
            result.item.prepared_manifest_sha256,
            result.package.prepared_manifest_sha256,
        )
        self.assertEqual(result.package.item.authored.payload, b"first\r\n\x93\xfa\x96{\x8c\xea\r\n")
        self.assertEqual(result.audit["device_operation"], "none")
        self.assertFalse(result.audit["usb_accessed"])
        self.assertIn("NO DEVICE CHANGE", result.audit["notice"])
        self.assertEqual(
            result.audit["source"]["sha256"],
            hashlib.sha256(self.source.read_bytes()).hexdigest(),
        )
        self.assertEqual(result.audit["prepared"]["folder_path"], "root\\Offline Book")
        self.assertEqual(result.audit["prepared"]["child_path"], "root\\Offline Book\\chapter.txt")
        self.assertEqual(self.source.read_text(encoding="utf-8"), "first\n日本語\n")

    def test_prepare_is_deterministic_for_unchanged_item(self):
        first = prepare_library_item(
            self.catalog,
            self.item.item_id,
            "Offline Book",
            "chapter.txt",
            now="2026-08-23T10:01:00+00:00",
        )
        second = prepare_library_item(
            self.catalog,
            self.item.item_id,
            "Offline Book",
            "chapter.txt",
            now="2026-08-23T10:02:00+00:00",
        )

        self.assertEqual(first.package.prepared_manifest_sha256, second.package.prepared_manifest_sha256)
        self.assertEqual(first.package.item.authored.payload, second.package.item.authored.payload)
        self.assertEqual(second.item.state, STATE_READY)

    def test_invalid_cp932_content_blocks_item_without_usb(self):
        source = self.root / "emoji.txt"
        source.write_text("emoji 😀\n", encoding="utf-8")
        item = self.catalog.import_file(source)

        with self.assertRaisesRegex(LibraryPreparationError, "CP932"):
            prepare_library_item(self.catalog, item.item_id, "Book", "chapter.txt")

        updated = LibraryCatalog(self.catalog.path).get(item.item_id)
        self.assertEqual(updated.state, STATE_BLOCKED)
        self.assertEqual(updated.preparation_state, PREPARATION_BLOCKED)
        self.assertIn("CP932", updated.last_validation_error)

    def test_stale_source_is_rejected_and_original_hash_is_preserved(self):
        original_hash = self.item.source_sha256
        self.source.write_text("changed\n", encoding="utf-8")

        with self.assertRaises(LibraryPreparationError):
            prepare_library_item(self.catalog, self.item.item_id, "Book", "chapter.txt")

        updated = LibraryCatalog(self.catalog.path).get(self.item.item_id)
        self.assertEqual(updated.source_sha256, original_hash)
        self.assertNotEqual(updated.observed_source_sha256, original_hash)
        self.assertEqual(updated.state, STATE_BLOCKED)
        self.assertIn("changed", updated.last_validation_error)

    def test_invalid_target_is_rejected_and_catalog_records_error(self):
        with self.assertRaisesRegex(LibraryPreparationError, "CP932"):
            prepare_library_item(self.catalog, self.item.item_id, "Book", "😀.txt")

        updated = LibraryCatalog(self.catalog.path).get(self.item.item_id)
        self.assertEqual(updated.state, STATE_BLOCKED)
        self.assertEqual(updated.preparation_state, PREPARATION_BLOCKED)


if __name__ == "__main__":
    unittest.main()
