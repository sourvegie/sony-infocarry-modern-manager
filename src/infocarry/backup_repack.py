"""Offline structural repacking for an existing parsed backup blob.

This module preserves the original record tree, header extensions, unknown
record fields, content gaps, and trailer. It can replace payload bytes for
existing file records, rename one existing record in-place, or delete one
reachable *file* record while remapping the remaining metadata and content
offsets. It has no USB integration. Adding a file is kept in
``backup_duplicate`` because it requires a copied manager record template.

The result is a structurally valid candidate blob. It is not yet claimed to be
a complete manager-compatible ``VICDATA.bin`` generator for arbitrary content
changes.
"""

from typing import Mapping

from .backup_format import (
    BackupFormatError,
    ParsedBackupBlob,
    calculate_backup_checksum,
    parse_backup_blob,
)


class BackupRepackError(BackupFormatError):
    """Raised when a structural replacement cannot be performed safely."""


def _encode_record_name(name: str) -> bytes:
    if not isinstance(name, str) or not name:
        raise BackupRepackError("record name must be a non-empty string")
    if "\x00" in name or "\\" in name or "/" in name:
        raise BackupRepackError(
            "record name must be one path component without NUL or separators"
        )
    if name in {".", ".."}:
        raise BackupRepackError("record name cannot be a traversal component")
    try:
        encoded = name.encode("cp932", errors="strict")
    except UnicodeEncodeError as exc:
        raise BackupRepackError("record name is not representable in CP932") from exc
    if len(encoded) >= 0x28:
        raise BackupRepackError("record name must fit the 40-byte metadata field")
    return encoded


def rename_existing_record(
    parsed: ParsedBackupBlob, record_offset: int, new_name: str
) -> bytes:
    """Rename one reachable metadata record without changing tree shape.

    Only the CP932 name field is changed. The record flag, extension, native
    payload, parent relationship, unknown fields, and all content bytes are
    preserved. A sibling collision is rejected, and the resulting checksum
    and path index are validated before returning.
    """

    if not isinstance(parsed, ParsedBackupBlob):
        raise BackupRepackError("parsed must be a ParsedBackupBlob")
    if isinstance(record_offset, bool) or not isinstance(record_offset, int):
        raise BackupRepackError("record_offset must be an integer")
    try:
        record = parsed.record_at(record_offset)
    except BackupFormatError as exc:
        raise BackupRepackError(str(exc)) from exc
    path = parsed.paths.get(record_offset)
    if path is None:
        raise BackupRepackError(f"record 0x{record_offset:x} is not reachable")
    if record.name in {"root", "..", "."}:
        raise BackupRepackError("root and traversal records cannot be renamed")
    encoded_name = _encode_record_name(new_name)
    if new_name == record.name:
        raise BackupRepackError("new record name is identical to the existing name")
    parent = path[:-1]
    if any(
        other_offset != record_offset
        and other_path[:-1] == parent
        and other_path[-1] == new_name
        for other_offset, other_path in parsed.paths.items()
    ):
        raise BackupRepackError(
            f"record name {new_name!r} already exists in the target directory"
        )

    output = bytearray(parsed.data)
    name_start = record_offset + 0x18
    name_end = record_offset + 0x40
    if name_start < parsed.header.metadata_start or name_end > parsed.header.content_start:
        raise BackupRepackError("record name field is outside metadata")
    # Preserve unknown bytes after the old NUL; only replace the meaningful
    # prefix and terminator.
    suffix_start = name_start + len(encoded_name) + 1
    output[name_start:name_end] = encoded_name + b"\x00" + output[suffix_start:name_end]
    output[0x1C:0x20] = b"\x00" * 4
    checksum = calculate_backup_checksum(bytes(output))
    output[0x1C:0x20] = checksum.to_bytes(4, "big")
    result = bytes(output)
    try:
        rebuilt = parse_backup_blob(result)
    except BackupFormatError as exc:
        raise BackupRepackError(f"renamed blob failed structural validation: {exc}") from exc
    if rebuilt.paths.get(record_offset, ())[-1:] != (new_name,):
        raise BackupRepackError("renamed record path did not validate")
    return result


def _u32(value: int, label: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= 0xFFFFFFFF
    ):
        raise BackupRepackError(f"{label} must fit an unsigned 32-bit integer")


def _aligned_segment_end(segment_start: int, segment_length: int) -> int:
    """Return the observed four-byte-aligned end of one content segment.

    The native failed-delete candidate removed the selected record's occupied
    bytes plus the three-byte gap immediately following them.  That is the
    four-byte alignment boundary, not a final-output padding decision.
    """

    if segment_start < 0 or segment_length < 0:
        raise BackupRepackError("content segment values must be non-negative")
    end = segment_start + segment_length
    return end + ((-end) % 4)


def repack_existing_records(
    parsed: ParsedBackupBlob, replacements: Mapping[int, bytes]
) -> bytes:
    """Replace payloads for existing records and return a validated blob.

    ``replacements`` maps metadata record offsets to complete payload bytes,
    excluding each record's preserved native prefix. An empty mapping returns
    the original bytes unchanged. Every file segment—including untouched
    files—is retained in original content order, and gaps are copied verbatim.
    """

    if not replacements:
        return parsed.data

    records_by_offset = {record.offset: record for record in parsed.records}
    for offset, payload in replacements.items():
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise BackupRepackError("replacement record offsets must be integers")
        record = records_by_offset.get(offset)
        if record is None:
            raise BackupRepackError(
                f"replacement targets unknown metadata record 0x{offset:x}"
            )
        if record.kind != "file":
            raise BackupRepackError(
                f"replacement target 0x{offset:x} is not a file record"
            )
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise BackupRepackError(
                f"replacement payload for 0x{offset:x} must be bytes-like"
            )
        _u32(len(payload), f"replacement payload length for 0x{offset:x}")

    header = parsed.header
    original_content = parsed.data[
        header.content_start : header.content_start + header.content_length
    ]
    segments = []
    for record in parsed.records:
        if record.kind != "file":
            continue
        prefix_length = record.payload_prefix_length
        if prefix_length is None:
            raise BackupRepackError(
                f"file record 0x{record.offset:x} has an unsupported native prefix"
            )
        start = record.field_04_be32
        end = start + prefix_length + record.field_08_be32
        if start > len(original_content) or end > len(original_content):
            raise BackupRepackError(
                f"file record 0x{record.offset:x} content segment is outside the blob"
            )
        segments.append((start, end, record, prefix_length))

    segments.sort(key=lambda item: (item[0], item[1], item[2].offset))
    rebuilt_content = bytearray()
    cursor = 0
    updated_fields = {}
    for start, end, record, prefix_length in segments:
        if start < cursor:
            raise BackupRepackError(
                f"file record 0x{record.offset:x} overlaps an earlier content segment"
            )
        rebuilt_content.extend(original_content[cursor:start])
        new_field_04 = len(rebuilt_content)
        prefix = original_content[start : start + prefix_length]
        old_payload_start = start + prefix_length
        old_payload_end = old_payload_start + record.field_08_be32
        replacement = replacements.get(record.offset)
        payload = (
            bytes(replacement)
            if replacement is not None
            else original_content[old_payload_start:old_payload_end]
        )
        rebuilt_content.extend(prefix)
        rebuilt_content.extend(payload)
        updated_fields[record.offset] = (new_field_04, len(payload))
        cursor = end
    rebuilt_content.extend(original_content[cursor:])

    padding = (-(header.content_start + len(rebuilt_content))) % 4
    rebuilt_content.extend(b"\x00" * padding)
    _u32(len(rebuilt_content), "rebuilt content length")

    output = bytearray(parsed.data[: header.content_start])
    for offset, (field_04, field_08) in updated_fields.items():
        output[offset + 0x04 : offset + 0x08] = field_04.to_bytes(4, "big")
        output[offset + 0x08 : offset + 0x0C] = field_08.to_bytes(4, "big")
    output.extend(rebuilt_content)
    output.extend(parsed.data[-4:])

    total_length = header.content_start + len(rebuilt_content) + 4
    _u32(total_length, "rebuilt total length")
    output[0x18:0x1C] = (total_length - 1).to_bytes(4, "big")
    output[0x34:0x38] = len(rebuilt_content).to_bytes(4, "big")
    output[0x38:0x3C] = total_length.to_bytes(4, "big")
    output[0x1C:0x20] = b"\x00" * 4
    checksum = calculate_backup_checksum(bytes(output))
    output[0x1C:0x20] = checksum.to_bytes(4, "big")

    result = bytes(output)
    try:
        parse_backup_blob(result)
    except BackupFormatError as exc:
        raise BackupRepackError(f"rebuilt blob failed structural validation: {exc}") from exc
    return result


def delete_existing_file(
    parsed: ParsedBackupBlob,
    record_offset: int,
    *,
    metadata_timestamps: Mapping[int, int] | None = None,
) -> bytes:
    """Delete one reachable file and rebuild offsets without guessing a tree.

    The operation is intentionally narrower than a general filesystem
    mutator: directories, parent markers, unknown records, and record order
    are preserved; only the selected file record and its native content
    segment are removed. Metadata pointers are remapped by one fixed record
    size, and the selected parent's child table is shortened by one record.
    A complete parse and payload/path invariant check is performed before the
    candidate is returned. When ``metadata_timestamps`` is supplied, it must
    contain one explicit opaque timestamp value for every surviving metadata
    record. This supports the attempt-02 observed timestamp normalization
    without inventing a general timestamp rule.
    """

    if not isinstance(parsed, ParsedBackupBlob):
        raise BackupRepackError("parsed must be a ParsedBackupBlob")
    if isinstance(record_offset, bool) or not isinstance(record_offset, int):
        raise BackupRepackError("record_offset must be an integer")
    try:
        record = parsed.record_at(record_offset)
    except BackupFormatError as exc:
        raise BackupRepackError(str(exc)) from exc
    path = parsed.paths.get(record_offset)
    if path is None:
        raise BackupRepackError(f"record 0x{record_offset:x} is not reachable")
    if record.kind != "file":
        raise BackupRepackError("only reachable file records can be deleted")

    if metadata_timestamps is not None:
        if not isinstance(metadata_timestamps, Mapping):
            raise BackupRepackError("metadata_timestamps must be a mapping or None")
        surviving_offsets = {
            current.offset for current in parsed.records if current.offset != record_offset
        }
        if set(metadata_timestamps) != surviving_offsets:
            raise BackupRepackError(
                "metadata_timestamps must contain exactly every surviving record offset"
            )
        for offset, timestamp in metadata_timestamps.items():
            _u32(offset, "metadata timestamp record offset")
            _u32(timestamp, f"metadata timestamp at 0x{offset:x}")

    parent_candidates = [
        (offset, parent)
        for offset, parent_path in parsed.paths.items()
        if parent_path == path[:-1]
        for parent in (parsed.record_at(offset),)
        if parent.kind == "directory"
    ]
    if len(parent_candidates) != 1:
        raise BackupRepackError("could not resolve the selected file's parent directory")
    parent_offset, parent = parent_candidates[0]
    child_start = parent.field_04_be32 + parsed.header.record_size
    child_end = child_start + parent.field_08_be32
    child_offsets = tuple(
        offset
        for offset in range(child_start, child_end, parsed.header.record_size)
    )
    if record_offset not in child_offsets:
        raise BackupRepackError("selected file is not linked from its parent child table")
    if parent.field_08_be32 < parsed.header.record_size:
        raise BackupRepackError("parent child table cannot be shortened safely")

    try:
        prefix, payload = parsed.payload_parts(record)
    except BackupFormatError as exc:
        raise BackupRepackError(str(exc)) from exc
    content = parsed.data[
        parsed.header.content_start : parsed.header.content_start + parsed.header.content_length
    ]
    segment_start = record.field_04_be32
    segment_length = len(prefix) + len(payload)
    segment_end = segment_start + segment_length
    aligned_segment_end = _aligned_segment_end(segment_start, segment_length)
    if segment_start < 0 or aligned_segment_end > len(content):
        raise BackupRepackError("selected file content segment is outside the content region")

    record_size = parsed.header.record_size
    metadata = bytearray()
    for current in parsed.records:
        if current.offset == record_offset:
            continue
        raw = bytearray.fromhex(current.raw_hex)
        if metadata_timestamps is not None:
            raw[0x0C:0x10] = metadata_timestamps[current.offset].to_bytes(4, "big")
        if current.kind == "directory":
            # Ordinary directory records point to their own offset; parent
            # markers point to the parent directory. Both references shift
            # when the removed record precedes them in metadata.
            pointer = current.field_04_be32
            # The native delete candidate rebases a metadata pointer equal to
            # the removed record offset as well as pointers after it.  This
            # includes the pointer immediately before the deleted subtree's
            # first child marker.
            if pointer >= record_offset:
                pointer -= record_size
                raw[0x04:0x08] = pointer.to_bytes(4, "big")
            if current.offset == parent_offset:
                raw[0x08:0x0C] = (
                    current.field_08_be32 - record_size
                ).to_bytes(4, "big")
            elif current.name == ".." and current.field_08_be32 in {
                record_offset,
                record_offset + record_size,
            }:
                # This field is not semantically named. The native candidate
                # rebased the observed ``..`` marker boundary immediately after
                # the deleted metadata record. Retain the older helper's exact
                # boundary case as well for its established synthetic fixture;
                # no device-facing delete path exists.
                raw[0x08:0x0C] = (
                    current.field_08_be32 - record_size
                ).to_bytes(4, "big")
        if current.kind == "file":
            content_offset = current.field_04_be32
            if content_offset >= aligned_segment_end:
                content_offset -= aligned_segment_end - segment_start
                raw[0x04:0x08] = content_offset.to_bytes(4, "big")
        metadata.extend(raw)

    # Remove the occupied segment and its observed alignment gap.  The native
    # candidate did not add a compensating final pad after this removal.
    rebuilt_content = content[:segment_start] + content[aligned_segment_end:]

    header = bytearray(parsed.data[: parsed.header.metadata_start])
    new_content_start = parsed.header.content_start - record_size
    header[0x2C:0x30] = len(metadata).to_bytes(4, "big")
    header[0x30:0x34] = new_content_start.to_bytes(4, "big")
    header[0x34:0x38] = len(rebuilt_content).to_bytes(4, "big")
    total_length = len(header) + len(metadata) + len(rebuilt_content) + 4
    _u32(total_length, "rebuilt total length")
    header[0x18:0x1C] = (total_length - 1).to_bytes(4, "big")
    header[0x38:0x3C] = total_length.to_bytes(4, "big")

    output = bytearray(bytes(header) + bytes(metadata) + rebuilt_content + parsed.data[-4:])
    output[0x1C:0x20] = b"\x00" * 4
    output[0x1C:0x20] = calculate_backup_checksum(bytes(output)).to_bytes(4, "big")
    result = bytes(output)
    try:
        rebuilt = parse_backup_blob(result)
    except BackupFormatError as exc:
        raise BackupRepackError(f"deleted blob failed structural validation: {exc}") from exc
    if len(rebuilt.records) != len(parsed.records) - 1:
        raise BackupRepackError("deleted blob did not remove exactly one record")
    if any(candidate_path == path for candidate_path in rebuilt.paths.values()):
        raise BackupRepackError("deleted file path remains reachable")
    for old_offset, old_path in parsed.paths.items():
        if old_offset == record_offset:
            continue
        expected_offset = old_offset if old_offset < record_offset else old_offset - record_size
        if rebuilt.paths.get(expected_offset) != old_path:
            raise BackupRepackError("deletion changed an unrelated reachable path")
        old_record = parsed.record_at(old_offset)
        new_record = rebuilt.record_at(expected_offset)
        if old_record.kind == "file":
            _, old_payload = parsed.payload_parts(old_record)
            _, new_payload = rebuilt.payload_parts(new_record)
            if old_payload != new_payload:
                raise BackupRepackError("deletion changed an unrelated file payload")
    return result


__all__ = [
    "BackupRepackError",
    "delete_existing_file",
    "rename_existing_record",
    "repack_existing_records",
]
