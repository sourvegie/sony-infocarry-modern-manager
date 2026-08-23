import json
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import calculate_backup_checksum
from infocarry.fixture_report import (
    FixtureReportError,
    analyze_fixture,
    write_fixture_report,
)
from infocarry.viclv import VicLvEntry, build_viclv
from infocarry.vicmem import (
    VICMEM_CATEGORY_RECORD_SIZE,
    VicMemSection,
    build_vicmem,
)


def make_record(flag, extension, field04, field08, name, field14=0):
    raw = bytearray(64)
    raw[0] = flag
    raw[1:4] = extension.encode("ascii").ljust(3, b"\x00")
    raw[4:8] = field04.to_bytes(4, "big")
    raw[8:12] = field08.to_bytes(4, "big")
    raw[12:16] = (1_787_207_892).to_bytes(4, "big")
    raw[16:20] = (0xFFFFFFFF).to_bytes(4, "big")
    raw[20:24] = field14.to_bytes(4, "big")
    encoded = name.encode("cp932")
    raw[24 : 24 + len(encoded)] = encoded
    return bytes(raw)


def make_fixture_blob(payload=b"hello\r\n"):
    root = make_record(0xD0, "", 0x40, 0x80, "root")
    parent = make_record(0xD0, "", 0x40, 0x80, "..")
    file_record = make_record(0xE0, "txt", 0, len(payload), "memo", 0x200)
    metadata = root + parent + file_record
    content_start = 0x40 + len(metadata)
    content = b"\xff" * 0x20 + payload
    content += b"\x00" * (-(content_start + len(content)) % 4)
    total_length = content_start + len(content) + 4
    header = bytearray(64)
    header[:14] = b"infoCarry 2.00"
    header[14:16] = b"\x01\x00"
    header[16:18] = (64).to_bytes(2, "big")
    header[0x14:0x18] = (0x20).to_bytes(4, "big")
    header[0x18:0x1C] = (total_length - 1).to_bytes(4, "big")
    header[0x28:0x2C] = (0x40).to_bytes(4, "big")
    header[0x2C:0x30] = len(metadata).to_bytes(4, "big")
    header[0x30:0x34] = content_start.to_bytes(4, "big")
    header[0x34:0x38] = len(content).to_bytes(4, "big")
    header[0x38:0x3C] = total_length.to_bytes(4, "big")
    header[0x3C:0x40] = b"\xff" * 4
    blob = bytearray(bytes(header) + metadata + content + b"\xff" * 4)
    blob[0x1C:0x20] = calculate_backup_checksum(blob).to_bytes(4, "big")
    return bytes(blob)


def make_category_record(path):
    encoded = path.encode("cp932")
    return encoded + b"\x00" + b"\x00" * (VICMEM_CATEGORY_RECORD_SIZE - len(encoded) - 1)


class FixtureReportTests(unittest.TestCase):
    def _write_fixture(self, root):
        (root / "Backup").mkdir()
        (root / "Memo").mkdir()
        (root / "ICM" / "保存").mkdir(parents=True)
        encoded = bytes(value ^ 0xAA for value in make_fixture_blob())
        (root / "Backup" / "VICDATA.bin").write_bytes(encoded)
        vicmem = build_vicmem(
            (
                VicMemSection(
                    auxiliary=b"\x00" * 4,
                    records=(make_category_record("memo.txt"),),
                ),
                None,
                None,
                None,
            ),
            None,
        )
        (root / "Memo" / "VICMEM.bin").write_bytes(vicmem)
        (root / "Memo" / "VICLV.bin").write_bytes(
            build_viclv((VicLvEntry.from_cp932_path(2, ""),))
        )
        (root / "ICM" / "保存" / "order.vnw").write_bytes(b";v1.0\nmemo.txt\n")

    def test_analyze_verifies_encoding_and_correlates_sidecars(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixture"
            root.mkdir()
            self._write_fixture(root)
            report = analyze_fixture(root)
            self.assertEqual(report["format"], "infocarry-fixture-report-v1")
            self.assertTrue(report["vicdata"]["magic_verified"])
            self.assertTrue(report["vicdata"]["checksum_verified"])
            self.assertEqual(report["vicdata"]["xor_key"], "0xaa")
            self.assertTrue(report["sidecars"]["VICMEM.bin"]["round_trip_exact"])
            self.assertTrue(report["sidecars"]["VICLV.bin"]["round_trip_exact"])
            self.assertTrue(report["sidecars"]["order.vnw"]["round_trip_exact"])
            self.assertEqual(report["vicdata"]["summary"]["files"], 1)
            self.assertEqual(
                report["correlations"]["VICMEM"][0]["backup_record_offset"],
                "0x000000c0",
            )
            self.assertEqual(
                report["correlations"]["VICLV"][0]["backup_record_offset"],
                "0x00000040",
            )
            self.assertEqual(report["sidecars"]["order.vnw"]["entries"][0]["path"], "memo.txt")

    def test_writer_creates_only_manifest_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixture"
            root.mkdir()
            self._write_fixture(root)
            destination = Path(temporary) / "report"
            write_fixture_report(root, destination)
            manifest = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(manifest["format"], "infocarry-fixture-report-v1")
            self.assertEqual(sorted(path.name for path in destination.iterdir()), ["manifest.json"])
            with self.assertRaises(FixtureReportError):
                write_fixture_report(root, destination)


if __name__ == "__main__":
    unittest.main()
