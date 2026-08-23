"""Offline serializers for the two fixed state ranges of command ``0x101b``.

Static analysis of ``VicTwo.dll`` shows that the ordinary write worker first
zero-initializes a 0x100-byte buffer and fills it with four 64-byte records,
then does the same for a 0x40-byte buffer containing ten dwords.  These
helpers reproduce only that byte layout.  They deliberately accept structural
objects instead of importing the USB-facing backup module, so importing this
module cannot open a device or require a transport backend.

The correlation between these buffers and the four ``0x001b``--``0x001e``
responses plus the ``0x001f`` response is a static/category-order correlation.
The serializers therefore preserve the legacy allocator's zero-filled unused
tail rather than copying parser-only ``unused_tail_hex`` bytes.  They are
candidate builders for offline comparison, not a claim that the complete
eight-range write payload is device-compatible.
"""

from typing import Protocol, Sequence


FIXED_STATE_LENGTH = 0x40
OFFSET_LIST_RANGE_COUNT = 4
OFFSET_LIST_MAX_COUNT = 13
GROUPED_VALUE_GROUP_COUNT = 2
GROUPED_VALUE_COUNT = 5


class StateSerializationError(ValueError):
    """Raised when a fixed-state candidate cannot fit the legacy layout."""


def _validate_rebase_value(value: int, label: str) -> None:
    _require_uint(value, 0xFFFFFFFF, label)
    if value and value % 0x40:
        raise StateSerializationError(
            f"{label} is not a metadata-record-aligned offset"
        )


def rebase_fixed_state_responses(
    offset_list_responses: Sequence[bytes],
    grouped_values_response: bytes,
    *,
    insertion_offset: int,
    metadata_delta: int,
) -> tuple[bytes, bytes]:
    """Rebase only established metadata-record references in fixed state.

    The four ``0x001b``--``0x001e`` responses contain counted record-offset
    lists.  The first dword of each ``0x001f`` bookmark group is also a
    verified metadata-relative record offset.  Those references are shifted
    when a new 64-byte metadata record is inserted.  Every other byte,
    including unused tails and unresolved bookmark/category fields, is
    preserved exactly; no new state membership is assigned.
    """

    if not isinstance(offset_list_responses, (tuple, list)) or len(offset_list_responses) != 4:
        raise StateSerializationError("expected four fixed offset-list responses")
    _require_uint(insertion_offset, 0xFFFFFFFF, "state insertion offset")
    _require_uint(metadata_delta, 0xFFFFFFFF, "state metadata delta")
    if insertion_offset % 0x40 or metadata_delta == 0 or metadata_delta % 0x40:
        raise StateSerializationError(
            "state insertion offset and metadata delta must be record-aligned"
        )

    rebased_lists = []
    for response_index, response in enumerate(offset_list_responses):
        if not isinstance(response, (bytes, bytearray, memoryview)):
            raise StateSerializationError(
                f"fixed offset-list response {response_index} must be bytes-like"
            )
        raw = bytearray(response)
        if len(raw) != FIXED_STATE_LENGTH:
            raise StateSerializationError(
                f"fixed offset-list response {response_index} must be 64 bytes"
            )
        count = int.from_bytes(raw[0:4], "big")
        if count > OFFSET_LIST_MAX_COUNT:
            raise StateSerializationError(
                f"fixed offset-list response {response_index} count exceeds 13"
            )
        for entry_index in range(count):
            start = 8 + entry_index * 4
            value = int.from_bytes(raw[start : start + 4], "big")
            _validate_rebase_value(
                value,
                f"fixed offset-list response {response_index} entry {entry_index}",
            )
            if value >= insertion_offset:
                rebased = value + metadata_delta
                _require_uint(
                    rebased,
                    0xFFFFFFFF,
                    f"rebased fixed offset-list response {response_index} entry {entry_index}",
                )
                raw[start : start + 4] = rebased.to_bytes(4, "big")
        rebased_lists.append(bytes(raw))

    if not isinstance(grouped_values_response, (bytes, bytearray, memoryview)):
        raise StateSerializationError("grouped-values response must be bytes-like")
    grouped = bytearray(grouped_values_response)
    if len(grouped) != FIXED_STATE_LENGTH:
        raise StateSerializationError("grouped-values response must be 64 bytes")
    for group_index, start in enumerate((0, 20)):
        value = int.from_bytes(grouped[start : start + 4], "big")
        _validate_rebase_value(value, f"bookmark group {group_index} record offset")
        if value >= insertion_offset:
            rebased = value + metadata_delta
            _require_uint(rebased, 0xFFFFFFFF, f"rebased bookmark group {group_index}")
            grouped[start : start + 4] = rebased.to_bytes(4, "big")
    return tuple(rebased_lists), bytes(grouped)


class OffsetListState(Protocol):
    """Attributes required from an offset-list parser result."""

    count: int
    value_04_be16: int
    value_06_be16: int
    record_offsets: Sequence[int]


class GroupedValuesState(Protocol):
    """Attributes required from a grouped-values parser result."""

    groups: Sequence[Sequence[int]]


def _require_uint(value: int, maximum: int, label: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= maximum
    ):
        raise StateSerializationError(
            f"{label} must fit an unsigned {maximum.bit_length()}-bit integer"
        )


def serialize_offset_list_state(response: OffsetListState) -> bytes:
    """Serialize one 64-byte offset-list state record.

    The first dword, two fixed words, and exactly ``count`` offsets are written
    big-endian.  The remaining bytes are zero because the legacy destination
    came from a zero-filling allocator before the serializer ran.
    """

    _require_uint(response.count, 0xFFFFFFFF, "offset-list count")
    if response.count > OFFSET_LIST_MAX_COUNT:
        raise StateSerializationError(
            f"offset-list count {response.count} exceeds {OFFSET_LIST_MAX_COUNT}"
        )
    if len(response.record_offsets) != response.count:
        raise StateSerializationError(
            "offset-list record_offsets length does not match count"
        )
    _require_uint(response.value_04_be16, 0xFFFF, "offset-list value at +0x04")
    _require_uint(response.value_06_be16, 0xFFFF, "offset-list value at +0x06")
    for index, offset in enumerate(response.record_offsets):
        _require_uint(offset, 0xFFFFFFFF, f"offset-list record offset {index}")

    result = bytearray(FIXED_STATE_LENGTH)
    result[0:4] = response.count.to_bytes(4, "big")
    result[4:6] = response.value_04_be16.to_bytes(2, "big")
    result[6:8] = response.value_06_be16.to_bytes(2, "big")
    for index, offset in enumerate(response.record_offsets):
        start = 8 + index * 4
        result[start : start + 4] = offset.to_bytes(4, "big")
    return bytes(result)


def serialize_offset_list_ranges(responses: Sequence[OffsetListState]) -> bytes:
    """Serialize the four ordered 64-byte offset-list records into 0x100 bytes."""

    if len(responses) != OFFSET_LIST_RANGE_COUNT:
        raise StateSerializationError(
            f"expected {OFFSET_LIST_RANGE_COUNT} offset-list responses; got {len(responses)}"
        )
    return b"".join(serialize_offset_list_state(response) for response in responses)


def serialize_grouped_values_state(response: GroupedValuesState) -> bytes:
    """Serialize two groups of five big-endian dwords into one 64-byte record."""

    if len(response.groups) != GROUPED_VALUE_GROUP_COUNT:
        raise StateSerializationError(
            f"expected {GROUPED_VALUE_GROUP_COUNT} grouped-value groups; got {len(response.groups)}"
        )
    values = []
    for group_index, group in enumerate(response.groups):
        if len(group) != GROUPED_VALUE_COUNT:
            raise StateSerializationError(
                f"group {group_index} has {len(group)} values; expected {GROUPED_VALUE_COUNT}"
            )
        for value_index, value in enumerate(group):
            _require_uint(value, 0xFFFFFFFF, f"group {group_index} value {value_index}")
            values.append(value)

    result = bytearray(FIXED_STATE_LENGTH)
    for index, value in enumerate(values):
        start = index * 4
        result[start : start + 4] = value.to_bytes(4, "big")
    return bytes(result)


__all__ = [
    "FIXED_STATE_LENGTH",
    "GROUPED_VALUE_COUNT",
    "GROUPED_VALUE_GROUP_COUNT",
    "OFFSET_LIST_MAX_COUNT",
    "OFFSET_LIST_RANGE_COUNT",
    "StateSerializationError",
    "rebase_fixed_state_responses",
    "serialize_grouped_values_state",
    "serialize_offset_list_ranges",
    "serialize_offset_list_state",
]
