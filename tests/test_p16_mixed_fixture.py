from pathlib import Path
import hashlib
import json
import unittest

from infocarry.bitmap import decode_monochrome_bmp
from infocarry.prepared_media_package import build_prepared_media_package


FIXTURE = Path(__file__).parents[1] / "samples/generated/P16-001-native-mixed-txt-bmp"
SOURCE = FIXTURE / "source/IC_P16_MIXED_20260830_01"


class P16MixedFixtureTests(unittest.TestCase):
    def test_manifest_and_sha256sums_bind_exact_ordered_sources(self):
        manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["root_folder"], "IC_P16_MIXED_20260830_01")
        self.assertEqual(
            sorted(path.name for path in SOURCE.iterdir()),
            ["01-introduction.txt", "02-page-01.bmp", "03-ending.txt"],
        )
        self.assertEqual(
            [item["kind"] for item in manifest["ordered_children"]],
            ["txt", "bmp", "txt"],
        )
        self.assertEqual([item["order"] for item in manifest["ordered_children"]], [1, 2, 3])
        expected = {
            line.split("  ", 1)[1]: line.split("  ", 1)[0]
            for line in (FIXTURE / "SHA256SUMS.txt").read_text().splitlines()
            if line.strip()
        }
        for relative, digest in expected.items():
            self.assertEqual(hashlib.sha256((FIXTURE / relative).read_bytes()).hexdigest(), digest)
        self.assertEqual(manifest["source_count"], 3)
        self.assertEqual(manifest["total_source_bytes"], 10585)

    def test_fixture_is_strict_and_reproducible_through_typed_offline_model(self):
        specs = (
            (SOURCE / "01-introduction.txt", "01-introduction.txt"),
            (SOURCE / "02-page-01.bmp", "02-page-01.bmp"),
            (SOURCE / "03-ending.txt", "03-ending.txt"),
        )
        package = build_prepared_media_package(specs, "IC_P16_MIXED_20260830_01")
        repeat = build_prepared_media_package(specs, "IC_P16_MIXED_20260830_01")
        self.assertEqual(package.manifest_dict(), repeat.manifest_dict())
        self.assertEqual([item.kind for item in package.items], ["txt", "bmp", "txt"])
        self.assertEqual(package.prepared_payload_bytes, 10585)
        self.assertEqual(package.aligned_content_bytes, 10684)
        self.assertEqual(package.estimated_growth_lower_bound, 11004)
        self.assertFalse(package.manifest_dict()["usb_accessed"])

    def test_txt_markers_and_crlf_are_exact(self):
        introduction = (SOURCE / "01-introduction.txt").read_bytes()
        ending = (SOURCE / "03-ending.txt").read_bytes()
        for data, marker in (
            (introduction, b"P16-001-INTRO-END"),
            (ending, b"P16-001-ENDING-END"),
        ):
            self.assertIn(marker, data)
            self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
            self.assertNotIn(b"\x00", data)
            data.decode("utf-8", errors="strict").encode("cp932", errors="strict")

    def test_bmp_profile_and_visual_sentinels_are_exact(self):
        payload = (SOURCE / "02-page-01.bmp").read_bytes()
        preview = decode_monochrome_bmp(payload)
        self.assertEqual((preview.width, preview.height), (237, 320))
        self.assertEqual(payload[:2], b"BM")
        self.assertEqual(int.from_bytes(payload[14:18], "little"), 40)
        self.assertEqual(int.from_bytes(payload[26:28], "little"), 1)
        self.assertEqual(int.from_bytes(payload[28:30], "little"), 1)
        self.assertEqual(int.from_bytes(payload[30:34], "little"), 0)
        self.assertEqual(int.from_bytes(payload[10:14], "little"), 62)
        self.assertEqual(int.from_bytes(payload[2:6], "little"), len(payload))
        self.assertEqual(int.from_bytes(payload[46:50], "little"), 0)
        self.assertEqual(payload[54:62], b"\x00\x00\x00\x00\xff\xff\xff\x00")
        self.assertEqual(payload[62 : 62 + 32], b"\x00" * 32)
        row_y1 = payload[62 + 318 * 32 : 62 + 319 * 32]
        self.assertEqual((row_y1[0], row_y1[14], row_y1[29]), (0x3F, 0xFD, 0xE0))
        row_y100 = payload[62 + 219 * 32 : 62 + 220 * 32]
        self.assertEqual((row_y100[0], row_y100[12], row_y100[14], row_y100[17]), (0x7F, 0xF7, 0xFD, 0x7F))


if __name__ == "__main__":
    unittest.main()
