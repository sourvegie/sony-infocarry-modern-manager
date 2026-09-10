"""UI-independent readiness model for the Experimental Library profile.

This module describes reusable host/product eligibility only.  It deliberately
does not import the historical operation review, candidate builders, claim
stores, locks, USB access, or sender code.  A readiness result is therefore a
product explanation, never an authorization or a live-transfer request.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Optional

from .capability_profile import (
    CAPABILITY_PROFILE_STATUS,
    CapabilityProfileError,
    INITIAL_EXPERIMENTAL_PROFILE_ID,
    initial_capability_profile,
)
from .device_model_profile import (
    DeviceModelProfile,
    MODEL_STATUS_UNCHARACTERIZED,
    VNW_V15_PROFILE,
    VNW_V15_PROFILE_ID,
)


LIBRARY_TRANSFER_READINESS_FORMAT = "infocarry-library-transfer-readiness-v1"
EXPERIMENTAL_LIBRARY_PROFILE_ID = INITIAL_EXPERIMENTAL_PROFILE_ID
EXPERIMENTAL_LIBRARY_PROFILE_STATUS = CAPABILITY_PROFILE_STATUS
EXPERIMENTAL_CHILD_KINDS = ("txt", "bmp", "txt")
PREPARED_MEDIA_PACKAGE_FORMAT = "infocarry-prepared-typed-media-package-v1"
LIBRARY_TRANSFER_READINESS_STATUS = (
    "Experimental profile eligible — live transfer not enabled in this build"
)


class LibraryTransferReadinessError(ValueError):
    """Raised when a readiness input cannot be represented at all."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _copy(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy(child) for child in value]
    return value


def _is_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _extract_folder_name(folder_path: Any) -> Optional[str]:
    if not isinstance(folder_path, str) or not folder_path.startswith("root\\"):
        return None
    name = folder_path[len("root\\") :]
    if not name or "\\" in name:
        return None
    return name


def _evidence_reason(reason: str) -> bool:
    lowered = reason.casefold()
    return any(
        phrase in lowered
        for phrase in (
            "verified device backup is required",
            "verified offline backup",
            "verified backup",
            "capacity was not supplied",
            "capacity evidence",
            "not capacity-cleared",
        )
    )


def _baseline_identity_is_v15(baseline: Mapping[str, Any]) -> bool:
    identity = baseline.get("device_identity")
    if isinstance(identity, Mapping):
        return (
            identity.get("vendor_id") == "0x054c"
            and identity.get("product_id") == "0x001e"
        )
    if isinstance(identity, (list, tuple)):
        return tuple(identity) == ("0x054c", "0x001e")
    return False


def _add_plan_reasons(
    plan: Mapping[str, Any],
    reasons: list[str],
    fresh_evidence: list[str],
) -> None:
    if plan.get("format") != "infocarry-library-transfer-plan-v1":
        reasons.append("the selected plan is not the canonical offline Library plan")
    if plan.get("state") != "previewed_offline":
        reasons.append("the selected plan is not an offline review")
    if plan.get("usb_accessed") is not False or plan.get("device_change") != "none":
        reasons.append("the plan claims device access or a device change")

    grouping = plan.get("grouping")
    if not isinstance(grouping, Mapping):
        reasons.append("package grouping metadata is missing")
    else:
        if grouping.get("automatic_grouping") is not False:
            reasons.append("automatic package grouping is not permitted")
        if grouping.get("overlap_status") != "none":
            reasons.append("selected package destinations overlap another package")
        overlap_paths = grouping.get("overlap_paths", [])
        if overlap_paths not in (None, []) or not isinstance(overlap_paths, list):
            reasons.append("automatic grouping or destination overlap is not permitted")

    selection = plan.get("selection")
    if not isinstance(selection, Mapping):
        reasons.append("explicit Library selection metadata is missing")
    else:
        selected_ids = selection.get("selected_item_ids")
        if selection.get("mode") != "selected":
            reasons.append("the Experimental profile requires explicit selected-item planning")
        elif not isinstance(selected_ids, list) or len(selected_ids) != 1:
            reasons.append("select exactly one prepared Library package; selections are never merged")

    plan_eligibility = plan.get("eligibility")
    if not isinstance(plan_eligibility, Mapping):
        reasons.append("offline plan eligibility metadata is missing")
    else:
        if plan_eligibility.get("transfer_enabled") is not False:
            reasons.append("the offline plan cannot enable transfer")
        if plan_eligibility.get("device_candidate_eligible") is not False:
            reasons.append("the offline plan cannot advertise device-candidate eligibility")
        if plan_eligibility.get("offline_review_ready") is not True:
            reasons.append("the offline plan is not review-ready")
        if plan_eligibility.get("queue_ready") is not True:
            plan_reasons = plan_eligibility.get("reasons", [])
            evidence_reasons = [
                reason
                for reason in plan_reasons
                if isinstance(reason, str) and _evidence_reason(reason)
            ]
            for reason in evidence_reasons:
                if isinstance(reason, str):
                    fresh_evidence.append(reason)
            if not evidence_reasons:
                reasons.append("the offline plan is not queue-ready")

    safety = plan.get("safety")
    if not isinstance(safety, Mapping):
        reasons.append("offline plan safety metadata is missing")
    else:
        for key in (
            "source_mutated",
            "catalog_mutated",
            "candidate_constructed",
            "authorization_created",
            "transaction_constructed",
            "sender_called",
            "automatic_retry",
        ):
            if safety.get(key) is not False:
                reasons.append(f"offline plan safety flag {key!r} is not false")


def build_library_transfer_readiness(
    plan_report: Mapping[str, Any],
    *,
    model_profile: DeviceModelProfile = VNW_V15_PROFILE,
) -> "LibraryTransferReadiness":
    """Build one deterministic host/product readiness explanation.

    The input is the existing offline queue-plan report.  Missing baseline or
    missing capacity is not treated as package-shape failure: it produces an
    eligible host profile with an explicit fresh-evidence requirement.  Any
    structural, model, conflict, or tamper problem remains blocked.
    """

    if not isinstance(plan_report, Mapping):
        raise LibraryTransferReadinessError("Library transfer plan is malformed")
    if not isinstance(model_profile, DeviceModelProfile):
        raise LibraryTransferReadinessError("device model profile is malformed")

    reasons: list[str] = []
    fresh_evidence: list[str] = []
    _add_plan_reasons(plan_report, reasons, fresh_evidence)

    if model_profile != VNW_V15_PROFILE or not model_profile.transfer_capable:
        if model_profile.capability_status == MODEL_STATUS_UNCHARACTERIZED:
            reasons.append(
                "VNW-V10 is uncharacterized; read-only discovery is required and V15 transfer rules do not apply"
            )
        else:
            reasons.append("only the reviewed Sony InfoCarry VNW-V15 model profile is supported")

    declared_model_id = plan_report.get("device_model_profile_id")
    if declared_model_id is not None and declared_model_id != VNW_V15_PROFILE_ID:
        reasons.append("the selected plan is bound to a different device model profile")

    selection = plan_report.get("selection")
    selected_ids = (
        selection.get("selected_item_ids")
        if isinstance(selection, Mapping)
        else None
    )
    items = plan_report.get("items")
    item: Mapping[str, Any] = {}
    if not isinstance(items, list) or len(items) != 1:
        reasons.append("the Experimental profile requires exactly one selected Library package")
    elif not isinstance(items[0], Mapping):
        reasons.append("the selected Library package report is malformed")
    else:
        item = items[0]
    if isinstance(selected_ids, list) and len(selected_ids) == 1 and item:
        if item.get("item_id") != selected_ids[0]:
            reasons.append("the selected Library item identity does not match the plan")
    elif not isinstance(selected_ids, list) or len(selected_ids) != 1:
        # _add_plan_reasons already explains the zero/multiple-selection case.
        pass

    artifact = item.get("prepared_artifact")
    destination = item.get("destination")
    children = artifact.get("ordered_children") if isinstance(artifact, Mapping) else None
    paths = destination.get("paths") if isinstance(destination, Mapping) else None
    folder_path = paths[0] if isinstance(paths, list) and paths else None
    folder_name = _extract_folder_name(folder_path)
    normalized_children: list[dict[str, Any]] = []
    exact_package = True

    if item.get("operation_type") != "prepared_flat_typed_package":
        reasons.append("the selected item is not an explicitly imported prepared Library package")
        exact_package = False
    if item.get("execution_eligible") is not False:
        reasons.append("the selected package cannot advertise execution eligibility")
    if not isinstance(artifact, Mapping):
        reasons.append("the prepared package manifest is missing")
        exact_package = False
    else:
        if artifact.get("contract") != PREPARED_MEDIA_PACKAGE_FORMAT:
            reasons.append("the prepared package manifest contract is unsupported")
            exact_package = False
        manifest_sha256 = artifact.get("manifest_sha256")
        if not _is_digest(manifest_sha256):
            reasons.append("the prepared package manifest hash is malformed")
            exact_package = False

    if not isinstance(children, list) or len(children) != len(EXPERIMENTAL_CHILD_KINDS):
        reasons.append("the selected package must contain exactly three direct children")
        exact_package = False
    else:
        if folder_name is None:
            reasons.append("the package destination must be exactly one root-level folder")
            exact_package = False
        for index, (child, expected_kind) in enumerate(
            zip(children, EXPERIMENTAL_CHILD_KINDS)
        ):
            if not isinstance(child, Mapping):
                reasons.append(f"prepared package child {index + 1} is malformed")
                exact_package = False
                continue
            normalized_children.append(dict(child))
            if child.get("kind") != expected_kind or child.get("order") != index:
                reasons.append("child order/kinds must be exactly TXT → BMP → TXT")
                exact_package = False
            if folder_name is not None and child.get("path") != f"{folder_path}\\{child.get('name', '')}":
                reasons.append("prepared package child path is nested, missing, or outside the root folder")
                exact_package = False

    if folder_name is not None and isinstance(paths, list):
        expected_paths = [
            folder_path,
            *[
                f"{folder_path}\\{child.get('name')}"
                for child in normalized_children
            ],
        ]
        if paths != expected_paths or len(paths) != 1 + len(EXPERIMENTAL_CHILD_KINDS):
            reasons.append("destination must contain exactly the root folder and its three direct children")
            exact_package = False
    elif not isinstance(paths, list):
        reasons.append("prepared package destination paths are malformed")
        exact_package = False

    if exact_package and folder_name is not None:
        try:
            normalized_children = list(
                initial_capability_profile().validate_package(
                    folder_name=folder_name,
                    children=normalized_children,
                )
            )
        except CapabilityProfileError as exc:
            reasons.append(f"canonical preparation/profile validation failed: {exc}")
            exact_package = False

    if item:
        item_reasons = item.get("reasons", [])
        if not isinstance(item_reasons, list):
            reasons.append("selected package review reasons are malformed")
        else:
            for reason in item_reasons:
                if not isinstance(reason, str):
                    reasons.append("selected package review reasons are malformed")
                elif _evidence_reason(reason):
                    fresh_evidence.append(reason)
                else:
                    reasons.append(reason)
        if item.get("queue_ready") is not True:
            item_evidence_reasons = [
                reason
                for reason in item_reasons
                if isinstance(reason, str) and _evidence_reason(reason)
            ] if isinstance(item_reasons, list) else []
            for reason in item_reasons if isinstance(item_reasons, list) else []:
                if isinstance(reason, str) and not _evidence_reason(reason):
                    # The queue planner is the canonical source revalidation
                    # boundary.  A non-evidence reason must not be promoted.
                    reasons.append(f"offline package revalidation is not complete: {reason}")
            if not item_evidence_reasons and not item_reasons:
                reasons.append("the selected package is not queue-ready")

    baseline_value = plan_report.get("baseline")
    if baseline_value is None:
        baseline = {"available": False}
    elif not isinstance(baseline_value, Mapping):
        reasons.append("verified baseline metadata is malformed")
        baseline = {"available": False}
    else:
        baseline = baseline_value
    baseline_available = baseline.get("available") is True
    if baseline_available and not _baseline_identity_is_v15(baseline):
        reasons.append("verified baseline is not for the reviewed Sony InfoCarry VNW-V15 session")
    if baseline_available:
        baseline_status = "verified baseline supplied; destination paths checked"
    else:
        baseline_status = "not supplied — destination conflicts cannot be cleared offline"
        fresh_evidence.append("a verified baseline is required to clear destination conflicts")

    conflicts = item.get("conflicts", []) if item else []
    if not isinstance(conflicts, list):
        reasons.append("destination conflict metadata is malformed")
        conflicts = []
    elif conflicts:
        reasons.append("the selected destination already exists in the verified baseline")
    baseline_paths = baseline.get("paths", baseline.get("existing_paths"))
    if isinstance(baseline_paths, (list, tuple)) and isinstance(paths, list):
        known_paths = {path.casefold() for path in baseline_paths if isinstance(path, str)}
        baseline_conflicts = [
            path for path in paths if isinstance(path, str) and path.casefold() in known_paths
        ]
        if baseline_conflicts and not conflicts:
            conflicts = [{"path": path, "reason": "destination exists in the verified baseline"} for path in baseline_conflicts]
            reasons.append("the selected destination already exists in the verified baseline")

    capacity_value = item.get("capacity") if item else None
    if capacity_value is None:
        capacity_value = plan_report.get("capacity")
    if capacity_value is None:
        capacity_input = {}
    elif not isinstance(capacity_value, Mapping):
        reasons.append("capacity metadata is malformed")
        capacity_input = {}
    else:
        capacity_input = capacity_value
    capacity_status = capacity_input.get("status", "not_evaluated")
    if capacity_status == "insufficient_for_lower_bound":
        reasons.append("available baseline capacity is below the package lower bound")
    elif capacity_status in {
        "not_evaluated_without_verified_backup",
        "unknown",
        "not_evaluated",
    }:
        fresh_evidence.append("fresh native capacity evidence is required before any live attempt")
    elif capacity_status not in {"sufficient_for_lower_bound_only", "sufficient"}:
        reasons.append("capacity status is not a reviewed value")
    for key in ("baseline_model_bytes", "available_bytes", "lower_bound_bytes"):
        value = capacity_input.get(key)
        if value is not None and not _is_nonnegative_int(value):
            reasons.append(f"capacity field {key!r} is malformed")

    # These keys may be present in an operation-specific or tampered input,
    # but they are intentionally never copied into a reusable product review.
    historical_keys = {
        "operation_identity",
        "authorization",
        "confirmation",
        "owner_approval",
        "bundle",
        "preflight",
        "candidate",
        "transaction",
    }
    historical_identity_supplied = bool(historical_keys.intersection(plan_report))
    if item:
        historical_identity_supplied = historical_identity_supplied or bool(
            historical_keys.intersection(item)
        )
    if historical_identity_supplied:
        fresh_evidence.append(
            "historical operation identity is ignored; a future attempt requires fresh evidence and separate review"
        )

    # A malformed/mismatched package, model substitution, conflict, or a
    # non-evidence queue failure blocks.  Missing fresh live evidence merely
    # keeps a valid host-profile result clearly unavailable for execution.
    blocked = bool(reasons) or not exact_package
    host_profile_eligible = not blocked
    if host_profile_eligible:
        fresh_evidence.extend(
            (
                "a fresh complete verified device backup is required before any live attempt",
                "fresh native 0x0019 capacity evidence and exact candidate growth are required",
                "a separately reviewed operation identity and transaction-specific confirmation are required",
            )
        )
    # Preserve deterministic first occurrence order while avoiding repeated
    # evidence messages from both the plan and item reports.
    fresh_evidence = list(dict.fromkeys(fresh_evidence))
    reasons = list(dict.fromkeys(reasons))
    state = "eligible_needs_fresh_live_evidence" if host_profile_eligible else "blocked"
    status_text = (
        LIBRARY_TRANSFER_READINESS_STATUS
        if host_profile_eligible
        else f"Blocked — {reasons[0] if reasons else 'selected package is outside the Experimental profile'}"
    )

    report: dict[str, Any] = {
        "format": LIBRARY_TRANSFER_READINESS_FORMAT,
        "state": state,
        "profile": {
            "id": EXPERIMENTAL_LIBRARY_PROFILE_ID,
            "status": EXPERIMENTAL_LIBRARY_PROFILE_STATUS,
            "device_model_profile_id": VNW_V15_PROFILE_ID,
            "required_child_kinds": list(EXPERIMENTAL_CHILD_KINDS),
            "root_level_only": True,
            "exact_child_count": len(EXPERIMENTAL_CHILD_KINDS),
            "automatic_grouping": False,
            "multi_selection_merge": False,
            "live_enabled": False,
        },
        "device_model": model_profile.to_dict(),
        "selection": {
            "count": len(selected_ids) if isinstance(selected_ids, list) else 0,
            "logical_item_id": selected_ids[0]
            if isinstance(selected_ids, list) and len(selected_ids) == 1
            else None,
            "explicit_one_package": isinstance(selected_ids, list) and len(selected_ids) == 1,
            "multi_selection_merged": False,
        },
        "package": {
            "folder_path": folder_path if isinstance(folder_path, str) else None,
            "ordered_children": _copy(normalized_children),
            "prepared_manifest_sha256": artifact.get("manifest_sha256")
            if isinstance(artifact, Mapping)
            else None,
            "source_bytes": artifact.get("source_bytes")
            if isinstance(artifact, Mapping)
            else None,
            "prepared_payload_bytes": artifact.get("prepared_payload_bytes")
            if isinstance(artifact, Mapping)
            else None,
        },
        "destination": {
            "paths": _copy(paths) if isinstance(paths, list) else [],
            "conflicts": _copy(conflicts),
            "baseline_status": baseline_status,
        },
        "capacity": {
            "status": capacity_status,
            "baseline_model_bytes": capacity_input.get("baseline_model_bytes"),
            "available_bytes": capacity_input.get("available_bytes"),
            "lower_bound_bytes": capacity_input.get("lower_bound_bytes"),
            "exact_growth_known": False,
            "candidate_growth_bytes": None,
            "remaining_after_transfer_bytes": None,
            "fresh_native_capacity_required": True,
        },
        "evidence": {
            "verified_baseline_available": baseline_available,
            "fresh_complete_backup_required": True,
            "fresh_native_capacity_required": True,
            "historical_operation_identity_reused": False,
            "historical_operation_identity_supplied": historical_identity_supplied,
        },
        "transfer_boundary": {
            "host_only": True,
            "authorization_exposed": False,
            "candidate_constructed": False,
            "transaction_constructed": False,
            "sender_called": False,
            "device_changing_operations": 0,
            "transfer_enabled": False,
        },
        "eligibility": {
            "host_profile_eligible": host_profile_eligible,
            "needs_fresh_live_evidence": host_profile_eligible and bool(fresh_evidence),
            "blocked": blocked,
            "status_text": status_text,
            "reasons": reasons,
            "fresh_evidence_reasons": fresh_evidence,
        },
    }
    report["review_sha256"] = _sha256_json(report)
    return LibraryTransferReadiness(report=report)


def validate_library_transfer_readiness(report: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the deterministic integrity binding of a readiness report."""

    if not isinstance(report, Mapping):
        raise LibraryTransferReadinessError("readiness report is malformed")
    expected = report.get("review_sha256")
    if not _is_digest(expected):
        raise LibraryTransferReadinessError("readiness report hash is malformed")
    unsigned = dict(report)
    unsigned.pop("review_sha256", None)
    if _sha256_json(unsigned) != expected:
        raise LibraryTransferReadinessError("readiness report was modified after creation")
    if report.get("format") != LIBRARY_TRANSFER_READINESS_FORMAT:
        raise LibraryTransferReadinessError("readiness report format is unsupported")
    boundary = report.get("transfer_boundary")
    if not isinstance(boundary, Mapping) or boundary != {
        "host_only": True,
        "authorization_exposed": False,
        "candidate_constructed": False,
        "transaction_constructed": False,
        "sender_called": False,
        "device_changing_operations": 0,
        "transfer_enabled": False,
    }:
        raise LibraryTransferReadinessError("readiness report transfer boundary is unsafe")
    return _copy(report)


@dataclass(frozen=True)
class LibraryTransferReadiness:
    """Framework-independent, non-authorizing product readiness result."""

    report: Mapping[str, Any]

    @property
    def host_profile_eligible(self) -> bool:
        return bool(self.report.get("eligibility", {}).get("host_profile_eligible"))

    @property
    def needs_fresh_live_evidence(self) -> bool:
        return bool(self.report.get("eligibility", {}).get("needs_fresh_live_evidence"))

    @property
    def blocked(self) -> bool:
        return bool(self.report.get("eligibility", {}).get("blocked"))

    @property
    def transfer_enabled(self) -> bool:
        return False

    @property
    def review_sha256(self) -> str:
        return str(self.report.get("review_sha256", ""))

    def verify_integrity(self) -> bool:
        try:
            validate_library_transfer_readiness(self.report)
        except LibraryTransferReadinessError:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return _copy(self.report)


build_experimental_library_readiness = build_library_transfer_readiness


__all__ = [
    "EXPERIMENTAL_CHILD_KINDS",
    "EXPERIMENTAL_LIBRARY_PROFILE_ID",
    "EXPERIMENTAL_LIBRARY_PROFILE_STATUS",
    "LIBRARY_TRANSFER_READINESS_FORMAT",
    "LIBRARY_TRANSFER_READINESS_STATUS",
    "LibraryTransferReadiness",
    "LibraryTransferReadinessError",
    "build_experimental_library_readiness",
    "build_library_transfer_readiness",
    "validate_library_transfer_readiness",
]
