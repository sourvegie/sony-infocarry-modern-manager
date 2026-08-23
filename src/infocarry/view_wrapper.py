"""Lossless parsing of the observed 32-byte text-view payload prefix.

The field names in this module deliberately refer to the legacy internal
object offsets recovered from ``VicTwo.dll``.  They are not user-facing
semantic names: the captured device state proves that these bytes are mutable
view state, but does not yet prove whether an individual value is a cursor,
scroll position, renderer flag, or another implementation detail.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Union


TEXT_VIEW_WRAPPER_SIZE = 0x20
LEGACY_PREFIX_MIN_SIZE = 0x10
LEGACY_INTERNAL_REQUIRED_SIZE = 0x51

BytesLike = Union[bytes, bytearray, memoryview]


class ViewWrapperError(ValueError):
    """Raised when a text-view wrapper is not exactly representable."""


def _be16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "big")


def _be32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "big")


def calculate_text_view_checksum(data: bytes) -> int:
    """Return the legacy checksum word for a 32-byte wrapper.

    ``VicTwo.dll`` sums the seven big-endian words beginning at offset 4 and
    stores the two's-complement of that sum minus the number of 4-byte words
    in the wrapper (eight).  This is equivalent to the first word required for
    the complete wrapper sum to be ``0xfffffff8``.
    """

    if len(data) != TEXT_VIEW_WRAPPER_SIZE:
        raise ViewWrapperError(
            f"text-view wrapper must be {TEXT_VIEW_WRAPPER_SIZE} bytes, got {len(data)}"
        )
    total = sum(
        _be32(data, offset)
        for offset in range(4, TEXT_VIEW_WRAPPER_SIZE, 4)
    )
    return (-total - (TEXT_VIEW_WRAPPER_SIZE // 4)) & 0xFFFFFFFF


def serialize_legacy_prefix(
    internal_object: BytesLike, prefix_length: int
) -> bytes:
    """Serialize the fixed prefix emitted by legacy helper ``0x100042f0``.

    The helper is used for 16/32-byte view prefixes and as the fixed-record
    contribution inside the model-range append worker. It fills the requested
    prefix with ``0xff``, copies the raw internal fields at offsets ``+0x50``,
    ``+0x44``, ``+0x46``, ``+0x48`` and ``+0x4c`` (the latter four only when
    the flag's low bit is clear), then stores a big-endian checksum word at
    offset zero. This covers the verified prefix boundary only; it does not
    serialize following variable text/data or infer the model-node grammar.
    """

    if not isinstance(internal_object, (bytes, bytearray, memoryview)):
        raise ViewWrapperError("internal object must be bytes-like")
    source = bytes(internal_object)
    if len(source) < LEGACY_INTERNAL_REQUIRED_SIZE:
        raise ViewWrapperError(
            f"internal object must contain at least {LEGACY_INTERNAL_REQUIRED_SIZE:#x} bytes"
        )
    if (
        isinstance(prefix_length, bool)
        or not isinstance(prefix_length, int)
        or prefix_length < LEGACY_PREFIX_MIN_SIZE
        or prefix_length % 4
    ):
        raise ViewWrapperError(
            "prefix_length must be a positive multiple of four of at least 0x10"
        )

    result = bytearray(b"\xff" * prefix_length)
    result[4] = source[0x50]
    if not (source[0x50] & 0x01):
        result[5] = source[0x44]
        result[6:8] = source[0x46:0x48][::-1]
        result[8:12] = source[0x48:0x4C][::-1]
        result[12:16] = source[0x4C:0x50][::-1]
    total = sum(
        int.from_bytes(result[offset : offset + 4], "big")
        for offset in range(4, prefix_length, 4)
    )
    checksum = (-total - (prefix_length // 4)) & 0xFFFFFFFF
    result[0:4] = checksum.to_bytes(4, "big")
    return bytes(result)


@dataclass(frozen=True)
class TextViewWrapper:
    """Raw fields exposed by the legacy 32-byte text prefix serializer."""

    raw_hex: str
    checksum_be32: int
    state_byte_internal_50: int
    field_44_internal_byte: int
    field_46_internal_be16: int
    field_48_internal_be32: int
    field_4c_internal_be32: int
    tail_hex: str
    checksum_valid: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_text_view_wrapper(data: bytes) -> TextViewWrapper:
    """Parse a captured 32-byte text prefix without interpreting its meaning."""

    if len(data) != TEXT_VIEW_WRAPPER_SIZE:
        raise ViewWrapperError(
            f"text-view wrapper must be {TEXT_VIEW_WRAPPER_SIZE} bytes, got {len(data)}"
        )
    stored = _be32(data, 0)
    return TextViewWrapper(
        raw_hex=data.hex(),
        checksum_be32=stored,
        state_byte_internal_50=data[4],
        field_44_internal_byte=data[5],
        field_46_internal_be16=_be16(data, 6),
        field_48_internal_be32=_be32(data, 8),
        field_4c_internal_be32=_be32(data, 12),
        tail_hex=data[16:].hex(),
        checksum_valid=stored == calculate_text_view_checksum(data),
    )
