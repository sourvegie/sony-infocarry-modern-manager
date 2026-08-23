import unittest

from infocarry.bitmap import BitmapFormatError, decode_monochrome_bmp


def make_monochrome_bmp(width=9, height=2, *, top_down=False):
    row_stride = ((width + 31) // 32) * 4
    pixels = bytearray(row_stride * height)
    # The first displayed row has white pixels at x=0 and x=width-1. BMP
    # palette index 1 is white; positive heights store rows bottom-up.
    top_row = bytearray(row_stride)
    top_row[0] = 0x80
    top_row[(width - 1) // 8] |= 1 << (7 - ((width - 1) % 8))
    rows = [top_row, bytearray(row_stride)]
    if not top_down:
        rows.reverse()
    for index, row in enumerate(rows):
        pixels[index * row_stride : (index + 1) * row_stride] = row

    payload = bytearray(62 + len(pixels))
    payload[:2] = b"BM"
    payload[2:6] = len(payload).to_bytes(4, "little")
    payload[10:14] = (62).to_bytes(4, "little")
    payload[14:18] = (40).to_bytes(4, "little")
    payload[18:22] = width.to_bytes(4, "little", signed=True)
    payload[22:26] = (-height if top_down else height).to_bytes(4, "little", signed=True)
    payload[26:28] = (1).to_bytes(2, "little")
    payload[28:30] = (1).to_bytes(2, "little")
    payload[30:34] = (0).to_bytes(4, "little")
    payload[34:38] = len(pixels).to_bytes(4, "little")
    payload[46:50] = (2).to_bytes(4, "little")
    payload[54:58] = b"\x00\x00\x00\x00"
    payload[58:62] = b"\xff\xff\xff\x00"
    payload[62:] = pixels
    return bytes(payload)


class BitmapPreviewTests(unittest.TestCase):
    def test_decodes_bottom_up_monochrome_bmp_to_ppm(self):
        preview = decode_monochrome_bmp(make_monochrome_bmp())
        self.assertEqual((preview.width, preview.height), (9, 2))
        self.assertTrue(preview.ppm.startswith(b"P3\n9 2\n255\n"))
        self.assertIn(b"255 255 255 0 0 0", preview.ppm)
        self.assertIn(b"0 0 0 255 255 255", preview.ppm)
        self.assertEqual(preview.photo_rows[0].split(), [
            "{#ffffff", "#000000", "#000000", "#000000", "#000000",
            "#000000", "#000000", "#000000", "#ffffff}",
        ])

    def test_decodes_top_down_monochrome_bmp(self):
        preview = decode_monochrome_bmp(make_monochrome_bmp(top_down=True))
        self.assertTrue(preview.ppm.startswith(b"P3\n9 2\n255\n"))
        self.assertIn(b"255 255 255 0 0 0", preview.ppm)
        self.assertTrue(preview.photo_rows[0].startswith("{#ffffff "))

    def test_rejects_non_monochrome_or_truncated_bmp(self):
        invalid = bytearray(make_monochrome_bmp())
        invalid[28:30] = (24).to_bytes(2, "little")
        with self.assertRaises(BitmapFormatError):
            decode_monochrome_bmp(bytes(invalid))
        with self.assertRaises(BitmapFormatError):
            decode_monochrome_bmp(make_monochrome_bmp()[:-1])


if __name__ == "__main__":
    unittest.main()
