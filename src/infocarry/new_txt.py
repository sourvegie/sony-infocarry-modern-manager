"""Offline construction and comparison of one new root-level TXT record.

This is the first Milestone F candidate boundary.  It starts from a complete
verified backup, uses the existing template-backed metadata rewriter, and
constructs a USB-neutral ``0x101b`` candidate in memory.  It does not open a
device, write a backup, update Manager sidecars, or expose a CLI/GUI action.

The state rebase deliberately shifts only metadata-relative references whose
meaning is established by Phase 7.  It preserves unused tails and unresolved
fields and does not assign a category, mark, bookmark, selection, or order
membership to the new file.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Optional

from .backup_duplicate import BackupDuplicateError, add_file_from_template
from .backup_format import BackupFormatError, ParsedBackupBlob, parse_backup_blob
from .text_authoring import TextAuthoringError, encode_cp932_text
from .write_artifact import (
    ProspectiveWriteTransaction,
    WriteArtifactError,
    build_staging_range,
)
from .write_gate import (
    DEFAULT_MAX_AGE_SECONDS,
    VerifiedBackup,
    WriteGateError,
    verify_fresh_backup,
)
from .write_state import StateSerializationError, rebase_fixed_state_responses


NEW_ROOT_TXT_FORMAT = "infocarry-offline-new-root-txt-v1"
_DYNAMIC_BLOB_KEY = "0x8004:backup-blob"
_FIXED_STATE_KEYS = (
    "0x001b:response-001b",
    "0x001c:response-001c",
    "0x001d:response-001d",
    "0x001e:response-001e",
)
_GROUPED_STATE_KEY = "0x001f:response-001f"
_REQUIRED_BACKUP_KEYS = (
    "0x0024:response-0024",
    *_FIXED_STATE_KEYS,
    _GROUPED_STATE_KEY,
    "0x8004:backup-blob-probe",
    _DYNAMIC_BLOB_KEY,
)


class NewTxtAddError(ValueError):
    """Raised when the narrow offline new-TXT candidate is unsafe."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _read_verified_object(backup: VerifiedBackup, key: str) -> bytes:
    filename = backup.object_filename(key)
    if filename is None:
        raise NewTxtAddError(f"verified backup is missing required object {key}")
    try:
        data = (backup.directory / filename).read_bytes()
    except OSError as exc:
        raise NewTxtAddError(f"could not read verified backup object {key}: {exc}") from exc
    digest = backup.object_sha256(key)
    if digest != _sha256(data):
        raise NewTxtAddError(f"verified backup object {key} changed after verification")
    return data


def _validate_complete_backup(
    backup_directory: Path,
    *,
    now: Optional[datetime],
    max_age_seconds: Optional[float],
) -> VerifiedBackup:
    try:
        backup = verify_fresh_backup(
            backup_directory,
            now=now,
            max_age_seconds=max_age_seconds,
        )
    except WriteGateError as exc:
        raise NewTxtAddError(f"fresh complete backup validation failed: {exc}") from exc
    missing = [key for key in _REQUIRED_BACKUP_KEYS if backup.object_sha256(key) is None]
    if missing:
        raise NewTxtAddError(
            "fresh complete backup is missing required state objects: "
            + ", ".join(missing)
        )
    return backup


def _validate_target_filename(filename: str) -> tuple[str, bytes]:
    if not isinstance(filename, str) or not filename:
        raise NewTxtAddError("target filename must be a non-empty string")
    if (
        filename in {".", ".."}
        or "\x00" in filename
        or "/" in filename
        or "\\" in filename
        or filename != filename.strip()
        or not filename.endswith(".txt")
    ):
        raise NewTxtAddError(
            "target filename must be one trimmed root-level CP932 name ending in .txt"
        )
    basename = filename[:-4]
    if not basename or "." in basename:
        raise NewTxtAddError(
            "target filename must have one unambiguous basename and the .txt extension"
        )
    try:
        encoded = basename.encode("cp932", errors="strict")
    except UnicodeEncodeError as exc:
        raise NewTxtAddError("target filename is not representable in CP932") from exc
    if len(encoded) >= 40:
        raise NewTxtAddError(
            "target filename basename must leave room for the metadata NUL terminator"
        )
    return basename, encoded


def _load_source_bytes(
    source_path: Path,
    *,
    source_encoding: str,
) -> tuple[bytes, bytes, str]:
    path = Path(source_path).expanduser().resolve()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise NewTxtAddError(f"could not read source TXT {path}: {exc}") from exc
    source_hash = _sha256(raw)
    if not isinstance(source_encoding, str) or source_encoding not in {"cp932", "utf-8"}:
        raise NewTxtAddError(
            "source_encoding must be either strict cp932 or strict utf-8"
        )
    try:
        text = raw.decode(source_encoding, errors="strict")
    except UnicodeDecodeError as exc:
        display_encoding = source_encoding.upper()
        raise NewTxtAddError(
            f"source TXT is not valid {display_encoding}"
        ) from exc
    try:
        authored = encode_cp932_text(text)
    except TextAuthoringError as exc:
        raise NewTxtAddError(f"source TXT failed strict CP932/CRLF authoring: {exc}") from exc
    return raw, authored.payload, source_hash


def _validate_timestamp_overrides(
    timestamps: Optional[Mapping[int, int]],
) -> Optional[dict[int, int]]:
    if timestamps is None:
        return None
    if not isinstance(timestamps, Mapping):
        raise NewTxtAddError("metadata_timestamps must be a mapping")
    result: dict[int, int] = {}
    for offset, timestamp in timestamps.items():
        if (
            isinstance(offset, bool)
            or not isinstance(offset, int)
            or isinstance(timestamp, bool)
            or not isinstance(timestamp, int)
            or not 0 <= timestamp <= 0xFFFFFFFF
        ):
            raise NewTxtAddError("metadata timestamp overrides must use integer offsets and uint32 values")
        result[offset] = timestamp
    return result


def _resolve_template(
    parsed: ParsedBackupBlob,
    source_template_offset: int,
) -> tuple[Any, tuple[str, ...]]:
    if isinstance(source_template_offset, bool) or not isinstance(source_template_offset, int):
        raise NewTxtAddError("source_template_offset must be an integer")
    try:
        template = parsed.record_at(source_template_offset)
    except BackupFormatError as exc:
        raise NewTxtAddError(f"source template is invalid: {exc}") from exc
    path = parsed.paths.get(source_template_offset)
    if path is None or template.kind != "file":
        raise NewTxtAddError("source template must be a reachable file")
    if path[:-1] != ("root",) or template.extension.lower() != "txt":
        raise NewTxtAddError("source template must be a reachable root-level TXT record")
    if template.payload_prefix_length is None:
        raise NewTxtAddError("source template has an unsupported native payload prefix")
    return template, path


def _preservation_report(
    before: ParsedBackupBlob,
    after: ParsedBackupBlob,
    target_path: tuple[str, ...],
) -> dict[str, Any]:
    before_paths = set(before.paths.values())
    after_paths = set(after.paths.values())
    expected_paths = before_paths | {target_path}
    if after_paths != expected_paths:
        raise NewTxtAddError("candidate changed the reachable path set beyond the one new TXT")
    preserved = 0
    for path in sorted(before_paths):
        before_offset = next(offset for offset, value in before.paths.items() if value == path)
        after_offset = next(offset for offset, value in after.paths.items() if value == path)
        before_record = before.record_at(before_offset)
        after_record = after.record_at(after_offset)
        if before_record.kind != after_record.kind or before_record.extension != after_record.extension:
            raise NewTxtAddError(f"candidate changed preserved record shape at {'\\'.join(path)}")
        if before_record.field_10_be32 != after_record.field_10_be32:
            raise NewTxtAddError(f"candidate changed preserved unknown field at {'\\'.join(path)}")
        if before_record.field_14_be32 != after_record.field_14_be32:
            raise NewTxtAddError(f"candidate changed preserved prefix field at {'\\'.join(path)}")
        if before_record.kind == "file":
            try:
                _before_prefix, before_payload = before.payload_parts(before_record)
                _after_prefix, after_payload = after.payload_parts(after_record)
            except BackupFormatError as exc:
                raise NewTxtAddError(f"preserved payload validation failed at {'\\'.join(path)}: {exc}") from exc
            if before_payload != after_payload:
                raise NewTxtAddError(f"candidate changed preserved payload at {'\\'.join(path)}")
        preserved += 1
    return {
        "preserved_reachable_records": preserved,
        "preserved_paths": len(before_paths),
        "preserved_file_payloads": sum(record.kind == "file" for record in before.records if record.offset in before.paths),
        "unrelated_changes_verified": True,
    }


def _build_transaction(
    candidate_blob: bytes,
    rebased_states: tuple[bytes, bytes],
) -> ProspectiveWriteTransaction:
    range1, range2 = rebased_states
    try:
        return ProspectiveWriteTransaction(
            ranges=(
                range1,
                range2,
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
        raise NewTxtAddError(f"candidate transaction could not be constructed: {exc}") from exc


@dataclass(frozen=True)
class NewTxtAddResult:
    """An offline candidate and its deterministic audit."""

    candidate_blob: bytes
    transaction: ProspectiveWriteTransaction
    audit: Mapping[str, Any]

    def audit_dict(self) -> dict[str, Any]:
        return dict(self.audit)


@dataclass(frozen=True)
class NewTxtComparison:
    """Exact or explicitly normalized comparison with a complete backup."""

    exact: bool
    normalized_equivalent: bool
    candidate_blob_sha256: str
    actual_blob_sha256: str
    permitted_differences: tuple[Mapping[str, Any], ...]
    unexpected_differences: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "exact": self.exact,
            "normalized_equivalent": self.normalized_equivalent,
            "candidate_blob_sha256": self.candidate_blob_sha256,
            "actual_blob_sha256": self.actual_blob_sha256,
            "permitted_differences": [dict(item) for item in self.permitted_differences],
            "unexpected_differences": list(self.unexpected_differences),
        }


def build_new_root_txt_add(
    backup_directory: Path,
    source_path: Path,
    target_filename: str,
    *,
    source_template_offset: int,
    available_capacity_bytes: Optional[int],
    source_encoding: str = "cp932",
    record_timestamp_be32: Optional[int] = None,
    metadata_timestamps: Optional[Mapping[int, int]] = None,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> NewTxtAddResult:
    """Build one root-level TXT candidate without mutating any input.

    ``available_capacity_bytes`` is an explicit safe budget supplied by the
    caller. It is not inferred from a blob length or a response whose capacity
    semantics remain unresolved; ``None`` therefore fails closed.
    """

    if (
        available_capacity_bytes is None
        or isinstance(available_capacity_bytes, bool)
        or not isinstance(available_capacity_bytes, int)
        or available_capacity_bytes < 0
    ):
        raise NewTxtAddError(
            "available capacity cannot be established safely; provide a non-negative byte budget"
        )
    if record_timestamp_be32 is not None and (
        isinstance(record_timestamp_be32, bool)
        or not isinstance(record_timestamp_be32, int)
        or not 0 <= record_timestamp_be32 <= 0xFFFFFFFF
    ):
        raise NewTxtAddError("record_timestamp_be32 must fit an unsigned 32-bit integer")
    timestamp_overrides = _validate_timestamp_overrides(metadata_timestamps)
    basename, _encoded_basename = _validate_target_filename(target_filename)
    backup = _validate_complete_backup(
        backup_directory,
        now=now,
        max_age_seconds=max_age_seconds,
    )
    raw_source, authored_payload, source_hash = _load_source_bytes(
        source_path,
        source_encoding=source_encoding,
    )
    baseline_blob = _read_verified_object(backup, _DYNAMIC_BLOB_KEY)
    try:
        parsed = parse_backup_blob(baseline_blob)
    except BackupFormatError as exc:
        raise NewTxtAddError(f"fresh backup dynamic blob failed validation: {exc}") from exc
    root = parsed.record_at(parsed.header.metadata_start)
    if root.kind != "directory" or root.name != "root":
        raise NewTxtAddError("fresh backup does not have the required root directory")
    if any(
        path == ("root", basename)
        and parsed.record_at(offset).extension.lower() == "txt"
        for offset, path in parsed.paths.items()
    ):
        raise NewTxtAddError(f"duplicate root-level TXT target: {target_filename!r}")
    template, template_path = _resolve_template(parsed, source_template_offset)
    if template.name.casefold() == basename.casefold():
        raise NewTxtAddError("target filename would reuse the source template name")

    try:
        candidate_blob = add_file_from_template(
            parsed,
            parsed.header.metadata_start,
            source_template_offset,
            basename,
            authored_payload,
            timestamp_be32=record_timestamp_be32,
            metadata_timestamps=timestamp_overrides,
        )
        candidate = parse_backup_blob(candidate_blob)
    except (BackupDuplicateError, BackupFormatError, OverflowError) as exc:
        raise NewTxtAddError(f"template-backed TXT construction failed: {exc}") from exc

    target_path = ("root", basename)
    target_offsets = [offset for offset, path in candidate.paths.items() if path == target_path]
    if len(target_offsets) != 1:
        raise NewTxtAddError("candidate did not contain exactly one new root-level TXT record")
    target_offset = target_offsets[0]
    target = candidate.record_at(target_offset)
    if target.extension.lower() != "txt" or target.kind != "file":
        raise NewTxtAddError("candidate target is not a TXT file record")
    preservation = _preservation_report(parsed, candidate, target_path)
    prefix, payload = candidate.payload_parts(target)
    if payload != authored_payload:
        raise NewTxtAddError("candidate target payload is not the authored CP932/CRLF payload")

    metadata_delta = candidate.header.metadata_length - parsed.header.metadata_length
    if metadata_delta != parsed.header.record_size:
        raise NewTxtAddError("candidate metadata growth is not exactly one record")
    state_insertion_offset = target_offset - parsed.header.metadata_start
    try:
        state_before = tuple(
            _read_verified_object(backup, key) for key in _FIXED_STATE_KEYS
        )
        grouped_before = _read_verified_object(backup, _GROUPED_STATE_KEY)
        rebased_offset_lists, rebased_grouped = rebase_fixed_state_responses(
            state_before,
            grouped_before,
            insertion_offset=state_insertion_offset,
            metadata_delta=metadata_delta,
        )
    except StateSerializationError as exc:
        raise NewTxtAddError(f"fixed-state reference rebasing failed closed: {exc}") from exc

    transaction = _build_transaction(
        candidate_blob,
        (b"".join(rebased_offset_lists), rebased_grouped),
    )
    candidate_growth = len(candidate_blob) - len(baseline_blob)
    if candidate_growth < 0:
        raise NewTxtAddError("candidate unexpectedly shrank the baseline blob")
    if candidate_growth > available_capacity_bytes:
        raise NewTxtAddError(
            f"candidate requires {candidate_growth} bytes; available capacity budget is "
            f"{available_capacity_bytes}"
        )
    padding_bytes = candidate_growth - metadata_delta - len(prefix) - len(payload)
    if padding_bytes < 0 or padding_bytes >= 4:
        raise NewTxtAddError("candidate allocation padding is outside the observed 0..3-byte range")

    audit: dict[str, Any] = {
        "format": NEW_ROOT_TXT_FORMAT,
        "state": "offline_only",
        "usb_transmission_performed": False,
        "device_identity": {
            "vendor_id": backup.device_identity[0],
            "product_id": backup.device_identity[1],
        },
        "source": {
            "path": str(Path(source_path).expanduser().resolve()),
            "size": len(raw_source),
            "sha256": source_hash,
            "encoded_payload_size": len(authored_payload),
            "encoded_payload_sha256": _sha256(authored_payload),
            "source_encoding": source_encoding,
            "encoding": "cp932",
            "newline_policy": "crlf",
        },
        "target": {
            "path": "root\\" + target_filename,
            "record_offset_hex": _hex(target_offset),
            "record_flag_hex": _hex(target.flag),
            "extension": target.extension,
            "record_field_04_hex": _hex(target.field_04_be32),
            "payload_offset_hex": _hex(candidate.header.content_start + target.field_04_be32 + len(prefix)),
            "payload_length": len(payload),
            "payload_sha256": _sha256(payload),
            "native_prefix_length": len(prefix),
            "native_prefix_sha256": _sha256(prefix),
        },
        "template": {
            "record_offset_hex": _hex(source_template_offset),
            "path": "\\".join(template_path) + "." + template.extension,
            "record_sha256": _sha256(bytes.fromhex(template.raw_hex)),
        },
        "baseline": {
            "backup_directory": str(backup.directory),
            "manifest_sha256": backup.manifest_sha256,
            "blob_sha256": backup.blob_sha256,
            "blob_size": len(baseline_blob),
        },
        "candidate": {
            "blob_sha256": _sha256(candidate_blob),
            "blob_size": len(candidate_blob),
            "transaction_sha256": transaction.concatenated_sha256,
            "transaction_payload_length": transaction.payload_length,
            "range_lengths": [len(item) for item in transaction.ranges],
        },
        "allocation": {
            "metadata_delta": metadata_delta,
            "content_delta": candidate.header.content_length - parsed.header.content_length,
            "record_segment_length": len(prefix) + len(payload),
            "alignment_padding_bytes": padding_bytes,
            "candidate_growth_bytes": candidate_growth,
            "available_capacity_budget_bytes": available_capacity_bytes,
            "capacity_check": "passed",
        },
        "state_rebase": {
            "metadata_insertion_offset_relative_hex": _hex(state_insertion_offset),
            "metadata_delta": metadata_delta,
            "fixed_response_commands": ["0x001b", "0x001c", "0x001d", "0x001e", "0x001f"],
            "new_membership_assigned": False,
            "unknown_fields_preserved": True,
            "policy": "shift only established metadata-relative record references; preserve all other bytes and tails",
        },
        "preservation": preservation,
        "assumptions": [
            "The captured TXT record template is sufficient for one new root-level TXT record.",
            "Manager-local VICMEM.bin, VICLV.bin, and order.vnw are preserved unchanged; no new sidecar membership is invented.",
            "Timestamp overrides are evidence-only inputs; the default candidate preserves baseline timestamps.",
            "Successful 0x101b completion 0x0000 is a checked protocol assumption for new-add application, not independently confirmed here.",
            "The supplied capacity budget is an external safe bound; device capacity-field semantics are not inferred.",
        ],
    }
    audit_bytes = json.dumps(audit, sort_keys=True, separators=(",", ":")).encode("utf-8")
    audit["audit_sha256"] = _sha256(audit_bytes)
    return NewTxtAddResult(candidate_blob=candidate_blob, transaction=transaction, audit=audit)


def _normalized_blob(data: bytes, parsed: ParsedBackupBlob) -> bytes:
    normalized = bytearray(data)
    normalized[0x1C:0x20] = b"\x00" * 4
    for record in parsed.records:
        normalized[record.offset + 0x0C : record.offset + 0x10] = b"\x00" * 4
    return bytes(normalized)


def compare_new_txt_candidate(
    result: NewTxtAddResult,
    actual_backup_directory: Path,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> NewTxtComparison:
    """Compare an offline candidate with a complete post-add backup.

    Normalized equivalence permits only per-record timestamp changes and the
    checksum consequence of those timestamp changes. Any other difference is
    reported as unexpected.
    """

    if not isinstance(result, NewTxtAddResult):
        raise NewTxtAddError("result must be a NewTxtAddResult")
    actual_backup = _validate_complete_backup(
        actual_backup_directory,
        now=now,
        max_age_seconds=max_age_seconds,
    )
    if actual_backup.device_identity != (
        result.audit["device_identity"]["vendor_id"],
        result.audit["device_identity"]["product_id"],
    ):
        raise NewTxtAddError("actual backup device identity differs from the candidate baseline")
    actual_blob = _read_verified_object(actual_backup, _DYNAMIC_BLOB_KEY)
    exact = actual_blob == result.candidate_blob
    permitted: list[Mapping[str, Any]] = []
    unexpected: list[str] = []
    try:
        candidate_parsed = parse_backup_blob(result.candidate_blob)
        actual_parsed = parse_backup_blob(actual_blob)
    except BackupFormatError as exc:
        raise NewTxtAddError(f"candidate comparison blob failed structural validation: {exc}") from exc

    if not exact:
        if len(result.candidate_blob) != len(actual_blob):
            unexpected.append("blob_length")
        if _normalized_blob(result.candidate_blob, candidate_parsed) == _normalized_blob(
            actual_blob, actual_parsed
        ):
            candidate_by_path = {
                path: candidate_parsed.record_at(offset)
                for offset, path in candidate_parsed.paths.items()
            }
            actual_by_path = {
                path: actual_parsed.record_at(offset)
                for offset, path in actual_parsed.paths.items()
            }
            if set(candidate_by_path) != set(actual_by_path):
                unexpected.append("reachable_paths")
            else:
                for path in sorted(candidate_by_path):
                    left = candidate_by_path[path]
                    right = actual_by_path[path]
                    if left.timestamp_be32 != right.timestamp_be32:
                        permitted.append(
                            {
                                "kind": "record_timestamp",
                                "path": "\\".join(path),
                                "candidate": left.timestamp_be32,
                                "actual": right.timestamp_be32,
                            }
                        )
                if result.candidate_blob[0x1C:0x20] != actual_blob[0x1C:0x20]:
                    permitted.append(
                        {
                            "kind": "checksum_consequence_of_permitted_timestamps",
                            "candidate": result.candidate_blob[0x1C:0x20].hex(),
                            "actual": actual_blob[0x1C:0x20].hex(),
                        }
                    )
        else:
            unexpected.append("normalized_blob")
    return NewTxtComparison(
        exact=exact,
        normalized_equivalent=exact or not unexpected,
        candidate_blob_sha256=_sha256(result.candidate_blob),
        actual_blob_sha256=_sha256(actual_blob),
        permitted_differences=tuple(permitted),
        unexpected_differences=tuple(unexpected),
    )


__all__ = [
    "NEW_ROOT_TXT_FORMAT",
    "NewTxtAddError",
    "NewTxtAddResult",
    "NewTxtComparison",
    "build_new_root_txt_add",
    "compare_new_txt_candidate",
]
