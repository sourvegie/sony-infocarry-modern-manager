"""Read-only parsing helpers for native SnoopyPro ``.usblog`` captures.

The native SnoopyPro format is not a public InfoCarry protocol format.  This
module therefore implements only the record pattern verified in the preserved
Phase 8 captures: a host-to-device bulk payload marker followed by a matching
completion marker, and the ordinary eight-range ``0x101b`` transaction layout
observed in those captures.  It never opens USB, replays a trace, or writes a
capture file.

Offsets returned by this module are offsets in the original native file.  A
``Usblog101bCapture`` contains copied payload bytes so callers can hash and
compare ranges without retaining a mutable buffer or touching the source file.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct


MARKER = b"\x48\x00\x09\x00"
_COMMAND_RECORD_PREFIX = b"\x06\x00\x00\x00\x01\x00"
_COMMAND = 0x101B
# The native payload/completion records use 16-bit fields at +0x14 and
# +0x18.  The enclosing 0x101b command has a separate 32-bit length.
_MAX_PAYLOAD_LENGTH = 0xFFFF
_RANGE3_FILL = 0xFF
_RANGE3_STAGING_LENGTH = 8
_RANGE3_TOTAL_LENGTH = 0x10000 - 0x100 - 0x40


class UsblogParseError(ValueError):
    """Raised when a native capture does not match the verified layout."""


@dataclass(frozen=True)
class BulkPayloadRecord:
    """One validated native payload record and its completion record."""

    marker_offset: int
    payload_offset: int
    completion_offset: int
    length: int
    flags: int
    payload: bytes


@dataclass(frozen=True)
class Usblog101bCapture:
    """The verified ordinary-send portion of one native ``0x101b`` trace."""

    record_offset: int
    command_offset: int
    declared_length: int
    records: tuple[BulkPayloadRecord, ...]
    ranges: tuple[bytes, ...]

    @property
    def range3_n(self) -> int:
        """Return the big-endian ``N`` staging field from range 3."""

        return struct.unpack(">I", self.ranges[2][:4])[0]

    @property
    def range3_m(self) -> int:
        """Return the big-endian ``M`` staging field from range 3."""

        return struct.unpack(">I", self.ranges[2][4:8])[0]

    @property
    def range_lengths(self) -> tuple[int, ...]:
        """Return the eight recovered range lengths in wire order."""

        return tuple(len(item) for item in self.ranges)


def _coerce_bytes(data: bytes | bytearray | memoryview) -> bytes:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("data must be bytes-like")
    return bytes(data)


def find_101b_headers(data: bytes | bytearray | memoryview) -> tuple[int, ...]:
    """Return record-prefix offsets for visible command ``0x101b`` headers.

    The six bytes at each returned offset are the native record prefix
    ``06 00 00 00 01 00``.  The command word starts six bytes later.  This is
    deliberately a byte-pattern search, not a generic SnoopyPro decoder; the
    caller should still validate each result with :func:`extract_101b`.
    """

    raw = _coerce_bytes(data)
    offsets: list[int] = []
    cursor = 0
    while True:
        offset = raw.find(_COMMAND_RECORD_PREFIX, cursor)
        if offset < 0:
            return tuple(offsets)
        command_offset = offset + len(_COMMAND_RECORD_PREFIX)
        if command_offset + 6 <= len(raw):
            command, declared = struct.unpack_from("<HI", raw, command_offset)
            if command == _COMMAND and declared > 0:
                offsets.append(offset)
        cursor = offset + 1


def _parse_payload_at(raw: bytes, marker_offset: int, remaining: int) -> BulkPayloadRecord | None:
    """Validate a candidate payload/completion pair at ``marker_offset``."""

    header_end = marker_offset + 0x1A
    if header_end > len(raw) or raw[marker_offset : marker_offset + 4] != MARKER:
        return None

    length = struct.unpack_from("<H", raw, marker_offset + 0x14)[0]
    if not 0 < length <= remaining or length > _MAX_PAYLOAD_LENGTH:
        return None

    payload_offset = header_end
    completion_offset = payload_offset + length
    completion_end = completion_offset + 0x1A
    if completion_end > len(raw) or raw[completion_offset : completion_offset + 4] != MARKER:
        return None

    completion_kind = struct.unpack_from("<H", raw, completion_offset + 0x14)[0]
    completion_length = struct.unpack_from("<H", raw, completion_offset + 0x18)[0]
    if completion_kind != 2 or completion_length != length:
        return None

    flags = struct.unpack_from("<H", raw, marker_offset + 0x18)[0]
    return BulkPayloadRecord(
        marker_offset=marker_offset,
        payload_offset=payload_offset,
        completion_offset=completion_offset,
        length=length,
        flags=flags,
        payload=raw[payload_offset:completion_offset],
    )


def _next_payload(raw: bytes, start: int, remaining: int) -> BulkPayloadRecord | None:
    cursor = start
    while True:
        marker_offset = raw.find(MARKER, cursor)
        if marker_offset < 0:
            return None
        record = _parse_payload_at(raw, marker_offset, remaining)
        if record is not None:
            return record
        cursor = marker_offset + 1


def _split_observed_ranges(records: tuple[BulkPayloadRecord, ...]) -> tuple[bytes, ...]:
    """Split the range sequence verified in the two ordinary-send captures.

    The wire carries payload records for ranges 1, 2, 3, 5, and 8.  Ranges 4,
    6, and 7 have zero descriptors/payload in this path.  Range 3 is
    recognizable by its eight-byte big-endian ``N/M`` prefix and ``0xff`` fill;
    range 5 is the following fixed 64-byte record.  This function is
    intentionally scoped to that observed path and rejects a different layout
    instead of silently assigning its bytes to the wrong range.
    """

    if len(records) < 4:
        raise UsblogParseError("0x101b payload has too few native records")

    range1 = records[0].payload
    range2 = records[1].payload
    first_range3 = records[2].payload
    if len(first_range3) < _RANGE3_STAGING_LENGTH or any(
        byte != _RANGE3_FILL for byte in first_range3[_RANGE3_STAGING_LENGTH:]
    ):
        raise UsblogParseError("range 3 staging/fill pattern is not recognized")

    range3_parts = [first_range3]
    index = 3
    while index < len(records) and all(byte == _RANGE3_FILL for byte in records[index].payload):
        range3_parts.append(records[index].payload)
        index += 1

    if index >= len(records):
        raise UsblogParseError("range 5 record is missing after range 3")
    range3 = b"".join(range3_parts)

    range5 = records[index].payload
    if len(range5) != 0x40:
        raise UsblogParseError("range 5 is not the observed 64-byte record")
    index += 1
    range8 = b"".join(record.payload for record in records[index:])

    if len(range1) != 0x100 or len(range2) != 0x40:
        raise UsblogParseError("range 1 or range 2 length differs from the observed path")
    if len(range3) != _RANGE3_TOTAL_LENGTH:
        raise UsblogParseError(
            f"range 3 length is {len(range3):#x}, expected {_RANGE3_TOTAL_LENGTH:#x}"
        )
    if not range8:
        raise UsblogParseError("range 8 payload is missing")
    if len(range1) + len(range2) + len(range3) != 0x10000:
        raise UsblogParseError("ranges 1-3 do not fill the observed 0x10000-byte prefix")

    return (range1, range2, range3, b"", range5, b"", b"", range8)


def extract_101b(
    data: bytes | bytearray | memoryview, record_offset: int
) -> Usblog101bCapture:
    """Extract one verified ordinary-send ``0x101b`` transaction.

    ``record_offset`` must be one of the offsets returned by
    :func:`find_101b_headers`.  Extraction stops only after the sum of matched
    native payload lengths equals the command's declared length.  A mismatch,
    truncation, or unrecognized range layout raises :class:`UsblogParseError`.
    """

    raw = _coerce_bytes(data)
    if isinstance(record_offset, bool) or not isinstance(record_offset, int) or record_offset < 0:
        raise TypeError("record_offset must be a non-negative integer")
    if raw[record_offset : record_offset + 6] != _COMMAND_RECORD_PREFIX:
        raise UsblogParseError("record offset does not contain a native command prefix")

    command_offset = record_offset + len(_COMMAND_RECORD_PREFIX)
    if command_offset + 6 > len(raw):
        raise UsblogParseError("truncated 0x101b command header")
    command, declared_length = struct.unpack_from("<HI", raw, command_offset)
    if command != _COMMAND:
        raise UsblogParseError(f"command at offset is {command:#x}, not 0x101b")
    if declared_length == 0:
        raise UsblogParseError("0x101b declared length is zero")

    records: list[BulkPayloadRecord] = []
    consumed = 0
    cursor = command_offset + 6
    while consumed < declared_length:
        record = _next_payload(raw, cursor, declared_length - consumed)
        if record is None:
            raise UsblogParseError(
                f"could not find the next payload record after {consumed:#x} bytes"
            )
        records.append(record)
        consumed += record.length
        cursor = record.completion_offset + 0x1A

    if consumed != declared_length:
        raise UsblogParseError("payload length sum does not equal the 0x101b declaration")

    record_tuple = tuple(records)
    ranges = _split_observed_ranges(record_tuple)
    range3_n = struct.unpack(">I", ranges[2][:4])[0]
    range3_m = struct.unpack(">I", ranges[2][4:8])[0]
    if range3_n != 0:
        raise UsblogParseError("the observed splitter only supports N=0 range-4 staging")
    if range3_m != len(ranges[4]) + len(ranges[7]):
        raise UsblogParseError("range-3 M does not equal the observed ranges 5+8 length")
    if declared_length != 0x10000 + range3_n + range3_m:
        raise UsblogParseError("declared 0x101b length does not match N/M staging fields")

    return Usblog101bCapture(
        record_offset=record_offset,
        command_offset=command_offset,
        declared_length=declared_length,
        records=record_tuple,
        ranges=ranges,
    )


__all__ = [
    "BulkPayloadRecord",
    "Usblog101bCapture",
    "UsblogParseError",
    "extract_101b",
    "find_101b_headers",
]
