from pathlib import Path
import tempfile
import unittest

from infocarry.prepared_ebook_plan import (
    PREPARED_EBOOK_NOTICE,
    PreparedEbookPlanError,
    build_prepared_ebook_plan,
)

try:
    from test_prepared_media_package import make_profile_bmp
except ModuleNotFoundError:
    from tests.test_prepared_media_package import make_profile_bmp


class PreparedEbookPlanTests(unittest.TestCase):
    def _manifest(self, root: Path):
        first = root / "first.txt"
        image = root / "page.bmp"
        last = root / "last.txt"
        first.write_text("first\n", encoding="utf-8")
        image.write_bytes(make_profile_bmp())
        last.write_text("last\n", encoding="utf-8")
        return {
            "format": "synthetic-ebook-manifest-v1",
            "title": "Offline Synthetic",
            "root_folder": "Offline Ebook",
            "sections": [],
            "items": [
                {"source": first, "name": "chapter-1.txt"},
                {"source": image, "name": "page-1.bmp"},
                {"source": last, "name": "chapter-2.txt"},
            ],
        }, (first, image, last)

    def test_flat_manifest_plan_is_deterministic_and_ineligible_for_device(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, _sources = self._manifest(root)
            first = build_prepared_ebook_plan(manifest)
            second = build_prepared_ebook_plan(manifest)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(first.plan_sha256, second.plan_sha256)
            self.assertFalse(first.eligible)
            self.assertEqual(first.to_dict()["notice"], PREPARED_EBOOK_NOTICE)
            self.assertFalse(first.to_dict()["usb_accessed"])
            self.assertEqual(
                [item["kind"] for item in first.to_dict()["target"]["ordered_items"]],
                ["txt", "bmp", "txt"],
            )
            self.assertIn("nested folder construction is unproven and fail-closed", first.to_dict()["eligibility"]["reasons"])

    def test_plan_binds_paths_hashes_growth_and_expected_readback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, sources = self._manifest(root)
            plan = build_prepared_ebook_plan(manifest)
            report = plan.to_dict()
            self.assertEqual(report["target"]["paths"][0], "root\\Offline Ebook")
            self.assertEqual(len(report["target"]["ordered_items"]), 3)
            self.assertEqual(report["capacity"]["growth_bytes"], plan.package.estimated_growth_lower_bound)
            self.assertEqual(
                report["policy"]["expected_readback"]["added_paths"],
                report["target"]["paths"],
            )
            self.assertEqual(report["policy"]["expected_readback"]["removed_paths"], [])
            self.assertTrue(all(source.exists() for source in sources))

    def test_nonempty_sections_are_rejected_without_flattening(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, _sources = self._manifest(root)
            manifest["sections"] = [{"name": "Chapter 1", "items": []}]
            with self.assertRaisesRegex(PreparedEbookPlanError, "nested section folders"):
                build_prepared_ebook_plan(manifest)

    def test_item_section_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, _sources = self._manifest(root)
            manifest["items"][0]["section"] = "Chapter 1"
            with self.assertRaisesRegex(PreparedEbookPlanError, "nested section folders"):
                build_prepared_ebook_plan(manifest)

    def test_malformed_manifest_and_missing_items_fail_closed(self):
        with self.assertRaises(PreparedEbookPlanError):
            build_prepared_ebook_plan(None)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, _sources = self._manifest(root)
            for replacement in (None, [], [{"source": root / "missing.txt", "name": "one.txt"}]):
                manifest["items"] = replacement
                with self.assertRaises(PreparedEbookPlanError):
                    build_prepared_ebook_plan(manifest)

    def test_source_mutation_changes_the_plan_on_rebuild(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, sources = self._manifest(root)
            before = build_prepared_ebook_plan(manifest)
            sources[0].write_text("changed\n", encoding="utf-8")
            after = build_prepared_ebook_plan(manifest)
            self.assertNotEqual(before.plan_sha256, after.plan_sha256)
            self.assertNotEqual(
                before.to_dict()["target"]["ordered_items"][0]["source_sha256"],
                after.to_dict()["target"]["ordered_items"][0]["source_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
