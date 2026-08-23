from pathlib import Path
import hashlib
import tempfile
import unittest

from infocarry.prepared_package import (
    PREPARED_PACKAGE_CONFIRMATION,
    PreparedPackageError,
    PreparedTextItem,
    PreparedTextPackage,
    build_prepared_text_package,
    export_prepared_text_package,
)
from infocarry.text_authoring import encode_cp932_text


class PreparedPackageTests(unittest.TestCase):
    def _source(self, root: Path, data: bytes = "日本語\nline".encode("utf-8")) -> Path:
        path = root / "source.txt"
        path.write_bytes(data)
        return path

    def test_strict_preparation_is_deterministic_and_usb_neutral(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._source(root)
            first = build_prepared_text_package(source, "Offline Book", "chapter.txt")
            second = build_prepared_text_package(source, "Offline Book", "chapter.txt")
            self.assertEqual(first.manifest_dict(), second.manifest_dict())
            self.assertEqual(first.prepared_manifest_sha256, second.prepared_manifest_sha256)
            self.assertEqual(first.target_item_path, "root\\Offline Book\\chapter.txt")
            self.assertEqual(first.item.authored.payload, "日本語\r\nline".encode("cp932"))
            self.assertFalse(first.manifest_dict()["usb_accessed"])
            self.assertEqual(first.manifest_dict()["notice"], PREPARED_PACKAGE_CONFIRMATION)
            self.assertFalse(first.manifest_dict()["safety"]["candidate_bytes_included"])
            self.assertEqual(source.read_bytes(), "日本語\nline".encode("utf-8"))

    def test_newline_normalization_and_size_accounting(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = build_prepared_text_package(
                self._source(Path(temporary), b"a\nb\rc\r\nd"),
                "Book",
                "chapter.txt",
            )
            self.assertEqual(package.item.authored.payload, b"a\r\nb\r\nc\r\nd")
            self.assertEqual(package.prepared_payload_bytes, 10)
            self.assertEqual(package.aligned_content_bytes, 44)
            self.assertEqual(package.estimated_growth_lower_bound, 236)
            self.assertFalse(package.manifest_dict()["size"]["exact_device_growth_known"])

    def test_rejects_invalid_utf8_cp932_nul_and_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = (
                (b"\xff", "invalid UTF-8"),
                ("😀".encode("utf-8"), "unsupported CP932"),
                (b"safe\x00text", "embedded NUL"),
            )
            for data, label in cases:
                with self.subTest(label=label):
                    with self.assertRaises(PreparedPackageError):
                        build_prepared_text_package(self._source(root, data), "Book", "chapter.txt")
            source = self._source(root)
            for folder, item in (("..", "chapter.txt"), ("Book/child", "chapter.txt"), ("Book", "bad.bin")):
                with self.subTest(folder=folder, item=item):
                    with self.assertRaises(PreparedPackageError):
                        build_prepared_text_package(source, folder, item)

    def test_duplicate_item_names_are_rejected(self):
        authored = encode_cp932_text("same")
        with self.assertRaises(PreparedPackageError):
            PreparedTextPackage(
                source_path=Path("/tmp/source.txt"),
                source_bytes=b"same",
                source_text="same",
                source_sha256=hashlib.sha256(b"same").hexdigest(),
                folder_name="Book",
                items=(PreparedTextItem("chapter.txt", authored), PreparedTextItem("chapter.txt", authored)),
            )

    def test_export_is_new_only_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._source(root, b"source\n")
            package = build_prepared_text_package(source, "Book", "chapter.txt")
            destination = root / "package"
            export_prepared_text_package(package, destination)
            self.assertEqual((destination / "source/source.txt").read_bytes(), b"source\n")
            self.assertEqual(
                (destination / "prepared/Book/chapter.txt").read_bytes(), b"source\r\n"
            )
            with self.assertRaises(PreparedPackageError):
                export_prepared_text_package(package, destination)
            self.assertEqual((destination / "source/source.txt").read_bytes(), b"source\n")


if __name__ == "__main__":
    unittest.main()
