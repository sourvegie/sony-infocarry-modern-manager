import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from infocarry.backup import BackupObjectSpec, RawBackupArchive
from infocarry.desktop import DesktopWorkflowError, DesktopWorkflowModel
from infocarry.write_gate import PostWriteVerification

try:
    from test_backup_format import make_text_blob
except ModuleNotFoundError:
    from tests.test_backup_format import make_text_blob


class DesktopWorkflowModelTests(unittest.TestCase):
    def _backup(self, root: Path, blob: bytes = None) -> Path:
        directory = root / "backup"
        archive = RawBackupArchive.create(directory)
        if blob is None:
            blob = make_text_blob(b"old\r\ntext")
        archive.save(BackupObjectSpec(0x8004, "backup-blob", len(blob)), blob)
        archive.finalize()
        return directory

    def test_load_select_preview_and_save_are_offline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = DesktopWorkflowModel()
            rows = model.load_backup(self._backup(root))
            file_row = next(row for row in rows if row.kind == "file")
            self.assertFalse(model.state.device_write_enabled)
            model.select_record(file_row.record_offset)
            text_path = root / "new.txt"
            text_path.write_text("new\ntext", encoding="utf-8")
            report = model.preview_text(text_path, max_payload_bytes=128)
            self.assertFalse(report["workflow"]["device_accessed"])
            saved = model.save_preview_report(root / "preview")
            self.assertTrue(saved.exists())

    def test_selected_text_replacement_preview_reports_target_and_source_sizes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = DesktopWorkflowModel()
            rows = model.load_backup(self._backup(root))
            file_row = next(row for row in rows if row.kind == "file")
            model.select_record(file_row.record_offset)
            text_path = root / "replacement.txt"
            source = "日本語\nreplacement"
            text_path.write_text(source, encoding="utf-8")

            report = model.preview_selected_text_replacement(
                text_path, max_payload_bytes=128
            )

            self.assertEqual(report["workflow"]["target_record_offset"], "0x000000c0")
            self.assertEqual(report["workflow"]["target_path"], "root\\memo.txt")
            self.assertEqual(report["workflow"]["input_path"], str(text_path.resolve()))
            self.assertEqual(report["authoring"]["input_characters"], len(source))
            self.assertEqual(
                report["authoring"]["input_utf8_bytes"], len(source.encode("utf-8"))
            )
            self.assertGreater(report["authoring"]["encoded_payload_bytes"], 0)
            self.assertTrue(report["target"]["native_prefix"]["preserved_exactly"])
            self.assertFalse(report["safety"]["candidate_bytes_included"])
            self.assertFalse(report["workflow"]["device_accessed"])
            self.assertEqual(model.state.preview_report, report)

    def test_selected_text_replacement_preview_reports_authoring_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = DesktopWorkflowModel()
            file_row = next(
                row for row in model.load_backup(self._backup(root)) if row.kind == "file"
            )
            model.select_record(file_row.record_offset)

            unsupported = root / "unsupported.txt"
            unsupported.write_text("unsupported 😀", encoding="utf-8")
            with self.assertRaisesRegex(DesktopWorkflowError, "U\\+1F600"):
                model.preview_selected_text_replacement(unsupported)

            nul = root / "nul.txt"
            nul.write_bytes(b"has\x00nul")
            with self.assertRaisesRegex(DesktopWorkflowError, "NUL"):
                model.preview_selected_text_replacement(nul)

            oversized = root / "oversized.txt"
            oversized.write_text("too long", encoding="utf-8")
            with self.assertRaisesRegex(DesktopWorkflowError, "capacity is 2"):
                model.preview_selected_text_replacement(oversized, max_payload_bytes=2)

    def test_read_bitmap_preview_is_offline(self):
        try:
            from test_bitmap import make_monochrome_bmp
        except ModuleNotFoundError:
            from tests.test_bitmap import make_monochrome_bmp

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            blob = make_text_blob(
                make_monochrome_bmp(9, 2), field14=0x100, extension="bmp"
            )
            model = DesktopWorkflowModel()
            rows = model.load_backup(self._backup(root, blob))
            image_row = next(row for row in rows if row.extension == "bmp")
            preview = model.read_selected_bitmap(image_row.record_offset)
            self.assertEqual((preview.width, preview.height), (9, 2))
            self.assertTrue(preview.ppm.startswith(b"P3\n9 2\n255\n"))
            self.assertEqual(model.state.device_write_enabled, False)

    def test_rejects_non_text_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            model = DesktopWorkflowModel()
            model.load_backup(self._backup(Path(temporary)))
            model.select_record(0x40)
            with self.assertRaises(DesktopWorkflowError):
                model.preview_text(Path(temporary) / "missing.txt")

    def test_read_preview_and_selected_export_are_offline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = DesktopWorkflowModel()
            rows = model.load_backup(self._backup(root))
            file_row = next(row for row in rows if row.kind == "file")
            self.assertEqual(model.read_selected_text(file_row.record_offset), "old\r\ntext")
            destination = root / "selected-export"
            manifest = model.export_selection(destination, [file_row.record_offset])
            self.assertEqual(manifest["summary"]["files"], 1)
            self.assertEqual(manifest["summary"]["directories"], 0)
            self.assertEqual(
                manifest["selection"]["selected_reachable_offsets"],
                [f"0x{file_row.record_offset:08x}"],
            )
            file_entry = manifest["records"][0]
            self.assertTrue((destination / file_entry["native_path"]).exists())
            self.assertFalse(model.state.device_write_enabled)

    def test_records_only_a_complete_post_write_verification_result(self):
        model = DesktopWorkflowModel()
        verification = PostWriteVerification(
            before=SimpleNamespace(to_dict=lambda: {"directory": "before"}),
            after=SimpleNamespace(to_dict=lambda: {"directory": "after"}),
            fixed_state_matches=True,
            dynamic_blob_matches=True,
            unrelated_objects_unchanged=True,
        )
        result = model.record_post_write_verification(verification)
        self.assertEqual(result["after_backup"]["directory"], "after")
        self.assertEqual(model.state.post_write_verification, result)
        self.assertIn("read-back verified", model.state.status)
        self.assertFalse(model.state.device_write_enabled)

    def test_rejects_incomplete_post_write_verification_without_retry_message(self):
        model = DesktopWorkflowModel()
        verification = PostWriteVerification(
            before=SimpleNamespace(to_dict=lambda: {"directory": "before"}),
            after=SimpleNamespace(to_dict=lambda: {"directory": "after"}),
            fixed_state_matches=False,
            dynamic_blob_matches=True,
            unrelated_objects_unchanged=True,
        )
        with self.assertRaisesRegex(DesktopWorkflowError, "did not pass"):
            model.record_post_write_verification(verification)
        self.assertIsNone(model.state.post_write_verification)
        self.assertIn("do not retry", model.state.status)


if __name__ == "__main__":
    unittest.main()
