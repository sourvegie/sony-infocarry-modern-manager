"""Strict parser for standard USB descriptors.

This module has no USB dependency and is tested using captured descriptor bytes.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .constants import (
    USB_DESCRIPTOR_CONFIGURATION,
    USB_DESCRIPTOR_DEVICE,
    USB_DESCRIPTOR_ENDPOINT,
    USB_DESCRIPTOR_INTERFACE,
    USB_TRANSFER_TYPE_NAMES,
)


class DescriptorError(ValueError):
    """Raised when a USB descriptor is truncated or internally inconsistent."""


def _u16le(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


@dataclass(frozen=True)
class DeviceDescriptor:
    usb_version_bcd: int
    device_class: int
    device_subclass: int
    device_protocol: int
    endpoint_zero_max_packet_size: int
    vendor_id: int
    product_id: int
    device_version_bcd: int
    manufacturer_string_index: int
    product_string_index: int
    serial_string_index: int
    configuration_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EndpointDescriptor:
    address: int
    direction: str
    transfer_type: int
    transfer_type_name: str
    max_packet_size: int
    interval: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InterfaceDescriptor:
    number: int
    alternate_setting: int
    endpoint_count: int
    interface_class: int
    interface_subclass: int
    interface_protocol: int
    string_index: int
    endpoints: List[EndpointDescriptor] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConfigurationDescriptor:
    total_length: int
    interface_count: int
    configuration_value: int
    string_index: int
    attributes: int
    max_power_ma: int
    interfaces: List[InterfaceDescriptor] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DescriptorSet:
    device: DeviceDescriptor
    configuration: ConfigurationDescriptor
    active_alternate_setting: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_device_descriptor(data: bytes) -> DeviceDescriptor:
    if len(data) != 18:
        raise DescriptorError(f"device descriptor must be exactly 18 bytes, got {len(data)}")
    if data[0] != 18 or data[1] != USB_DESCRIPTOR_DEVICE:
        raise DescriptorError("invalid device descriptor header")
    return DeviceDescriptor(
        usb_version_bcd=_u16le(data, 2),
        device_class=data[4],
        device_subclass=data[5],
        device_protocol=data[6],
        endpoint_zero_max_packet_size=data[7],
        vendor_id=_u16le(data, 8),
        product_id=_u16le(data, 10),
        device_version_bcd=_u16le(data, 12),
        manufacturer_string_index=data[14],
        product_string_index=data[15],
        serial_string_index=data[16],
        configuration_count=data[17],
    )


def parse_configuration_descriptor(data: bytes) -> ConfigurationDescriptor:
    if len(data) < 9:
        raise DescriptorError("configuration descriptor is shorter than its 9-byte header")
    if data[0] != 9 or data[1] != USB_DESCRIPTOR_CONFIGURATION:
        raise DescriptorError("invalid configuration descriptor header")
    total_length = _u16le(data, 2)
    if total_length != len(data):
        raise DescriptorError(
            f"configuration total length is {total_length}, received {len(data)} bytes"
        )

    configuration = ConfigurationDescriptor(
        total_length=total_length,
        interface_count=data[4],
        configuration_value=data[5],
        string_index=data[6],
        attributes=data[7],
        max_power_ma=data[8] * 2,
    )
    current_interface: Optional[InterfaceDescriptor] = None
    offset = data[0]
    while offset < len(data):
        if offset + 2 > len(data):
            raise DescriptorError(f"truncated descriptor header at offset {offset}")
        length = data[offset]
        descriptor_type = data[offset + 1]
        if length < 2:
            raise DescriptorError(f"invalid descriptor length {length} at offset {offset}")
        end = offset + length
        if end > len(data):
            raise DescriptorError(f"descriptor at offset {offset} extends beyond input")
        descriptor = data[offset:end]

        if descriptor_type == USB_DESCRIPTOR_INTERFACE:
            if length < 9:
                raise DescriptorError(f"short interface descriptor at offset {offset}")
            current_interface = InterfaceDescriptor(
                number=descriptor[2],
                alternate_setting=descriptor[3],
                endpoint_count=descriptor[4],
                interface_class=descriptor[5],
                interface_subclass=descriptor[6],
                interface_protocol=descriptor[7],
                string_index=descriptor[8],
            )
            configuration.interfaces.append(current_interface)
        elif descriptor_type == USB_DESCRIPTOR_ENDPOINT:
            if length < 7:
                raise DescriptorError(f"short endpoint descriptor at offset {offset}")
            if current_interface is None:
                raise DescriptorError(f"endpoint descriptor before interface at offset {offset}")
            transfer_type = descriptor[3] & 0x03
            endpoint = EndpointDescriptor(
                address=descriptor[2],
                direction="in" if descriptor[2] & 0x80 else "out",
                transfer_type=transfer_type,
                transfer_type_name=USB_TRANSFER_TYPE_NAMES[transfer_type],
                max_packet_size=_u16le(descriptor, 4) & 0x07FF,
                interval=descriptor[6],
            )
            current_interface.endpoints.append(endpoint)

        offset = end

    for interface in configuration.interfaces:
        if len(interface.endpoints) != interface.endpoint_count:
            raise DescriptorError(
                f"interface {interface.number} alt {interface.alternate_setting} declares "
                f"{interface.endpoint_count} endpoints but contains {len(interface.endpoints)}"
            )
    return configuration


def parse_descriptor_set(
    device_data: bytes,
    configuration_data: bytes,
    active_alternate_setting: Optional[int] = None,
) -> DescriptorSet:
    return DescriptorSet(
        device=parse_device_descriptor(device_data),
        configuration=parse_configuration_descriptor(configuration_data),
        active_alternate_setting=active_alternate_setting,
    )
