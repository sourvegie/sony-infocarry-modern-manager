"""Offline construction of the captured one-folder/one-TXT package shape.

The Milestone I folder capture proves one narrow native layout: a new root
directory record, one leading ``..`` record, and one TXT child are inserted
before the existing root boundary.  This module reproduces that captured
shape from a baseline blob and a preserved post-capture template.  It does
not infer a general directory grammar, generate sidecars, or access USB.

Timestamps remain an explicit caller input because the available evidence
does not establish their generation rule.  Omitting a timestamp is therefore
an intentional failure, not a request to use current time or a copied value.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping, Optional

from .backup_format import (
    BackupFormatError,
    BackupRecord,
    ParsedBackupBlob,
    calculate_backup_checksum,
    parse_backup_blob,
)
from .text_authoring import TextAuthoringError, encode_cp932_text


PREPARED_FOLDER_FORMAT = "infocarry-offline-prepared-folder-v1"
MODERN_PREPARED_FOLDER_FORMAT = "infocarry-modern-constrained-folder-v1"
_RECORD_SIZE = 0x40
_TEXT_PREFIX_SIZE = 0x20


class PreparedFolderError(ValueError):
    """Raised when the narrow captured folder shape cannot be reproduced."""


@dataclass(frozen=True)
class PreparedFolderCandidate:
    """An offline candidate blob and its audit report."""

    candidate_blob: bytes
    audit: Mapping[str, Any]

    def audit_dict(self) -> dict[str, Any]:
        return dict(self.audit)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _u32(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFFFFFFFF:
        raise PreparedFolderError(f"{label} must fit an unsigned 32-bit integer")


def _encode_component(value: str, label: str) -> bytes:
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or "\x00" in value
        or "\\" in value
        or "/" in value
        or value != value.strip()
    ):
        raise PreparedFolderError(
            f"{label} must be one trimmed non-traversal path component without NUL or separators"
        )
    try:
        encoded = value.encode("cp932", errors="strict")
    except UnicodeEncodeError as exc:
        raise PreparedFolderError(f"{label} is not representable in CP932") from exc
    if len(encoded) >= 0x28:
        raise PreparedFolderError(f"{label} must leave room for the metadata NUL terminator")
    return encoded


def _child_basename(filename: str) -> tuple[str, bytes]:
    if not isinstance(filename, str) or not filename.endswith(".txt"):
        raise PreparedFolderError("child_filename must be one root-folder TXT name ending in .txt")
    basename = filename[:-4]
    if not basename or "." in basename:
        raise PreparedFolderError("child_filename must have one unambiguous TXT basename")
    return basename, _encode_component(basename, "child filename")


def _replace_name(raw: bytearray, encoded: bytes) -> None:
    suffix_start = 0x18 + len(encoded) + 1
    raw[0x18:0x40] = encoded + b"\x00" + raw[suffix_start:0x40]


def _raw_record(record: BackupRecord) -> bytearray:
    return bytearray.fromhex(record.raw_hex)


def _aligned_segment_length(prefix: bytes, payload: bytes) -> int:
    length = len(prefix) + len(payload)
    return length + ((-length) % 4)


def _template_parts(
    template: ParsedBackupBlob,
    template_folder_path: tuple[str, ...],
    template_child_path: tuple[str, ...],
) -> tuple[BackupRecord, BackupRecord, BackupRecord, bytes]:
    folder_offsets = [offset for offset, path in template.paths.items() if path == template_folder_path]
    child_offsets = [offset for offset, path in template.paths.items() if path == template_child_path]
    if len(folder_offsets) != 1 or len(child_offsets) != 1:
        raise PreparedFolderError("template must contain exactly one folder and one TXT child at the requested paths")
    folder = template.record_at(folder_offsets[0])
    child = template.record_at(child_offsets[0])
    if folder.kind != "directory" or folder.name == ".." or template_folder_path[:-1] != ("root",):
        raise PreparedFolderError("template folder must be a reachable root-level directory")
    if child.kind != "file" or child.extension.lower() != "txt" or child_offsets[0] != folder.offset + 2 * _RECORD_SIZE:
        raise PreparedFolderError("template child is not the captured TXT position")
    if folder.field_04_be32 != folder.offset or folder.field_08_be32 != 2 * _RECORD_SIZE:
        raise PreparedFolderError("template folder does not have the captured two-record child table")
    leading = template.record_at(folder.offset + _RECORD_SIZE)
    if leading.kind != "directory" or leading.name != ".." or leading.field_08_be32 != folder.offset:
        raise PreparedFolderError("template leading parent marker does not match the captured shape")
    prefix, _payload = template.payload_parts(child)
    if len(prefix) != _TEXT_PREFIX_SIZE:
        raise PreparedFolderError("template TXT child does not have the observed 32-byte native prefix")
    return folder, leading, child, prefix


def _validate_timestamp_map(
    parsed: ParsedBackupBlob,
    timestamps: Optional[Mapping[int, int]],
) -> Optional[dict[int, int]]:
    if timestamps is None:
        return None
    if not isinstance(timestamps, Mapping):
        raise PreparedFolderError("metadata_timestamps must be a mapping")
    expected = {record.offset for record in parsed.records}
    result: dict[int, int] = {}
    for offset, timestamp in timestamps.items():
        if isinstance(offset, bool) or not isinstance(offset, int) or offset not in expected:
            raise PreparedFolderError("metadata_timestamps must use every baseline record offset")
        _u32(timestamp, f"metadata timestamp at {_hex(offset)}")
        result[offset] = timestamp
    if set(result) != expected:
        raise PreparedFolderError("metadata_timestamps must contain exactly every baseline record offset")
    return result


def _preserve_paths(
    before: ParsedBackupBlob,
    after: ParsedBackupBlob,
    added_paths: set[tuple[str, ...]],
) -> dict[str, Any]:
    before_paths = set(before.paths.values())
    after_paths = set(after.paths.values())
    if after_paths != before_paths | added_paths:
        raise PreparedFolderError("candidate changed the reachable path set beyond the prepared folder")
    preserved_files = 0
    preserved_records = 0
    for path in sorted(before_paths):
        before_offset = next(offset for offset, value in before.paths.items() if value == path)
        after_offset = next(offset for offset, value in after.paths.items() if value == path)
        old = before.record_at(before_offset)
        new = after.record_at(after_offset)
        if (old.kind, old.extension, old.field_10_be32, old.field_14_be32, old.name) != (
            new.kind,
            new.extension,
            new.field_10_be32,
            new.field_14_be32,
            new.name,
        ):
            raise PreparedFolderError(f"candidate changed preserved metadata at {'\\'.join(path)}")
        if old.kind == "file":
            _old_prefix, old_payload = before.payload_parts(old)
            _new_prefix, new_payload = after.payload_parts(new)
            if old_payload != new_payload:
                raise PreparedFolderError(f"candidate changed preserved payload at {'\\'.join(path)}")
            if _old_prefix != _new_prefix:
                raise PreparedFolderError(f"candidate changed preserved native prefix at {'\\'.join(path)}")
            preserved_files += 1
        preserved_records += 1
    return {
        "preserved_reachable_records": preserved_records,
        "preserved_file_payloads": preserved_files,
        "unrelated_changes_verified": True,
    }


def _validate_template_shared_content(
    baseline: ParsedBackupBlob,
    template: ParsedBackupBlob,
    template_folder_path: tuple[str, ...],
    template_child_path: tuple[str, ...],
) -> dict[str, Any]:
    """Verify that the preserved post-capture template changed only the package."""

    baseline_paths = set(baseline.paths.values())
    # A later constrained modern smoke may start from the exact preserved
    # capture-7 post-add state.  In that case the template is being reused as
    # a structural template for a second, distinct package; it is not a
    # before/after pair for the current operation.  Requiring byte identity
    # keeps this exception narrow and prevents arbitrary fresh baselines from
    # being treated as proven folder geometry.
    if baseline.data == template.data:
        return {
            "template_baseline_exact": True,
            "shared_reachable_records": len(baseline.paths),
            "shared_file_payloads": sum(
                1
                for offset in baseline.paths
                if baseline.record_at(offset).kind == "file"
            ),
            "shared_content_verified": True,
        }
    expected_template_paths = baseline_paths | {template_folder_path, template_child_path}
    if set(template.paths.values()) != expected_template_paths:
        raise PreparedFolderError(
            "template must add exactly the captured folder and TXT child paths"
        )
    if len(template.records) != len(baseline.records) + 3:
        raise PreparedFolderError(
            "template must contain exactly three additional metadata records"
        )

    preserved_files = 0
    preserved_records = 0
    for path in sorted(baseline_paths):
        before_offsets = [offset for offset, value in baseline.paths.items() if value == path]
        after_offsets = [offset for offset, value in template.paths.items() if value == path]
        if len(before_offsets) != 1 or len(after_offsets) != 1:
            raise PreparedFolderError("template shared paths must remain uniquely reachable")
        before = baseline.record_at(before_offsets[0])
        after = template.record_at(after_offsets[0])
        if (before.kind, before.extension, before.field_10_be32, before.field_14_be32, before.name) != (
            after.kind,
            after.extension,
            after.field_10_be32,
            after.field_14_be32,
            after.name,
        ):
            raise PreparedFolderError(
                f"template changed preserved metadata at {'\\'.join(path)}"
            )
        if before.kind == "file":
            before_prefix, before_payload = baseline.payload_parts(before)
            after_prefix, after_payload = template.payload_parts(after)
            if before_prefix != after_prefix:
                raise PreparedFolderError(
                    f"template changed preserved native prefix at {'\\'.join(path)}"
                )
            if before_payload != after_payload:
                raise PreparedFolderError(
                    f"template changed preserved payload at {'\\'.join(path)}"
                )
            preserved_files += 1
        preserved_records += 1
    return {
        "template_baseline_exact": False,
        "shared_reachable_records": preserved_records,
        "shared_file_payloads": preserved_files,
        "shared_content_verified": True,
    }


def _build_root_folder_text_candidate(
    baseline: ParsedBackupBlob,
    template: ParsedBackupBlob,
    folder_name: str,
    child_filename: str,
    text: str,
    *,
    timestamp_be32: Optional[int],
    metadata_timestamps: Optional[Mapping[int, int]] = None,
    preserve_existing_timestamps: bool = False,
    policy_name: str = "legacy_golden_fixture",
    format_name: str = PREPARED_FOLDER_FORMAT,
    template_folder_path: tuple[str, ...] = ("root", "IC_I_FOLDER_20260823_01"),
    template_child_path: tuple[str, ...] = ("root", "IC_I_FOLDER_20260823_01", "chapter"),
) -> PreparedFolderCandidate:
    """Build one captured-shape root folder containing one TXT child.

    ``template`` must be a preserved post-operation blob with the exact
    three-record folder shape observed in capture 7.  ``baseline`` is a
    separate complete pre-operation blob.  The caller must supply the
    timestamp because no safe generation rule is established.
    """

    if not isinstance(baseline, ParsedBackupBlob) or not isinstance(template, ParsedBackupBlob):
        raise PreparedFolderError("baseline and template must be ParsedBackupBlob values")
    if timestamp_be32 is None:
        raise PreparedFolderError("new-record timestamp must be explicit")
    _u32(timestamp_be32, "timestamp_be32")
    folder_encoded = _encode_component(folder_name, "folder name")
    child_basename, child_encoded = _child_basename(child_filename)
    timestamps = _validate_timestamp_map(baseline, metadata_timestamps)
    if preserve_existing_timestamps and timestamps is not None:
        raise PreparedFolderError(
            "modern policy preserves existing timestamps and does not accept a rewrite map"
        )
    folder_template, leading_template, child_template, prefix = _template_parts(
        template, template_folder_path, template_child_path
    )
    template_validation = _validate_template_shared_content(
        baseline,
        template,
        template_folder_path,
        template_child_path,
    )

    root = baseline.record_at(baseline.header.metadata_start)
    if root.kind != "directory" or root.name != "root":
        raise PreparedFolderError("baseline does not begin with the root directory")
    target_folder_path = ("root", folder_name)
    target_child_path = target_folder_path + (child_basename,)
    if target_folder_path in baseline.paths.values() or target_child_path in baseline.paths.values():
        raise PreparedFolderError("prepared folder or child already exists in baseline")

    root_marker_offset = root.field_04_be32 + _RECORD_SIZE + root.field_08_be32
    try:
        root_marker = baseline.record_at(root_marker_offset)
    except BackupFormatError as exc:
        raise PreparedFolderError("baseline root does not have the captured insertion boundary") from exc
    if root_marker.kind != "directory" or root_marker.name != "..":
        raise PreparedFolderError("baseline root insertion boundary is not a parent marker")

    content = baseline.data[
        baseline.header.content_start : baseline.header.content_start + baseline.header.content_length
    ]
    reachable_records = tuple(
        (path, baseline.record_at(offset))
        for offset, path in baseline.paths.items()
    )
    root_files = [
        record
        for path, record in reachable_records
        if len(path) == 2 and record.kind == "file"
    ]
    content_insert_at = 0
    for record in root_files:
        file_prefix, file_payload = baseline.payload_parts(record)
        start = record.field_04_be32
        end = start + _aligned_segment_length(file_prefix, file_payload)
        if end > len(content):
            raise PreparedFolderError("baseline root-level TXT content segment is outside the content region")
        content_insert_at = max(content_insert_at, end)
    later_files = [
        record.field_04_be32
        for path, record in reachable_records
        if len(path) > 2 and record.kind == "file"
    ]
    if later_files and min(later_files) != content_insert_at:
        raise PreparedFolderError("baseline content has an unproven gap at the captured insertion boundary")

    try:
        authored = encode_cp932_text(text)
    except TextAuthoringError as exc:
        raise PreparedFolderError(f"prepared TXT failed strict CP932/CRLF authoring: {exc}") from exc
    new_segment_length = _aligned_segment_length(prefix, authored.payload)
    content_delta = new_segment_length
    metadata_delta = 3 * _RECORD_SIZE
    insertion_index = (root_marker_offset - baseline.header.metadata_start) // _RECORD_SIZE

    shifted: list[bytes] = []
    for record in baseline.records:
        raw = _raw_record(record)
        if timestamps is not None:
            raw[0x0C:0x10] = timestamps[record.offset].to_bytes(4, "big")
        if record.offset == root.offset:
            raw[0x08:0x0C] = (record.field_08_be32 + _RECORD_SIZE).to_bytes(4, "big")
        elif record.name == ".." and record.field_08_be32 == root_marker.field_08_be32:
            # The captured Manager updates the shared root-table width in
            # every observed leading ``..`` marker, not only the marker at
            # the insertion boundary.  Keep this narrow rule explicit.
            raw[0x08:0x0C] = (record.field_08_be32 + _RECORD_SIZE).to_bytes(4, "big")
        if record.kind == "directory":
            if record.field_04_be32 + _RECORD_SIZE >= root_marker_offset:
                raw[0x04:0x08] = (record.field_04_be32 + metadata_delta).to_bytes(4, "big")
        elif record.kind == "file" and record.field_04_be32 >= content_insert_at:
            raw[0x04:0x08] = (record.field_04_be32 + content_delta).to_bytes(4, "big")
        shifted.append(bytes(raw))

    inserted_folder_offset = root_marker_offset
    folder_raw = _raw_record(folder_template)
    folder_raw[0x04:0x08] = inserted_folder_offset.to_bytes(4, "big")
    folder_raw[0x08:0x0C] = (2 * _RECORD_SIZE).to_bytes(4, "big")
    folder_raw[0x0C:0x10] = timestamp_be32.to_bytes(4, "big")
    _replace_name(folder_raw, folder_encoded)

    leading_raw = _raw_record(leading_template)
    leading_raw[0x04:0x08] = root.field_04_be32.to_bytes(4, "big")
    leading_raw[0x08:0x0C] = inserted_folder_offset.to_bytes(4, "big")
    leading_raw[0x0C:0x10] = timestamp_be32.to_bytes(4, "big")

    child_raw = _raw_record(child_template)
    child_raw[0x04:0x08] = content_insert_at.to_bytes(4, "big")
    child_raw[0x08:0x0C] = len(authored.payload).to_bytes(4, "big")
    child_raw[0x0C:0x10] = timestamp_be32.to_bytes(4, "big")
    _replace_name(child_raw, child_encoded)

    metadata_records: list[bytes] = []
    for index, raw in enumerate(shifted):
        if index == insertion_index:
            metadata_records.extend((bytes(folder_raw), bytes(leading_raw), bytes(child_raw)))
        metadata_records.append(raw)
    metadata = b"".join(metadata_records)
    rebuilt_content = (
        content[:content_insert_at]
        + prefix
        + authored.payload
        + b"\xff" * (new_segment_length - len(prefix) - len(authored.payload))
        + content[content_insert_at:]
    )

    header = bytearray(baseline.data[: baseline.header.metadata_start])
    new_content_start = baseline.header.content_start + metadata_delta
    header[0x2C:0x30] = len(metadata).to_bytes(4, "big")
    header[0x30:0x34] = new_content_start.to_bytes(4, "big")
    header[0x34:0x38] = len(rebuilt_content).to_bytes(4, "big")
    total_length = len(header) + len(metadata) + len(rebuilt_content) + 4
    header[0x18:0x1C] = (total_length - 1).to_bytes(4, "big")
    header[0x38:0x3C] = total_length.to_bytes(4, "big")
    output = bytearray(bytes(header) + metadata + rebuilt_content + baseline.data[-4:])
    output[0x1C:0x20] = b"\x00" * 4
    output[0x1C:0x20] = calculate_backup_checksum(bytes(output)).to_bytes(4, "big")
    candidate_blob = bytes(output)
    try:
        candidate = parse_backup_blob(candidate_blob)
    except BackupFormatError as exc:
        raise PreparedFolderError(f"prepared folder candidate failed validation: {exc}") from exc

    preservation = _preserve_paths(
        baseline,
        candidate,
        {target_folder_path, target_child_path},
    )
    child_offsets = [offset for offset, path in candidate.paths.items() if path == target_child_path]
    if len(child_offsets) != 1:
        raise PreparedFolderError("candidate did not contain exactly one prepared TXT child")
    child = candidate.record_at(child_offsets[0])
    child_prefix, child_payload = candidate.payload_parts(child)
    if child_payload != authored.payload or child_prefix != prefix:
        raise PreparedFolderError("candidate child payload or native prefix does not match the prepared source")
    if len(candidate.records) != len(baseline.records) + 3:
        raise PreparedFolderError("candidate metadata did not grow by exactly three records")

    audit = {
        "format": format_name,
        "state": "offline_only",
        "usb_transmission_performed": False,
        "baseline_blob_sha256": _sha256(baseline.data),
        "template_blob_sha256": _sha256(template.data),
        "candidate_blob_sha256": _sha256(candidate_blob),
        "template_validation": template_validation,
        "timestamp_policy": policy_name,
        "new_record_timestamp_be32": _hex(timestamp_be32),
        "existing_record_timestamps": (
            "preserved"
            if preserve_existing_timestamps
            else "copied_from_explicit_legacy_map_or_baseline"
        ),
        "timestamp_assignment": "explicit_frozen_new_records_only"
        if preserve_existing_timestamps
        else "explicit_new_record_plus_legacy_map",
        "timestamp_generation_resolved": False,
        "source": {
            "encoding": "cp932",
            "newline_policy": "crlf",
            "encoded_payload_bytes": len(authored.payload),
            "encoded_payload_sha256": _sha256(authored.payload),
        },
        "target": {
            "folder_path": "root\\" + folder_name,
            "child_path": "root\\" + folder_name + "\\" + child_filename,
            "folder_record_offset_hex": _hex(inserted_folder_offset),
            "child_record_offset_hex": _hex(child.offset),
            "child_field_04_hex": _hex(child.field_04_be32),
            "child_payload_offset_hex": _hex(candidate.header.content_start + child.field_04_be32 + len(child_prefix)),
            "child_payload_length": len(child_payload),
            "child_native_prefix_sha256": _sha256(child_prefix),
        },
        "allocation": {
            "metadata_records_added": 3,
            "metadata_bytes_added": metadata_delta,
            "content_aligned_bytes_added": content_delta,
            "candidate_growth_bytes": len(candidate_blob) - len(baseline.data),
            "content_insert_offset_hex": _hex(content_insert_at),
            "alignment_padding_bytes": new_segment_length - len(prefix) - len(authored.payload),
        },
        "preservation": preservation,
        "assumptions": [
            "The folder and leading parent-marker bytes are copied from the preserved capture template.",
            "The native 32-byte TXT wrapper is copied from the preserved capture template.",
            "The observed root insertion boundary and three-record metadata shape are not generalized beyond this scope.",
            "Timestamp generation remains unresolved and is never synthesized by this builder.",
            "Manager sidecars and fixed-state responses are not constructed by this device-blob builder.",
        ],
    }
    return PreparedFolderCandidate(candidate_blob=candidate_blob, audit=audit)


def build_root_folder_text_candidate(
    baseline: ParsedBackupBlob,
    template: ParsedBackupBlob,
    folder_name: str,
    child_filename: str,
    text: str,
    *,
    timestamp_be32: Optional[int],
    metadata_timestamps: Optional[Mapping[int, int]] = None,
    template_folder_path: tuple[str, ...] = ("root", "IC_I_FOLDER_20260823_01"),
    template_child_path: tuple[str, ...] = ("root", "IC_I_FOLDER_20260823_01", "chapter"),
) -> PreparedFolderCandidate:
    """Reproduce the legacy capture-7 shape with its explicit timestamp map."""

    return _build_root_folder_text_candidate(
        baseline,
        template,
        folder_name,
        child_filename,
        text,
        timestamp_be32=timestamp_be32,
        metadata_timestamps=metadata_timestamps,
        preserve_existing_timestamps=False,
        policy_name="legacy_golden_fixture",
        format_name=PREPARED_FOLDER_FORMAT,
        template_folder_path=template_folder_path,
        template_child_path=template_child_path,
    )


def build_modern_root_folder_text_candidate(
    baseline: ParsedBackupBlob,
    template: ParsedBackupBlob,
    folder_name: str,
    child_filename: str,
    text: str,
    *,
    new_record_timestamp_be32: Optional[int],
    template_folder_path: tuple[str, ...] = ("root", "IC_I_FOLDER_20260823_01"),
    template_child_path: tuple[str, ...] = ("root", "IC_I_FOLDER_20260823_01", "chapter"),
) -> PreparedFolderCandidate:
    """Build the constrained modern one-folder/one-TXT offline candidate.

    Existing record timestamps are preserved byte-for-byte.  The one explicit
    frozen timestamp is assigned only to the new folder, its leading parent
    marker, and its TXT child.  This is a modern experimental policy, not a
    reconstruction of the legacy operation-wide timestamp rewrite.
    """

    return _build_root_folder_text_candidate(
        baseline,
        template,
        folder_name,
        child_filename,
        text,
        timestamp_be32=new_record_timestamp_be32,
        metadata_timestamps=None,
        preserve_existing_timestamps=True,
        policy_name="modern_constrained_preserve_existing_explicit_new_records",
        format_name=MODERN_PREPARED_FOLDER_FORMAT,
        template_folder_path=template_folder_path,
        template_child_path=template_child_path,
    )


__all__ = [
    "MODERN_PREPARED_FOLDER_FORMAT",
    "PREPARED_FOLDER_FORMAT",
    "PreparedFolderCandidate",
    "PreparedFolderError",
    "build_modern_root_folder_text_candidate",
    "build_root_folder_text_candidate",
]
