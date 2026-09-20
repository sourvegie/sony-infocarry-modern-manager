import sys
import types
import unittest
from unittest.mock import patch

from infocarry.usb_access import DeviceAccessError, find_devices, find_sony_devices


class MacOSUsbBackendTests(unittest.TestCase):
    def test_macos_uses_packaged_libusb_backend_when_available(self):
        backend = object()
        package = types.SimpleNamespace(find_library=lambda _name: "/bundled/libusb.dylib")
        with patch("infocarry.usb_access.sys.platform", "darwin"), patch.dict(
            sys.modules, {"libusb_package": package}
        ), patch("usb.backend.libusb1.get_backend", return_value=backend) as get_backend, patch(
            "usb.core.find", return_value=()
        ) as find:
            self.assertEqual(find_devices(), [])
            self.assertEqual(find_sony_devices(), [])

        self.assertEqual(get_backend.call_count, 2)
        for call in find.call_args_list:
            self.assertIs(call.kwargs["backend"], backend)
            self.assertEqual(call.kwargs["idVendor"], 0x054C)
        self.assertEqual(find.call_args_list[0].kwargs["idProduct"], 0x001E)
        self.assertNotIn("idProduct", find.call_args_list[1].kwargs)

    def test_packaged_libusb_without_a_native_library_fails_before_enumeration(self):
        package = types.SimpleNamespace(find_library=lambda _name: None)
        with patch("infocarry.usb_access.sys.platform", "darwin"), patch.dict(
            sys.modules, {"libusb_package": package}
        ), patch("usb.backend.libusb1.get_backend", return_value=None), patch(
            "usb.core.find"
        ) as find:
            with self.assertRaisesRegex(DeviceAccessError, "could not be located"):
                find_sony_devices()
        find.assert_not_called()

    def test_source_development_can_use_pyusb_default_without_package(self):
        with patch("infocarry.usb_access.sys.platform", "darwin"), patch.dict(
            sys.modules, {"libusb_package": None}
        ), patch("usb.core.find", return_value=()) as find:
            self.assertEqual(find_devices(), [])
        self.assertNotIn("backend", find.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
