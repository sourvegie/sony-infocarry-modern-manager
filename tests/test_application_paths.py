from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from infocarry.app_paths import (
    EXECUTION_CLAIMS_FILENAME,
    INDETERMINATE_LOCK_FILENAME,
    LEGACY_APPLICATION_DIRECTORY_NAME,
    PROPOSED_APPLICATION_DIRECTORY_NAME,
    application_paths,
    resource_path,
)


class ApplicationPathsTests(unittest.TestCase):
    def test_macos_preserves_legacy_application_support_root_and_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            paths = application_paths(home=home, environ={}, platform="darwin", os_name="posix")
            legacy = (home / "Library" / "Application Support" / LEGACY_APPLICATION_DIRECTORY_NAME).resolve()

            self.assertEqual(paths.safety_root, legacy)
            self.assertEqual(paths.execution_claims_database, legacy / EXECUTION_CLAIMS_FILENAME)
            self.assertEqual(paths.indeterminate_write_lock, legacy / INDETERMINATE_LOCK_FILENAME)
            self.assertEqual(paths.root, legacy)
            self.assertEqual(paths.library_catalog, legacy / "library.json")
            self.assertEqual(paths.backup_root, legacy / "Backups")
            self.assertEqual(paths.evidence_root, legacy / "Evidence")
            self.assertEqual(paths.prepared_content_root, legacy / "Prepared Content")
            self.assertEqual(paths.source_metadata_root, legacy / "Prepared Content" / "Source Metadata")
            self.assertEqual(paths.preview_cache_root, legacy / "Cache" / "Previews")
            self.assertEqual(paths.latest_backup_record, legacy / "Backups" / "latest-complete.json")
            self.assertEqual(
                paths.alternate_safety_roots,
                (
                    (home / "Library" / "Application Support" / PROPOSED_APPLICATION_DIRECTORY_NAME / "Safety").resolve(),
                    (home / "Library" / "Application Support" / PROPOSED_APPLICATION_DIRECTORY_NAME).resolve(),
                ),
            )
            self.assertFalse(legacy.exists(), "resolving paths must not create user data")

    def test_windows_preserves_appdata_and_roaming_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            configured = Path(temporary) / "roaming"
            with_appdata = application_paths(
                home=home,
                environ={"APPDATA": str(configured)},
                platform="win32",
                os_name="nt",
            )
            fallback = application_paths(
                home=home,
                environ={},
                platform="win32",
                os_name="nt",
            )

            self.assertEqual(
                with_appdata.safety_root,
                (configured / LEGACY_APPLICATION_DIRECTORY_NAME).resolve(),
            )
            self.assertEqual(with_appdata.root, with_appdata.safety_root)
            self.assertEqual(
                fallback.safety_root,
                (home / "AppData" / "Roaming" / LEGACY_APPLICATION_DIRECTORY_NAME).resolve(),
            )

    def test_linux_keeps_xdg_state_and_data_roots_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            state_home = Path(temporary) / "state"
            data_home = Path(temporary) / "data"
            paths = application_paths(
                home=home,
                environ={"XDG_STATE_HOME": str(state_home), "XDG_DATA_HOME": str(data_home)},
                platform="linux",
                os_name="posix",
            )

            self.assertEqual(paths.safety_root, (state_home / LEGACY_APPLICATION_DIRECTORY_NAME).resolve())
            self.assertEqual(paths.root, (data_home / LEGACY_APPLICATION_DIRECTORY_NAME).resolve())
            self.assertEqual(paths.library_catalog, paths.root / "library.json")
            self.assertEqual(paths.execution_claims_database, paths.safety_root / EXECUTION_CLAIMS_FILENAME)
            self.assertEqual(
                paths.alternate_safety_roots,
                (
                    (state_home / PROPOSED_APPLICATION_DIRECTORY_NAME / "Safety").resolve(),
                    (state_home / PROPOSED_APPLICATION_DIRECTORY_NAME).resolve(),
                ),
            )

    def test_linux_xdg_fallbacks_preserve_state_and_data_split(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            paths = application_paths(home=home, environ={}, platform="linux", os_name="posix")

            self.assertEqual(paths.safety_root, (home / ".local" / "state" / LEGACY_APPLICATION_DIRECTORY_NAME).resolve())
            self.assertEqual(paths.root, (home / ".local" / "share" / LEGACY_APPLICATION_DIRECTORY_NAME).resolve())

    def test_resource_path_uses_bundle_root_independent_of_cwd_and_rejects_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle_root = Path(temporary) / "Bundle"
            unrelated_cwd = Path(temporary) / "日本語" / "working directory"
            unrelated_cwd.mkdir(parents=True)
            original_cwd = Path.cwd()
            try:
                os.chdir(unrelated_cwd)
                resolved = resource_path("assets", "notice.txt", bundle_root=bundle_root)
            finally:
                os.chdir(original_cwd)

            self.assertEqual(resolved, bundle_root / "assets" / "notice.txt")
            with self.assertRaisesRegex(ValueError, "inside the application bundle"):
                resource_path("..", "outside.txt", bundle_root=bundle_root)
            with self.assertRaisesRegex(ValueError, "inside the application bundle"):
                resource_path(str(Path(temporary).resolve()), bundle_root=bundle_root)

    def test_frozen_resource_path_uses_meipass(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle_root = Path(temporary) / "_MEI12345"
            with patch("infocarry.app_paths.sys.frozen", True, create=True), patch(
                "infocarry.app_paths.sys._MEIPASS", str(bundle_root), create=True
            ):
                self.assertEqual(resource_path("license.txt"), bundle_root / "license.txt")


if __name__ == "__main__":
    unittest.main()
