"""Offline candidate and capacity gate for the constrained text package.

This module composes the already narrow capture-7-shaped folder builder with
the exact fixed-state preflight and the existing prospective ``0x101b`` range
artifact.  It is deliberately not an authorization gate and has no transport
dependency.  Every input is re-read and hash-checked before a candidate is
returned, and a caller must provide the preserved capture-7 template.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Mapping, Optional

from .backup_format import BackupFormatError, ParsedBackupBlob, parse_backup_blob
from .capacity import (
    CapacitySemanticsError,
    assess_legacy_remaining_budget,
    assess_total_capacity,
)
from .capacity_evidence import (
    NativeCapacityEvidence,
    NativeCapacityEvidenceError,
    NativeCapacityResponse,
)
from .prepared_fixed_state import (
    PreparedFixedStateAssessment,
    PreparedFixedStateError,
    PreparedFixedStateSnapshot,
    assess_prepared_fixed_state,
)
from .prepared_folder import PreparedFolderCandidate, PreparedFolderError, build_modern_root_folder_text_candidate
from .prepared_package import PreparedTextPackage
from .write_artifact import ProspectiveWriteTransaction, WriteArtifactError, build_staging_range
from .write_gate import VerifiedBackup


PREPARED_PACKAGE_CANDIDATE_FORMAT = "infocarry-modern-constrained-package-candidate-v1"
_DYNAMIC_BLOB_KEY = "0x8004:backup-blob"
_RECORD_SIZE = 0x40


class PreparedPackageCandidateError(ValueError):
    """Raised when a constrained package candidate cannot be built safely."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_verified_blob(backup: VerifiedBackup) -> bytes:
    filename = backup.object_filename(_DYNAMIC_BLOB_KEY)
    expected = backup.object_sha256(_DYNAMIC_BLOB_KEY)
    if filename is None or expected is None or expected != backup.blob_sha256:
        raise PreparedPackageCandidateError("verified backup is missing its dynamic blob binding")
    try:
        data = (backup.directory / filename).read_bytes()
    except OSError as exc:
        raise PreparedPackageCandidateError(f"could not read verified backup dynamic blob: {exc}") from exc
    if _sha256(data) != expected:
        raise PreparedPackageCandidateError("verified backup dynamic blob changed after verification")
    return data


def _validate_source(package: PreparedTextPackage) -> None:
    try:
        current = package.source_path.read_bytes()
    except OSError as exc:
        raise PreparedPackageCandidateError(f"could not re-read prepared source: {exc}") from exc
    if current != package.source_bytes or _sha256(current) != package.source_sha256:
        raise PreparedPackageCandidateError("prepared source changed after package preparation")


def _path_conflicts(parsed: ParsedBackupBlob, package: PreparedTextPackage) -> list[dict[str, Any]]:
    proposed = {
        ("root", package.folder_name): package.target_folder_path,
        ("root", package.folder_name, package.item.name): package.target_item_path,
    }
    conflicts: list[dict[str, Any]] = []
    for offset, path in parsed.paths.items():
        for proposed_path, display in proposed.items():
            if tuple(part.casefold() for part in path) == tuple(part.casefold() for part in proposed_path):
                conflicts.append(
                    {
                        "path": display,
                        "existing_path": _display_path(parsed, offset),
                        "record_offset": offset,
                        "reason": "destination path already exists, case-insensitively",
                    }
                )
    return conflicts


def _display_path(parsed: ParsedBackupBlob, offset: int) -> str:
    path = parsed.paths[offset]
    record = parsed.record_at(offset)
    suffix = f".{record.extension}" if record.kind == "file" and record.extension else ""
    return "\\".join(path[:-1] + (path[-1] + suffix,))


def _build_transaction(
    candidate_blob: bytes,
    fixed_state: PreparedFixedStateSnapshot,
) -> ProspectiveWriteTransaction:
    if len(candidate_blob) < 0x40:
        raise PreparedPackageCandidateError("candidate dynamic blob is shorter than its 64-byte header")
    try:
        return ProspectiveWriteTransaction(
            ranges=(
                fixed_state.range1,
                fixed_state.range2,
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
        raise PreparedPackageCandidateError(f"prospective package transaction is invalid: {exc}") from exc


@dataclass(frozen=True)
class PreparedPackageCandidate:
    """A complete, offline-only package candidate bound to one backup."""

    package: PreparedTextPackage
    backup: VerifiedBackup
    baseline: ParsedBackupBlob
    candidate: ParsedBackupBlob
    folder_candidate: PreparedFolderCandidate
    fixed_state: PreparedFixedStateSnapshot
    fixed_state_assessment: PreparedFixedStateAssessment
    transaction: ProspectiveWriteTransaction
    capacity_limit_bytes: int
    baseline_model_bytes: int
    candidate_model_bytes: int
    remaining_growth_bytes: int
    capacity_source: str
    available_capacity_bytes: int
    native_capacity_evidence: Optional[NativeCapacityEvidence]
    audit: Mapping[str, Any]

    @property
    def candidate_blob(self) -> bytes:
        return self.folder_candidate.candidate_blob

    @property
    def candidate_blob_sha256(self) -> str:
        return _sha256(self.candidate_blob)

    @property
    def transaction_sha256(self) -> str:
        return self.transaction.concatenated_sha256

    def audit_dict(self) -> dict[str, Any]:
        return dict(self.audit)


def build_prepared_package_candidate(
    package: PreparedTextPackage,
    backup: VerifiedBackup,
    template: ParsedBackupBlob,
    *,
    new_record_timestamp_be32: int,
    capacity_limit_bytes: Optional[int] = None,
    baseline_model_bytes: Optional[int] = None,
    candidate_model_bytes: Optional[int] = None,
    capacity_source: str = "explicit_total_limit",
    available_capacity_bytes: Optional[int] = None,
    native_capacity_response: Optional[NativeCapacityResponse] = None,
) -> PreparedPackageCandidate:
    """Build one constrained root-folder/TXT candidate from a fresh backup.

    ``capacity_limit_bytes`` is the preferred native meaning: the complete
    candidate model size must not exceed the dispatcher limit.  The older
    ``available_capacity_bytes`` argument remains an explicitly named
    compatibility path for offline callers that only have a remaining-growth
    budget; it is never presented as native device evidence.  ``template``
    must be the preserved capture-7 three-record template; no wrapper or
    directory bytes are invented.
    """

    if not isinstance(package, PreparedTextPackage):
        raise PreparedPackageCandidateError("package must be a PreparedTextPackage")
    if not isinstance(backup, VerifiedBackup):
        raise PreparedPackageCandidateError("backup must be a verified complete backup")
    if not isinstance(template, ParsedBackupBlob):
        raise PreparedPackageCandidateError("template must be a parsed preserved capture-7 blob")
    if isinstance(new_record_timestamp_be32, bool) or not isinstance(new_record_timestamp_be32, int) or not 0 <= new_record_timestamp_be32 <= 0xFFFFFFFF:
        raise PreparedPackageCandidateError("new_record_timestamp_be32 must fit an unsigned 32-bit integer")
    if native_capacity_response is not None and not isinstance(native_capacity_response, NativeCapacityResponse):
        raise PreparedPackageCandidateError("native_capacity_response must be parsed 0x0019 evidence")
    if native_capacity_response is not None:
        try:
            backup_identity = tuple(int(value, 16) for value in backup.device_identity)
        except (TypeError, ValueError) as exc:
            raise PreparedPackageCandidateError("verified backup device identity is not hexadecimal VID/PID") from exc
        if native_capacity_response.device_identity != backup_identity:
            raise PreparedPackageCandidateError("native capacity response device identity differs from the verified backup")
    supplied_total_fields = (capacity_limit_bytes, baseline_model_bytes, candidate_model_bytes)
    if native_capacity_response is not None:
        if any(value is not None for value in supplied_total_fields) or available_capacity_bytes is not None:
            raise PreparedPackageCandidateError("native capacity evidence cannot be combined with caller capacity values")
    elif any(value is not None for value in supplied_total_fields):
        if capacity_limit_bytes is None:
            raise PreparedPackageCandidateError("capacity_limit_bytes is required with total-capacity fields")
        if isinstance(capacity_limit_bytes, bool) or not isinstance(capacity_limit_bytes, int) or capacity_limit_bytes < 0:
            raise PreparedPackageCandidateError("capacity_limit_bytes must be a non-negative integer")
        if available_capacity_bytes is not None:
            raise PreparedPackageCandidateError("total capacity and remaining-growth capacity cannot be combined")
    elif available_capacity_bytes is None:
        raise PreparedPackageCandidateError("capacity cannot be established safely")
    elif isinstance(available_capacity_bytes, bool) or not isinstance(available_capacity_bytes, int) or available_capacity_bytes < 0:
        raise PreparedPackageCandidateError("available_capacity_bytes must be a non-negative integer")
    if not isinstance(capacity_source, str) or not capacity_source:
        raise PreparedPackageCandidateError("capacity_source must be a non-empty string")

    _validate_source(package)
    baseline_blob = _read_verified_blob(backup)
    try:
        baseline = parse_backup_blob(baseline_blob)
    except BackupFormatError as exc:
        raise PreparedPackageCandidateError(f"verified backup dynamic blob failed validation: {exc}") from exc

    conflicts = _path_conflicts(baseline, package)
    if conflicts:
        raise PreparedPackageCandidateError(
            "prepared package destination conflicts with the fresh backup: "
            + ", ".join(entry["path"] for entry in conflicts)
        )

    fixed_assessment = assess_prepared_fixed_state(backup)
    try:
        fixed_state = fixed_assessment.require_supported()
    except PreparedFixedStateError as exc:
        raise PreparedPackageCandidateError(f"fresh fixed-state preflight rejected package: {exc}") from exc
    try:
        folder_candidate = build_modern_root_folder_text_candidate(
            baseline,
            template,
            package.folder_name,
            package.item.name,
            package.source_text,
            new_record_timestamp_be32=new_record_timestamp_be32,
        )
    except PreparedFolderError as exc:
        raise PreparedPackageCandidateError(f"constrained folder candidate rejected: {exc}") from exc
    try:
        candidate = parse_backup_blob(folder_candidate.candidate_blob)
    except BackupFormatError as exc:
        raise PreparedPackageCandidateError(f"candidate dynamic blob failed validation: {exc}") from exc

    actual_baseline_model_bytes = len(baseline_blob)
    actual_candidate_model_bytes = len(folder_candidate.candidate_blob)
    if baseline_model_bytes is not None and baseline_model_bytes != actual_baseline_model_bytes:
        raise PreparedPackageCandidateError("baseline model length is inconsistent with the verified backup blob")
    if candidate_model_bytes is not None and candidate_model_bytes != actual_candidate_model_bytes:
        raise PreparedPackageCandidateError("candidate model length is inconsistent with the candidate blob")
    baseline_model_bytes = actual_baseline_model_bytes
    candidate_model_bytes = actual_candidate_model_bytes
    try:
        native_capacity_evidence = None
        if native_capacity_response is not None:
            try:
                native_capacity_evidence = native_capacity_response.bind_model_lengths(
                    baseline_model_bytes,
                    candidate_model_bytes,
                )
                capacity = assess_total_capacity(
                    native_capacity_evidence.capacity_limit_bytes,
                    native_capacity_evidence.baseline_model_bytes,
                    native_capacity_evidence.candidate_model_bytes,
                    source=native_capacity_evidence.evidence_source,
                )
            except NativeCapacityEvidenceError as exc:
                raise PreparedPackageCandidateError(str(exc)) from exc
        elif capacity_limit_bytes is not None:
            capacity = assess_total_capacity(
                capacity_limit_bytes,
                baseline_model_bytes,
                candidate_model_bytes,
                source=capacity_source,
            )
        else:
            capacity = assess_legacy_remaining_budget(
                available_capacity_bytes,
                baseline_model_bytes,
                candidate_model_bytes,
            )
    except CapacitySemanticsError as exc:
        raise PreparedPackageCandidateError(str(exc)) from exc
    candidate_growth = capacity.candidate_growth_bytes
    metadata_growth = candidate.header.metadata_length - baseline.header.metadata_length
    content_growth = candidate.header.content_length - baseline.header.content_length
    if candidate_growth <= 0:
        raise PreparedPackageCandidateError("candidate package growth must be positive")
    if metadata_growth != 3 * _RECORD_SIZE:
        raise PreparedPackageCandidateError("candidate metadata growth is not exactly three records")
    if content_growth <= 0:
        raise PreparedPackageCandidateError("candidate content growth must be positive")
    if candidate_growth != metadata_growth + content_growth:
        raise PreparedPackageCandidateError(
            "candidate growth is inconsistent with metadata and aligned content growth"
        )
    transaction = _build_transaction(folder_candidate.candidate_blob, fixed_state)
    if transaction.variable_n + transaction.variable_m != candidate_model_bytes:
        raise PreparedPackageCandidateError("candidate model length is inconsistent with the prospective transaction")
    added_offsets = [
        offset
        for offset, path in candidate.paths.items()
        if path not in baseline.paths.values()
    ]
    added_paths = sorted(_display_path(candidate, offset) for offset in added_offsets)
    if added_paths != sorted([package.target_folder_path, package.target_item_path]):
        raise PreparedPackageCandidateError("candidate added paths outside the one-folder/one-TXT scope")

    audit = {
        "format": PREPARED_PACKAGE_CANDIDATE_FORMAT,
        "state": "offline_only",
        "usb_transmission_performed": False,
        "device_identity": {
            "vendor_id": backup.device_identity[0],
            "product_id": backup.device_identity[1],
        },
        "source": {
            "path": str(package.source_path),
            "sha256": package.source_sha256,
            "utf8_bytes": len(package.source_bytes),
            "prepared_payload_bytes": package.prepared_payload_bytes,
            "prepared_payload_sha256": _sha256(package.item.authored.payload),
        },
        "package": {
            "folder_path": package.target_folder_path,
            "child_path": package.target_item_path,
            "prepared_manifest_sha256": package.prepared_manifest_sha256,
        },
        "baseline": {
            "manifest_sha256": backup.manifest_sha256,
            "blob_sha256": backup.blob_sha256,
            "blob_length": len(baseline_blob),
            "record_count": len(baseline.records),
            "reachable_path_count": len(baseline.paths),
        },
        "candidate": {
            "blob_sha256": _sha256(folder_candidate.candidate_blob),
            "blob_length": len(folder_candidate.candidate_blob),
            "record_count": len(candidate.records),
            "reachable_path_count": len(candidate.paths),
            "added_paths": added_paths,
            "new_record_timestamp_be32": f"0x{new_record_timestamp_be32:08x}",
            "folder_record_offset": folder_candidate.audit["target"]["folder_record_offset_hex"],
            "child_record_offset": folder_candidate.audit["target"]["child_record_offset_hex"],
        },
        "allocation": {
            "metadata_growth_bytes": metadata_growth,
            "aligned_content_growth_bytes": content_growth,
            "candidate_growth_bytes": capacity.candidate_growth_bytes,
            "complete_candidate_growth_bytes": capacity.candidate_growth_bytes,
            "capacity_limit_bytes": capacity.capacity_limit_bytes,
            "baseline_model_bytes": capacity.baseline_model_bytes,
            "candidate_model_bytes": capacity.candidate_model_bytes,
            "remaining_growth_bytes": capacity.remaining_growth_bytes,
            "capacity_source": capacity.source,
            # Compatibility alias: this is remaining growth, not total limit.
            "available_capacity_bytes": capacity.remaining_growth_bytes,
            "capacity_result": "sufficient",
        },
        "capacity_evidence": (
            native_capacity_evidence.to_dict()
            if native_capacity_evidence is not None
            else None
        ),
        "fixed_state": fixed_assessment.to_dict(),
        "transaction": {
            "command": "0x101b",
            "payload_length": transaction.payload_length,
            "sha256": transaction.concatenated_sha256,
            "range_lengths": [len(data) for data in transaction.ranges],
            "fixed_state_hashes": [
                _sha256(data) for data in (fixed_state.raw_blocks)
            ],
        },
        "preservation": folder_candidate.audit["preservation"],
        "assumptions": [
            "The preserved capture-7 folder, leading marker, and TXT prefix are the only templates used.",
            "Existing record timestamps are preserved byte-for-byte.",
            "One explicit frozen timestamp is assigned only to the three new records.",
            "Only exact capture-7-compatible all-zero fixed state is eligible; no rebasing is attempted.",
            "No category, mark, bookmark, selection, history, or Manager-side sidecar membership is assigned.",
            "This candidate is not evidence of arbitrary folder or multi-record compatibility.",
        ],
    }
    return PreparedPackageCandidate(
        package=package,
        backup=backup,
        baseline=baseline,
        candidate=candidate,
        folder_candidate=folder_candidate,
        fixed_state=fixed_state,
        fixed_state_assessment=fixed_assessment,
        transaction=transaction,
        capacity_limit_bytes=capacity.capacity_limit_bytes,
        baseline_model_bytes=capacity.baseline_model_bytes,
        candidate_model_bytes=capacity.candidate_model_bytes,
        remaining_growth_bytes=capacity.remaining_growth_bytes,
        capacity_source=capacity.source,
        available_capacity_bytes=capacity.remaining_growth_bytes,
        native_capacity_evidence=native_capacity_evidence,
        audit=audit,
    )


__all__ = [
    "PREPARED_PACKAGE_CANDIDATE_FORMAT",
    "PreparedPackageCandidate",
    "PreparedPackageCandidateError",
    "build_prepared_package_candidate",
]
