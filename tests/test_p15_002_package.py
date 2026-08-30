import hashlib
import json
from pathlib import Path
import unittest

from infocarry.prepared_multi_text import build_prepared_text_package_set


PACKAGE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "samples"
    / "generated"
    / "P15-002-modern-multi-chapter-txt"
)
SOURCE_ROOT = PACKAGE_ROOT / "source" / "IC_P15_MULTI_20260828_02"
P15001_PACKAGE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "samples"
    / "generated"
    / "P15-001-native-multi-chapter-txt"
)


class P15002PackageTests(unittest.TestCase):
    def _manifest(self):
        return json.loads((PACKAGE_ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_manifest_binds_new_four_ordered_crlf_cp932_sources(self):
        manifest = self._manifest()
        self.assertEqual(manifest["task"], "P15-002")
        self.assertEqual(manifest["status"], "IMPLEMENTATION_READY")
        self.assertEqual(manifest["root_folder"], "IC_P15_MULTI_20260828_02")
        self.assertEqual(manifest["source_count"], 4)
        self.assertTrue(manifest["baseline_binding"]["target_absent_from_latest_preserved_post"])
        self.assertEqual(
            manifest["baseline_binding"]["capture_01_folder_preserved"],
            "IC_P15_MULTI_20260828_01",
        )

        for expected_order, item in enumerate(manifest["ordered_children"], start=1):
            source = PACKAGE_ROOT / item["source_path"]
            data = source.read_bytes()
            self.assertEqual(item["order"], expected_order)
            self.assertEqual(item["bytes"], len(data))
            self.assertEqual(item["sha256"], hashlib.sha256(data).hexdigest())
            self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
            data.decode("cp932", errors="strict")
            text = data.decode("ascii")
            self.assertIn(f"Order marker: {expected_order:02d} of 04.", text)
            self.assertIn(item["content_end_marker"], text)

    def test_ordered_model_matches_exact_p15002_sources(self):
        manifest = self._manifest()
        specs = tuple(
            (PACKAGE_ROOT / item["source_path"], item["target_path"].rsplit("\\", 1)[1])
            for item in manifest["ordered_children"]
        )
        package = build_prepared_text_package_set(
            specs,
            manifest["root_folder"],
        )
        self.assertEqual(package.target_item_paths, tuple(item["target_path"] for item in manifest["ordered_children"]))
        self.assertEqual(package.prepared_payload_bytes, 484)
        self.assertEqual(
            tuple(item.source_sha256 for item in package.items),
            tuple(item["sha256"] for item in manifest["ordered_children"]),
        )

    def test_package_is_flat_and_keeps_p15001_evidence_distinct(self):
        manifest = self._manifest()
        self.assertTrue(all(path.parent == SOURCE_ROOT for path in SOURCE_ROOT.glob("*.txt")))
        self.assertEqual(
            sorted(path.name for path in SOURCE_ROOT.glob("*.txt")),
            ["chapter-01.txt", "chapter-02.txt", "chapter-03.txt", "chapter-04.txt"],
        )
        self.assertFalse(any(PACKAGE_ROOT.rglob("*.bin")))
        self.assertFalse(any(PACKAGE_ROOT.rglob("*.usblog")))
        self.assertEqual(
            json.loads((P15001_PACKAGE_ROOT / "manifest.json").read_text(encoding="utf-8"))["root_folder"],
            "IC_P15_MULTI_20260828_01",
        )
        self.assertNotIn("IC_P15_MULTI_20260828_01", manifest["root_folder"])

    def test_checksum_manifest_covers_only_manifest_and_sources(self):
        entries = {}
        for line in (PACKAGE_ROOT / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines():
            digest, relative = line.split("  ", 1)
            entries[relative] = digest
        expected = {"manifest.json"}
        expected.update(item["source_path"] for item in self._manifest()["ordered_children"])
        self.assertEqual(set(entries), expected)
        for relative, expected_digest in entries.items():
            self.assertEqual(
                hashlib.sha256((PACKAGE_ROOT / relative).read_bytes()).hexdigest(),
                expected_digest,
                relative,
            )


if __name__ == "__main__":
    unittest.main()
