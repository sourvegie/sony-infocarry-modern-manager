"""Pure offline deletion modeling for one existing ordinary TXT record.

This module deliberately does not know about USB, backup directories, fixed
state response objects, or authorization.  It transforms one already parsed
and checksum-validated dynamic model using the established structural
repacker, then proves the path, pointer, timestamp, payload, and unknown-byte
invariants that the provisional modern deletion policy permits.

The legacy Manager rewrote shared timestamps during the observed deletion, but
the causal rule is unresolved.  The modern provisional policy therefore
preserves every surviving timestamp exactly and removes only the deleted
record's metadata, without claiming legacy equivalence.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping, Optional

from .backup_format import BackupFormatError, ParsedBackupBlob, parse_backup_blob
from .backup_repack import BackupRepackError, delete_existing_file


DELETE_MODEL_FORMAT = "infocarry-offline-delete-model-v1"
_CONTENT_ALIGNMENT = 4


class DeleteModelError(ValueError):
    """Raised when a safe one-record offline deletion cannot be built."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _path_for(parsed: ParsedBackupBlob, record: Any) -> Optional[str]:
    parts = parsed.paths.get(record.offset)
    if parts is None:
        return None
    path = "\\".join(parts)
    return f"{path}.{record.extension}" if record.extension else path


def _payloads(parsed: ParsedBackupBlob) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for record in parsed.records:
        if record.kind != "file" or record.offset not in parsed.paths:
            continue
        path = _path_for(parsed, record)
        if path is None:
            raise DeleteModelError(f"reachable file 0x{record.offset:x} has no path")
        if path in result:
            raise DeleteModelError(f"reachable file path is ambiguous: {path}")
        try:
            _prefix, payload = parsed.payload_parts(record)
        except BackupFormatError as exc:
            raise DeleteModelError(f"file payload is malformed at 0x{record.offset:x}: {exc}") from exc
        result[path] = payload
    return result


def _content_geometry(parsed: ParsedBackupBlob, record: Any) -> tuple[int, int, int, int]:
    try:
        prefix, payload = parsed.payload_parts(record)
    except BackupFormatError as exc:
        raise DeleteModelError(f"target payload is malformed: {exc}") from exc
    start = record.field_04_be32
    end = start + len(prefix) + len(payload)
    aligned_end = end + ((-end) % _CONTENT_ALIGNMENT)
    if start < 0 or aligned_end > parsed.header.content_length:
        raise DeleteModelError("target content segment is outside the content region")
    if start % _CONTENT_ALIGNMENT:
        raise DeleteModelError("target content offset is not four-byte aligned")
    for other in parsed.records:
        if other.kind != "file" or other.offset == record.offset:
            continue
        try:
            other_prefix, other_payload = parsed.payload_parts(other)
        except BackupFormatError as exc:
            raise DeleteModelError(f"unrelated file payload is malformed: {exc}") from exc
        other_start = other.field_04_be32
        other_end = other_start + len(other_prefix) + len(other_payload)
        if other_start < aligned_end and other_end > start:
            raise DeleteModelError("target overlaps another file segment or alignment gap")
    return start, end, aligned_end, aligned_end - start


def _parent_offset(parsed: ParsedBackupBlob, target: Any) -> int:
    target_path = parsed.paths.get(target.offset)
    if target_path is None:
        raise DeleteModelError("target is not reachable")
    candidates = [
        offset
        for offset, path in parsed.paths.items()
        if path == target_path[:-1] and parsed.record_at(offset).kind == "directory"
    ]
    if len(candidates) != 1:
        raise DeleteModelError("target parent is missing or ambiguous")
    return candidates[0]


def _expected_survivor_raw(
    parsed: ParsedBackupBlob,
    record: Any,
    *,
    target_offset: int,
    aligned_end: int,
    removed_content_length: int,
    parent_offset: int,
) -> bytes:
    """Apply only the established pointer changes to one copied raw record."""

    record_size = parsed.header.record_size
    raw = bytearray.fromhex(record.raw_hex)
    if record.kind == "directory":
        if record.field_04_be32 >= target_offset:
            raw[0x04:0x08] = (record.field_04_be32 - record_size).to_bytes(4, "big")
        if record.offset == parent_offset:
            if record.field_08_be32 < record_size:
                raise DeleteModelError("parent child table cannot be shortened safely")
            raw[0x08:0x0C] = (record.field_08_be32 - record_size).to_bytes(4, "big")
        elif record.name == ".." and record.field_08_be32 in {
            target_offset,
            target_offset + record_size,
        }:
            raw[0x08:0x0C] = (record.field_08_be32 - record_size).to_bytes(4, "big")
    elif record.kind == "file" and record.field_04_be32 >= aligned_end:
        raw[0x04:0x08] = (
            record.field_04_be32 - removed_content_length
        ).to_bytes(4, "big")
    return bytes(raw)


@dataclass(frozen=True)
class OfflineDeleteModel:
    """Deterministic candidate for one existing ordinary TXT leaf."""

    source_blob_sha256: str
    candidate_blob: bytes
    target_path: str
    target_record_offset: int
    target_payload_sha256: str
    audit: Mapping[str, Any]

    @property
    def candidate_blob_sha256(self) -> str:
        return _sha256(self.candidate_blob)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.audit)


def build_one_txt_delete_model(
    parsed: ParsedBackupBlob,
    target_path: str,
    target_record_offset: int,
) -> OfflineDeleteModel:
    """Build and independently validate a one-record TXT deletion candidate."""

    if not isinstance(parsed, ParsedBackupBlob):
        raise DeleteModelError("parsed backup model is required")
    if not isinstance(target_path, str) or not target_path or "\x00" in target_path:
        raise DeleteModelError("target path must be a non-empty NUL-free string")
    if isinstance(target_record_offset, bool) or not isinstance(target_record_offset, int):
        raise DeleteModelError("target record offset must be an integer")
    if (
        target_record_offset < parsed.header.metadata_start
        or (target_record_offset - parsed.header.metadata_start) % parsed.header.record_size
    ):
        raise DeleteModelError("target record offset is not metadata-record aligned")
    try:
        target = parsed.record_at(target_record_offset)
    except BackupFormatError as exc:
        raise DeleteModelError(f"target record cannot be resolved: {exc}") from exc
    actual_path = _path_for(parsed, target)
    if actual_path is None or actual_path != target_path:
        raise DeleteModelError("target path does not match the exact reachable record")
    if sum(_path_for(parsed, record) == target_path for record in parsed.records) != 1:
        raise DeleteModelError("target path is ambiguous")
    if target.name == "root" and target.kind == "directory":
        raise DeleteModelError("root record cannot be deleted")
    if target.kind != "file":
        raise DeleteModelError("only an existing ordinary TXT file can be deleted")
    if target.extension.lower() != "txt":
        raise DeleteModelError("only an existing ordinary TXT file can be deleted")
    if target.name in {".", ".."}:
        raise DeleteModelError("directory marker cannot be deleted")

    before_payloads = _payloads(parsed)
    if target_path not in before_payloads:
        raise DeleteModelError("target payload is not reachable")
    segment_start, segment_end, aligned_end, removed_content_length = _content_geometry(
        parsed, target
    )
    parent_offset = _parent_offset(parsed, target)
    source_blob_sha256 = _sha256(parsed.data)
    try:
        candidate_blob = delete_existing_file(parsed, target_record_offset)
    except BackupRepackError as exc:
        raise DeleteModelError(f"structural deletion failed: {exc}") from exc
    try:
        after = parse_backup_blob(candidate_blob)
    except BackupFormatError as exc:
        raise DeleteModelError(f"candidate failed independent parsing: {exc}") from exc

    record_size = parsed.header.record_size
    if len(after.records) != len(parsed.records) - 1:
        raise DeleteModelError("candidate record count did not decrease by exactly one")
    before_paths = {
        _path_for(parsed, record) for record in parsed.records if record.offset in parsed.paths
    }
    after_paths = {
        _path_for(after, record) for record in after.records if record.offset in after.paths
    }
    if before_paths - after_paths != {target_path} or after_paths - before_paths:
        raise DeleteModelError("candidate path delta is not exactly one target removal")
    if len(after_paths) != len(after.paths):
        raise DeleteModelError("candidate contains ambiguous reachable paths")

    after_payloads = _payloads(after)
    if set(before_payloads) - {target_path} != set(after_payloads):
        raise DeleteModelError("candidate does not preserve every surviving file path")
    for path, payload in after_payloads.items():
        if payload != before_payloads[path]:
            raise DeleteModelError(f"candidate changed surviving payload: {path}")

    for record in parsed.records:
        if record.offset == target_record_offset:
            continue
        expected_offset = (
            record.offset
            if record.offset < target_record_offset
            else record.offset - record_size
        )
        try:
            actual = after.record_at(expected_offset)
        except BackupFormatError as exc:
            raise DeleteModelError(
                f"surviving record 0x{record.offset:x} did not rebase safely"
            ) from exc
        expected_raw = _expected_survivor_raw(
            parsed,
            record,
            target_offset=target_record_offset,
            aligned_end=aligned_end,
            removed_content_length=removed_content_length,
            parent_offset=parent_offset,
        )
        if actual.raw_hex != expected_raw.hex():
            raise DeleteModelError(
                f"unrelated or unknown metadata bytes changed at 0x{record.offset:x}"
            )
        if actual.timestamp_be32 != record.timestamp_be32:
            raise DeleteModelError("surviving record timestamps were not preserved")
        if actual.field_04_be32 % _CONTENT_ALIGNMENT and actual.kind == "file":
            raise DeleteModelError("candidate file content offset is not aligned")
        if actual.kind == "directory" and actual.field_08_be32 % record_size:
            raise DeleteModelError("candidate directory child table is not aligned")

    target_payload_sha256 = _sha256(before_payloads[target_path])
    preserved_payload_hashes = {
        path: _sha256(payload) for path, payload in sorted(after_payloads.items())
    }
    audit = {
        "format": DELETE_MODEL_FORMAT,
        "state": "offline_candidate",
        "usb_transmission_performed": False,
        "operation": "delete_one_existing_txt",
        "target": {
            "path": target_path,
            "record_offset_hex": f"0x{target_record_offset:08x}",
            "payload_sha256": target_payload_sha256,
            "payload_length": len(before_payloads[target_path]),
        },
        "baseline": {
            "blob_sha256": source_blob_sha256,
            "model_length": len(parsed.data),
            "record_count": len(parsed.records),
        },
        "candidate": {
            "blob_sha256": _sha256(candidate_blob),
            "model_length": len(candidate_blob),
            "record_count": len(after.records),
            "removed_paths": [target_path],
            "added_paths": [],
        },
        "allocation": {
            "record_size": record_size,
            "metadata_delta": -record_size,
            "content_segment_start": segment_start,
            "content_segment_end": segment_end,
            "aligned_content_end": aligned_end,
            "removed_aligned_bytes": removed_content_length,
            "model_delta": len(candidate_blob) - len(parsed.data),
            "parent_record_offset_hex": f"0x{parent_offset:08x}",
        },
        "timestamps": {
            "policy": "preserve_surviving_timestamps",
            "classification": "provisional_modern_safety_policy",
            "legacy_generation_rule": "unresolved",
            "removed_record_timestamp": target.timestamp_be32,
        },
        "preservation": {
            "surviving_payload_count": len(after_payloads),
            "surviving_payload_sha256": preserved_payload_hashes,
            "unknown_record_fields": "preserved_except_proven_pointer_rebasing",
            "source_unchanged": True,
        },
        "rules": {
            "observed": [
                "metadata records use the validated header record size",
                "content removal ends at the observed four-byte alignment boundary",
            ],
            "inferred": [
                "the existing structural pointer-remapping rules apply to this parsed tree"
            ],
            "unresolved": [
                "legacy operation-wide timestamp generation",
                "general fixed-state reference rebasing",
            ],
        },
        "safety": {
            "device_accessed": False,
            "candidate_bytes_included": False,
            "automatic_retry_allowed": False,
        },
    }
    return OfflineDeleteModel(
        source_blob_sha256=source_blob_sha256,
        candidate_blob=candidate_blob,
        target_path=target_path,
        target_record_offset=target_record_offset,
        target_payload_sha256=target_payload_sha256,
        audit=audit,
    )


__all__ = [
    "DELETE_MODEL_FORMAT",
    "DeleteModelError",
    "OfflineDeleteModel",
    "build_one_txt_delete_model",
]
