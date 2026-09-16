from pathlib import Path
import tempfile
import unittest

from infocarry.content_workspace import (
    ContentSourceKind,
    ContentWorkspace,
    ContentWorkspaceCancelled,
    ContentWorkspaceError,
    ContentWorkspaceSettings,
    UnsupportedContentError,
)
from infocarry.library import LibraryCatalog
from infocarry.library_transfer_plan import build_library_transfer_queue_plan
from infocarry.library_transfer_readiness import (
    ReadinessReasonCode,
    build_library_transfer_readiness,
    readiness_state_from_error,
)
from infocarry.library_workflow import LibraryWorkflowService
from infocarry.offline_conversion import PageLayout
from infocarry.prepared_media_package import build_prepared_media_package, export_prepared_media_package


def make_profile_bmp() -> bytes:
    width, height = 237, 320
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
    payload[28:30] = (1).to_bytes(2, "little")
    payload[34:38] = len(pixels).to_bytes(4, "little")
    payload[46:50] = (2).to_bytes(4, "little")
    payload[58:62] = b"\xff\xff\xff\x00"
    payload[62:] = pixels
    return bytes(payload)


class ContentWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = ContentWorkspace()

    def tearDown(self):
        self.temporary.cleanup()

    def test_txt_is_deterministic_and_surfaces_normalization(self):
        source = self.root / "story.txt"
        source.write_text("A “quoted” line — with an ellipsis…\n", encoding="utf-8")
        first = self.workspace.prepare(source)
        second = self.workspace.prepare(source)
        self.assertEqual(first.artifact.to_dict(), second.artifact.to_dict())
        self.assertEqual(first.source_kind, ContentSourceKind.TXT)
        self.assertEqual(first.preview.artifact, first.artifact)
        self.assertEqual(first.preview.text_excerpt, source.read_text(encoding="utf-8"))
        self.assertTrue(first.preview.normalization_substitutions)
        self.assertTrue(first.preview.warnings)

    def test_bmp_is_deterministic_and_payload_mutation_changes_identity(self):
        source = self.root / "page.bmp"
        source.write_bytes(make_profile_bmp())
        first = self.workspace.prepare(source)
        second = self.workspace.prepare(source)
        self.assertEqual(first.artifact.artifact_identity, second.artifact.artifact_identity)
        self.assertEqual(first.artifact.children[0].kind, "bmp")
        mutated = bytearray(source.read_bytes())
        mutated[-1] = 1
        source.write_bytes(mutated)
        self.assertNotEqual(first.artifact.artifact_identity, self.workspace.prepare(source).artifact.artifact_identity)

    def test_settings_and_logical_root_participate_in_identity(self):
        source = self.root / "story.txt"
        source.write_text("same", encoding="utf-8")
        first = self.workspace.prepare(source)
        changed_root = self.workspace.prepare(
            source, settings=ContentWorkspaceSettings(root_name="Renamed")
        )
        changed_layout = self.workspace.prepare(
            source,
            settings=ContentWorkspaceSettings(
                page_layout=PageLayout(columns=20)
            ),
        )
        self.assertNotEqual(first.artifact.artifact_identity, changed_root.artifact.artifact_identity)
        self.assertNotEqual(first.artifact.artifact_identity, changed_layout.artifact.artifact_identity)

    def test_library_source_change_discards_persisted_artifact(self):
        source = self.root / "story.txt"
        source.write_text("before", encoding="utf-8")
        catalog = LibraryCatalog(self.root / "library.json")
        imported = catalog.import_file(source)
        LibraryWorkflowService(catalog).prepare_preview(imported.item_id)
        source.write_text("after", encoding="utf-8")
        refreshed = catalog.refresh(imported.item_id)
        self.assertEqual(refreshed.preparation_state, "stale")
        self.assertIsNone(refreshed.prepared_artifact)

    def test_review_rechecks_source_before_using_saved_artifact(self):
        source = self.root / "story.txt"
        source.write_text("before", encoding="utf-8")
        catalog = LibraryCatalog(self.root / "library.json")
        imported = catalog.import_file(source)
        preview = LibraryWorkflowService(catalog).prepare_preview(imported.item_id)
        source.write_text("after", encoding="utf-8")
        plan = build_library_transfer_queue_plan(
            catalog,
            selected_item_ids=[imported.item_id],
            canonical_artifacts={imported.item_id: preview.artifact},
        ).to_dict()
        self.assertIn("source hash changed", " ".join(plan["items"][0]["reasons"]))
        self.assertFalse(plan["items"][0]["queue_ready"])

    def test_folder_hierarchy_keeps_legacy_manifest_and_canonical_identity_distinct(self):
        folder = self.root / "Book"
        folder.mkdir()
        (folder / "one.txt").write_text("one", encoding="utf-8")
        catalog = LibraryCatalog(self.root / "library.json")
        imported = catalog.import_folder(folder)
        preview = LibraryWorkflowService(catalog).prepare_preview(imported.item_id)
        saved = catalog.get(imported.item_id)
        self.assertNotEqual(saved.prepared_manifest_sha256, preview.artifact.artifact_identity)
        plan = build_library_transfer_queue_plan(
            catalog,
            selected_item_ids=[imported.item_id],
            canonical_artifacts={imported.item_id: preview.artifact},
        )
        item_report = plan.to_dict()["items"][0]
        self.assertEqual(item_report["prepared_artifact"]["artifact_identity"], preview.artifact.artifact_identity)
        self.assertEqual(item_report["prepared_artifact"]["manifest_sha256"], saved.prepared_manifest_sha256)
        self.assertFalse(plan.queue_ready)

    def test_strict_unsupported_character_is_typed(self):
        source = self.root / "unsupported.txt"
        source.write_text("not representable 😀", encoding="utf-8")
        with self.assertRaises(ContentWorkspaceError):
            self.workspace.prepare(source)

    def test_epub_is_explicitly_deferred(self):
        source = self.root / "book.epub"
        source.write_bytes(b"not converted")
        with self.assertRaisesRegex(UnsupportedContentError, "This format is not ready for conversion yet"):
            self.workspace.prepare(source)
        state = readiness_state_from_error(
            UnsupportedContentError("This format is not ready for conversion yet.")
        )
        self.assertEqual(state.reason_codes, (ReadinessReasonCode.UNSUPPORTED_SOURCE_FORMAT,))
        self.assertEqual(state.message, "This format is not ready for conversion yet.")

    def test_prepared_package_uses_existing_canonical_adapter(self):
        first = self.root / "first.txt"
        page = self.root / "page.bmp"
        last = self.root / "last.txt"
        first.write_text("first", encoding="utf-8")
        page.write_bytes(make_profile_bmp())
        last.write_text("last", encoding="utf-8")
        package = build_prepared_media_package(
            ((first, "one.txt"), (page, "page.bmp"), (last, "two.txt")), "Book"
        )
        destination = self.root / "package"
        export_prepared_media_package(package, destination)
        result = self.workspace.prepare(destination)
        self.assertEqual(result.source_kind, ContentSourceKind.PREPARED_PACKAGE)
        self.assertEqual(
            result.artifact.artifact_identity,
            package.to_prepared_content_artifact().artifact_identity,
        )
        self.assertEqual(result.artifact.children[0].order, 0)

    def test_prepared_folder_uses_existing_hierarchy_adapter(self):
        folder = self.root / "Folder"
        folder.mkdir()
        (folder / "one.txt").write_text("one", encoding="utf-8")
        (folder / "two.txt").write_text("two", encoding="utf-8")
        result = self.workspace.prepare(folder)
        self.assertEqual(result.source_kind, ContentSourceKind.PREPARED_FOLDER)
        self.assertEqual(result.artifact.root_name, "Folder")
        self.assertEqual([child.name for child in result.artifact.children], ["one.txt", "two.txt"])

    def test_library_prepare_preview_and_review_share_canonical_identity(self):
        source = self.root / "story.txt"
        source.write_text("review me", encoding="utf-8")
        catalog = LibraryCatalog(self.root / "library.json")
        imported = catalog.import_file(source)
        workflow_preview = LibraryWorkflowService(catalog).prepare_preview(imported.item_id)
        item = catalog.get(imported.item_id)
        self.assertEqual(item.preparation_state, "prepared")
        self.assertEqual(item.prepared_artifact["artifact_identity"], workflow_preview.artifact.artifact_identity)
        self.assertIs(workflow_preview.prepared.preview.artifact, workflow_preview.artifact)

        plan = build_library_transfer_queue_plan(
            catalog,
            selected_item_ids=[imported.item_id],
            canonical_artifacts={imported.item_id: workflow_preview.artifact},
        )
        report = plan.to_dict()
        self.assertEqual(
            report["items"][0]["prepared_artifact"]["artifact_identity"],
            workflow_preview.artifact.artifact_identity,
        )
        readiness = build_library_transfer_readiness(report)
        self.assertTrue(readiness.prepared_content_valid)
        self.assertFalse(readiness.host_profile_eligible)
        self.assertIn("valid", readiness.to_dict()["eligibility"]["status_text"])

    def test_cancellation_is_safe_before_preparation(self):
        source = self.root / "story.txt"
        source.write_text("cancel", encoding="utf-8")
        import threading

        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(ContentWorkspaceCancelled):
            self.workspace.prepare(source, cancel_event=cancelled)


if __name__ == "__main__":
    unittest.main()
