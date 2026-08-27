"""Offline candidate construction for one root folder with ordered children.

The builder is deliberately narrower than a general ebook writer.  It reuses
the capture-7 folder geometry and requires an existing native record template
for every child kind.  It never invents a TXT or BMP wrapper, touches USB, or
assigns Manager-side state.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping, Optional, Sequence

from .backup_format import BackupFormatError, BackupRecord, ParsedBackupBlob, parse_backup_blob, calculate_backup_checksum
from .capacity import CapacitySemanticsError, assess_total_capacity
from .capacity_evidence import NativeCapacityEvidence, NativeCapacityResponse, NativeCapacityEvidenceError
from .prepared_fixed_state import PreparedFixedStateAssessment, PreparedFixedStateError, PreparedFixedStateSnapshot, assess_prepared_fixed_state
from .prepared_media_package import PreparedBitmapSourceItem, PreparedMediaPackage
from .prepared_multi_text import PreparedTextPackageSet, PreparedTextSourceItem
from .prepared_folder import PreparedFolderError, _aligned_segment_length, _encode_component, _raw_record, _replace_name
from .write_artifact import ProspectiveWriteTransaction, WriteArtifactError, build_staging_range
from .write_gate import VerifiedBackup


PREPARED_MULTI_CANDIDATE_FORMAT = "infocarry-modern-ordered-package-candidate-v1"
_RECORD_SIZE = 0x40
_TEXT_PREFIX_SIZE = 0x20
_DYNAMIC_BLOB_KEY = "0x8004:backup-blob"


class PreparedMultiCandidateError(ValueError):
    """Raised when the narrow ordered package candidate is unsafe."""


PreparedPackageInput = PreparedTextPackageSet | PreparedMediaPackage


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _read_verified_blob(backup: VerifiedBackup) -> bytes:
    filename = backup.object_filename(_DYNAMIC_BLOB_KEY)
    expected = backup.object_sha256(_DYNAMIC_BLOB_KEY)
    if filename is None or expected is None or expected != backup.blob_sha256:
        raise PreparedMultiCandidateError("verified backup is missing its dynamic blob binding")
    try:
        data = (backup.directory / filename).read_bytes()
    except OSError as exc:
        raise PreparedMultiCandidateError(f"could not read verified backup dynamic blob: {exc}") from exc
    if _sha256(data) != expected:
        raise PreparedMultiCandidateError("verified backup dynamic blob changed after verification")
    return data


def _items(package: PreparedPackageInput) -> tuple[PreparedTextSourceItem | PreparedBitmapSourceItem, ...]:
    if not isinstance(package, (PreparedTextPackageSet, PreparedMediaPackage)):
        raise PreparedMultiCandidateError("package must be an ordered TXT or TXT/BMP package")
    values = tuple(package.items)
    if len(values) < 2:
        raise PreparedMultiCandidateError("ordered device package requires at least two children")
    return values


def _item_payload(item: PreparedTextSourceItem | PreparedBitmapSourceItem) -> bytes:
    if isinstance(item, PreparedTextSourceItem):
        return item.authored.payload
    if isinstance(item, PreparedBitmapSourceItem):
        return item.source_bytes
    raise PreparedMultiCandidateError("package item has an unsupported type")


def _item_basename(item: PreparedTextSourceItem | PreparedBitmapSourceItem) -> str:
    suffix = ".txt" if item.kind == "txt" else ".bmp"
    name = item.name
    if not name.lower().endswith(suffix) or not name[:-len(suffix)] or "." in name[:-len(suffix)]:
        raise PreparedMultiCandidateError(f"item name is not an unambiguous {item.kind} name: {name!r}")
    _encode_component(name[:-len(suffix)], f"{item.kind} item name")
    return name[:-len(suffix)]


def _display_path(path: tuple[str, ...], kind: Optional[str] = None) -> str:
    if kind is not None and path:
        return "\\".join(path[:-1] + (path[-1] + "." + kind,))
    return "\\".join(path)


def _record_for_path(parsed: ParsedBackupBlob, path: tuple[str, ...]) -> BackupRecord:
    offsets = [offset for offset, value in parsed.paths.items() if value == path]
    if len(offsets) != 1:
        raise PreparedMultiCandidateError(
            f"expected exactly one template record at {_display_path(path)}"
        )
    return parsed.record_at(offsets[0])


def _template_records(
    template: ParsedBackupBlob,
    folder_path: tuple[str, ...],
    template_item_paths: Mapping[str, tuple[str, ...]],
    needed_kinds: Sequence[str],
) -> tuple[BackupRecord, BackupRecord, dict[str, BackupRecord]]:
    folder = _record_for_path(template, folder_path)
    if folder.kind != "directory" or folder.name == ".." or folder_path[:-1] != ("root",):
        raise PreparedMultiCandidateError("template folder must be a reachable root-level directory")
    if folder.field_04_be32 != folder.offset or folder.field_08_be32 < _RECORD_SIZE:
        raise PreparedMultiCandidateError("template folder has no supported child table")
    try:
        leading = template.record_at(folder.offset + _RECORD_SIZE)
    except BackupFormatError as exc:
        raise PreparedMultiCandidateError("template leading parent marker is missing") from exc
    if leading.kind != "directory" or leading.name != ".." or leading.field_08_be32 != folder.offset:
        raise PreparedMultiCandidateError("template leading parent marker is not supported")
    child_start = folder.offset + _RECORD_SIZE
    child_end = child_start + folder.field_08_be32
    result: dict[str, BackupRecord] = {}
    for kind in needed_kinds:
        path = template_item_paths.get(kind)
        if path is None:
            raise PreparedMultiCandidateError(
                f"a validated native {kind.upper()} record template is required"
            )
        record = _record_for_path(template, path)
        if record.kind != "file" or record.extension.lower() != kind:
            raise PreparedMultiCandidateError(
                f"template path for {kind.upper()} is not a matching file record"
            )
        if not child_start <= record.offset < child_end or (record.offset - child_start) % _RECORD_SIZE:
            raise PreparedMultiCandidateError(
                f"template {kind.upper()} record is not a direct child of the template folder"
            )
        if record.payload_prefix_length != _TEXT_PREFIX_SIZE:
            raise PreparedMultiCandidateError(
                f"template {kind.upper()} record does not have the validated 32-byte native prefix"
            )
        result[kind] = record
    return folder, leading, result


def _compare_template_shared(
    baseline: ParsedBackupBlob,
    template: ParsedBackupBlob,
    template_folder_path: tuple[str, ...],
    template_item_paths: Mapping[str, tuple[str, ...]],
) -> dict[str, Any]:
    if baseline.data == template.data:
        return {"baseline_template_identical": True, "shared_records_verified": len(baseline.paths)}
    expected = set(baseline.paths.values()) | {template_folder_path}
    expected.update(template_item_paths.values())
    if set(template.paths.values()) != expected:
        raise PreparedMultiCandidateError("template changes paths beyond its declared package shape")
    if len(template.records) != len(baseline.records) + 2 + len(template_item_paths):
        raise PreparedMultiCandidateError("template does not contain the declared structural additions")
    for path in baseline.paths.values():
        old = _record_for_path(baseline, path)
        new = _record_for_path(template, path)
        old_raw = bytes.fromhex(old.raw_hex)
        new_raw = bytes.fromhex(new.raw_hex)
        if old_raw[:4] + old_raw[0x0C:] != new_raw[:4] + new_raw[0x0C:]:
            raise PreparedMultiCandidateError(f"template changed preserved metadata at {_display_path(path)}")
        if old.kind == "file":
            old_prefix, old_payload = baseline.payload_parts(old)
            new_prefix, new_payload = template.payload_parts(new)
            if old_prefix != new_prefix or old_payload != new_payload:
                raise PreparedMultiCandidateError(f"template changed preserved content at {_display_path(path)}")
    return {"baseline_template_identical": False, "shared_records_verified": len(baseline.paths)}


def _preserve_shared(
    baseline: ParsedBackupBlob,
    candidate: ParsedBackupBlob,
    added_paths: set[tuple[str, ...]],
) -> dict[str, Any]:
    if set(candidate.paths.values()) != set(baseline.paths.values()) | added_paths:
        raise PreparedMultiCandidateError("candidate changed the reachable path set outside the requested package")
    for path in baseline.paths.values():
        old = _record_for_path(baseline, path)
        new = _record_for_path(candidate, path)
        old_raw = bytes.fromhex(old.raw_hex)
        new_raw = bytes.fromhex(new.raw_hex)
        # Field 04/08 are the only fields this repacker is allowed to change.
        # The remainder includes timestamps, flags, names, wrappers and unknown bytes.
        if old_raw[:4] + old_raw[0x0C:] != new_raw[:4] + new_raw[0x0C:]:
            raise PreparedMultiCandidateError(f"candidate changed preserved bytes at {_display_path(path)}")
        if old.kind == "file":
            old_prefix, old_payload = baseline.payload_parts(old)
            new_prefix, new_payload = candidate.payload_parts(new)
            if old_prefix != new_prefix or old_payload != new_payload:
                raise PreparedMultiCandidateError(f"candidate changed preserved content at {_display_path(path)}")
    return {
        "preserved_paths": len(baseline.paths),
        "preserved_file_payloads": sum(1 for record in baseline.records if record.kind == "file"),
        "shared_timestamps_unchanged": True,
        "unknown_record_bytes_preserved": True,
        "unrelated_changes_verified": True,
    }


def _transaction(candidate_blob: bytes, fixed: PreparedFixedStateSnapshot) -> ProspectiveWriteTransaction:
    try:
        return ProspectiveWriteTransaction(
            ranges=(
                fixed.range1,
                fixed.range2,
                build_staging_range(0, len(candidate_blob)),
                b"",
                candidate_blob[:0x40],
                b"",
                b"",
                candidate_blob[0x40:],
            ),
            variable_n=0,
            variable_m=len(candidate_blob),
        )
    except (WriteArtifactError, OverflowError) as exc:
        raise PreparedMultiCandidateError(f"prospective transaction is invalid: {exc}") from exc


@dataclass(frozen=True)
class PreparedMultiPackageCandidate:
    package: PreparedPackageInput
    backup: VerifiedBackup
    baseline: ParsedBackupBlob
    candidate: ParsedBackupBlob
    candidate_blob: bytes
    fixed_state: PreparedFixedStateSnapshot
    fixed_state_assessment: PreparedFixedStateAssessment
    transaction: ProspectiveWriteTransaction
    capacity_limit_bytes: int
    baseline_model_bytes: int
    candidate_model_bytes: int
    remaining_growth_bytes: int
    native_capacity_evidence: NativeCapacityEvidence
    audit: Mapping[str, Any]

    @property
    def candidate_blob_sha256(self) -> str:
        return _sha256(self.candidate_blob)

    @property
    def transaction_sha256(self) -> str:
        return self.transaction.concatenated_sha256

    def audit_dict(self) -> dict[str, Any]:
        return dict(self.audit)


def build_prepared_multi_package_candidate(
    package: PreparedPackageInput,
    backup: VerifiedBackup,
    template: ParsedBackupBlob,
    *,
    new_record_timestamp_be32: int,
    native_capacity_response: NativeCapacityResponse,
    template_folder_path: tuple[str, ...] = ("root", "IC_I_FOLDER_20260823_01"),
    template_item_paths: Optional[Mapping[str, tuple[str, ...]]] = None,
) -> PreparedMultiPackageCandidate:
    """Build one ordered multi-child candidate using only native capacity evidence."""

    if not isinstance(backup, VerifiedBackup) or not isinstance(template, ParsedBackupBlob):
        raise PreparedMultiCandidateError("backup and template must be verified parsed values")
    if not isinstance(native_capacity_response, NativeCapacityResponse):
        raise PreparedMultiCandidateError("multi-child candidates require parsed native 0x0019 evidence")
    if isinstance(new_record_timestamp_be32, bool) or not isinstance(new_record_timestamp_be32, int) or not 0 <= new_record_timestamp_be32 <= 0xFFFFFFFF:
        raise PreparedMultiCandidateError("new_record_timestamp_be32 must fit uint32")
    values = _items(package)
    names = [item.name.casefold() for item in values]
    if len(set(names)) != len(names):
        raise PreparedMultiCandidateError("ordered package names must be unique case-insensitively")
    template_item_paths = dict(template_item_paths or {})
    needed_kinds = tuple(dict.fromkeys(item.kind for item in values))
    for item in values:
        try:
            current = item.source_path.read_bytes()
        except OSError as exc:
            raise PreparedMultiCandidateError(f"could not reread package source {item.source_path}: {exc}") from exc
        if current != item.source_bytes or _sha256(current) != item.source_sha256:
            raise PreparedMultiCandidateError(f"package source changed: {item.source_path}")
    baseline_blob = _read_verified_blob(backup)
    try:
        baseline = parse_backup_blob(baseline_blob)
    except BackupFormatError as exc:
        raise PreparedMultiCandidateError(f"verified backup dynamic blob is malformed: {exc}") from exc
    if native_capacity_response.device_identity != tuple(int(value, 16) for value in backup.device_identity):
        raise PreparedMultiCandidateError("native capacity response device identity differs from backup")
    root = baseline.record_at(baseline.header.metadata_start)
    if root.kind != "directory" or root.name != "root":
        raise PreparedMultiCandidateError("baseline does not begin with root")
    folder_path = ("root", package.folder_name)
    child_paths = tuple(folder_path + (_item_basename(item),) for item in values)
    existing = {tuple(part.casefold() for part in path) for path in baseline.paths.values()}
    for path in (folder_path, *child_paths):
        if tuple(part.casefold() for part in path) in existing:
            raise PreparedMultiCandidateError(f"destination path already exists: {_display_path(path)}")
    try:
        folder_template, leading_template, prefix_templates = _template_records(
            template, template_folder_path, template_item_paths, needed_kinds
        )
        template_validation = _compare_template_shared(
            baseline, template, template_folder_path, template_item_paths
        )
    except (BackupFormatError, PreparedMultiCandidateError) as exc:
        if isinstance(exc, PreparedMultiCandidateError):
            raise
        raise PreparedMultiCandidateError(str(exc)) from exc
    try:
        root_marker_offset = root.field_04_be32 + _RECORD_SIZE + root.field_08_be32
        root_marker = baseline.record_at(root_marker_offset)
    except BackupFormatError as exc:
        raise PreparedMultiCandidateError("baseline root insertion boundary is unavailable") from exc
    if root_marker.kind != "directory" or root_marker.name != "..":
        raise PreparedMultiCandidateError("baseline root insertion boundary is not a parent marker")
    content = baseline.data[baseline.header.content_start : baseline.header.content_start + baseline.header.content_length]
    content_insert_at = 0
    for path, record in ((path, baseline.record_at(offset)) for offset, path in baseline.paths.items()):
        if len(path) != 2 or record.kind != "file":
            continue
        prefix, payload = baseline.payload_parts(record)
        end = record.field_04_be32 + _aligned_segment_length(prefix, payload)
        if end > len(content):
            raise PreparedMultiCandidateError("baseline root-level content segment is outside content")
        content_insert_at = max(content_insert_at, end)
    later_files = [baseline.record_at(offset).field_04_be32 for offset, path in baseline.paths.items() if len(path) > 2 and baseline.record_at(offset).kind == "file"]
    if later_files and min(later_files) != content_insert_at:
        raise PreparedMultiCandidateError("baseline content contains an unproven insertion gap")
    segments: list[bytes] = []
    item_reports: list[dict[str, Any]] = []
    content_delta = 0
    for item in values:
        payload = _item_payload(item)
        prefix, _ = template.payload_parts(prefix_templates[item.kind])
        aligned = _aligned_segment_length(prefix, payload)
        segments.append(prefix + payload + b"\xff" * (aligned - len(prefix) - len(payload)))
        content_delta += aligned
    metadata_delta = (2 + len(values)) * _RECORD_SIZE
    insertion_index = (root_marker_offset - baseline.header.metadata_start) // _RECORD_SIZE
    shifted: list[bytes] = []
    for record in baseline.records:
        raw = _raw_record(record)
        if record.offset == root.offset:
            raw[0x08:0x0C] = (record.field_08_be32 + _RECORD_SIZE).to_bytes(4, "big")
        elif record.kind == "directory" and record.name == ".." and record.field_08_be32 == root_marker.field_08_be32:
            raw[0x08:0x0C] = (record.field_08_be32 + _RECORD_SIZE).to_bytes(4, "big")
        if record.kind == "directory" and record.field_04_be32 + _RECORD_SIZE >= root_marker_offset:
            raw[0x04:0x08] = (record.field_04_be32 + metadata_delta).to_bytes(4, "big")
        elif record.kind == "file" and record.field_04_be32 >= content_insert_at:
            raw[0x04:0x08] = (record.field_04_be32 + content_delta).to_bytes(4, "big")
        shifted.append(bytes(raw))
    folder_raw = _raw_record(folder_template)
    folder_raw[0x04:0x08] = root_marker_offset.to_bytes(4, "big")
    folder_raw[0x08:0x0C] = ((len(values) + 1) * _RECORD_SIZE).to_bytes(4, "big")
    folder_raw[0x0C:0x10] = new_record_timestamp_be32.to_bytes(4, "big")
    _replace_name(folder_raw, _encode_component(package.folder_name, "folder name"))
    leading_raw = _raw_record(leading_template)
    leading_raw[0x04:0x08] = root.field_04_be32.to_bytes(4, "big")
    leading_raw[0x08:0x0C] = root_marker_offset.to_bytes(4, "big")
    leading_raw[0x0C:0x10] = new_record_timestamp_be32.to_bytes(4, "big")
    inserted: list[bytes] = [bytes(folder_raw), bytes(leading_raw)]
    item_metadata_offset = root_marker_offset + 2 * _RECORD_SIZE
    content_cursor = content_insert_at
    for index, (item, segment) in enumerate(zip(values, segments)):
        raw = _raw_record(prefix_templates[item.kind])
        raw[0x04:0x08] = content_cursor.to_bytes(4, "big")
        raw[0x08:0x0C] = len(_item_payload(item)).to_bytes(4, "big")
        raw[0x0C:0x10] = new_record_timestamp_be32.to_bytes(4, "big")
        _replace_name(raw, _encode_component(_item_basename(item), f"{item.kind} item name"))
        inserted.append(bytes(raw))
        item_reports.append({
            "order": index,
            "kind": item.kind,
            "path": _display_path(child_paths[index], item.kind),
            "record_offset": _hex(item_metadata_offset),
            "payload_offset": _hex(baseline.header.content_start + content_cursor + _TEXT_PREFIX_SIZE),
            "payload_length": len(_item_payload(item)),
            "source_sha256": item.source_sha256,
            "payload_sha256": _sha256(_item_payload(item)),
            "native_prefix_sha256": _sha256(prefix_templates[item.kind] and template.payload_parts(prefix_templates[item.kind])[0]),
        })
        item_metadata_offset += _RECORD_SIZE
        content_cursor += len(segment)
    metadata_records: list[bytes] = []
    for index, raw in enumerate(shifted):
        if index == insertion_index:
            metadata_records.extend(inserted)
        metadata_records.append(raw)
    metadata = b"".join(metadata_records)
    rebuilt_content = content[:content_insert_at] + b"".join(segments) + content[content_insert_at:]
    header = bytearray(baseline.data[: baseline.header.metadata_start])
    total_length = len(header) + len(metadata) + len(rebuilt_content) + 4
    header[0x2C:0x30] = len(metadata).to_bytes(4, "big")
    header[0x30:0x34] = (baseline.header.content_start + metadata_delta).to_bytes(4, "big")
    header[0x34:0x38] = len(rebuilt_content).to_bytes(4, "big")
    header[0x18:0x1C] = (total_length - 1).to_bytes(4, "big")
    header[0x38:0x3C] = total_length.to_bytes(4, "big")
    output = bytearray(bytes(header) + metadata + rebuilt_content + baseline.data[-4:])
    output[0x1C:0x20] = b"\x00" * 4
    output[0x1C:0x20] = calculate_backup_checksum(bytes(output)).to_bytes(4, "big")
    candidate_blob = bytes(output)
    try:
        candidate = parse_backup_blob(candidate_blob)
    except BackupFormatError as exc:
        raise PreparedMultiCandidateError(f"candidate failed structural validation: {exc}") from exc
    added = {folder_path, *child_paths}
    preservation = _preserve_shared(baseline, candidate, added)
    for path, item in zip(child_paths, values):
        record = _record_for_path(candidate, path)
        prefix, payload = candidate.payload_parts(record)
        if payload != _item_payload(item) or prefix != template.payload_parts(prefix_templates[item.kind])[0]:
            raise PreparedMultiCandidateError(f"candidate payload mismatch at {_display_path(path, item.kind)}")
        if record.timestamp_be32 != new_record_timestamp_be32:
            raise PreparedMultiCandidateError("new child timestamp does not match explicit timestamp")
    folder = _record_for_path(candidate, folder_path)
    leading = candidate.record_at(folder.offset + _RECORD_SIZE)
    if folder.field_08_be32 != (len(values) + 1) * _RECORD_SIZE or leading.name != ".." or leading.timestamp_be32 != new_record_timestamp_be32:
        raise PreparedMultiCandidateError("candidate folder geometry or timestamp is invalid")
    fixed_assessment = assess_prepared_fixed_state(backup)
    try:
        fixed = fixed_assessment.require_supported()
    except PreparedFixedStateError as exc:
        raise PreparedMultiCandidateError(f"fresh fixed state is unsupported: {exc}") from exc
    try:
        evidence = native_capacity_response.bind_model_lengths(len(baseline_blob), len(candidate_blob))
        capacity = assess_total_capacity(
            evidence.capacity_limit_bytes,
            evidence.baseline_model_bytes,
            evidence.candidate_model_bytes,
            source=evidence.evidence_source,
        )
    except (NativeCapacityEvidenceError, CapacitySemanticsError) as exc:
        raise PreparedMultiCandidateError(str(exc)) from exc
    transaction = _transaction(candidate_blob, fixed)
    if transaction.variable_m + transaction.variable_n != len(candidate_blob):
        raise PreparedMultiCandidateError("transaction model length does not match candidate")
    if len(candidate.records) != len(baseline.records) + 2 + len(values):
        raise PreparedMultiCandidateError("candidate record count is inconsistent with ordered package")
    audit = {
        "format": PREPARED_MULTI_CANDIDATE_FORMAT,
        "state": "offline_only",
        "usb_transmission_performed": False,
        "device_identity": {"vendor_id": backup.device_identity[0], "product_id": backup.device_identity[1]},
        "package": {
            "folder_path": package.target_folder_path,
            "paths": [_display_path(folder_path), *[_display_path(path, item.kind) for path, item in zip(child_paths, values)]],
            "record_offsets": [_hex(folder.offset), *[report["record_offset"] for report in item_reports]],
            "ordered_items": item_reports,
            "prepared_manifest_sha256": package.prepared_manifest_sha256,
        },
        "baseline": {"manifest_sha256": backup.manifest_sha256, "blob_sha256": _sha256(baseline_blob), "blob_length": len(baseline_blob), "record_count": len(baseline.records)},
        "candidate": {"blob_sha256": _sha256(candidate_blob), "blob_length": len(candidate_blob), "record_count": len(candidate.records), "added_paths": [_display_path(folder_path), *[_display_path(path, item.kind) for path, item in zip(child_paths, values)]], "new_record_timestamp_be32": _hex(new_record_timestamp_be32)},
        "allocation": {"metadata_records_added": 2 + len(values), "metadata_growth_bytes": metadata_delta, "aligned_content_growth_bytes": content_delta, "candidate_growth_bytes": len(candidate_blob) - len(baseline_blob), "capacity_limit_bytes": capacity.capacity_limit_bytes, "baseline_model_bytes": capacity.baseline_model_bytes, "candidate_model_bytes": capacity.candidate_model_bytes, "remaining_growth_bytes": capacity.remaining_growth_bytes, "capacity_result": "sufficient"},
        "capacity_evidence": evidence.to_dict(),
        "fixed_state": fixed_assessment.to_dict(),
        "transaction": {"command": "0x101b", "sha256": transaction.concatenated_sha256, "payload_length": transaction.payload_length, "range_lengths": [len(value) for value in transaction.ranges], "fixed_state_hashes": [_sha256(value) for value in fixed.raw_blocks]},
        "template_validation": template_validation,
        "preservation": preservation,
        "policy": {"timestamp": "one_explicit_frozen_value_for_new_records_only", "fixed_state": "exact_fresh_capture7_all_zero_bytes_preserved", "manager_sidecars": "not part of device transaction"},
        "assumptions": ["The folder and each child wrapper are copied from explicitly supplied validated native templates.", "The captured root insertion geometry is reused for this offline candidate only.", "This is not proof of arbitrary package or nested-folder compatibility."],
    }
    return PreparedMultiPackageCandidate(package, backup, baseline, candidate, candidate_blob, fixed, fixed_assessment, transaction, capacity.capacity_limit_bytes, capacity.baseline_model_bytes, capacity.candidate_model_bytes, capacity.remaining_growth_bytes, evidence, audit)


__all__ = [
    "PREPARED_MULTI_CANDIDATE_FORMAT",
    "PreparedMultiCandidateError",
    "PreparedMultiPackageCandidate",
    "build_prepared_multi_package_candidate",
]
