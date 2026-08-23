"""Offline preview for one prepared folder/TXT package.

The preview reads a complete verified backup, compares proposed paths, and
reports the proven and blocked primitives.  It never constructs a candidate
blob, mutates the backup, opens USB, or authorizes a sender.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Optional

from .backup_format import BackupFormatError, parse_backup_blob
from .prepared_package import PreparedTextPackage
from .write_gate import VerifiedBackup


PREPARED_TRANSFER_PLAN_FORMAT = "infocarry-prepared-transfer-plan-v1"


class PreparedTransferPlanError(ValueError):
    """Raised when an offline package preview cannot be built safely."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True)
class PreparedTransferPlan:
    """Hash-bound, no-device-change preview for one prepared package."""

    report: Mapping[str, Any]

    @property
    def eligible(self) -> bool:
        return bool(self.report["eligibility"]["candidate_eligible"])

    @property
    def plan_sha256(self) -> str:
        return str(self.report["plan_sha256"])

    def to_dict(self) -> dict[str, Any]:
        return dict(self.report)


def _read_verified_blob(backup: VerifiedBackup) -> bytes:
    key = "0x8004:backup-blob"
    filename = backup.object_filename(key)
    expected_hash = backup.object_sha256(key)
    if filename is None or expected_hash is None:
        raise PreparedTransferPlanError("verified backup is missing its dynamic blob")
    path = backup.directory / filename
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise PreparedTransferPlanError(f"could not read verified backup blob: {exc}") from exc
    if _sha256(data) != expected_hash or expected_hash != backup.blob_sha256:
        raise PreparedTransferPlanError("verified backup dynamic blob changed after verification")
    return data


def build_prepared_transfer_plan(
    package: PreparedTextPackage,
    backup: VerifiedBackup,
    *,
    available_capacity_bytes: Optional[int] = None,
) -> PreparedTransferPlan:
    """Compare a logical package with a complete verified backup.

    A non-negative capacity is interpreted only against the package's
    lower-bound estimate.  It cannot make an unproven folder transaction
    eligible.
    """

    if not isinstance(package, PreparedTextPackage):
        raise PreparedTransferPlanError("package must be a PreparedTextPackage")
    if not isinstance(backup, VerifiedBackup):
        raise PreparedTransferPlanError("backup must be a verified complete backup")
    if available_capacity_bytes is not None and (
        isinstance(available_capacity_bytes, bool)
        or not isinstance(available_capacity_bytes, int)
        or available_capacity_bytes < 0
    ):
        raise PreparedTransferPlanError("available_capacity_bytes must be a non-negative integer or None")
    try:
        baseline_blob = _read_verified_blob(backup)
        parsed = parse_backup_blob(baseline_blob)
    except (BackupFormatError, PreparedTransferPlanError) as exc:
        if isinstance(exc, PreparedTransferPlanError):
            raise
        raise PreparedTransferPlanError(f"verified backup dynamic blob failed validation: {exc}") from exc

    folder_path = ("root", package.folder_name)
    item_path = folder_path + (package.item.name,)
    conflicts: list[dict[str, Any]] = []
    for path in (folder_path, item_path):
        if path in parsed.paths.values():
            offset = next(offset for offset, value in parsed.paths.items() if value == path)
            record = parsed.record_at(offset)
            conflicts.append(
                {
                    "path": "\\".join(path),
                    "record_offset": offset,
                    "record_kind": record.kind,
                    "reason": "proposed package path already exists",
                }
            )

    lower_bound = package.estimated_growth_lower_bound
    if available_capacity_bytes is None:
        capacity = {
            "status": "unknown",
            "available_bytes": None,
            "lower_bound_bytes": lower_bound,
            "exact_growth_known": False,
        }
    elif available_capacity_bytes < lower_bound:
        capacity = {
            "status": "insufficient_for_lower_bound",
            "available_bytes": available_capacity_bytes,
            "lower_bound_bytes": lower_bound,
            "exact_growth_known": False,
        }
    else:
        capacity = {
            "status": "sufficient_for_lower_bound_only",
            "available_bytes": available_capacity_bytes,
            "lower_bound_bytes": lower_bound,
            "exact_growth_known": False,
        }

    report: dict[str, Any] = {
        "format": PREPARED_TRANSFER_PLAN_FORMAT,
        "state": "previewed",
        "usb_accessed": False,
        "device_change": "none",
        "notice": "OFFLINE PREVIEW ONLY — no device change has occurred",
        "package": {
            "folder_path": package.target_folder_path,
            "item_path": package.target_item_path,
            "source_sha256": package.source_sha256,
            "prepared_manifest_sha256": package.prepared_manifest_sha256,
            "prepared_payload_sha256": package.item.to_dict(0)["prepared_payload_sha256"],
            "prepared_payload_bytes": package.prepared_payload_bytes,
            "native_wrapper_bytes_required": package.item.to_dict(0)["native_wrapper"]["length_bytes"],
        },
        "baseline": {
            "device_identity": {
                "vendor_id": backup.device_identity[0],
                "product_id": backup.device_identity[1],
            },
            "manifest_sha256": backup.manifest_sha256,
            "blob_sha256": backup.blob_sha256,
            "object_count": backup.object_count,
            "record_count": len(parsed.records),
            "reachable_record_count": len(parsed.paths),
        },
        "proposed": {
            "destination_paths": [package.target_folder_path, package.target_item_path],
            "required_new_records": [
                {"role": "directory", "path": package.target_folder_path},
                {"role": "parent_marker", "path": f"{package.target_folder_path}\\.."},
                {"role": "txt_child", "path": package.target_item_path},
            ],
            "child_order": [package.item.name],
            "folder_depth": 1,
        },
        "conflicts": {
            "status": "conflict" if conflicts else "none",
            "entries": conflicts,
        },
        "size": {
            "prepared_payload_bytes": package.prepared_payload_bytes,
            "aligned_content_bytes": package.aligned_content_bytes,
            "estimated_device_growth_lower_bound": lower_bound,
            "capacity": capacity,
        },
        "proven_primitives": {
            "offline_utf8_to_cp932_crlf_preparation": True,
            "standalone_root_txt_creation": True,
            "capture7_one_folder_one_txt_fixture_reproduction": True,
            "existing_folder_record_parsing": True,
            "new_root_folder_creation": False,
            "new_multi_record_creation": False,
            "folder_child_pointer_construction": False,
            "folder_sidecar_lifecycle": False,
        },
        "blocked_primitives": [
            "fresh_folder_timestamp_generation",
            "fresh_fixed_state_derivation",
            "exact_folder_package_growth_and_capacity_semantics",
            "request4_completion_decoding",
            "live_folder_package_transaction",
        ],
        "eligibility": {
            "preparation_ready": True,
            "root_txt_primitive_proven_separately": True,
            "exact_capture7_fixture_reproduction_scope": True,
            "root_folder_creation_proven": False,
            "multi_record_creation_proven": False,
            "exact_growth_known": False,
            "name_conflict_free": not conflicts,
            "capacity_safely_sufficient": capacity["status"] == "sufficient_for_lower_bound_only",
            "candidate_eligible": False,
            "reasons": [
                "new root-folder creation is unproven",
                "new multi-record folder-plus-child construction is unproven",
                "exact device growth and folder capacity semantics are unresolved",
                "no device candidate is constructed by this preview",
            ] + (["proposed package path conflicts with the verified backup"] if conflicts else []),
        },
        "safety": {
            "candidate_bytes_included": False,
            "authorization_created": False,
            "sender_called": False,
            "automatic_retry": False,
        },
    }
    report["plan_sha256"] = _sha256(_canonical_json(report))
    return PreparedTransferPlan(report=report)


__all__ = [
    "PREPARED_TRANSFER_PLAN_FORMAT",
    "PreparedTransferPlan",
    "PreparedTransferPlanError",
    "build_prepared_transfer_plan",
]
