import unittest
from pathlib import Path


class PackagedManagerAddControlTests(unittest.TestCase):
    def test_macos_and_windows_bootstraps_smoke_the_host_only_add_path(self):
        scripts = Path(__file__).parents[1] / "scripts"
        requirements = (
            '== "+ Add"',
            'add_menu.invoke(0)',
            'add_menu.invoke(1)',
            '"Add Files…", "Add Folder…"',
            '"nested_folder_imported": True',
            '"source_files_unchanged": True',
            '"add_under_lock_and_unavailable_runtime"',
            '"runtime_provider_available": False',
            '"operation_binding_present": False',
            'locked_store.record_indeterminate(',
            '"write_lock_unchanged": True',
            '"claims_created": 0',
            '"sender_markers_created": 0',
            'def forbid_device_enumeration(',
            'def forbid_sender(',
        )
        for name in ("macos_manager_entry.py", "windows_manager_entry.py"):
            with self.subTest(entrypoint=name):
                source = (scripts / name).read_text(encoding="utf-8")
                for required in requirements:
                    self.assertIn(required, source)


if __name__ == "__main__":
    unittest.main()
