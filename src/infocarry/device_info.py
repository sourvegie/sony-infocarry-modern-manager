"""Command-specific, read-only InfoCarry information queries."""

from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Optional

from .protocol import ReadOnlyReceiver, TransferLengthError
from .transport import InfoCarrySession


COMMAND_CONFIGURATION_INFO = 0x0018
COMMAND_HARDWARE_INFO = 0x0019
INFO_RESPONSE_LENGTH = 64


@dataclass(frozen=True)
class RawInfoResponse:
    command: int
    kind: str
    data: bytes


@dataclass(frozen=True)
class ConfigurationInfo:
    leading_value: int
    settings_hex: str
    reserved_hex: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HardwareInfo:
    display_width_pixels: int
    display_height_pixels: int
    field_04_be16: int
    field_06_be16: int
    field_08_be32: int
    field_0c_be16: int
    field_0e_be16: int
    field_10_be32: int
    field_14_be32: int
    reserved_hex: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _require_info_length(data: bytes) -> None:
    if len(data) != INFO_RESPONSE_LENGTH:
        raise TransferLengthError(
            f"information response is {len(data)} bytes; expected {INFO_RESPONSE_LENGTH}"
        )


def parse_configuration_info(data: bytes) -> ConfigurationInfo:
    """Preserve the model-specific settings without assigning unknown names."""

    _require_info_length(data)
    # VicTwo consumes bytes 1..11 for the VNW model variants. Byte 0 is kept
    # separately because its exact semantic name is not yet verified.
    return ConfigurationInfo(
        leading_value=data[0],
        settings_hex=data[1:12].hex(" "),
        reserved_hex=data[12:].hex(" "),
    )


def parse_hardware_info(data: bytes) -> HardwareInfo:
    """Decode verified big-endian numeric fields and retain unknown names."""

    _require_info_length(data)
    be16 = lambda offset: int.from_bytes(data[offset : offset + 2], "big")
    be32 = lambda offset: int.from_bytes(data[offset : offset + 4], "big")
    return HardwareInfo(
        display_width_pixels=be16(0x00),
        display_height_pixels=be16(0x02),
        field_04_be16=be16(0x04),
        field_06_be16=be16(0x06),
        field_08_be32=be32(0x08),
        field_0c_be16=be16(0x0C),
        field_0e_be16=be16(0x0E),
        field_10_be32=be32(0x10),
        field_14_be32=be32(0x14),
        reserved_hex=data[0x18:].hex(" "),
    )


def decode_info_response(response: RawInfoResponse) -> Dict[str, Any]:
    if response.command == COMMAND_CONFIGURATION_INFO:
        return parse_configuration_info(response.data).to_dict()
    if response.command == COMMAND_HARDWARE_INFO:
        return parse_hardware_info(response.data).to_dict()
    raise ValueError(f"no information parser for command 0x{response.command:04x}")


class DeviceInfoClient:
    """Expose only the two statically verified information commands."""

    def __init__(self, session: InfoCarrySession):
        self._receiver = ReadOnlyReceiver(
            session.backend,
            session.endpoints.bulk_in,
            allowed_commands=frozenset(
                {COMMAND_CONFIGURATION_INFO, COMMAND_HARDWARE_INFO}
            ),
        )

    def read_configuration(
        self, *, cancelled: Optional[Callable[[], bool]] = None
    ) -> RawInfoResponse:
        return self._read_exact(
            COMMAND_CONFIGURATION_INFO, "configuration", cancelled
        )

    def read_hardware(
        self, *, cancelled: Optional[Callable[[], bool]] = None
    ) -> RawInfoResponse:
        return self._read_exact(COMMAND_HARDWARE_INFO, "hardware", cancelled)

    def _read_exact(
        self,
        command: int,
        kind: str,
        cancelled: Optional[Callable[[], bool]],
    ) -> RawInfoResponse:
        data = self._receiver.receive(
            command, INFO_RESPONSE_LENGTH, cancelled=cancelled
        )
        _require_info_length(data)
        return RawInfoResponse(command=command, kind=kind, data=data)
