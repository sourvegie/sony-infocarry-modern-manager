"""Read-only readiness preview for an ordered prepared package.

The preview is a presentation model, not an authorization or transfer
operation.  It can summarize a logical package before a device candidate
exists, or summarize an already-built offline candidate.  No USB module is
imported and no candidate bytes are included in the report.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Mapping, Optional

from .backup_format import BackupFormatError, ParsedBackupBlob, parse_backup_blob
from .prepared_media_package import PreparedMediaPackage
from .prepared_multi_text import PreparedTextPackageSet
from .prepared_package_multi_candidate import PreparedMultiPackageCandidate
from .write_gate import VerifiedBackup


PREPARED_PACKAGE_READINESS_FORMAT = "infocarry-prepared-package-readiness-v1"
PreparedPackageInput = PreparedTextPackageSet | PreparedMediaPackage


class PreparedPackageReadinessError(ValueError):
    """Raised when a readiness preview cannot be represented safely."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_backup_blob(backup: VerifiedBackup) -> bytes:
    filename = backup.object_filename("0x8004:backup-blob")
    expected = backup.object_sha256("0x8004:backup-blob")
    if filename is None or expected is None:
        raise PreparedPackageReadinessError("verified backup has no dynamic model object")
    try:
        data = (backup.directory / filename).read_bytes()
    except OSError as exc:
        raise PreparedPackageReadinessError(f"could not read verified backup model: {exc}") from exc
    if _sha256(data) != expected:
        raise PreparedPackageReadinessError("verified backup model changed after verification")
    return data


def _display_path(parsed: ParsedBackupBlob, path: tuple[str, ...]) -> str:
    offsets = [offset for offset, value in parsed.paths.items() if value == path]
    if len(offsets) != 1:
        raise PreparedPackageReadinessError("backup contains an ambiguous reachable path")
    record = parsed.record_at(offsets[0])
    if record.kind == "file":
        return "\\".join(path[:-1] + (path[-1] + "." + record.extension,))
    return "\\".join(path)


def _backup_paths(backup: VerifiedBackup) -> set[str]:
    try:
        parsed = parse_backup_blob(_read_backup_blob(backup))
    except BackupFormatError as exc:
        raise PreparedPackageReadinessError(f"verified backup model is malformed: {exc}") from exc
    return {_display_path(parsed, path).casefold() for path in parsed.paths.values()}


def _item_report(package: PreparedPackageInput) -> list[dict[str, Any]]:
    folder_path = package.target_folder_path
    reports: list[dict[str, Any]] = []
    for order, item in enumerate(package.items):
        if item.kind == "txt":
            encoded_bytes = len(item.authored.payload)
            source_bytes = len(item.source_bytes)
        elif item.kind == "bmp":
            encoded_bytes = len(item.source_bytes)
            source_bytes = len(item.source_bytes)
        else:
            raise PreparedPackageReadinessError(f"unsupported package item kind: {item.kind!r}")
        reports.append(
            {
                "order": order,
                "kind": item.kind,
                "path": package.target_item_paths[order],
                "source_sha256": item.source_sha256,
                "payload_sha256": item.payload_sha256,
                "source_bytes": source_bytes,
                "encoded_or_payload_bytes": encoded_bytes,
                "aligned_content_bytes": item.aligned_content_bytes,
                "source_path": str(item.source_path),
            }
        )
    return reports


@dataclass(frozen=True)
class PreparedPackageReadinessPreview:
    """A JSON-safe, read-only package readiness summary."""

    package: PreparedPackageInput
    report: Mapping[str, Any]

    @property
    def candidate_available(self) -> bool:
        return self.report["candidate"]["available"] is True

    def to_dict(self) -> dict[str, Any]:
        return dict(self.report)


def build_prepared_package_readiness_preview(
    package: PreparedPackageInput,
    *,
    backup: Optional[VerifiedBackup] = None,
    candidate: Optional[PreparedMultiPackageCandidate] = None,
) -> PreparedPackageReadinessPreview:
    """Build a read-only package preview without calling USB or a sender."""

    if not isinstance(package, (PreparedTextPackageSet, PreparedMediaPackage)):
        raise PreparedPackageReadinessError(
            "readiness preview supports only the ordered TXT or TXT/BMP package models"
        )
    if candidate is not None:
        if not isinstance(candidate, PreparedMultiPackageCandidate):
            raise PreparedPackageReadinessError("candidate must be a prepared multi-package candidate")
        if candidate.package != package:
            raise PreparedPackageReadinessError("candidate package differs from preview package")
        if backup is not None and candidate.backup.manifest_sha256 != backup.manifest_sha256:
            raise PreparedPackageReadinessError("candidate and preview backup differ")
        backup = candidate.backup

    target_paths = [package.target_folder_path, *package.target_item_paths]
    conflicts: list[str] = []
    if backup is not None:
        existing = _backup_paths(backup)
        conflicts = [path for path in target_paths if path.casefold() in existing]

    items = _item_report(package)
    capacity: dict[str, Any]
    candidate_report: dict[str, Any]
    if candidate is None:
        capacity = {
            "status": "not_evaluated_without_candidate",
            "baseline_model_bytes": None if backup is None else len(_read_backup_blob(backup)),
            "candidate_model_bytes": None,
            "growth_bytes": package.estimated_growth_lower_bound,
            "capacity_limit_bytes": None,
            "remaining_growth_bytes": None,
            "native_capacity_response_sha256": None,
        }
        candidate_report = {
            "available": False,
            "candidate_blob_sha256": None,
            "candidate_blob_length": None,
            "transaction_sha256": None,
            "record_count_before": None,
            "record_count_after": None,
        }
    else:
        allocation = dict(candidate.audit["allocation"])
        capacity = {
            "status": allocation["capacity_result"],
            "baseline_model_bytes": allocation["baseline_model_bytes"],
            "candidate_model_bytes": allocation["candidate_model_bytes"],
            "growth_bytes": allocation["candidate_growth_bytes"],
            "capacity_limit_bytes": allocation["capacity_limit_bytes"],
            "remaining_growth_bytes": allocation["remaining_growth_bytes"],
            "native_capacity_response_sha256": candidate.native_capacity_evidence.raw_response_sha256,
        }
        candidate_report = {
            "available": True,
            "candidate_blob_sha256": candidate.candidate_blob_sha256,
            "candidate_blob_length": len(candidate.candidate_blob),
            "transaction_sha256": candidate.transaction_sha256,
            "record_count_before": len(candidate.baseline.records),
            "record_count_after": len(candidate.candidate.records),
        }

    reasons: list[str] = []
    if conflicts:
        reasons.append("one or more destination paths already exist in the verified backup")
    if candidate is None:
        reasons.append("no native multi-child candidate has been constructed")
    reasons.append("multi-child live transfer remains unproven and disabled")
    report = {
        "format": PREPARED_PACKAGE_READINESS_FORMAT,
        "state": "previewed_offline",
        "notice": "OFFLINE PACKAGE READINESS PREVIEW — no device change occurred",
        "usb_accessed": False,
        "device_change": "none",
        "package": {
            "folder_path": package.target_folder_path,
            "paths": target_paths,
            "ordered_items": items,
            "prepared_manifest_sha256": package.prepared_manifest_sha256,
            "minimum_metadata_records": package.minimum_metadata_records,
            "estimated_growth_lower_bound": package.estimated_growth_lower_bound,
        },
        "backup": {
            "verified": backup is not None,
            "manifest_sha256": None if backup is None else backup.manifest_sha256,
            "blob_sha256": None if backup is None else backup.blob_sha256,
        },
        "conflicts": conflicts,
        "unsupported": [],
        "capacity": capacity,
        "candidate": candidate_report,
        "compatibility": {
            "preparation": "ready",
            "ordered_txt_bmp_package": "ready_offline",
            "root_folder_creation": "proven_only_for_existing_constrained_shape",
            "multi_record_creation": "offline_candidate_only",
            "live_transfer": "blocked",
            "normal_gui_cli_action": "disabled",
        },
        "eligibility": {
            "offline_preview_ready": not conflicts,
            "live_transfer_eligible": False,
            "reasons": reasons,
        },
        "safety": {
            "source_mutated": False,
            "candidate_bytes_included": False,
            "sender_called": False,
            "automatic_retry": False,
        },
    }
    return PreparedPackageReadinessPreview(package=package, report=report)


__all__ = [
    "PREPARED_PACKAGE_READINESS_FORMAT",
    "PreparedPackageReadinessError",
    "PreparedPackageReadinessPreview",
    "build_prepared_package_readiness_preview",
]
