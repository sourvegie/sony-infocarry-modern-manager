from pathlib import Path
import json
import tempfile
import unittest

from infocarry.prepared_media_package import (
    EXPECTED_BMP_HEIGHT,
    EXPECTED_BMP_WIDTH,
    NATIVE_BMP_PREFIX_LENGTH,
    PREPARED_MEDIA_CONFIRMATION,
    PreparedBitmapSourceItem,
    PreparedMediaPackageError,
    build_prepared_media_package,
    export_prepared_media_package,
)


def make_profile_bmp(width=EXPECTED_BMP_WIDTH, height=EXPECTED_BMP_HEIGHT, *, bits=1):
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
    payload[28:30] = bits.to_bytes(2, "little")
    payload[30:34] = (0).to_bytes(4, "little")
    payload[34:38] = len(pixels).to_bytes(4, "little")
    payload[46:50] = (2).to_bytes(4, "little")
    payload[54:58] = b"\x00\x00\x00\x00"
    payload[58:62] = b"\xff\xff\xff\x00"
    payload[62:] = pixels
    return bytes(payload)


class PreparedMediaPackageTests(unittest.TestCase):
    def _sources(self, root: Path):
        first = root / "first.txt"
        image = root / "page.bmp"
        last = root / "last.txt"
        first.write_bytes("first\n".encode("utf-8"))
        image.write_bytes(make_profile_bmp())
        last.write_bytes("last\n".encode("utf-8"))
        return first, image, last

    def test_valid_txt_bmp_txt_order_is_deterministic_and_usb_neutral(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, image, last = self._sources(root)
            specs = ((first, "chapter-1.txt"), (image, "page-1.bmp"), (last, "chapter-2.txt"))
            package = build_prepared_media_package(specs, "Mixed Book")
            repeat = build_prepared_media_package(specs, "Mixed Book")
            self.assertEqual(package.manifest_dict(), repeat.manifest_dict())
            self.assertEqual([item.kind for item in package.items], ["txt", "bmp", "txt"])
            self.assertEqual(package.prepared_manifest_sha256, repeat.prepared_manifest_sha256)
            self.assertFalse(package.manifest_dict()["usb_accessed"])
            self.assertEqual(package.manifest_dict()["notice"], PREPARED_MEDIA_CONFIRMATION)
            self.assertEqual(package.manifest_dict()["compatibility"]["device_candidate"], "blocked")

    def test_bmp_profile_and_payload_hash_are_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, image, last = self._sources(root)
            package = build_prepared_media_package(
                ((first, "one.txt"), (image, "page.bmp"), (last, "two.txt")), "Book"
            )
            bmp = package.items[1]
            self.assertIsInstance(bmp, PreparedBitmapSourceItem)
            entry = package.manifest_dict()["items"][1]
            self.assertEqual(entry["bmp"]["width"], EXPECTED_BMP_WIDTH)
            self.assertEqual(entry["bmp"]["height"], EXPECTED_BMP_HEIGHT)
            self.assertEqual(entry["bmp"]["bits_per_pixel"], 1)
            self.assertEqual(entry["bmp"]["pixel_offset"], 62)
            self.assertEqual(entry["bmp"]["row_stride"], 32)
            self.assertEqual(entry["bmp"]["payload_sha256"], bmp.payload_sha256)
            self.assertEqual(entry["native_wrapper"]["length_bytes"], NATIVE_BMP_PREFIX_LENGTH)

    def test_size_accounting_is_a_lower_bound_not_a_device_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, image, last = self._sources(root)
            package = build_prepared_media_package(
                ((first, "one.txt"), (image, "page.bmp"), (last, "two.txt")), "Book"
            )
            self.assertEqual(package.minimum_metadata_records, 5)
            self.assertEqual(
                package.estimated_growth_lower_bound,
                5 * 0x40 + package.aligned_content_bytes,
            )
            self.assertFalse(package.manifest_dict()["size"]["exact_device_growth_known"])

    def test_rejects_wrong_dimensions_and_non_one_bit_bmp(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, image, last = self._sources(root)
            for payload in (make_profile_bmp(width=240), make_profile_bmp(bits=24)):
                image.write_bytes(payload)
                with self.assertRaises(PreparedMediaPackageError):
                    build_prepared_media_package(
                        ((first, "one.txt"), (image, "page.bmp"), (last, "two.txt")), "Book"
                    )

    def test_rejects_truncated_or_malformed_bmp(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, image, last = self._sources(root)
            for payload in (make_profile_bmp()[:-1], b"not bmp"):
                image.write_bytes(payload)
                with self.assertRaises(PreparedMediaPackageError):
                    build_prepared_media_package(
                        ((first, "one.txt"), (image, "page.bmp"), (last, "two.txt")), "Book"
                    )

    def test_rejects_missing_type_and_extension_conflicts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, image, last = self._sources(root)
            with self.assertRaisesRegex(PreparedMediaPackageError, "both TXT and BMP"):
                build_prepared_media_package(((first, "one.txt"), (last, "two.txt")), "Book")
            with self.assertRaises(PreparedMediaPackageError):
                build_prepared_media_package(
                    ((first, "one.bmp"), (image, "page.bmp"), (last, "two.txt")), "Book"
                )

    def test_rejects_duplicate_names_and_source_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, image, last = self._sources(root)
            with self.assertRaisesRegex(PreparedMediaPackageError, "unique"):
                build_prepared_media_package(
                    ((first, "one.txt"), (image, "PAGE.BMP"), (last, "one.TXT")), "Book"
                )
            with self.assertRaisesRegex(PreparedMediaPackageError, "source paths"):
                build_prepared_media_package(
                    ((first, "one.txt"), (image, "page.bmp"), (first, "two.txt")), "Book"
                )

    def test_strict_txt_errors_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, image, last = self._sources(root)
            for data in (b"\xff", "😀".encode("utf-8"), b"bad\x00text"):
                first.write_bytes(data)
                with self.assertRaises(PreparedMediaPackageError):
                    build_prepared_media_package(
                        ((first, "one.txt"), (image, "page.bmp"), (last, "two.txt")), "Book"
                    )

    def test_export_is_new_only_and_sources_are_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, image, last = self._sources(root)
            originals = (first.read_bytes(), image.read_bytes(), last.read_bytes())
            package = build_prepared_media_package(
                ((first, "one.txt"), (image, "page.bmp"), (last, "two.txt")), "Book"
            )
            destination = root / "package"
            export_prepared_media_package(package, destination)
            self.assertEqual((destination / "source/0002_page.bmp").read_bytes(), originals[1])
            self.assertEqual((destination / "prepared/Book/page.bmp").read_bytes(), originals[1])
            self.assertEqual(json.loads((destination / "manifest.json").read_text())["prepared_manifest_sha256"], package.prepared_manifest_sha256)
            with self.assertRaises(PreparedMediaPackageError):
                export_prepared_media_package(package, destination)
            self.assertEqual((first.read_bytes(), image.read_bytes(), last.read_bytes()), originals)


if __name__ == "__main__":
    unittest.main()
