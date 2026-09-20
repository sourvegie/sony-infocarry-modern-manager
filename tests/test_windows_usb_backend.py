import sys
import types
import unittest
from unittest.mock import patch

import usb.core

from infocarry.usb_access import DeviceAccessError, find_devices


class WindowsUsbBackendTests(unittest.TestCase):
    def test_windows_discovery_uses_packaged_backend(self):
        backend = object()
        package = types.SimpleNamespace(find_library=lambda _name: None)
        with patch("infocarry.usb_access.sys.platform", "win32"), patch.dict(
            sys.modules, {"libusb_package": package}
        ), patch(
            "usb.backend.libusb1.get_backend", return_value=backend
        ) as get_backend, patch(
            "usb.core.find", return_value=()
        ) as find:
            self.assertEqual(find_devices(), [])

        get_backend.assert_called_once_with(find_library=package.find_library)
        self.assertIs(find.call_args.kwargs["backend"], backend)
        self.assertTrue(find.call_args.kwargs["find_all"])
        self.assertEqual(find.call_args.kwargs["idVendor"], 0x054C)
        self.assertEqual(find.call_args.kwargs["idProduct"], 0x001E)

    def test_windows_missing_native_backend_fails_before_enumeration(self):
        package = types.SimpleNamespace(find_library=lambda _name: None)
        with patch("infocarry.usb_access.sys.platform", "win32"), patch.dict(
            sys.modules, {"libusb_package": package}
        ), patch("usb.backend.libusb1.get_backend", return_value=None), patch(
            "usb.core.find"
        ) as find:
            with self.assertRaisesRegex(DeviceAccessError, "could not be located"):
                find_devices()

        find.assert_not_called()

    def test_windows_missing_packaged_dependency_fails_closed(self):
        with patch("infocarry.usb_access.sys.platform", "win32"), patch.dict(
            sys.modules, {"libusb_package": None}
        ), patch("usb.core.find") as find:
            with self.assertRaisesRegex(DeviceAccessError, "requires the packaged"):
                find_devices()

        find.assert_not_called()

    def test_linux_keeps_pyusb_platform_default(self):
        with patch("infocarry.usb_access.sys.platform", "linux"), patch(
            "infocarry.usb_access._windows_libusb_backend"
        ) as windows_backend, patch("usb.core.find", return_value=()) as find:
            self.assertEqual(find_devices(), [])

        windows_backend.assert_not_called()
        self.assertNotIn("backend", find.call_args.kwargs)

    def test_pyusb_enumeration_errors_remain_read_only_access_errors(self):
        with patch("infocarry.usb_access.sys.platform", "darwin"), patch(
            "usb.core.find", side_effect=usb.core.USBError("no backend")
        ):
            with self.assertRaisesRegex(DeviceAccessError, "USB enumeration failed"):
                find_devices()


if __name__ == "__main__":
    unittest.main()
