"""Read-only standard USB access for the Sony InfoCarry."""

from dataclasses import dataclass
import sys
from typing import Any, List, Optional, Tuple

import usb.core

from .constants import (
    INFOCARRY_PRODUCT_ID,
    SONY_VENDOR_ID,
    USB_DESCRIPTOR_CONFIGURATION,
    USB_DESCRIPTOR_DEVICE,
    USB_REQUEST_GET_DESCRIPTOR,
    USB_REQUEST_GET_INTERFACE,
    USB_REQUEST_TYPE_DEVICE_IN,
    USB_REQUEST_TYPE_INTERFACE_IN,
)


class DeviceAccessError(RuntimeError):
    """Raised when the supported device is missing or cannot be read safely."""


@dataclass(frozen=True)
class DetectedDevice:
    bus: Optional[int]
    address: Optional[int]
    vendor_id: int
    product_id: int


def _packaged_libusb_backend(*, required: bool) -> Any:
    """Load a bundled libusb backend when the frozen app supplies it.

    PyUSB is a Python wrapper and does not itself supply the native libusb
    library. Packaged Windows and macOS apps include ``libusb-package``; pass
    its explicit locator so discovery does not depend on PATH, Homebrew, or a
    machine-wide native-library search path. Source installs may use PyUSB's
    established macOS default backend when the package is absent. This selects
    only the existing read-only access backend and does not install or replace
    a USB device driver.
    """

    try:
        import libusb_package
        import usb.backend.libusb1
    except ImportError as exc:
        if not required:
            return None
        raise DeviceAccessError("USB access requires the packaged libusb 1.0 runtime") from exc
    try:
        backend = usb.backend.libusb1.get_backend(
            find_library=libusb_package.find_library
        )
    except (OSError, usb.core.USBError) as exc:
        raise DeviceAccessError(
            f"the packaged libusb 1.0 runtime could not be loaded: {exc}"
        ) from exc
    if backend is None:
        raise DeviceAccessError(
            "the packaged libusb 1.0 runtime could not be located"
        )
    return backend


def _windows_libusb_backend() -> Any:
    """Compatibility helper for the pinned Windows package backend."""

    return _packaged_libusb_backend(required=True)


def _platform_backend() -> Any:
    if sys.platform == "win32":
        return _packaged_libusb_backend(required=True)
    if sys.platform == "darwin":
        return _packaged_libusb_backend(required=False)
    return None


def find_devices() -> List[Any]:
    """Find the exact reviewed VNW-V15 VID/PID with the platform backend."""

    backend = _platform_backend()
    try:
        arguments = {
            "find_all": True,
            "idVendor": SONY_VENDOR_ID,
            "idProduct": INFOCARRY_PRODUCT_ID,
        }
        if backend is not None:
            arguments["backend"] = backend
        return list(usb.core.find(**arguments))
    except usb.core.USBError as exc:
        raise DeviceAccessError(f"USB enumeration failed: {exc}") from exc


def find_sony_devices() -> List[Any]:
    """Enumerate Sony VID devices for unsupported-device home-state UX.

    This is standard USB identity discovery only. Callers must require the
    reviewed VNW-V15 VID/PID before opening a session or querying 0x0019.
    """

    arguments = {"find_all": True, "idVendor": SONY_VENDOR_ID}
    backend = _platform_backend()
    if backend is not None:
        arguments["backend"] = backend
    try:
        return list(usb.core.find(**arguments))
    except usb.core.USBError as exc:
        raise DeviceAccessError(f"USB enumeration failed: {exc}") from exc


def find_one_device() -> Any:
    devices = find_devices()
    if not devices:
        raise DeviceAccessError(
            f"Sony InfoCarry {SONY_VENDOR_ID:04x}:{INFOCARRY_PRODUCT_ID:04x} was not found"
        )
    if len(devices) > 1:
        raise DeviceAccessError(
            f"found {len(devices)} matching InfoCarry devices; connect only one for now"
        )
    return devices[0]


def describe_device(device: Any) -> DetectedDevice:
    return DetectedDevice(
        bus=getattr(device, "bus", None),
        address=getattr(device, "address", None),
        vendor_id=device.idVendor,
        product_id=device.idProduct,
    )


def _read_descriptor(device: Any, descriptor_type: int, length: int, timeout_ms: int) -> bytes:
    try:
        return bytes(
            device.ctrl_transfer(
                USB_REQUEST_TYPE_DEVICE_IN,
                USB_REQUEST_GET_DESCRIPTOR,
                descriptor_type << 8,
                0,
                length,
                timeout=timeout_ms,
            )
        )
    except usb.core.USBError as exc:
        raise DeviceAccessError(f"standard descriptor read failed: {exc}") from exc


def read_raw_descriptors(device: Any, timeout_ms: int = 1000) -> Tuple[bytes, bytes]:
    """Read only the standard device and configuration descriptors."""

    device_descriptor = _read_descriptor(
        device, USB_DESCRIPTOR_DEVICE, length=18, timeout_ms=timeout_ms
    )
    configuration_header = _read_descriptor(
        device, USB_DESCRIPTOR_CONFIGURATION, length=9, timeout_ms=timeout_ms
    )
    if len(configuration_header) != 9:
        raise DeviceAccessError(
            f"configuration header read returned {len(configuration_header)} bytes"
        )
    total_length = int.from_bytes(configuration_header[2:4], "little")
    if total_length < 9 or total_length > 4096:
        raise DeviceAccessError(f"refusing unreasonable configuration length {total_length}")
    configuration_descriptor = _read_descriptor(
        device,
        USB_DESCRIPTOR_CONFIGURATION,
        length=total_length,
        timeout_ms=timeout_ms,
    )
    return device_descriptor, configuration_descriptor


def read_active_alternate_setting(
    device: Any, interface_number: int = 0, timeout_ms: int = 1000
) -> Optional[int]:
    """Read the current interface alternate setting using USB GET_INTERFACE."""

    try:
        result = bytes(
            device.ctrl_transfer(
                USB_REQUEST_TYPE_INTERFACE_IN,
                USB_REQUEST_GET_INTERFACE,
                0,
                interface_number,
                1,
                timeout=timeout_ms,
            )
        )
    except usb.core.USBError:
        return None
    return result[0] if len(result) == 1 else None
