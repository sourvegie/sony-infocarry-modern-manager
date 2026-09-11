"""Offline Library transfer queue planning.

This module connects prepared local Library items to a reviewable queue plan.
It is deliberately independent of USB, candidate construction, authorization,
and sender code.  An explicitly imported prepared package remains one grouped
queue item; several unrelated Library items are never inferred to be one
native multi-child package.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from .backup_format import BackupFormatError, parse_backup_blob
from .capacity_evidence import NativeCapacityResponse
from .library import (
    PREPARATION_PREPARED,
    SOURCE_PRESENT,
    STATE_READY,
    LibraryCatalog,
    LibraryItem,
)
from .prepared_package import PreparedPackageError, build_prepared_text_package
from .prepared_media_package import (
    PreparedMediaPackageError,
    load_prepared_media_package,
)
from .prepared_transfer_plan import (
    PreparedTransferPlanError,
    build_prepared_transfer_plan,
)
from .write_gate import VerifiedBackup


LIBRARY_TRANSFER_PLAN_FORMAT = "infocarry-library-transfer-plan-v1"
LIBRARY_TRANSFER_PLAN_NOTICE = (
    "OFFLINE LIBRARY TRANSFER QUEUE — no device access or device change occurred"
)
SELECTION_SELECTED = "selected"
SELECTION_ALL_READY = "all_ready"
PREPARED_ROOT_TXT_OPERATION = "prepared_root_txt_package"
PREPARED_FLAT_PACKAGE_OPERATION = "prepared_flat_typed_package"
QUEUE_GROUPING_POLICY = "one_prepared_package_per_library_item_no_automatic_grouping"


class LibraryTransferPlanError(ValueError):
    """Raised when an offline Library queue plan cannot be represented safely."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _read_verified_blob(backup: VerifiedBackup) -> bytes:
    key = "0x8004:backup-blob"
    filename = backup.object_filename(key)
    expected = backup.object_sha256(key)
    if filename is None or expected is None:
        raise LibraryTransferPlanError("verified backup is missing its dynamic model")
    path = backup.directory / filename
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise LibraryTransferPlanError(f"could not read verified backup model: {exc}") from exc
    if _sha256(data) != expected or expected != backup.blob_sha256:
        raise LibraryTransferPlanError("verified backup dynamic model changed after verification")
    return data


def _backup_display_paths(backup: VerifiedBackup) -> dict[str, dict[str, Any]]:
    try:
        parsed = parse_backup_blob(_read_verified_blob(backup))
    except BackupFormatError as exc:
        raise LibraryTransferPlanError(f"verified backup dynamic model is malformed: {exc}") from exc

    result: dict[str, dict[str, Any]] = {}
    for offset, path in parsed.paths.items():
        record = parsed.record_at(offset)
        parts = path
        if record.kind == "file":
            parts = path[:-1] + (f"{path[-1]}.{record.extension}",)
        display_path = "\\".join(parts)
        result[display_path.casefold()] = {
            "path": display_path,
            "record_offset": offset,
            "record_kind": record.kind,
        }
    return result


def _backup_summary(backup: VerifiedBackup) -> dict[str, Any]:
    try:
        parsed = parse_backup_blob(_read_verified_blob(backup))
    except BackupFormatError as exc:
        raise LibraryTransferPlanError(f"verified backup dynamic model is malformed: {exc}") from exc
    return {
        "available": True,
        "device_identity": {
            "vendor_id": backup.device_identity[0],
            "product_id": backup.device_identity[1],
        },
        "manifest_sha256": backup.manifest_sha256,
        "blob_sha256": backup.blob_sha256,
        "object_count": backup.object_count,
        "record_count": len(parsed.records),
        "reachable_record_count": len(parsed.paths),
        "directory": str(backup.directory),
        "source": "verified_offline_backup",
    }


def _base_item_report(item: LibraryItem) -> dict[str, Any]:
    target_paths = []
    if item.target_folder_name:
        folder = f"root\\{item.target_folder_name}"
        target_paths.append(folder)
        if item.package is not None:
            target_paths.extend(
                f"{folder}\\{child['name']}"
                for child in item.package.children
            )
        elif item.target_child_name:
            target_paths.append(f"{folder}\\{item.target_child_name}")
    is_package = item.package is not None
    prepared_artifact: dict[str, Any] = {
        "manifest_sha256": item.prepared_manifest_sha256,
        "manifest_path": item.prepared_manifest_path,
    }
    if is_package:
        prepared_artifact.update(
            {
                "package_root": item.package.root_path,
                "contract": item.package.format,
                "child_order": [child.get("name") for child in item.package.children],
                "ordered_children": [
                    {
                        "order": child.get("order"),
                        "kind": child.get("kind"),
                        "name": child.get("name"),
                        "path": child.get("path"),
                        "source_sha256": child.get("source", {}).get("sha256"),
                        "source_bytes": child.get("source", {}).get("bytes"),
                        "prepared_payload_sha256": (
                            child.get("authoring", {}).get("prepared_payload_sha256")
                            if child.get("kind") == "txt"
                            else child.get("bmp", {}).get("payload_sha256")
                        ),
                    }
                    for child in item.package.children
                ],
            }
        )
    return {
        "item_id": item.item_id,
        "source": {
            "path": item.source_path,
            "filename": item.source_filename,
            "sha256": item.source_sha256,
            "size_bytes": item.source_size_bytes,
            "status": item.source_status,
        },
        "prepared_artifact": prepared_artifact,
        "destination": {
            "paths": target_paths,
            "folder_path": target_paths[0] if target_paths else None,
            "child_path": target_paths[1] if len(target_paths) > 1 else None,
        },
        "operation_type": PREPARED_FLAT_PACKAGE_OPERATION if is_package else PREPARED_ROOT_TXT_OPERATION,
        "execution_eligible": False,
        "compatibility_state": "blocked",
        "conflicts": [],
        "capacity": {
            "status": "not_evaluated",
            "lower_bound_bytes": None,
            "available_bytes": None,
            "exact_growth_known": False,
        },
        "queue_ready": False,
        "reasons": [],
    }


def _prepare_item_report(
    item: LibraryItem,
    *,
    backup: Optional[VerifiedBackup],
    available_capacity_bytes: Optional[int],
) -> dict[str, Any]:
    report = _base_item_report(item)
    reasons = report["reasons"]
    if not item.supported:
        reasons.append("Library source format is unsupported")
    if item.source_status != SOURCE_PRESENT:
        reasons.append(f"Library source is not current and present ({item.source_status})")
    if item.state != STATE_READY or item.preparation_state != PREPARATION_PREPARED:
        reasons.append("Library item has no current prepared artifact")
    if not item.target_folder_name or (item.package is None and not item.target_child_name):
        reasons.append("prepared destination folder and child are missing")
    if item.prepared_manifest_sha256 is None:
        reasons.append("prepared manifest hash is missing")
    if reasons:
        return report

    if item.package is not None:
        try:
            imported = load_prepared_media_package(Path(item.package.root_path))
        except (OSError, PreparedMediaPackageError) as exc:
            reasons.append(f"prepared package could not be revalidated: {exc}")
            return report
        if imported.manifest_sha256 != item.package.manifest_sha256:
            reasons.append("prepared package manifest hash does not match the Library catalog")
            return report
        if imported.manifest_sha256 != item.prepared_manifest_sha256:
            reasons.append("prepared manifest hash does not match the Library catalog")
            return report
        if str(imported.manifest_path) != item.package.manifest_path:
            reasons.append("prepared package manifest path does not match the Library catalog")
            return report
        if [dict(child) for child in imported.children] != [dict(child) for child in item.package.children]:
            reasons.append("prepared package child manifest differs from the Library grouping record")
            return report
        package = imported.package
        report["prepared_artifact"].update(
            {
                "manifest_sha256": imported.manifest_sha256,
                "manifest_path": str(imported.manifest_path),
                "source_bytes": sum(child.get("source", {}).get("bytes", 0) for child in imported.children),
                "prepared_payload_bytes": package.prepared_payload_bytes,
                "aligned_content_bytes": package.aligned_content_bytes,
                "estimated_growth_lower_bound": package.estimated_growth_lower_bound,
                "child_order": [child.name for child in package.items],
                "kind": "flat_txt_bmp_package",
                "ordered_children": [
                    {
                        "order": index,
                        "kind": child.kind,
                        "name": child.name,
                        "path": package.target_item_paths[index],
                        "source_sha256": child.source_sha256,
                        "source_bytes": (
                            len(child.source_bytes)
                            if child.kind == "bmp"
                            else len(child.source_bytes)
                        ),
                        "prepared_payload_sha256": child.payload_sha256,
                        "prepared_payload_bytes": (
                            len(child.source_bytes)
                            if child.kind == "bmp"
                            else len(child.authored.payload)
                        ),
                    }
                    for index, child in enumerate(package.items)
                ],
            }
        )
        report["destination"] = {
            "paths": [package.target_folder_path, *package.target_item_paths],
            "folder_path": package.target_folder_path,
            "child_path": None,
        }
        report["compatibility_state"] = "prepared_flat_package_ready_for_offline_review"
        report["capacity"]["lower_bound_bytes"] = package.estimated_growth_lower_bound
        if backup is not None:
            try:
                display_paths = _backup_display_paths(backup)
            except LibraryTransferPlanError as exc:
                reasons.append(f"verified backup comparison failed: {exc}")
                return report
            for destination in report["destination"]["paths"]:
                existing = display_paths.get(destination.casefold())
                if existing is not None:
                    report["conflicts"].append(
                        {
                            "path": existing["path"],
                            "record_offset": existing["record_offset"],
                            "record_kind": existing["record_kind"],
                            "reason": "proposed Library package destination already exists in the verified backup",
                        }
                    )
            report["capacity"] = {
                "status": (
                    "unknown"
                    if available_capacity_bytes is None
                    else (
                        "insufficient_for_lower_bound"
                        if available_capacity_bytes < package.estimated_growth_lower_bound
                        else "sufficient_for_lower_bound_only"
                    )
                ),
                "baseline_model_bytes": len(_read_verified_blob(backup)),
                "candidate_model_bytes": None,
                "lower_bound_bytes": package.estimated_growth_lower_bound,
                "available_bytes": available_capacity_bytes,
                "exact_growth_known": False,
            }
            if report["conflicts"]:
                reasons.append("one or more destination paths conflict with the verified backup")
            if report["capacity"]["status"] == "insufficient_for_lower_bound":
                reasons.append("available capacity is below the package lower bound")
            elif report["capacity"]["status"] == "unknown":
                reasons.append("available capacity was not supplied for this queue review")
        else:
            report["capacity"] = {
                "status": "not_evaluated_without_verified_backup",
                "lower_bound_bytes": package.estimated_growth_lower_bound,
                "available_bytes": None,
                "exact_growth_known": False,
            }
            reasons.append("verified device backup is required for destination and capacity review")
        report["queue_ready"] = not reasons
        return report

    try:
        package = build_prepared_text_package(
            Path(item.source_path),
            item.target_folder_name,
            item.target_child_name,
        )
    except (OSError, PreparedPackageError) as exc:
        reasons.append(f"prepared artifact could not be rebuilt: {exc}")
        return report

    if package.source_sha256 != item.source_sha256:
        reasons.append("source hash changed during queue planning")
        return report
    if package.prepared_manifest_sha256 != item.prepared_manifest_sha256:
        reasons.append("prepared manifest hash does not match the Library catalog")
        return report

    report["prepared_artifact"] = {
        "manifest_sha256": package.prepared_manifest_sha256,
        "manifest_path": item.prepared_manifest_path,
        "source_sha256": package.source_sha256,
        "source_bytes": len(package.source_bytes),
        "prepared_payload_bytes": package.prepared_payload_bytes,
        "aligned_content_bytes": package.aligned_content_bytes,
        "estimated_growth_lower_bound": package.estimated_growth_lower_bound,
        "child_order": [package.item.name],
        "kind": "txt",
    }
    report["destination"] = {
        "paths": [package.target_folder_path, package.target_item_path],
        "folder_path": package.target_folder_path,
        "child_path": package.target_item_path,
    }
    report["compatibility_state"] = "constrained_shape_ready_for_offline_review"
    report["capacity"]["lower_bound_bytes"] = package.estimated_growth_lower_bound

    if backup is not None:
        try:
            single_plan = build_prepared_transfer_plan(
                package,
                backup,
                available_capacity_bytes=available_capacity_bytes,
            )
        except PreparedTransferPlanError as exc:
            reasons.append(f"verified backup comparison failed: {exc}")
            return report
        single_report = single_plan.to_dict()
        report["capacity"] = dict(single_report["size"]["capacity"])
        display_paths = _backup_display_paths(backup)
        for destination in report["destination"]["paths"]:
            existing = display_paths.get(destination.casefold())
            if existing is not None:
                report["conflicts"].append(
                    {
                        "path": existing["path"],
                        "record_offset": existing["record_offset"],
                        "record_kind": existing["record_kind"],
                        "reason": "proposed Library destination already exists in the verified backup",
                    }
                )
        if report["conflicts"]:
            reasons.append("one or more destination paths conflict with the verified backup")
        if report["capacity"]["status"] == "insufficient_for_lower_bound":
            reasons.append("available capacity is below the package lower bound")
        elif report["capacity"]["status"] == "unknown":
            reasons.append("available capacity was not supplied for this queue review")
    else:
        report["capacity"] = {
            "status": "not_evaluated_without_verified_backup",
            "lower_bound_bytes": package.estimated_growth_lower_bound,
            "available_bytes": None,
            "exact_growth_known": False,
        }
        reasons.append("verified device backup is required for destination and capacity review")

    report["queue_ready"] = not reasons
    if report["queue_ready"]:
        report["compatibility_state"] = "constrained_shape_ready_for_offline_review"
    return report


def _validate_capacity_input(
    backup: Optional[VerifiedBackup],
    available_capacity_bytes: Optional[int],
    capacity_evidence: Optional[NativeCapacityResponse],
) -> None:
    if capacity_evidence is not None:
        if not isinstance(capacity_evidence, NativeCapacityResponse):
            raise LibraryTransferPlanError(
                "capacity_evidence must be parsed native 0x0019 evidence"
            )
        if backup is None:
            raise LibraryTransferPlanError(
                "capacity_evidence requires a verified offline backup baseline"
            )
        try:
            backup_identity = tuple(
                int(value, 16) for value in backup.device_identity
            )
        except (TypeError, ValueError) as exc:
            raise LibraryTransferPlanError(
                "verified backup device identity is malformed"
            ) from exc
        if capacity_evidence.device_identity != backup_identity:
            raise LibraryTransferPlanError(
                "capacity evidence identity differs from the verified backup"
            )
        if (
            available_capacity_bytes is not None
            and available_capacity_bytes != capacity_evidence.capacity_limit_bytes
        ):
            raise LibraryTransferPlanError(
                "available capacity differs from the parsed native capacity evidence"
            )
        available_capacity_bytes = capacity_evidence.capacity_limit_bytes
    if available_capacity_bytes is None:
        return
    if backup is None:
        raise LibraryTransferPlanError(
            "available_capacity_bytes requires a verified offline backup baseline"
        )
    if (
        isinstance(available_capacity_bytes, bool)
        or not isinstance(available_capacity_bytes, int)
        or available_capacity_bytes < 0
    ):
        raise LibraryTransferPlanError(
            "available_capacity_bytes must be a non-negative integer or None"
        )


def build_library_transfer_queue_plan(
    catalog: LibraryCatalog,
    *,
    selected_item_ids: Optional[Sequence[str]] = None,
    selection_mode: str = SELECTION_SELECTED,
    backup: Optional[VerifiedBackup] = None,
    available_capacity_bytes: Optional[int] = None,
    capacity_evidence: Optional[NativeCapacityResponse] = None,
) -> "LibraryTransferQueuePlan":
    """Build a no-device Library queue review plan.

    ``selected`` preserves the caller's explicit item order.  ``all_ready``
    includes only current, prepared, supported items and records other
    catalog entries in ``selection.excluded_items``.  No mode constructs a
    candidate, authorization, transaction, or sender action.  When supplied,
    ``capacity_evidence`` is the typed parsed native ``0x0019`` response and
    binds the reported capacity to the verified backup's VNW-V15 identity.
    """

    if not isinstance(catalog, LibraryCatalog):
        raise LibraryTransferPlanError("catalog must be a LibraryCatalog")
    if selection_mode not in {SELECTION_SELECTED, SELECTION_ALL_READY}:
        raise LibraryTransferPlanError(
            f"selection_mode must be {SELECTION_SELECTED!r} or {SELECTION_ALL_READY!r}"
        )
    _validate_capacity_input(backup, available_capacity_bytes, capacity_evidence)
    if capacity_evidence is not None:
        available_capacity_bytes = capacity_evidence.capacity_limit_bytes

    by_id = {item.item_id: item for item in catalog.items}
    excluded: list[dict[str, Any]] = []
    if selection_mode == SELECTION_SELECTED:
        if selected_item_ids is None or isinstance(selected_item_ids, (str, bytes)):
            raise LibraryTransferPlanError(
                "selected_item_ids is required for selected queue planning"
            )
        try:
            requested = tuple(selected_item_ids)
        except TypeError as exc:
            raise LibraryTransferPlanError(
                "selected_item_ids must be a sequence of item IDs"
            ) from exc
        if not requested:
            raise LibraryTransferPlanError("selected queue planning requires at least one item")
        if any(not isinstance(item_id, str) or not item_id for item_id in requested):
            raise LibraryTransferPlanError("selected queue planning contains an invalid item ID")
        if len(set(requested)) != len(requested):
            raise LibraryTransferPlanError("selected queue planning contains duplicate item IDs")
        unknown = [item_id for item_id in requested if item_id not in by_id]
        if unknown:
            raise LibraryTransferPlanError(
                f"selected Library item was not found: {unknown[0]}"
            )
        selected = [by_id[item_id] for item_id in requested]
    else:
        if selected_item_ids not in (None, (), []):
            raise LibraryTransferPlanError(
                "selected_item_ids cannot be combined with all_ready queue planning"
            )
        selected = []
        for item in catalog.items:
            is_ready = (
                item.supported
                and item.source_status == SOURCE_PRESENT
                and item.state == STATE_READY
                and item.preparation_state == PREPARATION_PREPARED
                and item.target_folder_name is not None
                and item.prepared_manifest_sha256 is not None
                and (
                    item.target_child_name is not None
                    or (
                        item.package is not None
                        and len(item.package.children) >= 2
                    )
                )
            )
            if is_ready:
                selected.append(item)
            else:
                excluded.append(
                    {
                        "item_id": item.item_id,
                        "source_filename": item.source_filename,
                        "state": item.state,
                        "preparation_state": item.preparation_state,
                        "source_status": item.source_status,
                        "reason": "not a current prepared supported Library item",
                    }
                )

    items = [
        _prepare_item_report(
            item,
            backup=backup,
            available_capacity_bytes=available_capacity_bytes,
        )
        for item in selected
    ]

    destination_owners: dict[str, list[int]] = {}
    for index, item_report in enumerate(items):
        for path in item_report["destination"]["paths"]:
            destination_owners.setdefault(path.casefold(), []).append(index)
    overlap_paths = {
        path: owners for path, owners in destination_owners.items() if len(owners) > 1
    }
    for path, owners in overlap_paths.items():
        display_path = next(
            destination
            for item_report in items
            for destination in item_report["destination"]["paths"]
            if destination.casefold() == path
        )
        for owner in owners:
            item_report = items[owner]
            item_report["conflicts"].append(
                {
                    "path": display_path,
                    "reason": "queue entries overlap; automatic package grouping is not supported",
                }
            )
            item_report["reasons"].append(
                "destination overlaps another queue entry; automatic grouping is disabled"
            )
            item_report["queue_ready"] = False
            item_report["compatibility_state"] = "blocked_by_queue_destination_overlap"

    total_lower_bound = sum(
        item["prepared_artifact"]["estimated_growth_lower_bound"]
        for item in items
        if item["prepared_artifact"].get("estimated_growth_lower_bound") is not None
    )
    total_source_bytes = sum(
        item["prepared_artifact"]["source_bytes"]
        for item in items
        if item["prepared_artifact"].get("source_bytes") is not None
    )
    total_payload_bytes = sum(
        item["prepared_artifact"]["prepared_payload_bytes"]
        for item in items
        if item["prepared_artifact"].get("prepared_payload_bytes") is not None
    )

    if backup is None:
        capacity = {
            "status": "not_evaluated_without_verified_backup",
            "baseline_model_bytes": None,
            "candidate_model_bytes": None,
            "lower_bound_bytes": total_lower_bound,
            "available_bytes": None,
            "exact_growth_known": False,
            "source": "no_verified_offline_backup_supplied",
        }
        baseline = {"available": False, "reason": "verified offline backup not supplied"}
    else:
        baseline = _backup_summary(backup)
        if available_capacity_bytes is None:
            capacity_status = "unknown"
        elif available_capacity_bytes < total_lower_bound:
            capacity_status = "insufficient_for_lower_bound"
        else:
            capacity_status = "sufficient_for_lower_bound_only"
        capacity = {
            "status": capacity_status,
            "baseline_model_bytes": len(_read_verified_blob(backup)),
            "candidate_model_bytes": None,
            "lower_bound_bytes": total_lower_bound,
            "available_bytes": available_capacity_bytes,
            "exact_growth_known": False,
            "source": (
                "offline_lower_bound_input"
                if available_capacity_bytes is not None
                else "no_capacity_evidence_supplied"
            ),
        }

    reasons: list[str] = [
        "this artifact is an offline queue review only; no device operation is available",
        "candidate construction, authorization, and transaction sending remain disabled",
        "each prepared Library item is kept as a separate package; no automatic grouping is inferred",
    ]
    if not items:
        reasons.append("no current prepared supported Library items were selected")
    if excluded:
        reasons.append("some catalog entries were excluded because they are not ready")
    if backup is None:
        reasons.append("destination conflicts and device capacity require a verified offline backup")
    elif capacity["status"] == "unknown":
        reasons.append("capacity was not supplied; the queue is not capacity-cleared")
    elif capacity["status"] == "insufficient_for_lower_bound":
        reasons.append("aggregate lower-bound growth exceeds the supplied capacity")
    for item in items:
        reasons.extend(
            f"{item['source']['filename']}: {reason}"
            for reason in item["reasons"]
        )

    queue_ready = bool(items) and all(item["queue_ready"] for item in items)
    report: dict[str, Any] = {
        "format": LIBRARY_TRANSFER_PLAN_FORMAT,
        "state": "previewed_offline",
        "notice": LIBRARY_TRANSFER_PLAN_NOTICE,
        "usb_accessed": False,
        "device_change": "none",
        "selection": {
            "mode": selection_mode,
            "selected_item_ids": [item.item_id for item in selected],
            "excluded_items": excluded,
        },
        "baseline": baseline,
        "grouping": {
            "policy": QUEUE_GROUPING_POLICY,
            "automatic_grouping": False,
            "overlap_status": "conflict" if overlap_paths else "none",
            "overlap_paths": sorted(
                next(
                    destination
                    for item_report in items
                    for destination in item_report["destination"]["paths"]
                    if destination.casefold() == path
                )
                for path in overlap_paths
            ),
        },
        "items": items,
        "totals": {
            "selected_items": len(items),
            "excluded_items": len(excluded),
            "queue_ready_items": sum(1 for item in items if item["queue_ready"]),
            "source_bytes": total_source_bytes,
            "prepared_payload_bytes": total_payload_bytes,
            "estimated_growth_lower_bound": total_lower_bound,
        },
        "capacity": capacity,
        "eligibility": {
            "offline_review_ready": bool(items),
            "queue_ready": queue_ready,
            "device_candidate_eligible": False,
            "transfer_enabled": False,
            "reasons": reasons,
        },
        "safety": {
            "source_mutated": False,
            "catalog_mutated": False,
            "candidate_constructed": False,
            "candidate_bytes_included": False,
            "authorization_created": False,
            "transaction_constructed": False,
            "sender_called": False,
            "automatic_retry": False,
        },
    }
    if capacity_evidence is not None:
        report["capacity"].update(
            {
                "source": "fresh_native_0x0019",
                "evidence_version": capacity_evidence.evidence_version,
                "native_response_sha256": capacity_evidence.raw_response_sha256,
                "device_identity": [
                    f"0x{value:04x}" for value in capacity_evidence.device_identity
                ],
            }
        )
    report["plan_sha256"] = _sha256(_canonical_json(report))
    return LibraryTransferQueuePlan(report=report)


@dataclass(frozen=True)
class LibraryTransferQueuePlan:
    """JSON-safe, framework-independent Library queue review artifact."""

    report: Mapping[str, Any]

    @property
    def review_ready(self) -> bool:
        return bool(self.report["eligibility"]["offline_review_ready"])

    @property
    def queue_ready(self) -> bool:
        return bool(self.report["eligibility"]["queue_ready"])

    @property
    def eligible(self) -> bool:
        """Always false: this plan never authorizes or enables a device action."""

        return False

    @property
    def plan_sha256(self) -> str:
        return str(self.report["plan_sha256"])

    def to_dict(self) -> dict[str, Any]:
        return dict(self.report)


# Keep the shorter name available for callers that refer to this as a plan
# rather than a queue.  Both names remain explicitly offline-only.
build_library_transfer_plan = build_library_transfer_queue_plan


__all__ = [
    "LIBRARY_TRANSFER_PLAN_FORMAT",
    "LIBRARY_TRANSFER_PLAN_NOTICE",
    "PREPARED_FLAT_PACKAGE_OPERATION",
    "PREPARED_ROOT_TXT_OPERATION",
    "QUEUE_GROUPING_POLICY",
    "SELECTION_ALL_READY",
    "SELECTION_SELECTED",
    "LibraryTransferPlanError",
    "LibraryTransferQueuePlan",
    "build_library_transfer_plan",
    "build_library_transfer_queue_plan",
]
