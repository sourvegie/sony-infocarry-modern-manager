"""Read-only standard USB access for the Sony InfoCarry."""

from dataclasses import dataclass
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


def find_devices() -> List[Any]:
    try:
        return list(
            usb.core.find(
                find_all=True,
                idVendor=SONY_VENDOR_ID,
                idProduct=INFOCARRY_PRODUCT_ID,
            )
        )
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
