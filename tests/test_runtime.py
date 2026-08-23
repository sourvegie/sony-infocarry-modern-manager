import unittest
from unittest.mock import patch

import tkinter

from infocarry.runtime import DesktopRuntimeError, check_desktop_runtime


class DesktopRuntimeTests(unittest.TestCase):
    def test_project_runtime_is_supported(self):
        with patch("infocarry.runtime.sys.version_info", (3, 12, 13)), patch.object(
            tkinter, "TkVersion", "9.0"
        ):
            runtime = check_desktop_runtime()
        self.assertEqual(runtime.python_version, (3, 12, 13))
        self.assertEqual(runtime.tk_version, (9, 0))
        self.assertIn("Python 3.12.13", runtime.description)
        self.assertIn("Tcl/Tk 9.0", runtime.description)

    def test_old_python_has_clear_recovery_message(self):
        with patch("infocarry.runtime.sys.version_info", (3, 9, 6)):
            with self.assertRaisesRegex(DesktopRuntimeError, "Python 3.12/Tk 9"):
                check_desktop_runtime()

    def test_old_tk_has_clear_recovery_message(self):
        with patch("infocarry.runtime.sys.version_info", (3, 12, 13)), patch.object(
            tkinter, "TkVersion", "8.5"
        ):
            with self.assertRaisesRegex(DesktopRuntimeError, "Tcl/Tk 9.0"):
                check_desktop_runtime()


if __name__ == "__main__":
    unittest.main()
