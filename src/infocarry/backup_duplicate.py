"""Offline duplication of existing backup records.

The manager capture provides one narrow, verified add-record example: copying
existing files into an existing directory.  This module reproduces that
structural operation for an already parsed blob and can then replace the
copied file's payload with caller-supplied bytes.  It does not invent model
nodes, rebuild sidecars, access USB, or claim that every arbitrary content
type is device-compatible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from .backup_format import (
    BackupFormatError,
    BackupRecord,
    ParsedBackupBlob,
    calculate_backup_checksum,
    parse_backup_blob,
)
from .backup_repack import BackupRepackError, repack_existing_records


class BackupDuplicateError(BackupFormatError):
    """Raised when a constrained duplicate cannot be built safely."""


@dataclass(frozen=True)
class DuplicateSpec:
    """One existing file to copy under a new name in the target directory."""

    source_offset: int
    new_name: str
    timestamp_be32: Optional[int] = None
    flag: Optional[int] = None


def _u32(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFFFFFFFF:
        raise BackupDuplicateError(f"{label} must fit an unsigned 32-bit integer")


def _validate_spec(spec: DuplicateSpec) -> None:
    if not isinstance(spec, DuplicateSpec):
        raise BackupDuplicateError("duplicates must contain DuplicateSpec values")
    if isinstance(spec.source_offset, bool) or not isinstance(spec.source_offset, int):
        raise BackupDuplicateError("source_offset must be an integer")
    if (
        not isinstance(spec.new_name, str)
        or not spec.new_name
        or "\x00" in spec.new_name
        or "\\" in spec.new_name
        or "/" in spec.new_name
        or spec.new_name in {".", ".."}
    ):
        raise BackupDuplicateError(
            "new_name must be one non-traversal path component without NUL or separators"
        )
    try:
        encoded = spec.new_name.encode("cp932")
    except UnicodeEncodeError as exc:
        raise BackupDuplicateError("new_name is not representable in CP932") from exc
    if len(encoded) >= 40:
        raise BackupDuplicateError("new_name must leave room for the metadata NUL terminator")
    if spec.timestamp_be32 is not None:
        _u32(spec.timestamp_be32, "timestamp_be32")
    if spec.flag is not None:
        if isinstance(spec.flag, bool) or not isinstance(spec.flag, int) or not 0 <= spec.flag <= 0xFF:
            raise BackupDuplicateError("flag must fit one byte")


def _aligned_copy(parsed: ParsedBackupBlob, record: BackupRecord) -> bytes:
    try:
        prefix, payload = parsed.payload_parts(record)
    except BackupFormatError as exc:
        raise BackupDuplicateError(str(exc)) from exc
    segment = prefix + payload
    return segment + b"\xff" * ((-len(segment)) % 4)


def duplicate_existing_records(
    parsed: ParsedBackupBlob,
    target_directory_offset: int,
    duplicates: Sequence[DuplicateSpec],
    *,
    metadata_timestamp_be32: Optional[int] = None,
    metadata_timestamps: Optional[Mapping[int, int]] = None,
) -> bytes:
    """Return a structurally valid blob with copies of existing files.

    The target directory must be reachable and have its observed ``..`` marker.
    New records are inserted immediately before that marker, and their content
    is inserted before the first later file segment.  Existing metadata can be
    timestamped uniformly with ``metadata_timestamp_be32`` to match the
    manager's observed rewrite behavior; ``metadata_timestamps`` may supply a
    per-source-offset map when a long transfer crosses a clock tick. Otherwise
    timestamps are preserved.
    """

    if not isinstance(parsed, ParsedBackupBlob):
        raise BackupDuplicateError("parsed must be a ParsedBackupBlob")
    if (
        isinstance(target_directory_offset, bool)
        or not isinstance(target_directory_offset, int)
        or target_directory_offset not in parsed.paths
    ):
        raise BackupDuplicateError("target_directory_offset is not reachable")
    target = parsed.record_at(target_directory_offset)
    if target.kind != "directory" or target.name == "..":
        raise BackupDuplicateError("target_directory_offset must name a reachable directory")
    if not isinstance(duplicates, (tuple, list)) or not duplicates:
        raise BackupDuplicateError("duplicates must be a non-empty tuple or list")
    for spec in duplicates:
        _validate_spec(spec)
    if metadata_timestamp_be32 is not None:
        _u32(metadata_timestamp_be32, "metadata_timestamp_be32")
    if metadata_timestamps is not None:
        if not isinstance(metadata_timestamps, Mapping):
            raise BackupDuplicateError("metadata_timestamps must be a mapping")
        for offset, timestamp in metadata_timestamps.items():
            if isinstance(offset, bool) or not isinstance(offset, int):
                raise BackupDuplicateError("metadata timestamp offsets must be integers")
            _u32(timestamp, f"metadata timestamp for 0x{offset:x}")

    existing_names = {
        record.name
        for record in parsed.records
        if record.offset in parsed.paths
        and parsed.paths[record.offset][:-1] == parsed.paths[target_directory_offset]
    }
    source_records: list[tuple[DuplicateSpec, BackupRecord, bytes]] = []
    new_names: set[str] = set()
    for spec in duplicates:
        if spec.new_name in existing_names or spec.new_name in new_names:
            raise BackupDuplicateError(f"duplicate destination name: {spec.new_name!r}")
        new_names.add(spec.new_name)
        try:
            source = parsed.record_at(spec.source_offset)
        except BackupFormatError as exc:
            raise BackupDuplicateError(str(exc)) from exc
        if source.kind != "file" or source.offset not in parsed.paths:
            raise BackupDuplicateError("each source must be a reachable file")
        source_records.append((spec, source, _aligned_copy(parsed, source)))

    # The first marker immediately after this directory's child table is the
    # shared boundary before the next subtree. Several later subtrees also
    # carry the same parent offset, so matching only ``field_04`` is ambiguous.
    marker_offset = (
        target.field_04_be32
        + parsed.header.record_size
        + target.field_08_be32
    )
    marker_candidates = [
        record
        for record in parsed.records
        if record.offset == marker_offset
        and record.kind == "directory"
        and record.name == ".."
        and record.field_04_be32 == target_directory_offset
    ]
    if len(marker_candidates) != 1:
        raise BackupDuplicateError(
            "target directory does not have exactly one observed parent marker"
        )
    marker = marker_candidates[0]
    metadata_delta = parsed.header.record_size * len(source_records)
    metadata_insert_index = (marker.offset - parsed.header.metadata_start) // parsed.header.record_size

    # The content follows metadata traversal order. Insert before the first
    # later file, or at the end when this is the last subtree.
    later_files = [
        record
        for record in parsed.records
        if record.kind == "file" and record.offset > marker.offset
    ]
    content_insert_at = min(
        (record.field_04_be32 for record in later_files),
        default=parsed.header.content_length,
    )
    if content_insert_at > parsed.header.content_length:
        raise BackupDuplicateError("content insertion point is outside the blob")
    copied_content = b"".join(segment for _, _, segment in source_records)
    content_delta = len(copied_content)

    shifted_records: list[bytes] = []
    for record in parsed.records:
        raw = bytearray.fromhex(record.raw_hex)
        timestamp = (
            metadata_timestamps.get(record.offset)
            if metadata_timestamps is not None
            else None
        )
        if timestamp is None:
            timestamp = metadata_timestamp_be32
        if timestamp is not None:
            raw[0x0C:0x10] = timestamp.to_bytes(4, "big")
        if record.offset == target_directory_offset:
            raw[0x08:0x0C] = (record.field_08_be32 + metadata_delta).to_bytes(4, "big")
        if record.name == ".." and record.field_04_be32 == target_directory_offset:
            raw[0x08:0x0C] = (record.field_08_be32 + metadata_delta).to_bytes(4, "big")
        if record.kind == "directory":
            if record.name == "..":
                # A parent marker stores its parent directory offset directly.
                # The value points at the parent directory's child-table
                # start minus one record. A root insertion therefore shifts a
                # marker when that child-table start is the insertion point,
                # even though the stored pointer itself is one record before
                # ``marker.offset``.
                if record.field_04_be32 + parsed.header.record_size >= marker.offset:
                    raw[0x04:0x08] = (record.field_04_be32 + metadata_delta).to_bytes(4, "big")
            # Ordinary directory field_04 is 0x40 before its child-table start.
            elif record.field_04_be32 + parsed.header.record_size >= marker.offset:
                raw[0x04:0x08] = (record.field_04_be32 + metadata_delta).to_bytes(4, "big")
        elif record.kind == "file" and record.field_04_be32 >= content_insert_at:
            raw[0x04:0x08] = (record.field_04_be32 + content_delta).to_bytes(4, "big")
        shifted_records.append(bytes(raw))

    new_records: list[bytes] = []
    content_position = content_insert_at
    for index, raw in enumerate(shifted_records):
        if index == metadata_insert_index:
            for spec, source, segment in source_records:
                record = bytearray.fromhex(source.raw_hex)
                record[0x04:0x08] = content_position.to_bytes(4, "big")
                timestamp = (
                    spec.timestamp_be32
                    if spec.timestamp_be32 is not None
                    else metadata_timestamps.get(spec.source_offset)
                    if metadata_timestamps is not None
                    and spec.source_offset in metadata_timestamps
                    else metadata_timestamp_be32
                    if metadata_timestamp_be32 is not None
                    else source.timestamp_be32
                )
                record[0x0C:0x10] = timestamp.to_bytes(4, "big")
                if spec.flag is not None:
                    record[0] = spec.flag
                record[0x18:0x40] = b"\x00" * 40
                encoded_name = spec.new_name.encode("cp932")
                record[0x18 : 0x18 + len(encoded_name)] = encoded_name
                new_records.append(bytes(record))
                content_position += len(segment)
        new_records.append(raw)

    metadata = b"".join(new_records)
    original_content = parsed.data[
        parsed.header.content_start : parsed.header.content_start + parsed.header.content_length
    ]
    content = (
        original_content[:content_insert_at]
        + copied_content
        + original_content[content_insert_at:]
    )
    header = bytearray(parsed.data[: parsed.header.metadata_start])
    header[0x2C:0x30] = len(metadata).to_bytes(4, "big")
    header[0x30:0x34] = (parsed.header.content_start + metadata_delta).to_bytes(4, "big")
    header[0x34:0x38] = len(content).to_bytes(4, "big")
    total_length = len(header) + len(metadata) + len(content) + 4
    header[0x18:0x1C] = (total_length - 1).to_bytes(4, "big")
    header[0x38:0x3C] = total_length.to_bytes(4, "big")

    result = bytearray(bytes(header) + metadata + content + parsed.data[-4:])
    result[0x1C:0x20] = b"\x00" * 4
    result[0x1C:0x20] = calculate_backup_checksum(bytes(result)).to_bytes(4, "big")
    rebuilt = bytes(result)
    try:
        parse_backup_blob(rebuilt)
    except BackupFormatError as exc:
        raise BackupDuplicateError(f"duplicated blob failed validation: {exc}") from exc
    return rebuilt


def add_file_from_template(
    parsed: ParsedBackupBlob,
    target_directory_offset: int,
    source_offset: int,
    new_name: str,
    payload: bytes,
    *,
    timestamp_be32: Optional[int] = None,
    flag: Optional[int] = None,
    metadata_timestamp_be32: Optional[int] = None,
    metadata_timestamps: Optional[Mapping[int, int]] = None,
) -> bytes:
    """Add one file using a captured record as its structural template.

    The manager's observed add path copies a complete 64-byte source record,
    including its extension, flag, native prefix, and unknown fields.  This
    helper reproduces that step, locates the newly reachable record, then
    replaces only its payload.  It therefore supports arbitrary *payload
    bytes* for an existing file type while intentionally refusing to invent a
    new record grammar or sidecar state.
    """

    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise BackupDuplicateError("payload must be bytes-like")
    spec = DuplicateSpec(
        source_offset=source_offset,
        new_name=new_name,
        timestamp_be32=timestamp_be32,
        flag=flag,
    )
    try:
        duplicated = duplicate_existing_records(
            parsed,
            target_directory_offset,
            [spec],
            metadata_timestamp_be32=metadata_timestamp_be32,
            metadata_timestamps=metadata_timestamps,
        )
        rebuilt = parse_backup_blob(duplicated)
    except (BackupDuplicateError, BackupFormatError) as exc:
        raise BackupDuplicateError(str(exc)) from exc

    target_path = parsed.paths[target_directory_offset] + (new_name,)
    candidates = [
        record.offset
        for record in rebuilt.records
        if record.kind == "file" and rebuilt.paths.get(record.offset) == target_path
    ]
    if len(candidates) != 1:
        raise BackupDuplicateError("new file did not resolve to exactly one reachable record")
    try:
        return repack_existing_records(rebuilt, {candidates[0]: bytes(payload)})
    except BackupRepackError as exc:
        raise BackupDuplicateError(f"new file payload failed validation: {exc}") from exc


__all__ = [
    "BackupDuplicateError",
    "DuplicateSpec",
    "add_file_from_template",
    "duplicate_existing_records",
]
