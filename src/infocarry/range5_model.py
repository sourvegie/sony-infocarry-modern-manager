"""Offline byte-level serializer and exact recovery for range 5.

The legacy worker initializes a 0x40-byte source object, passes it to
``VicTwo.dll`` helper ``0x10001550``, and sends the helper's 0x40-byte
destination as range 5 of command ``0x101b``.  This module reproduces only
that verified transformation.  It does not assign semantic names to the
fields, build ranges 4 or 6--8, open USB, or transmit a candidate.
"""

from dataclasses import dataclass
from typing import Union


RANGE5_LENGTH = 0x40


class Range5SerializationError(ValueError):
    """Raised when a range-5 source object has the wrong shape."""


BytesLike = Union[bytes, bytearray, memoryview]


@dataclass(frozen=True)
class Range5SourceRecovery:
    """A source-object candidate recovered from one captured wire block.

    ``unknown_offsets`` is retained so future helper revisions can report
    omitted source bytes explicitly. For the currently recovered helper the
    map is complete, so it is empty and ``round_trip`` is exact.
    """

    source: bytes
    unknown_offsets: tuple[int, ...]
    round_trip: bool


def _swap_u32(value: bytes) -> bytes:
    """Return the legacy helper's little-endian-memory to wire-byte swap."""

    return value[::-1]


def serialize_range5_model(source: BytesLike) -> bytes:
    """Serialize one verified 0x40-byte range-5 source object.

    The source is interpreted exactly as the helper does:

    * offsets ``0x00`` and ``0x04`` are copied as raw dwords;
    * the byte at ``0x08`` and bytes ``0x09``--``0x0d`` are copied;
    * the words at ``0x0e`` and ``0x10`` are emitted big-endian;
    * the word at ``0x12`` is copied as raw bytes;
    * dwords ``0x14`` through ``0x38`` are emitted big-endian at the same
      offsets; and
    * the final dword at ``0x3c`` is copied as raw bytes to output ``0x3c``.

    The destination is zero-filled first, then the helper writes the final
    source dword at offset ``0x3c``; all 64 output bytes are therefore
    represented by the source object.
    """

    if not isinstance(source, (bytes, bytearray, memoryview)):
        raise Range5SerializationError("range-5 source must be bytes-like")
    raw = bytes(source)
    if len(raw) != RANGE5_LENGTH:
        raise Range5SerializationError(
            f"range-5 source must be exactly {RANGE5_LENGTH} bytes"
        )

    result = bytearray(RANGE5_LENGTH)
    result[0:4] = raw[0:4]
    result[4:8] = raw[4:8]
    result[8] = raw[8]
    result[9:13] = raw[9:13]
    result[0x0D] = raw[0x0D]

    # These are the helper's packed word stores at destination 0x0e--0x13.
    result[0x0E:0x10] = raw[0x0E:0x10][::-1]
    result[0x10:0x12] = raw[0x10:0x12][::-1]
    result[0x12:0x14] = raw[0x12:0x14]

    for source_offset in range(0x14, 0x3C, 4):
        result[source_offset : source_offset + 4] = _swap_u32(
            raw[source_offset : source_offset + 4]
        )

    result[0x3C:0x40] = raw[0x3C:0x40]
    return bytes(result)


def recover_range5_source(wire: BytesLike) -> Range5SourceRecovery:
    """Recover a source-object candidate from a captured range-5 block.

    The byte-level map is complete for the fixed 64-byte helper: every source
    byte is either copied or transformed into a corresponding output location.
    The function rejects a wire block whose bytes could not have come from the
    recovered helper.
    """

    if not isinstance(wire, (bytes, bytearray, memoryview)):
        raise Range5SerializationError("range-5 wire block must be bytes-like")
    raw = bytes(wire)
    if len(raw) != RANGE5_LENGTH:
        raise Range5SerializationError(
            f"range-5 wire block must be exactly {RANGE5_LENGTH} bytes"
        )
    source = bytearray(RANGE5_LENGTH)
    source[0:4] = raw[0:4]
    source[4:8] = raw[4:8]
    source[8] = raw[8]
    source[9:13] = raw[9:13]
    source[0x0D] = raw[0x0D]
    source[0x0E:0x10] = raw[0x0E:0x10][::-1]
    source[0x10:0x12] = raw[0x10:0x12][::-1]
    source[0x12:0x14] = raw[0x12:0x14]
    for source_offset in range(0x14, 0x3C, 4):
        source[source_offset : source_offset + 4] = raw[
            source_offset : source_offset + 4
        ][::-1]
    source[0x3C:0x40] = raw[0x3C:0x40]

    candidate = bytes(source)
    if serialize_range5_model(candidate) != raw:
        raise Range5SerializationError("wire block is not representable by the recovered helper")
    return Range5SourceRecovery(
        source=candidate,
        unknown_offsets=(),
        round_trip=True,
    )


__all__ = [
    "RANGE5_LENGTH",
    "Range5SerializationError",
    "Range5SourceRecovery",
    "recover_range5_source",
    "serialize_range5_model",
]
