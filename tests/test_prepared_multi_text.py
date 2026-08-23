from pathlib import Path
import json
import tempfile
import unittest

from infocarry.prepared_multi_text import (
    PREPARED_MULTI_TEXT_CONFIRMATION,
    PreparedTextPackageSet,
    build_prepared_text_package_set,
    export_prepared_text_package_set,
)
from infocarry.prepared_package import PreparedPackageError


class PreparedMultiTextTests(unittest.TestCase):
    def _sources(self, root: Path):
        first = root / "first.txt"
        second = root / "second.txt"
        first.write_bytes("日本語\nfirst".encode("utf-8"))
        second.write_bytes(b"second\rline")
        return first, second

    def test_ordered_deterministic_package_is_usb_neutral(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self._sources(root)
            specs = ((first, "chapter-1.txt"), (second, "chapter-2.txt"))
            package = build_prepared_text_package_set(specs, "Offline Book")
            repeat = build_prepared_text_package_set(specs, "Offline Book")
            self.assertEqual(package.manifest_dict(), repeat.manifest_dict())
            self.assertEqual(package.prepared_manifest_sha256, repeat.prepared_manifest_sha256)
            self.assertEqual(
                package.target_item_paths,
                ("root\\Offline Book\\chapter-1.txt", "root\\Offline Book\\chapter-2.txt"),
            )
            self.assertEqual(package.items[0].authored.payload, "日本語\r\nfirst".encode("cp932"))
            self.assertEqual(package.items[1].authored.payload, b"second\r\nline")
            manifest = package.manifest_dict()
            self.assertFalse(manifest["usb_accessed"])
            self.assertEqual(manifest["notice"], PREPARED_MULTI_TEXT_CONFIRMATION)
            self.assertEqual([entry["order"] for entry in manifest["items"]], [0, 1])
            self.assertEqual(manifest["compatibility"]["device_candidate"], "blocked")

    def test_size_and_capacity_accounting_is_explicitly_a_lower_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self._sources(root)
            package = build_prepared_text_package_set(
                ((first, "one.txt"), (second, "two.txt")), "Book"
            )
            self.assertEqual(package.minimum_metadata_records, 4)
            self.assertEqual(package.aligned_content_bytes, 48 + 44)
            self.assertEqual(package.estimated_growth_lower_bound, 4 * 0x40 + 92)
            self.assertFalse(package.manifest_dict()["size"]["exact_device_growth_known"])
            self.assertEqual(
                package.manifest_dict()["size"]["capacity_result"],
                "not_evaluated_without_verified_backup",
            )

    def test_source_hashes_payload_hashes_and_manifest_are_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self._sources(root)
            package = build_prepared_text_package_set(
                ((first, "one.txt"), (second, "two.txt")), "Book"
            )
            manifest = package.manifest_dict()
            self.assertEqual(manifest["items"][0]["source"]["sha256"], package.items[0].source_sha256)
            self.assertEqual(
                manifest["items"][1]["authoring"]["prepared_payload_sha256"],
                package.items[1].payload_sha256,
            )
            self.assertEqual(manifest["prepared_manifest_sha256"], package.prepared_manifest_sha256)

    def test_rejects_duplicate_case_insensitive_target_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self._sources(root)
            with self.assertRaisesRegex(PreparedPackageError, "unique"):
                build_prepared_text_package_set(
                    ((first, "Chapter.txt"), (second, "chapter.TXT")), "Book"
                )

    def test_rejects_duplicate_source_paths_and_too_few_children(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self._sources(root)
            with self.assertRaises(PreparedPackageError):
                build_prepared_text_package_set(((first, "one.txt"),), "Book")
            with self.assertRaisesRegex(PreparedPackageError, "source paths"):
                build_prepared_text_package_set(
                    ((first, "one.txt"), (first, "two.txt")), "Book"
                )

    def test_rejects_invalid_encoding_nul_and_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self._sources(root)
            for data in (b"\xff", "😀".encode("utf-8"), b"safe\x00text"):
                first.write_bytes(data)
                with self.assertRaises(PreparedPackageError):
                    build_prepared_text_package_set(
                        ((first, "one.txt"), (second, "two.txt")), "Book"
                    )
            first.write_bytes(b"valid")
            for folder, name in (("..", "one.txt"), ("Book/child", "one.txt"), ("Book", "bad.bin")):
                with self.assertRaises(PreparedPackageError):
                    build_prepared_text_package_set(
                        ((first, name), (second, "two.txt")), folder
                    )

    def test_rejects_malformed_source_spec(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self._sources(root)
            for specs in (((first, "one.txt", "extra"), (second, "two.txt")), ("not-a-pair", (second, "two.txt"))):
                with self.assertRaises(PreparedPackageError):
                    build_prepared_text_package_set(specs, "Book")

    def test_export_is_new_only_and_preserves_all_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self._sources(root)
            package = build_prepared_text_package_set(
                ((first, "one.txt"), (second, "two.txt")), "Book"
            )
            destination = root / "package"
            export_prepared_text_package_set(package, destination)
            self.assertEqual((destination / "source/0001_first.txt").read_bytes(), first.read_bytes())
            self.assertEqual((destination / "source/0002_second.txt").read_bytes(), second.read_bytes())
            self.assertEqual((destination / "prepared/Book/one.txt").read_bytes(), "日本語\r\nfirst".encode("cp932"))
            manifest = json.loads((destination / "manifest.json").read_text("utf-8"))
            self.assertEqual(manifest["prepared_manifest_sha256"], package.prepared_manifest_sha256)
            with self.assertRaises(PreparedPackageError):
                export_prepared_text_package_set(package, destination)
            self.assertEqual(first.read_bytes(), "日本語\nfirst".encode("utf-8"))

    def test_source_change_requires_a_new_preparation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self._sources(root)
            package = build_prepared_text_package_set(
                ((first, "one.txt"), (second, "two.txt")), "Book"
            )
            first.write_bytes(b"changed")
            refreshed = build_prepared_text_package_set(
                ((first, "one.txt"), (second, "two.txt")), "Book"
            )
            self.assertNotEqual(package.prepared_manifest_sha256, refreshed.prepared_manifest_sha256)
            self.assertNotEqual(package.items[0].source_sha256, refreshed.items[0].source_sha256)


if __name__ == "__main__":
    unittest.main()
