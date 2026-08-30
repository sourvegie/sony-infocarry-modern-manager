from pathlib import Path
import hashlib
import json
import unittest

from infocarry.prepared_multi_text import build_prepared_text_package_set


PACKAGE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "samples"
    / "generated"
    / "P15-001-native-multi-chapter-txt"
)
SOURCE_ROOT = PACKAGE_ROOT / "source" / "IC_P15_MULTI_20260828_01"


class P15001PackageTests(unittest.TestCase):
    def _manifest(self):
        return json.loads((PACKAGE_ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_manifest_binds_four_ordered_crlf_cp932_sources(self):
        manifest = self._manifest()
        self.assertEqual(manifest["task"], "P15-001")
        self.assertEqual(manifest["root_folder"], "IC_P15_MULTI_20260828_01")
        self.assertEqual(manifest["source_count"], 4)
        self.assertEqual(manifest["total_source_bytes"], 480)
        self.assertTrue(manifest["preparation"]["strict_cp932"])
        self.assertTrue(manifest["native_evidence_required_before_modern_smoke"])

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

    def test_ordered_model_matches_the_exact_review_package(self):
        manifest = self._manifest()
        specs = tuple(
            (PACKAGE_ROOT / item["source_path"], item["target_path"].rsplit("\\", 1)[1])
            for item in manifest["ordered_children"]
        )
        package = build_prepared_text_package_set(
            specs,
            manifest["root_folder"],
        )
        self.assertEqual(
            package.target_item_paths,
            tuple(item["target_path"] for item in manifest["ordered_children"]),
        )
        self.assertEqual(package.prepared_payload_bytes, 480)
        self.assertEqual(
            tuple(item.source_sha256 for item in package.items),
            tuple(item["sha256"] for item in manifest["ordered_children"]),
        )
        self.assertTrue(all(item.kind == "txt" for item in package.items))
        self.assertEqual(len(package.items), 4)

    def test_package_shape_is_flat_and_contains_no_device_artifacts(self):
        manifest = self._manifest()
        self.assertTrue(all(path.parts[-2] == manifest["root_folder"] for path in SOURCE_ROOT.glob("*.txt")))
        self.assertEqual(sorted(path.name for path in SOURCE_ROOT.glob("*.txt")), [
            "chapter-01.txt",
            "chapter-02.txt",
            "chapter-03.txt",
            "chapter-04.txt",
        ])
        self.assertFalse(any(PACKAGE_ROOT.rglob("*.bin")))
        self.assertFalse(any(PACKAGE_ROOT.rglob("*.usblog")))
        self.assertFalse((PACKAGE_ROOT / "backup").exists())
        self.assertFalse((PACKAGE_ROOT / "capture").exists())

    def test_preservation_checksum_manifest_covers_manifest_and_sources(self):
        entries = {}
        for line in (PACKAGE_ROOT / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines():
            digest, relative = line.split("  ", 1)
            entries[relative] = digest
        expected = {"manifest.json"}
        expected.update(
            item["source_path"] for item in self._manifest()["ordered_children"]
        )
        self.assertEqual(set(entries), expected)
        for relative, expected_digest in entries.items():
            actual = hashlib.sha256((PACKAGE_ROOT / relative).read_bytes()).hexdigest()
            self.assertEqual(actual, expected_digest, relative)


if __name__ == "__main__":
    unittest.main()
