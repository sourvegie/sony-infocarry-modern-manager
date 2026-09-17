import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from infocarry.content_workspace import (
    ContentSourceKind,
    ContentWorkspace,
    ContentWorkspaceCancelled,
    ContentWorkspaceError,
    ContentWorkspaceSettings,
    EpubLimits,
    EpubPackageError,
    EpubSecurityError,
    UnsupportedContentError,
)
from infocarry.library import LibraryError, SUPPORTED_EPUB_FORMAT, LibraryCatalog
from infocarry.library_prepare import prepare_library_item
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


def write_epub(path: Path, *, chapter: str, include_image: bool = False) -> None:
    manifest_image = (
        '<item id="image" href="images/page.bmp" media-type="image/bmp"/>'
        if include_image
        else ""
    )
    image_tag = '<img src="images/page.bmp" alt="page image"/>' if include_image else ""
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
            <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
              <rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles>
            </container>""",
        )
        archive.writestr(
            "OEBPS/content.opf",
            f"""<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
              <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Sample Book</dc:title></metadata>
              <manifest><item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>{manifest_image}</manifest>
              <spine><itemref idref="chapter"/></spine>
            </package>""",
        )
        archive.writestr(
            "OEBPS/chapter.xhtml",
            f"<html><body><h1>Heading</h1><p>{chapter}</p>{image_tag}</body></html>",
        )
        if include_image:
            archive.writestr("OEBPS/images/page.bmp", make_profile_bmp())


class ContentWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = ContentWorkspace()

    def tearDown(self):
        self.temporary.cleanup()

    def test_txt_is_deterministic_and_surfaces_normalization(self):
        source = self.root / "story.txt"
        source_text = "A “quoted” line — with an ellipsis…\r\n"
        # Use explicit bytes so the source fixture has the same CRLF semantics
        # on every host.  Path.read_text() intentionally performs native
        # newline translation on Windows and is therefore not a stable oracle
        # for the raw source text used by the preview.
        source.write_bytes(source_text.encode("utf-8"))
        first = self.workspace.prepare(source)
        second = self.workspace.prepare(source)
        self.assertEqual(first.artifact.to_dict(), second.artifact.to_dict())
        self.assertEqual(first.source_kind, ContentSourceKind.TXT)
        self.assertEqual(first.preview.artifact, first.artifact)
        self.assertEqual(first.preview.text_excerpt, source_text)
        self.assertEqual(first.preparation_metadata["newline_policy"], "crlf")
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

    def test_epub_is_supported_but_remains_outside_the_live_profile(self):
        source = self.root / "book.epub"
        write_epub(source, chapter="hello")
        result = self.workspace.prepare(source)
        self.assertEqual(result.source_format, "epub")
        self.assertEqual(result.source_path, source.resolve())
        self.assertFalse(result.report()["safety"]["sender_called"])

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

    def test_epub_uses_title_spine_text_and_safe_bmp_projection(self):
        source = self.root / "book.epub"
        write_epub(source, chapter="Hello 日本語", include_image=True)

        result = self.workspace.prepare_epub(source)

        self.assertEqual(result.title, "Sample Book")
        self.assertEqual(
            [(child.kind, child.name) for child in result.artifact.children],
            [("txt", "chapter-001.txt"), ("bmp", "chapter-001-image-001.bmp")],
        )
        self.assertEqual(
            result.payloads[0].payload,
            b"Heading\r\nHello \x93\xfa\x96{\x8c\xea\r\npage image",
        )
        self.assertEqual(result.transfer_shape.classification, "plausible_future_vnw_v15_direct_leaf")
        self.assertTrue(result.normalization_occurred)
        self.assertIn("Some characters were adjusted", result.user_notice or "")
        self.assertFalse(result.report()["safety"]["usb_accessed"])

    def test_epub_unsupported_features_are_explicit_and_never_fetched(self):
        source = self.root / "book.epub"
        write_epub(
            source,
            chapter='<script>send_secret()</script><a href="https://example.invalid/book">remote</a>',
        )
        result = self.workspace.prepare_epub(source)
        kinds = {feature["kind"] for feature in result.unsupported_features}
        self.assertIn("javascript", kinds)
        self.assertIn("remote-resources", kinds)
        self.assertIn("remote", result.payloads[0].payload.decode("cp932"))

    def test_epub_zip_slip_and_external_entities_fail_closed(self):
        slip = self.root / "slip.epub"
        with ZipFile(slip, "w", ZIP_DEFLATED) as archive:
            archive.writestr("../escape", b"unsafe")
        with self.assertRaises(EpubSecurityError):
            self.workspace.inspect_epub(slip)

        entity = self.root / "entity.epub"
        with ZipFile(entity, "w", ZIP_DEFLATED) as archive:
            archive.writestr(
                "META-INF/container.xml",
                "<!DOCTYPE container [<!ENTITY x SYSTEM 'file:///tmp/x'>]><container/>",
            )
        with self.assertRaises(EpubSecurityError):
            self.workspace.inspect_epub(entity)

    def test_materialize_is_non_overwriting_and_contains_canonical_manifest(self):
        source = self.root / "book.epub"
        write_epub(source, chapter="hello")
        result = self.workspace.prepare_epub(source)
        destination = self.root / "prepared"
        ContentWorkspace.materialize(result, destination)
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["prepared_content_artifact"]["artifact_identity"],
            result.artifact.artifact_identity,
        )
        with self.assertRaisesRegex(ContentWorkspaceError, "overwrite"):
            ContentWorkspace.materialize(result, destination)

    def test_epub2_and_title_fallback_are_supported(self):
        source = self.root / "fallback.epub"
        with ZipFile(source, "w", ZIP_DEFLATED) as archive:
            archive.writestr(
                "META-INF/container.xml",
                '<container><rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles></container>',
            )
            archive.writestr(
                "OEBPS/content.opf",
                '<package version="2.0"><metadata/><manifest>'
                '<item id="chapter" href="chapter.html" media-type="text/html"/>'
                '</manifest><spine><itemref idref="chapter"/></spine></package>',
            )
            archive.writestr("OEBPS/chapter.html", "<html><body><p>hello</p></body></html>")
        result = self.workspace.prepare_epub(source)
        self.assertEqual(result.title, "content")
        self.assertEqual(result.artifact.children[0].kind, "txt")

    def test_epub_package_errors_and_drm_fail_closed(self):
        missing_container = self.root / "missing-container.epub"
        with ZipFile(missing_container, "w", ZIP_DEFLATED) as archive:
            archive.writestr("mimetype", "application/epub+zip")
        with self.assertRaises(EpubPackageError):
            self.workspace.inspect_epub(missing_container)

        missing_spine = self.root / "missing-spine.epub"
        with ZipFile(missing_spine, "w", ZIP_DEFLATED) as archive:
            archive.writestr(
                "META-INF/container.xml",
                '<container><rootfiles><rootfile full-path="book.opf"/></rootfiles></container>',
            )
            archive.writestr(
                "book.opf",
                '<package version="3.0"><manifest/><spine><itemref idref="missing"/></spine></package>',
            )
        with self.assertRaises(EpubPackageError):
            self.workspace.inspect_epub(missing_spine)

        drm = self.root / "drm.epub"
        write_epub(drm, chapter="hello")
        with ZipFile(drm, "a", ZIP_DEFLATED) as archive:
            archive.writestr("META-INF/encryption.xml", b"<encryption/>")
        with self.assertRaises(EpubPackageError):
            self.workspace.inspect_epub(drm)

    def test_epub_limits_are_production_and_enforced(self):
        source = self.root / "bounded.epub"
        write_epub(source, chapter="hello")
        with self.assertRaises(EpubSecurityError):
            ContentWorkspace(limits=EpubLimits(max_archive_entries=2)).inspect_epub(source)

    def test_epub_cancellation_is_typed_and_offline(self):
        source = self.root / "cancel.epub"
        write_epub(source, chapter="hello")
        with self.assertRaisesRegex(ContentWorkspaceError, "cancelled"):
            self.workspace.prepare_epub(source, cancelled=lambda: True)

    def test_library_cancellation_does_not_mark_the_source_blocked(self):
        import threading

        source = self.root / "cancel.epub"
        write_epub(source, chapter="hello")
        catalog = LibraryCatalog(self.root / "cancelled" / "library.json")
        item = catalog.import_file(source)
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(ContentWorkspaceCancelled):
            LibraryWorkflowService(catalog).prepare_preview(
                item.item_id,
                cancel_event=cancelled,
            )
        current = catalog.get(item.item_id)
        self.assertEqual(current.preparation_state, "unprepared")
        self.assertEqual(current.state, "imported")

    def test_same_source_is_deterministic_and_mutation_changes_identity(self):
        source = self.root / "book.epub"
        write_epub(source, chapter="hello")
        first = self.workspace.prepare_epub(source)
        second = self.workspace.prepare_epub(source)
        self.assertEqual(first.artifact.artifact_identity, second.artifact.artifact_identity)
        write_epub(source, chapter="changed")
        changed = self.workspace.prepare_epub(source)
        self.assertNotEqual(first.artifact.artifact_identity, changed.artifact.artifact_identity)

    def test_epub_enters_host_review_but_not_the_live_profile(self):
        source = self.root / "book.epub"
        write_epub(source, chapter="hello")
        catalog = LibraryCatalog(self.root / "review" / "library.json")
        item = catalog.import_file(source)
        LibraryWorkflowService(catalog).prepare_preview(item.item_id)
        plan = build_library_transfer_queue_plan(
            catalog,
            selected_item_ids=[item.item_id],
            selection_mode="selected",
        )
        report = plan.to_dict()
        self.assertEqual(report["items"][0]["operation_type"], "prepared_epub_content")
        self.assertFalse(report["eligibility"]["queue_ready"])
        self.assertFalse(report["safety"]["sender_called"])
        self.assertTrue(
            any(
                reason.startswith("EPUB preparation is host-only")
                for reason in report["items"][0]["reasons"]
            )
        )

    def test_library_catalog_and_prepare_path_accept_epub_without_device_access(self):
        source = self.root / "book.epub"
        write_epub(source, chapter="hello")
        catalog = LibraryCatalog(self.root / "prepare" / "library.json")
        item = catalog.import_file(source, now="2026-09-17T00:00:00+00:00")
        self.assertEqual(item.detected_format, SUPPORTED_EPUB_FORMAT)
        result = prepare_library_item(catalog, item.item_id, "Sample Book", "ignored.txt")
        self.assertEqual(result.artifact.root_name, "Sample Book")
        self.assertIsNone(result.item.target_child_name)
        self.assertEqual(result.audit["device_operation"], "none")

    def test_library_preview_routes_epub_through_the_workspace(self):
        source = self.root / "book.epub"
        write_epub(source, chapter="hello")
        catalog = LibraryCatalog(self.root / "preview" / "library.json")
        item = catalog.import_file(source)
        preview = LibraryWorkflowService(catalog).prepare_preview(item.item_id)
        self.assertEqual(preview.prepared.artifact.profile_id, "prepared-epub-content-v1")
        self.assertFalse(preview.to_dict()["foundation"]["usb_accessed"])


if __name__ == "__main__":
    unittest.main()
