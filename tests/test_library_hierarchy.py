from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from infocarry.capability_profile import (
    HIERARCHICAL_OFFLINE_PROFILE_ID,
    HIERARCHICAL_OFFLINE_PROFILE_STATUS,
    hierarchical_offline_capability_profile,
    initial_capability_profile,
)
from infocarry.library import (
    LIBRARY_FORMAT,
    LibraryCatalog,
    LibraryCatalogError,
    LibraryImportError,
    NODE_FOLDER,
)
from infocarry.library_prepare import LibraryPreparationError, prepare_library_hierarchy
from infocarry.library_workflow import LibraryWorkflowService
from infocarry.transfer_foundation import (
    CandidateLibrary,
    PreparedItem,
    TransferFoundationError,
)
def make_profile_bmp() -> bytes:
    width, height = 237, 320
    row_stride = ((width + 31) // 32) * 4
    pixels = bytes(row_stride * height)
    payload = bytearray(62 + len(pixels))
    payload[:2] = b"BM"
    payload[2:6] = len(payload).to_bytes(4, "little")
    payload[10:14] = (62).to_bytes(4, "little")
    payload[14:18] = (40).to_bytes(4, "little")
    payload[18:22] = width.to_bytes(4, "little", signed=True)
    payload[22:26] = height.to_bytes(4, "little", signed=True)
    payload[26:28] = (1).to_bytes(2, "little")
    payload[28:30] = (1).to_bytes(2, "little")
    payload[34:38] = len(pixels).to_bytes(4, "little")
    payload[46:50] = (2).to_bytes(4, "little")
    payload[58:62] = b"\xff\xff\xff\x00"
    payload[62:] = pixels
    return bytes(payload)


class HierarchicalLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.catalog_path = self.root / "app" / "library.json"

    def tearDown(self):
        self.temporary.cleanup()

    def _book(self) -> Path:
        book = self.root / "Book"
        section = book / "Section"
        section.mkdir(parents=True)
        (book / "z-last.txt").write_text("last\n", encoding="utf-8")
        (book / "a-first.txt").write_text("first\n", encoding="utf-8")
        (section / "page.bmp").write_bytes(make_profile_bmp())
        return book

    def test_recursive_import_persists_hierarchy_and_explicit_order(self):
        catalog = LibraryCatalog(self.catalog_path)
        root = catalog.import_folder(self._book(), now="2026-09-02T00:00:00+00:00")

        self.assertEqual(root.node_kind, NODE_FOLDER)
        self.assertEqual(
            [item.source_filename for item in catalog.children(root.item_id)],
            ["Section", "a-first.txt", "z-last.txt"],
        )
        first = catalog.children(root.item_id)[0]
        catalog.move_down(first.item_id)
        self.assertEqual(
            [item.source_filename for item in catalog.children(root.item_id)],
            ["a-first.txt", "Section", "z-last.txt"],
        )
        reloaded = LibraryCatalog(self.catalog_path)
        self.assertEqual(
            [item.source_filename for item in reloaded.children(root.item_id)],
            ["a-first.txt", "Section", "z-last.txt"],
        )
        self.assertEqual(reloaded.to_dict()["version"], 2)

    def test_multi_file_picker_order_is_not_alphabetized(self):
        second = self.root / "second.txt"
        first = self.root / "first.txt"
        second.write_text("2", encoding="utf-8")
        first.write_text("1", encoding="utf-8")
        catalog = LibraryCatalog(self.catalog_path)

        catalog.import_files((second, first), now="2026-09-02T00:00:00+00:00")

        self.assertEqual([item.source_filename for item in catalog.roots], ["second.txt", "first.txt"])

    def test_subtree_remove_is_catalog_only(self):
        book = self._book()
        catalog = LibraryCatalog(self.catalog_path)
        root = catalog.import_folder(book)
        descendant_count = len(catalog.items)

        self.assertTrue(catalog.remove(root.item_id))

        self.assertGreater(descendant_count, 1)
        self.assertEqual(catalog.items, ())
        self.assertTrue((book / "Section" / "page.bmp").is_file())
        self.assertTrue((book / "a-first.txt").is_file())

    def test_v1_catalog_migrates_in_serialized_order_on_first_mutation(self):
        one = self.root / "one.txt"
        two = self.root / "two.txt"
        one.write_text("one", encoding="utf-8")
        two.write_text("two", encoding="utf-8")
        seed = LibraryCatalog(self.catalog_path)
        item_one = seed.import_file(one)
        item_two = seed.import_file(two)
        raw = seed.to_dict()
        raw["version"] = 1
        raw["items"] = [item_two.to_dict(), item_one.to_dict()]
        for item in raw["items"]:
            item.pop("node_kind", None)
            item.pop("parent_id", None)
            item.pop("sibling_order", None)
        self.catalog_path.write_text(json.dumps(raw), encoding="utf-8")

        migrated = LibraryCatalog(self.catalog_path)
        self.assertEqual([item.source_filename for item in migrated.roots], ["two.txt", "one.txt"])
        migrated.move_down(item_two.item_id)
        self.assertEqual(LibraryCatalog(self.catalog_path).to_dict()["version"], 2)

    def test_recursive_import_rejects_symlink_and_duplicate_sibling_without_partial_save(self):
        book = self.root / "Unsafe"
        book.mkdir()
        target = self.root / "target.txt"
        target.write_text("target", encoding="utf-8")
        try:
            (book / "link.txt").symlink_to(target)
        except OSError:
            self.skipTest("symlink creation is unavailable")
        catalog = LibraryCatalog(self.catalog_path)
        with self.assertRaisesRegex(LibraryImportError, "symbolic-link"):
            catalog.import_folder(book)
        self.assertEqual(catalog.items, ())
        with self.assertRaisesRegex(LibraryImportError, "symbolic-link"):
            catalog.import_file(book / "link.txt")
        root_link = self.root / "Unsafe-link"
        try:
            root_link.symlink_to(book, target_is_directory=True)
        except OSError:
            self.skipTest("directory symlink creation is unavailable")
        with self.assertRaisesRegex(LibraryImportError, "symbolic-link"):
            catalog.import_folder(root_link)

        (book / "link.txt").unlink()
        (book / "one.txt").write_text("A", encoding="utf-8")
        (book / "two.txt").write_text("a", encoding="utf-8")
        catalog.import_folder(book)
        tampered = catalog.to_dict()
        tampered["items"][1]["source_filename"] = "DUP.txt"
        tampered["items"][2]["source_filename"] = "dup.txt"
        tampered_path = self.root / "tampered-library.json"
        tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
        with self.assertRaisesRegex(LibraryCatalogError, "duplicate sibling"):
            LibraryCatalog(tampered_path)

    def test_prepare_manifest_and_facade_preview_are_deterministic_and_offline(self):
        catalog = LibraryCatalog(self.catalog_path)
        root = catalog.import_folder(self._book())
        service = LibraryWorkflowService(catalog)

        first = service.prepare_preview(root.item_id)
        second = service.prepare_preview(root.item_id)
        report = first.to_dict()

        self.assertEqual(first.prepared.to_dict(), second.prepared.to_dict())
        self.assertEqual(first.foundation.plan.plan_sha256, second.foundation.plan.plan_sha256)
        self.assertEqual(report["prepared_manifest"]["profile_id"], HIERARCHICAL_OFFLINE_PROFILE_ID)
        self.assertEqual(report["device_tree_preview"]["profile_status"], HIERARCHICAL_OFFLINE_PROFILE_STATUS)
        self.assertEqual(
            [node["path"] for node in report["device_tree_preview"]["ordered_nodes"]],
            [
                "root\\Book",
                "root\\Book\\Section",
                "root\\Book\\Section\\page.bmp",
                "root\\Book\\a-first.txt",
                "root\\Book\\z-last.txt",
            ],
        )
        self.assertEqual(
            set(report["device_tree_preview"]["capacity"].values()), {"not_evaluated"}
        )
        self.assertFalse(report["foundation"]["execute_once"]["enabled"])
        self.assertFalse(report["foundation"]["usb_accessed"])
        self.assertEqual(report["drag_and_drop"]["status"], "unavailable_without_optional_tkdnd_adapter")

    def test_conflicts_are_precise_or_not_evaluated_without_baseline(self):
        catalog = LibraryCatalog(self.catalog_path)
        root = catalog.import_folder(self._book())
        service = LibraryWorkflowService(catalog)

        unknown = service.prepare_preview(root.item_id).device_tree
        conflict = service.prepare_preview(
            root.item_id, existing_paths=("root\\BOOK\\A-FIRST.TXT",)
        ).device_tree

        self.assertEqual(
            unknown["validation"]["existing_device_paths"],
            "not_evaluated_without_fresh_verified_baseline",
        )
        self.assertEqual(conflict["validation"]["existing_device_paths"], "conflict")
        self.assertEqual(
            conflict["validation"]["conflicts"],
            ("root\\Book", "root\\Book\\a-first.txt"),
        )

    def test_prepare_fails_closed_for_unsupported_cp932_depth_count_and_drift(self):
        unsupported = self.root / "Unsupported"
        unsupported.mkdir()
        (unsupported / "chapter.epub").write_bytes(b"epub")
        catalog = LibraryCatalog(self.catalog_path)
        root = catalog.import_folder(unsupported)
        with self.assertRaisesRegex(LibraryPreparationError, "unsupported"):
            prepare_library_hierarchy(catalog, root.item_id)

        catalog.remove(root.item_id)
        bad_cp932 = self.root / "Emoji"
        bad_cp932.mkdir()
        (bad_cp932 / "😀.txt").write_text("text", encoding="utf-8")
        root = catalog.import_folder(bad_cp932)
        with self.assertRaisesRegex(LibraryPreparationError, "CP932"):
            prepare_library_hierarchy(catalog, root.item_id)

        catalog.remove(root.item_id)
        deep = self.root / "Deep"
        (deep / "one" / "two").mkdir(parents=True)
        (deep / "one" / "two" / "leaf.txt").write_text("leaf", encoding="utf-8")
        root = catalog.import_folder(deep)
        with self.assertRaisesRegex(LibraryPreparationError, "directory depth"):
            prepare_library_hierarchy(catalog, root.item_id)

        catalog.remove(root.item_id)
        many = self.root / "Many"
        many.mkdir()
        for index in range(9):
            (many / f"{index}.txt").write_text(str(index), encoding="utf-8")
        root = catalog.import_folder(many)
        with self.assertRaisesRegex(LibraryPreparationError, "logical node count|leaf count"):
            prepare_library_hierarchy(catalog, root.item_id)

        catalog.remove(root.item_id)
        large = self.root / "Large"
        large.mkdir()
        (large / "large.txt").write_bytes(b"x" * 1_048_577)
        root = catalog.import_folder(large)
        with self.assertRaisesRegex(LibraryPreparationError, "source exceeds policy"):
            prepare_library_hierarchy(catalog, root.item_id)

        catalog.remove(root.item_id)
        book = self._book()
        root = catalog.import_folder(book)
        (book / "new.txt").write_text("new", encoding="utf-8")
        with self.assertRaisesRegex(LibraryPreparationError, "contents changed"):
            prepare_library_hierarchy(catalog, root.item_id)

    def test_tampered_manifest_and_candidate_attachment_are_blocked(self):
        catalog = LibraryCatalog(self.catalog_path)
        root = catalog.import_folder(self._book())
        result = LibraryWorkflowService(catalog).prepare_preview(root.item_id)
        tampered = result.prepared.to_dict()
        tampered["nodes"][1]["order"] = 9
        with self.assertRaisesRegex(TransferFoundationError, "hash differs"):
            PreparedItem.from_hierarchy_manifest(tampered)

        candidate = CandidateLibrary(
            "a" * 64,
            "b" * 64,
            "c" * 64,
            result.foundation.plan.destination_paths,
        )
        with self.assertRaisesRegex(TransferFoundationError, "cannot attach"):
            result.foundation.attach_candidate(candidate)
        with self.assertRaisesRegex(TransferFoundationError, "cannot attach live capacity"):
            result.foundation.attach_capacity(object())

    def test_rehashed_manifest_cannot_reorder_depth_first_stream_or_metadata(self):
        catalog = LibraryCatalog(self.catalog_path)
        root = catalog.import_folder(self._book())
        result = LibraryWorkflowService(catalog).prepare_preview(root.item_id)
        tampered = result.prepared.to_dict()
        tampered["nodes"][2], tampered["nodes"][3] = tampered["nodes"][3], tampered["nodes"][2]
        unsigned = dict(tampered)
        unsigned.pop("prepared_manifest_sha256")
        tampered["prepared_manifest_sha256"] = sha256(
            json.dumps(unsigned, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(TransferFoundationError, "pre-order"):
            PreparedItem.from_hierarchy_manifest(tampered)

        tampered = result.prepared.to_dict()
        tampered["safety"]["usb_accessed"] = True
        unsigned = dict(tampered)
        unsigned.pop("prepared_manifest_sha256")
        tampered["prepared_manifest_sha256"] = sha256(
            json.dumps(unsigned, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(TransferFoundationError, "safety"):
            PreparedItem.from_hierarchy_manifest(tampered)

    def test_flat_profile_digest_is_unchanged_and_nested_profile_is_distinct(self):
        flat = initial_capability_profile()
        nested = hierarchical_offline_capability_profile()
        self.assertEqual(
            flat.sha256,
            "bd556ba933213e36b9bfc121c8f349a9022cebcdbbccdd1623b6b1ec814cb15b",
        )
        self.assertNotEqual(flat.profile_id, nested.profile_id)
        self.assertFalse(nested.live_enabled)


if __name__ == "__main__":
    unittest.main()
