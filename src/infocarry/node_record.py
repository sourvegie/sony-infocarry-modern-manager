"""Offline serializer for the legacy 64-byte metadata node prefix.

``VicTwo.dll`` function ``0x10001930`` transforms the first 64 bytes of an
in-memory node into the big-endian record layout also observed in read-only
backup blobs.  This module reproduces only that verified transformation and
has no USB or write-transport integration.
"""

from typing import Union


NODE_RECORD_LENGTH = 0x40
NODE_NAME_OFFSET = 0x18
NODE_NAME_STORAGE_LENGTH = 0x28

BytesLike = Union[bytes, bytearray, memoryview]


class NodeRecordError(ValueError):
    """Raised when an internal node prefix cannot be serialized safely."""


def _legacy_shift_jis_lead_byte(value: int) -> bool:
    """Match the two lead-byte ranges tested by the legacy serializer."""

    return 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xEF


def serialize_internal_node_prefix(internal_prefix: BytesLike) -> bytes:
    """Serialize one exact 64-byte in-memory node prefix.

    Bytes 0--3 are copied unchanged.  The five host-order dwords at offsets
    4--23 are emitted big-endian.  The 40-byte storage area at offset 24 is
    copied unchanged unless its last byte is a dangling legacy Shift-JIS lead
    byte; in that case only 39 bytes are copied and the zero-initialized final
    byte remains zero.
    """

    if not isinstance(internal_prefix, (bytes, bytearray, memoryview)):
        raise NodeRecordError("internal node prefix must be bytes-like")
    source = bytes(internal_prefix)
    if len(source) != NODE_RECORD_LENGTH:
        raise NodeRecordError(
            f"internal node prefix is {len(source)} bytes; expected {NODE_RECORD_LENGTH}"
        )

    result = bytearray(NODE_RECORD_LENGTH)
    result[0:4] = source[0:4]
    for offset in range(0x04, NODE_NAME_OFFSET, 4):
        value = int.from_bytes(source[offset : offset + 4], "little")
        result[offset : offset + 4] = value.to_bytes(4, "big")

    copy_length = NODE_NAME_STORAGE_LENGTH
    penultimate = source[NODE_RECORD_LENGTH - 2]
    final = source[NODE_RECORD_LENGTH - 1]
    if not _legacy_shift_jis_lead_byte(
        penultimate
    ) and _legacy_shift_jis_lead_byte(final):
        copy_length -= 1
    result[NODE_NAME_OFFSET : NODE_NAME_OFFSET + copy_length] = source[
        NODE_NAME_OFFSET : NODE_NAME_OFFSET + copy_length
    ]
    return bytes(result)


__all__ = [
    "NODE_NAME_OFFSET",
    "NODE_NAME_STORAGE_LENGTH",
    "NODE_RECORD_LENGTH",
    "NodeRecordError",
    "serialize_internal_node_prefix",
]
