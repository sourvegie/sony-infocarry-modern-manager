import json
from pathlib import Path
import tempfile
import unittest

from infocarry.offline_conversion import (
    OfflineConversionError,
    PageLayout,
    export_text_document,
    load_utf8_text_document,
    monochrome_bmp_bytes,
    paginate_text,
)


class OfflineConversionTests(unittest.TestCase):
    def test_strict_utf8_cp932_document_and_pages_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "book.txt"
            source.write_bytes("第一行\n第二行\n".encode("utf-8"))
            document = load_utf8_text_document(
                source, layout=PageLayout(columns=4, lines_per_page=1)
            )
            self.assertEqual(document.authored.payload.decode("cp932"), "第一行\r\n第二行\r\n")
            self.assertEqual([page.text for page in document.pages], ["第一行", "第二行", ""])
            self.assertFalse(document.report()["device_accessed"])
            self.assertFalse(document.report()["candidate_bytes_included"])

    def test_unsupported_character_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "unsupported.txt"
            source.write_text("unsafe 🙂", encoding="utf-8")
            with self.assertRaisesRegex(OfflineConversionError, "unsupported by CP932"):
                load_utf8_text_document(source)

    def test_pagination_preserves_blank_lines_and_wraps_codepoints(self):
        pages = paginate_text("abcdEF\n\nxy", PageLayout(columns=4, lines_per_page=2))
        self.assertEqual([page.lines for page in pages], [("abcd", "EF"), ("", "xy")])

    def test_export_creates_non_device_package_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "notes.txt"
            source.write_text("hello\nworld", encoding="utf-8")
            document = load_utf8_text_document(source)
            destination = root / "export"
            export_text_document(document, destination)
            self.assertEqual((destination / "text_cp932.txt").read_bytes(), b"hello\r\nworld")
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["page_count"], document.page_count)
            self.assertFalse(manifest["device_accessed"])
            with self.assertRaisesRegex(OfflineConversionError, "refusing to overwrite"):
                export_text_document(document, destination)

    def test_monochrome_bmp_profile_is_exact_and_deterministic(self):
        width, height = 240, 320
        pixels = [[False] * width for _ in range(height)]
        pixels[0][0] = True
        pixels[-1][-1] = True
        data = monochrome_bmp_bytes(pixels)
        self.assertEqual(data[:2], b"BM")
        self.assertEqual(int.from_bytes(data[18:22], "little", signed=True), width)
        self.assertEqual(int.from_bytes(data[22:26], "little", signed=True), height)
        self.assertEqual(int.from_bytes(data[28:30], "little"), 1)
        self.assertEqual(len(data), 14 + 40 + 8 + 32 * 320)
        pixel_offset = int.from_bytes(data[10:14], "little")
        row_stride = 32
        self.assertEqual(data[pixel_offset + (height - 1) * row_stride] & 0x80, 0)
        self.assertEqual(data[pixel_offset + 239 // 8] & 0x01, 0)
        self.assertEqual(data, monochrome_bmp_bytes(pixels))

    def test_monochrome_bmp_rejects_wrong_matrix(self):
        with self.assertRaisesRegex(OfflineConversionError, "pixel matrix"):
            monochrome_bmp_bytes([[False]])


if __name__ == "__main__":
    unittest.main()
