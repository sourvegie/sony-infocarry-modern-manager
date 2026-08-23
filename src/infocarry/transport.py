"""Safe PyUSB session and read-only backend for the Sony InfoCarry."""

from dataclasses import dataclass
from typing import Any, Optional

import usb.core
import usb.util

from .constants import INFOCARRY_PRODUCT_ID, SONY_VENDOR_ID
from .descriptors import ConfigurationDescriptor, parse_descriptor_set
from .usb_access import (
    DeviceAccessError,
    find_one_device,
    read_active_alternate_setting,
    read_raw_descriptors,
)
from .protocol import ProtocolError


INFOCARRY_INTERFACE = 0
INFOCARRY_ALTERNATE_SETTING = 0


class UsbTransportError(DeviceAccessError, ProtocolError):
    """Raised when an otherwise valid protocol USB operation fails."""


@dataclass(frozen=True)
class TransportEndpoints:
    bulk_in: int
    bulk_out: int
    max_packet_size: int


def discover_transport_endpoints(
    configuration: ConfigurationDescriptor,
    *,
    interface_number: int = INFOCARRY_INTERFACE,
    alternate_setting: int = INFOCARRY_ALTERNATE_SETTING,
) -> TransportEndpoints:
    matches = [
        interface
        for interface in configuration.interfaces
        if interface.number == interface_number
        and interface.alternate_setting == alternate_setting
    ]
    if len(matches) != 1:
        raise DeviceAccessError(
            f"expected one interface {interface_number} alternate {alternate_setting}, "
            f"found {len(matches)}"
        )
    interface = matches[0]
    if (
        interface.interface_class,
        interface.interface_subclass,
        interface.interface_protocol,
    ) != (0xFF, 0x00, 0xFF):
        raise DeviceAccessError("InfoCarry interface identity does not match verified descriptors")
    bulk_in = [
        endpoint for endpoint in interface.endpoints
        if endpoint.transfer_type_name == "bulk" and endpoint.direction == "in"
    ]
    bulk_out = [
        endpoint for endpoint in interface.endpoints
        if endpoint.transfer_type_name == "bulk" and endpoint.direction == "out"
    ]
    if len(bulk_in) != 1 or len(bulk_out) != 1:
        raise DeviceAccessError(
            "verified alternate setting must contain exactly one bulk-IN and one bulk-OUT endpoint"
        )
    if bulk_in[0].max_packet_size != bulk_out[0].max_packet_size:
        raise DeviceAccessError("bulk endpoint maximum packet sizes do not match")
    return TransportEndpoints(
        bulk_in=bulk_in[0].address,
        bulk_out=bulk_out[0].address,
        max_packet_size=bulk_in[0].max_packet_size,
    )


class PyUsbReadOnlyBackend:
    """PyUSB adapter exposing no bulk-write operation."""

    def __init__(self, device: Any):
        self._device = device

    def control_out(
        self,
        request_type: int,
        request: int,
        value: int,
        index: int,
        data: bytes,
        timeout_ms: int,
    ) -> int:
        try:
            return int(
                self._device.ctrl_transfer(
                    request_type,
                    request,
                    value,
                    index,
                    data,
                    timeout=timeout_ms,
                )
            )
        except usb.core.USBError as exc:
            raise UsbTransportError(f"control OUT request 0x{request:02x} failed: {exc}") from exc

    def control_in(
        self,
        request_type: int,
        request: int,
        value: int,
        index: int,
        length: int,
        timeout_ms: int,
    ) -> bytes:
        try:
            return bytes(
                self._device.ctrl_transfer(
                    request_type,
                    request,
                    value,
                    index,
                    length,
                    timeout=timeout_ms,
                )
            )
        except usb.core.USBError as exc:
            raise UsbTransportError(f"control IN request 0x{request:02x} failed: {exc}") from exc

    def bulk_read(self, endpoint: int, length: int, timeout_ms: int) -> bytes:
        try:
            return bytes(self._device.read(endpoint, length, timeout=timeout_ms))
        except usb.core.USBError as exc:
            raise UsbTransportError(f"bulk read from endpoint 0x{endpoint:02x} failed: {exc}") from exc


class PyUsbWriteBackend(PyUsbReadOnlyBackend):
    """Opt-in PyUSB adapter exposing bulk-OUT for the guarded writer only.

    The normal :class:`InfoCarrySession` still creates
    :class:`PyUsbReadOnlyBackend`.  A future live-write caller must construct
    this adapter deliberately and pass it to ``AuthorizedWriteSender`` after
    obtaining a backup-bound write authorization.
    """

    def bulk_write(self, endpoint: int, data: bytes, timeout_ms: int) -> int:
        try:
            return int(self._device.write(endpoint, data, timeout=timeout_ms))
        except usb.core.USBError as exc:
            raise UsbTransportError(
                f"bulk write to endpoint 0x{endpoint:02x} failed: {exc}"
            ) from exc


class InfoCarrySession:
    """Claim and release the verified interface without sending an app command."""

    def __init__(self, device: Any, endpoints: TransportEndpoints):
        self.device = device
        self.endpoints = endpoints
        self.backend = PyUsbReadOnlyBackend(device)
        self._claimed = True
        self._closed = False

    @classmethod
    def open(cls, device: Optional[Any] = None, *, timeout_ms: int = 1000) -> "InfoCarrySession":
        selected = device if device is not None else find_one_device()
        if (
            getattr(selected, "idVendor", None),
            getattr(selected, "idProduct", None),
        ) != (SONY_VENDOR_ID, INFOCARRY_PRODUCT_ID):
            raise DeviceAccessError("refusing to open a device with an unsupported VID/PID")
        claimed = False
        try:
            raw_device, raw_configuration = read_raw_descriptors(selected, timeout_ms)
            descriptors = parse_descriptor_set(raw_device, raw_configuration)
            if (
                descriptors.device.vendor_id,
                descriptors.device.product_id,
            ) != (SONY_VENDOR_ID, INFOCARRY_PRODUCT_ID):
                raise DeviceAccessError("device descriptor VID/PID changed during open")
            endpoints = discover_transport_endpoints(descriptors.configuration)

            try:
                active_configuration = selected.get_active_configuration()
                active_value = active_configuration.bConfigurationValue
            except (usb.core.USBError, ValueError, AttributeError):
                active_value = None
            if active_value != descriptors.configuration.configuration_value:
                selected.set_configuration(descriptors.configuration.configuration_value)

            usb.util.claim_interface(selected, INFOCARRY_INTERFACE)
            claimed = True
            active_alt = read_active_alternate_setting(
                selected, INFOCARRY_INTERFACE, timeout_ms
            )
            if active_alt != INFOCARRY_ALTERNATE_SETTING:
                selected.set_interface_altsetting(
                    interface=INFOCARRY_INTERFACE,
                    alternate_setting=INFOCARRY_ALTERNATE_SETTING,
                )
                active_alt = read_active_alternate_setting(
                    selected, INFOCARRY_INTERFACE, timeout_ms
                )
            if active_alt != INFOCARRY_ALTERNATE_SETTING:
                raise DeviceAccessError(
                    f"could not verify alternate setting {INFOCARRY_ALTERNATE_SETTING}"
                )
            return cls(selected, endpoints)
        except Exception as exc:
            if claimed:
                try:
                    usb.util.release_interface(selected, INFOCARRY_INTERFACE)
                except usb.core.USBError:
                    pass
            try:
                usb.util.dispose_resources(selected)
            except usb.core.USBError:
                pass
            if isinstance(exc, usb.core.USBError):
                raise DeviceAccessError(f"failed to open InfoCarry interface: {exc}") from exc
            raise

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._claimed:
                usb.util.release_interface(self.device, INFOCARRY_INTERFACE)
                self._claimed = False
        except usb.core.USBError as exc:
            raise DeviceAccessError(f"failed to release InfoCarry interface: {exc}") from exc
        finally:
            usb.util.dispose_resources(self.device)

    def __enter__(self) -> "InfoCarrySession":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            self.close()
        except DeviceAccessError:
            if exc is None:
                raise
