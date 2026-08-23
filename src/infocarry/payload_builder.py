"""Guarded offline composition of the recovered ``0x101b`` ranges.

This module is an offline payload-generator boundary. The ordinary manager
path is fully expressible from a validated decoded ``VICDATA.bin`` blob:
range 5 is its first 64-byte header, range 8 is the exact remaining body, and
ordinary captures prove ranges 4, 6, and 7 are empty. Alternate model modes
still require explicit opaque ranges or caller-supplied nodes. No function
opens USB, replays a capture, or exposes a device-write operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .model_range import (
    ExplicitModelNode,
    ModelRangeError,
    serialize_explicit_model_range,
)
from .backup_format import BackupFormatError, parse_backup_blob
from .backup_repack import BackupRepackError, repack_existing_records
from .range5_model import Range5SerializationError, serialize_range5_model
from .usblog import Usblog101bCapture
from .write_artifact import (
    ProspectiveWriteTransaction,
    WriteArtifactError,
    build_staging_range,
)
from .write_state import (
    GroupedValuesState,
    OffsetListState,
    StateSerializationError,
    serialize_grouped_values_state,
    serialize_offset_list_ranges,
)


class PayloadBuilderError(ValueError):
    """Raised when offline payload inputs cannot be composed safely."""


def _bytes(value: bytes | bytearray | memoryview, label: str) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise PayloadBuilderError(f"{label} must be bytes-like")
    return bytes(value)


@dataclass(frozen=True)
class _OffsetState:
    count: int
    value_04_be16: int
    value_06_be16: int
    record_offsets: tuple[int, ...]


@dataclass(frozen=True)
class _GroupedState:
    groups: tuple[tuple[int, ...], tuple[int, ...]]


def _parse_offset_state(data: bytes) -> _OffsetState:
    if len(data) != 0x40:
        raise PayloadBuilderError("observed offset-list block must be 64 bytes")
    count = int.from_bytes(data[0:4], "big")
    if count >= 14:
        raise PayloadBuilderError("observed offset-list count exceeds 13")
    end = 8 + count * 4
    return _OffsetState(
        count=count,
        value_04_be16=int.from_bytes(data[4:6], "big"),
        value_06_be16=int.from_bytes(data[6:8], "big"),
        record_offsets=tuple(
            int.from_bytes(data[offset : offset + 4], "big")
            for offset in range(8, end, 4)
        ),
    )


def _parse_grouped_state(data: bytes) -> _GroupedState:
    if len(data) != 0x40:
        raise PayloadBuilderError("observed grouped-value block must be 64 bytes")
    values = tuple(
        int.from_bytes(data[offset : offset + 4], "big")
        for offset in range(0, 40, 4)
    )
    return _GroupedState(groups=(values[:5], values[5:]))


def build_offline_payload(
    offset_list_states: Sequence[OffsetListState],
    grouped_values_state: GroupedValuesState,
    *,
    range4: bytes | bytearray | memoryview = b"",
    range5_source: bytes | bytearray | memoryview,
    range6: bytes | bytearray | memoryview = b"",
    range7: bytes | bytearray | memoryview = b"",
    range8: bytes | bytearray | memoryview | None = None,
    model_nodes: Sequence[ExplicitModelNode] | None = None,
) -> ProspectiveWriteTransaction:
    """Compose a validated offline transaction from fixed and opaque inputs.

    The caller must provide the unresolved variable ranges explicitly. A
    sequence of ``model_nodes`` may be used when the caller already has the
    legacy internal objects and exact variable bytes; this applies only the
    recovered prefix/child/alignment grammar and does not convert a
    ``VICDATA.bin`` file into those nodes.
    """

    try:
        range1 = serialize_offset_list_ranges(offset_list_states)
        range2 = serialize_grouped_values_state(grouped_values_state)
        range5 = serialize_range5_model(range5_source)
    except (StateSerializationError, Range5SerializationError) as exc:
        raise PayloadBuilderError(str(exc)) from exc

    range4_bytes = _bytes(range4, "range 4")
    if range8 is not None and model_nodes is not None:
        raise PayloadBuilderError("provide either range8 bytes or model_nodes, not both")
    if model_nodes is not None:
        try:
            range8_bytes = serialize_explicit_model_range(model_nodes)
        except ModelRangeError as exc:
            raise PayloadBuilderError(str(exc)) from exc
    elif range8 is not None:
        range8_bytes = _bytes(range8, "range 8")
    else:
        raise PayloadBuilderError("range 8 bytes or model_nodes are required")
    opaque = {
        "range 6": _bytes(range6, "range 6"),
        "range 7": _bytes(range7, "range 7"),
        "range 8": range8_bytes,
    }
    variable_m = len(range5) + sum(len(data) for data in opaque.values())
    variable_n = len(range4_bytes)
    range3 = build_staging_range(variable_n, variable_m)

    try:
        return ProspectiveWriteTransaction(
            ranges=(
                range1,
                range2,
                range3,
                range4_bytes,
                range5,
                opaque["range 6"],
                opaque["range 7"],
                opaque["range 8"],
            ),
            variable_n=variable_n,
            variable_m=variable_m,
        )
    except WriteArtifactError as exc:
        raise PayloadBuilderError(str(exc)) from exc


def build_from_observed_capture(
    capture: Usblog101bCapture,
) -> ProspectiveWriteTransaction:
    """Re-compose one parsed ordinary capture without retaining its framing.

    This convenience function is a regression boundary: it parses the
    captured fixed ranges into the same source structures consumed by the
    serializers, recovers range 5's source object, and passes ranges 4, 6, 7,
    and 8 through as opaque evidence. It must reproduce the observed eight
    ranges exactly or raise an error; it does not create a new model payload.
    """

    if not isinstance(capture, Usblog101bCapture):
        raise PayloadBuilderError("capture must be a Usblog101bCapture")

    offset_states = tuple(
        _parse_offset_state(capture.ranges[0][offset : offset + 0x40])
        for offset in range(0, 0x100, 0x40)
    )
    grouped_state = _parse_grouped_state(capture.ranges[1])
    from .range5_model import recover_range5_source

    transaction = build_offline_payload(
        offset_states,
        grouped_state,
        range4=capture.ranges[3],
        range5_source=recover_range5_source(capture.ranges[4]).source,
        range6=capture.ranges[5],
        range7=capture.ranges[6],
        range8=capture.ranges[7],
    )
    if transaction.ranges != capture.ranges:
        raise PayloadBuilderError(
            "offline composition does not reproduce the observed eight ranges"
        )
    return transaction


def build_from_decoded_vicdata(
    decoded_vicdata: bytes | bytearray | memoryview,
    offset_list_states: Sequence[OffsetListState],
    grouped_values_state: GroupedValuesState,
) -> ProspectiveWriteTransaction:
    """Compose the ordinary ranges directly from a validated decoded blob.

    All preserved ordinary captures prove that range 5 is the first 64-byte
    VICDATA header and range 8 is the exact remaining decoded blob. This
    helper makes that relationship explicit while retaining the fixed state
    serializers for ranges 1 and 2. It is still an offline artifact builder:
    callers must supply a separate, verified state snapshot and no USB path is
    exposed here.
    """

    raw = _bytes(decoded_vicdata, "decoded VICDATA")
    try:
        parse_backup_blob(raw)
    except BackupFormatError as exc:
        raise PayloadBuilderError(f"decoded VICDATA is not structurally valid: {exc}") from exc
    if len(raw) < 0x40:
        raise PayloadBuilderError("decoded VICDATA is shorter than its 64-byte header")

    from .range5_model import recover_range5_source

    try:
        recovered = recover_range5_source(raw[:0x40])
    except Range5SerializationError as exc:
        raise PayloadBuilderError(f"VICDATA header is not a recovered range-5 value: {exc}") from exc
    transaction = build_offline_payload(
        offset_list_states,
        grouped_values_state,
        range5_source=recovered.source,
        range8=raw[0x40:],
    )
    if transaction.ranges[4] + transaction.ranges[7] != raw:
        raise PayloadBuilderError("VICDATA-to-range split is not byte-identical")
    return transaction


def build_ordinary_from_decoded_vicdata(
    decoded_vicdata: bytes | bytearray | memoryview,
    offset_list_states: Sequence[OffsetListState],
    grouped_values_state: GroupedValuesState,
) -> ProspectiveWriteTransaction:
    """Build the verified ordinary manager-path transaction.

    This named entry point makes the policy explicit: it accepts only a
    structurally valid decoded backup blob and emits empty ranges 4, 6, and 7
    exactly as observed in every preserved ordinary capture. It does not
    claim compatibility with the separate special/model modes that populate
    those ranges.
    """

    return build_from_decoded_vicdata(
        decoded_vicdata, offset_list_states, grouped_values_state
    )


def build_from_replacements(
    decoded_vicdata: bytes | bytearray | memoryview,
    replacements: dict[int, bytes | bytearray | memoryview],
    offset_list_states: Sequence[OffsetListState],
    grouped_values_state: GroupedValuesState,
) -> ProspectiveWriteTransaction:
    """Build an offline candidate after replacing existing record payloads.

    This is the first toolkit-authored content path. It deliberately keeps
    the existing record tree, native prefixes, sidecar-independent state, and
    unknown fields intact by delegating to the constrained structural repacker.
    Adding/removing/renaming records and synchronizing manager sidecars remain
    outside this function's contract.
    """

    raw = _bytes(decoded_vicdata, "decoded VICDATA")
    try:
        parsed = parse_backup_blob(raw)
        rebuilt = repack_existing_records(parsed, replacements)
    except (BackupFormatError, BackupRepackError) as exc:
        raise PayloadBuilderError(f"existing-record replacement failed: {exc}") from exc
    if not replacements:
        raise PayloadBuilderError("at least one existing-record replacement is required")
    return build_ordinary_from_decoded_vicdata(
        rebuilt, offset_list_states, grouped_values_state
    )


__all__ = [
    "PayloadBuilderError",
    "build_from_decoded_vicdata",
    "build_ordinary_from_decoded_vicdata",
    "build_from_observed_capture",
    "build_from_replacements",
    "build_offline_payload",
]
