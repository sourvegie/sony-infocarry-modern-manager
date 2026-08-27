from pathlib import Path
import unittest

from infocarry.prepared_ebook_candidate import (
    PreparedEbookCandidate,
    build_prepared_ebook_candidate,
)
from infocarry.prepared_ebook_plan import PreparedEbookPlanError

try:
    import test_prepared_package_multi_candidate as _multi_fixture
except ModuleNotFoundError:
    import tests.test_prepared_package_multi_candidate as _multi_fixture


class PreparedEbookCandidateTests(unittest.TestCase):
    def _case(self):
        temporary, package, backup, _candidate, template = _multi_fixture.PreparedMultiCandidateTests()._case(mixed=True)
        root = Path(temporary.name)
        manifest = {
            "root_folder": package.folder_name,
            "sections": [],
            "items": [
                {"source": str(item.source_path), "name": item.name}
                for item in package.items
            ],
        }
        candidate = build_prepared_ebook_candidate(
            manifest,
            backup,
            template,
            new_record_timestamp_be32=0x6A8ABA6F,
            native_capacity_response=_multi_fixture.PreparedMultiCandidateTests()._response(),
            template_folder_path=("root", "Template"),
            template_item_paths={
                "txt": ("root", "Template", "chapter"),
                "bmp": ("root", "Template", "page"),
            },
        )
        return temporary, manifest, candidate

    def test_flat_ebook_plan_connects_to_mixed_candidate(self):
        temporary, _manifest, result = self._case()
        self.addCleanup(temporary.cleanup)
        self.assertIsInstance(result, PreparedEbookCandidate)
        self.assertEqual(result.to_dict()["target_paths"], [
            "root\\NewBook", "root\\NewBook\\one.txt",
            "root\\NewBook\\page.bmp", "root\\NewBook\\two.txt",
        ])
        self.assertFalse(result.to_dict()["usb_accessed"])
        self.assertFalse(result.to_dict()["safety"]["sender_called"])
        self.assertEqual(result.candidate_blob_sha256, result.candidate.candidate_blob_sha256)

    def test_nested_sections_remain_rejected(self):
        temporary, manifest, _result = self._case()
        self.addCleanup(temporary.cleanup)
        nested = dict(manifest)
        nested["sections"] = [{"name": "chapter-1"}]
        with self.assertRaisesRegex(PreparedEbookPlanError, "nested section"):
            build_prepared_ebook_candidate(
                nested,
                _result.candidate.backup,
                _result.candidate.baseline,
                new_record_timestamp_be32=1,
                native_capacity_response=_multi_fixture.PreparedMultiCandidateTests()._response(),
                template_folder_path=("root", "Template"),
                template_item_paths={
                    "txt": ("root", "Template", "chapter"),
                    "bmp": ("root", "Template", "page"),
                },
            )


if __name__ == "__main__":
    unittest.main()
