"""Deterministic offline inventory for prepared-content evidence.

This module describes records already present in a validated backup.  It does
not infer how a Manager creates a folder, does not construct a device
transaction, and does not access USB.  The inventory deliberately separates
device-resident tree/payload facts from Manager-side evidence supplied by the
caller.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any, Iterable, Mapping, Optional, Sequence

from .backup_format import BackupFormatError, ParsedBackupBlob, BackupRecord


PREPARED_EVIDENCE_FORMAT = "infocarry-prepared-content-evidence-v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _path_text(path: Sequence[str]) -> str:
    return "\\".join(path)


def _align4(value: int) -> int:
    return (value + 3) & ~3


def _relationship_maps(
    parsed: ParsedBackupBlob,
) -> tuple[dict[int, tuple[int, ...]], dict[int, int], dict[int, int]]:
    by_offset = {record.offset: record for record in parsed.records}
    children: dict[int, tuple[int, ...]] = {}
    parent_by_child: dict[int, int] = {}
    marker_by_directory: dict[int, int] = {}
    for record in parsed.records:
        if record.kind != "directory":
            continue
        child_start = record.field_04_be32 + parsed.header.record_size
        child_end = child_start + record.field_08_be32
        if child_start < parsed.header.metadata_start or child_end > parsed.header.content_start:
            raise BackupFormatError(
                f"directory 0x{record.offset:x} child range is outside metadata"
            )
        direct: list[int] = []
        for child_offset in range(child_start, child_end, parsed.header.record_size):
            child = by_offset.get(child_offset)
            if child is None:
                raise BackupFormatError(
                    f"directory 0x{record.offset:x} references missing record "
                    f"0x{child_offset:x}"
                )
            if child.name == "..":
                continue
            direct.append(child_offset)
            parent_by_child[child_offset] = record.offset
        children[record.offset] = tuple(direct)
        marker_offset = child_end
        marker = by_offset.get(marker_offset)
        if (
            marker is not None
            and marker.kind == "directory"
            and marker.name == ".."
            and marker.field_04_be32 == record.offset
        ):
            marker_by_directory[record.offset] = marker.offset
    # Parent-marker records repeat offsets in their own small tables.  For
    # reachable records, the parsed path is the authoritative parent
    # relationship; use it to prevent a marker table from overwriting the
    # actual tree edge above.
    path_to_offset = {path: offset for offset, path in parsed.paths.items()}
    for offset, path in parsed.paths.items():
        if len(path) > 1:
            parent = path_to_offset.get(path[:-1])
            if parent is not None:
                parent_by_child[offset] = parent
    return children, parent_by_child, marker_by_directory


def _selected(record: BackupRecord, path: tuple[str, ...], roots: Optional[set[str]]) -> bool:
    return roots is None or (len(path) >= 2 and path[1] in roots)


def _file_details(
    parsed: ParsedBackupBlob,
    record: BackupRecord,
) -> dict[str, Any]:
    prefix, payload = parsed.payload_parts(record)
    content_start = parsed.header.content_start + record.field_04_be32
    payload_start = content_start + len(prefix)
    file_starts = sorted(
        parsed.header.content_start + candidate.field_04_be32
        for candidate in parsed.records
        if candidate.kind == "file" and candidate.offset in parsed.paths
    )
    index = file_starts.index(content_start)
    next_start = (
        file_starts[index + 1]
        if index + 1 < len(file_starts)
        else parsed.header.content_start + parsed.header.content_length
    )
    aligned_segment = _align4(len(prefix) + len(payload))
    gap_after = next_start - (content_start + aligned_segment)
    if gap_after < 0:
        raise BackupFormatError(
            f"file 0x{record.offset:x} overlaps the next content segment"
        )
    return {
        "payload_offset": payload_start,
        "payload_length": len(payload),
        "payload_sha256": _sha256(payload),
        "native_prefix_length": len(prefix),
        "native_prefix_sha256": _sha256(prefix),
        "aligned_segment_length": aligned_segment,
        "alignment_padding_bytes": aligned_segment - len(prefix) - len(payload),
        "content_gap_after_bytes": gap_after,
        "read_state": record.read_state,
    }


def inventory_records(
    parsed: ParsedBackupBlob,
    *,
    root_names: Optional[Iterable[str]] = None,
) -> dict[str, Any]:
    """Return a JSON-safe deterministic inventory of reachable backup records.

    ``root_names`` limits the result to complete subtrees below ``root``.  The
    returned offsets and relationships are device-resident facts.  Sidecar or
    Manager-source membership must be recorded separately by the caller.
    """

    if not isinstance(parsed, ParsedBackupBlob):
        raise TypeError("parsed must be a ParsedBackupBlob")
    roots = None if root_names is None else set(root_names)
    if roots is not None and any(not isinstance(root, str) or not root for root in roots):
        raise ValueError("root_names must contain non-empty strings")
    children, parent_by_child, marker_by_directory = _relationship_maps(parsed)
    records: list[dict[str, Any]] = []
    for record in parsed.records:
        path = parsed.paths.get(record.offset)
        if path is None or not _selected(record, path, roots):
            continue
        direct_children = children.get(record.offset, ())
        siblings = children.get(parent_by_child.get(record.offset, -1), ())
        sibling_index = siblings.index(record.offset) if record.offset in siblings else None
        entry: dict[str, Any] = {
            "offset": record.offset,
            "path": _path_text(path),
            "kind": record.kind,
            "flag": f"0x{record.flag:02x}",
            "extension": record.extension,
            "field_04": f"0x{record.field_04_be32:08x}",
            "field_08": f"0x{record.field_08_be32:08x}",
            "timestamp_be32": f"0x{record.timestamp_be32:08x}",
            "field_10": f"0x{record.field_10_be32:08x}",
            "field_14": f"0x{record.field_14_be32:08x}",
            "timestamp_utc": record.timestamp_be32,
            "parent_offset": parent_by_child.get(record.offset),
            "child_offsets": list(direct_children),
            "parent_marker_offset": marker_by_directory.get(record.offset),
            "sibling_index": sibling_index,
            "previous_sibling_offset": (
                siblings[sibling_index - 1] if sibling_index not in (None, 0) else None
            ),
            "next_sibling_offset": (
                siblings[sibling_index + 1]
                if sibling_index is not None and sibling_index + 1 < len(siblings)
                else None
            ),
        }
        if record.kind == "file":
            entry["file"] = _file_details(parsed, record)
        records.append(entry)
    records.sort(key=lambda item: item["offset"])
    return {
        "format": PREPARED_EVIDENCE_FORMAT,
        "blob_sha256": _sha256(parsed.data),
        "blob_bytes": len(parsed.data),
        "header": {
            "record_size": parsed.header.record_size,
            "metadata_start": parsed.header.metadata_start,
            "metadata_length": parsed.header.metadata_length,
            "content_start": parsed.header.content_start,
            "content_length": parsed.header.content_length,
            "total_length": parsed.header.total_length,
        },
        "selected_root_names": sorted(roots) if roots is not None else None,
        "summary": {
            "records": len(records),
            "directories": sum(item["kind"] == "directory" for item in records),
            "files": sum(item["kind"] == "file" for item in records),
            "extensions": dict(sorted(Counter(item["extension"] for item in records if item["kind"] == "file").items())),
        },
        "records": records,
    }


def canonical_inventory_sha256(inventory: Mapping[str, Any]) -> str:
    """Hash an inventory using deterministic UTF-8 JSON serialization."""

    encoded = json.dumps(
        inventory,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256(encoded)


__all__ = [
    "PREPARED_EVIDENCE_FORMAT",
    "canonical_inventory_sha256",
    "inventory_records",
]
