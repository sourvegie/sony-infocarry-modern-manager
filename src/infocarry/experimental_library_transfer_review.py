"""Hash-only review model for the narrowly supported Experimental transfer.

This module is intentionally free of USB, sender, and live-adapter imports so
the normal Library window can present the product boundary without exposing a
device-changing action.  The isolated execution entrypoint lives in
``experimental_library_transfer`` and delegates to the already reviewed
P17-017/P17-019 path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from .experimental_transfer_contract import experimental_safety_contract


EXPERIMENTAL_LIBRARY_REVIEW_FORMAT = "infocarry-experimental-library-transfer-review-v1"
EXPERIMENTAL_LIBRARY_PROFILE = "one_selected_library_item_root_txt_bmp_txt"
EXPERIMENTAL_OPERATION = "experimental_library_package_one_shot"
EXPERIMENTAL_TARGET_FOLDER = "IC_P18_LIBRARY_20260906_01"
EXPERIMENTAL_OWNER_APPROVAL = "APPROVE P18-010 AUX STATE PRESERVATION TEST 01"
EXPERIMENTAL_CONFIRMATION = "ADD IC_P18_LIBRARY_20260906_01 ONCE"
EXPERIMENTAL_CONFIRMATION_POLICY = "explicit_operation_phrase_v1"
EXPERIMENTAL_CHILDREN = (
    (0, "txt", "01-introduction.txt"),
    (1, "bmp", "02-page-01.bmp"),
    (2, "txt", "03-ending.txt"),
)
PREPARED_MEDIA_PACKAGE_FORMAT = "infocarry-prepared-typed-media-package-v1"
EXPERIMENTAL_SAFETY_POLICY = {
    "automatic_retry_allowed": False,
    "max_sender_calls": 1,
    "transaction_request": "0x101b",
    "accepted_completion": "0x0000",
}


class ExperimentalLibraryTransferReviewError(ValueError):
    """Raised when a review cannot safely represent an operation."""


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ExperimentalLibraryTransferReviewError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _copy(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy(child) for child in value]
    return value


def _expected_paths() -> list[str]:
    return [
        f"root\\{EXPERIMENTAL_TARGET_FOLDER}",
        *[
            f"root\\{EXPERIMENTAL_TARGET_FOLDER}\\{name}"
            for _order, _kind, name in EXPERIMENTAL_CHILDREN
        ],
    ]


def _review_item(plan: Mapping[str, Any]) -> Mapping[str, Any]:
    items = plan.get("items")
    if not isinstance(items, list) or len(items) != 1:
        raise ExperimentalLibraryTransferReviewError(
            "Experimental transfer requires exactly one selected Library item"
        )
    item = items[0]
    if not isinstance(item, Mapping):
        raise ExperimentalLibraryTransferReviewError("Library queue item is malformed")
    return item


def _package_is_exact(item: Mapping[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if item.get("operation_type") != "prepared_flat_typed_package":
        reasons.append("the selected item is not an explicitly imported prepared package")
    artifact = item.get("prepared_artifact")
    if not isinstance(artifact, Mapping) or artifact.get("contract") != PREPARED_MEDIA_PACKAGE_FORMAT:
        reasons.append("the package is not the versioned P17-002 typed-media contract")
    children = artifact.get("ordered_children") if isinstance(artifact, Mapping) else None
    if not isinstance(children, list) or len(children) != len(EXPERIMENTAL_CHILDREN):
        reasons.append("the package does not contain exactly three ordered children")
    else:
        for child, expected in zip(children, EXPERIMENTAL_CHILDREN):
            if not isinstance(child, Mapping):
                reasons.append("the package child manifest is malformed")
                break
            order, kind, name = expected
            if (
                child.get("order") != order
                or child.get("kind") != kind
                or child.get("name") != name
                or child.get("path") != _expected_paths()[order + 1]
            ):
                reasons.append(
                    "the package order/profile is not the proven TXT/BMP/TXT shape"
                )
                break
            for field in ("source_sha256", "prepared_payload_sha256"):
                try:
                    _digest(child.get(field), f"package child {name} {field}")
                except ExperimentalLibraryTransferReviewError:
                    reasons.append(f"the package child {name} has no valid {field}")
                    break
            for field in ("source_bytes", "prepared_payload_bytes"):
                value = child.get(field)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    reasons.append(f"the package child {name} has an invalid {field}")
                    break
    destination = item.get("destination", {})
    if not isinstance(destination, Mapping) or destination.get("paths") != _expected_paths():
        reasons.append("the destination is not the fixed root-level P18-010 package")
    if item.get("conflicts"):
        reasons.append("the destination conflicts with the verified device state")
    return not reasons, reasons


def _sealed_ready_bindings(
    preflight: Mapping[str, Any],
    bundle: Mapping[str, Any],
    item: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate only the public shape; the canonical runner validates bytes."""

    if bundle.get("format") != "infocarry-p17-017-library-package-operation-bundle-v1":
        raise ExperimentalLibraryTransferReviewError("operation bundle format is unsupported")
    if bundle.get("device_identity") != ["0x054c", "0x001e"]:
        raise ExperimentalLibraryTransferReviewError("operation bundle device identity is not Sony 054c:001e")
    if bundle.get("expected_folder_name") != EXPERIMENTAL_TARGET_FOLDER:
        raise ExperimentalLibraryTransferReviewError("operation bundle destination differs from the reviewed profile")
    if (
        bundle.get("owner_approval_phrase") != EXPERIMENTAL_OWNER_APPROVAL
        or bundle.get("confirmation_phrase") != EXPERIMENTAL_CONFIRMATION
        or bundle.get("confirmation_policy") != EXPERIMENTAL_CONFIRMATION_POLICY
    ):
        raise ExperimentalLibraryTransferReviewError("operation bundle approval differs from P18-010")
    if bundle.get("safety") != EXPERIMENTAL_SAFETY_POLICY:
        raise ExperimentalLibraryTransferReviewError("operation bundle safety policy differs from the reviewed one-shot policy")
    children = bundle.get("package_children")
    if not isinstance(children, list) or len(children) != len(EXPERIMENTAL_CHILDREN):
        raise ExperimentalLibraryTransferReviewError("operation bundle package children are malformed")
    for child, expected in zip(children, EXPERIMENTAL_CHILDREN):
        if not isinstance(child, Mapping) or tuple(
            (child.get("order"), child.get("kind"), child.get("name"))
        ) != expected:
            raise ExperimentalLibraryTransferReviewError("operation bundle child profile differs")
    expected_post = bundle.get("expected_post_operation")
    if not isinstance(expected_post, Mapping) or expected_post.get("added_paths") != _expected_paths():
        raise ExperimentalLibraryTransferReviewError("operation bundle expected post-state differs")
    _digest(bundle.get("bundle_sha256"), "bundle_sha256")
    for key in (
        "candidate_blob_sha256",
        "transaction_sha256",
        "preflight_seal_sha256",
        "core_preflight_seal_sha256",
        "baseline_state_identity_sha256",
        "capacity_response_sha256",
        "candidate_audit_sha256",
        "authorization_sha256",
        "expected_post_operation_sha256",
        "library_binding_sha256",
        "bookmark_binding_sha256",
    ):
        _digest(bundle.get(key), f"bundle.{key}")

    if preflight.get("state") != "ready_for_hardware_test_host_only":
        raise ExperimentalLibraryTransferReviewError("sealed preflight is not host-ready")
    if preflight.get("profile") != EXPERIMENTAL_LIBRARY_PROFILE:
        raise ExperimentalLibraryTransferReviewError("sealed preflight profile differs from the reviewed profile")
    if preflight.get("device_identity") != ["0x054c", "0x001e"]:
        raise ExperimentalLibraryTransferReviewError("sealed preflight device identity differs")
    if preflight.get("expected_folder_name") != EXPERIMENTAL_TARGET_FOLDER:
        raise ExperimentalLibraryTransferReviewError("sealed preflight destination differs")
    if (
        preflight.get("owner_approval_phrase") != EXPERIMENTAL_OWNER_APPROVAL
        or preflight.get("confirmation_phrase") != EXPERIMENTAL_CONFIRMATION
        or preflight.get("confirmation_policy") != EXPERIMENTAL_CONFIRMATION_POLICY
    ):
        raise ExperimentalLibraryTransferReviewError("sealed preflight approval differs from P18-010")
    for key, expected in (
        ("read_only_preflight", True),
        ("device_changing_operation_performed", False),
        ("usb_transmission_performed", False),
        ("target_absent_from_fresh_backup", True),
        ("approval_consumed", False),
        ("write_started", False),
        ("sender_calls", 0),
        ("backend_write_calls", 0),
        ("send_count", 0),
        ("completion", None),
        ("automatic_retry_allowed", False),
        ("normal_gui_cli_transfer_exposed", False),
    ):
        if preflight.get(key) != expected:
            raise ExperimentalLibraryTransferReviewError(
                f"sealed preflight field {key!r} is not the reviewed value"
            )
    candidate = preflight.get("candidate")
    if not isinstance(candidate, Mapping):
        raise ExperimentalLibraryTransferReviewError("sealed preflight candidate is malformed")
    candidate_summary = candidate.get("candidate")
    package = candidate.get("package")
    if not isinstance(candidate_summary, Mapping) or not isinstance(package, Mapping):
        raise ExperimentalLibraryTransferReviewError("sealed preflight candidate summary is malformed")
    if candidate_summary.get("blob_sha256") != bundle.get("candidate_blob_sha256"):
        raise ExperimentalLibraryTransferReviewError("candidate hash differs from the operation bundle")
    authorization = preflight.get("authorization")
    if not isinstance(authorization, Mapping):
        raise ExperimentalLibraryTransferReviewError("sealed preflight authorization is malformed")
    if authorization.get("candidate_transaction_sha256") != bundle.get("transaction_sha256"):
        raise ExperimentalLibraryTransferReviewError("transaction hash differs from the operation bundle")
    candidate_policy = candidate.get("policy")
    if not isinstance(candidate_policy, Mapping):
        raise ExperimentalLibraryTransferReviewError("candidate safety policy is malformed")
    if (
        authorization.get("fixed_state_policy") != bundle.get("fixed_state_policy")
        or candidate_policy.get("fixed_state") != bundle.get("fixed_state_policy")
        or authorization.get("fixed_state_before_sha256") != bundle.get("fixed_state_before_sha256")
        or authorization.get("fixed_state_candidate_sha256") != bundle.get("fixed_state_candidate_sha256")
        or authorization.get("bookmark_binding_sha256") != bundle.get("bookmark_binding_sha256")
    ):
        raise ExperimentalLibraryTransferReviewError("fixed-state policy differs across candidate, authorization, and bundle")
    if preflight.get("preflight_seal_sha256") != bundle.get("preflight_seal_sha256"):
        raise ExperimentalLibraryTransferReviewError("preflight seal differs from the operation bundle")
    if preflight.get("core_preflight_seal_sha256") != bundle.get("core_preflight_seal_sha256"):
        raise ExperimentalLibraryTransferReviewError("core preflight seal differs from the operation bundle")
    if package.get("paths") != _expected_paths():
        raise ExperimentalLibraryTransferReviewError("candidate package paths differ from the reviewed profile")
    candidate_children = package.get("ordered_items")
    if not isinstance(candidate_children, list) or len(candidate_children) != len(EXPERIMENTAL_CHILDREN):
        raise ExperimentalLibraryTransferReviewError("candidate package child summary is incomplete")
    plan_artifact = item.get("prepared_artifact")
    plan_children = plan_artifact.get("ordered_children") if isinstance(plan_artifact, Mapping) else None
    if not isinstance(plan_children, list) or len(plan_children) != len(EXPERIMENTAL_CHILDREN):
        raise ExperimentalLibraryTransferReviewError("Library package child manifest is incomplete")
    for child, plan_child, expected in zip(candidate_children, plan_children, EXPERIMENTAL_CHILDREN):
        order, kind, _name = expected
        if not isinstance(child, Mapping) or (
            child.get("order"),
            child.get("kind"),
            child.get("path"),
        ) != (order, kind, _expected_paths()[order + 1]):
            raise ExperimentalLibraryTransferReviewError("candidate ordered child summary differs")
        candidate_payload_sha256 = child.get(
            "payload_sha256", child.get("prepared_payload_sha256")
        )
        candidate_payload_bytes = child.get(
            "payload_length", child.get("prepared_payload_bytes")
        )
        if not isinstance(plan_child, Mapping) or (
            child.get("source_sha256") != plan_child.get("source_sha256")
            or candidate_payload_sha256 != plan_child.get("prepared_payload_sha256")
            or (
                candidate_payload_bytes is not None
                and candidate_payload_bytes != plan_child.get("prepared_payload_bytes")
            )
            or (
                child.get("source_bytes") is not None
                and child.get("source_bytes") != plan_child.get("source_bytes")
            )
        ):
            raise ExperimentalLibraryTransferReviewError(
                "candidate child hashes or source size differ from the Library manifest"
            )

    bundle_children = bundle.get("package_children")
    for bundle_child, plan_child, expected in zip(
        bundle_children, plan_children, EXPERIMENTAL_CHILDREN
    ):
        if not isinstance(bundle_child, Mapping) or not isinstance(plan_child, Mapping):
            raise ExperimentalLibraryTransferReviewError(
                "operation bundle child manifest is malformed"
            )
        order, kind, name = expected
        if (
            bundle_child.get("order"),
            bundle_child.get("kind"),
            bundle_child.get("name"),
        ) != expected or (
            bundle_child.get("source_sha256") != plan_child.get("source_sha256")
            or bundle_child.get("source_bytes") != plan_child.get("source_bytes")
            or bundle_child.get("prepared_payload_sha256")
            != plan_child.get("prepared_payload_sha256")
            or bundle_child.get("prepared_payload_bytes")
            != plan_child.get("prepared_payload_bytes")
        ):
            raise ExperimentalLibraryTransferReviewError(
                f"operation bundle child {name} differs from the Library manifest"
            )
    if item.get("prepared_artifact", {}).get("manifest_sha256") != package.get("prepared_manifest_sha256"):
        raise ExperimentalLibraryTransferReviewError("Library manifest differs from the sealed candidate")

    allocation = candidate.get("allocation", {})
    if not isinstance(allocation, Mapping):
        raise ExperimentalLibraryTransferReviewError("candidate allocation is malformed")
    capacity_values = {
        "capacity_limit_bytes": allocation.get("capacity_limit_bytes"),
        "baseline_model_bytes": allocation.get("baseline_model_bytes"),
        "candidate_model_bytes": allocation.get("candidate_model_bytes"),
        "candidate_growth_bytes": allocation.get("candidate_growth_bytes"),
        "remaining_growth_bytes": allocation.get("remaining_growth_bytes"),
    }
    if any(
        type(value) is not int or value < 0 for value in capacity_values.values()
    ):
        raise ExperimentalLibraryTransferReviewError(
            "sealed candidate capacity facts are incomplete"
        )
    if capacity_values["candidate_model_bytes"] < capacity_values["baseline_model_bytes"]:
        raise ExperimentalLibraryTransferReviewError(
            "sealed candidate capacity model length regresses"
        )
    if capacity_values["candidate_growth_bytes"] != (
        capacity_values["candidate_model_bytes"]
        - capacity_values["baseline_model_bytes"]
    ):
        raise ExperimentalLibraryTransferReviewError(
            "sealed candidate capacity growth is inconsistent"
        )
    if capacity_values["remaining_growth_bytes"] != (
        capacity_values["capacity_limit_bytes"]
        - capacity_values["baseline_model_bytes"]
    ):
        raise ExperimentalLibraryTransferReviewError(
            "sealed candidate remaining growth capacity is inconsistent"
        )
    if capacity_values["candidate_growth_bytes"] > capacity_values["remaining_growth_bytes"]:
        raise ExperimentalLibraryTransferReviewError(
            "sealed candidate growth exceeds remaining capacity"
        )
    remaining_after_transfer = (
        capacity_values["capacity_limit_bytes"]
        - capacity_values["candidate_model_bytes"]
    )
    if remaining_after_transfer < 0:
        raise ExperimentalLibraryTransferReviewError(
            "sealed candidate exceeds total model capacity"
        )
    return {
        "bundle_sha256": bundle["bundle_sha256"],
        "candidate_blob_sha256": bundle["candidate_blob_sha256"],
        "transaction_sha256": bundle["transaction_sha256"],
        "preflight_seal_sha256": bundle["preflight_seal_sha256"],
        "core_preflight_seal_sha256": bundle["core_preflight_seal_sha256"],
        "baseline_state_identity_sha256": bundle["baseline_state_identity_sha256"],
        "capacity_response_sha256": bundle["capacity_response_sha256"],
        "candidate_blob_length": candidate_summary.get("blob_length"),
        "candidate_growth_bytes": capacity_values["candidate_growth_bytes"],
        "capacity_limit_bytes": capacity_values["capacity_limit_bytes"],
        "remaining_growth_bytes": allocation.get("remaining_growth_bytes"),
        "baseline_model_bytes": capacity_values["baseline_model_bytes"],
        "candidate_model_bytes": capacity_values["candidate_model_bytes"],
        "remaining_after_transfer_bytes": remaining_after_transfer,
        "fresh_backup_required": True,
    }


@dataclass(frozen=True)
class ExperimentalLibraryTransferReview:
    """Hash-only product review; it never authorizes or executes a transfer."""

    report: Mapping[str, Any]

    @property
    def ready_for_hardware_test(self) -> bool:
        return self.report.get("eligibility", {}).get("state") == "ready_for_hardware_test"

    def to_dict(self) -> dict[str, Any]:
        return _copy(self.report)


def build_experimental_library_transfer_review(
    plan_report: Mapping[str, Any],
    *,
    preflight_report: Optional[Mapping[str, Any]] = None,
    bundle_report: Optional[Mapping[str, Any]] = None,
    audit_location: Optional[str] = None,
) -> ExperimentalLibraryTransferReview:
    """Build an Experimental review from one queue item and optional sealed data.

    A queue plan alone is intentionally preview-only.  The ready state requires
    a separately sealed, fully revalidated preflight and immutable bundle; the
    function only checks their hash-only shape and leaves byte validation to the
    canonical P17 loader/runner.
    """

    if not isinstance(plan_report, Mapping):
        raise ExperimentalLibraryTransferReviewError("Library queue plan is malformed")
    if plan_report.get("format") != "infocarry-library-transfer-plan-v1":
        raise ExperimentalLibraryTransferReviewError("Library queue plan format is unsupported")
    if plan_report.get("state") != "previewed_offline":
        raise ExperimentalLibraryTransferReviewError("Library queue plan is not an offline review")
    if plan_report.get("usb_accessed") is not False or plan_report.get("device_change") != "none":
        raise ExperimentalLibraryTransferReviewError("Library queue plan reports device access or change")
    selection = plan_report.get("selection", {})
    selected_ids = selection.get("selected_item_ids") if isinstance(selection, Mapping) else None
    reasons: list[str] = []
    eligibility = plan_report.get("eligibility")
    if not isinstance(eligibility, Mapping) or eligibility.get("queue_ready") is not True:
        reasons.append("the queue plan is not fully revalidated and queue-ready")
    if not isinstance(selection, Mapping) or selection.get("mode") != "selected":
        reasons.append("the Experimental operation requires explicit selected-item planning")
    for key in ("offline_review_ready", "device_candidate_eligible", "transfer_enabled"):
        expected = True if key == "offline_review_ready" else False
        if not isinstance(eligibility, Mapping) or eligibility.get(key) is not expected:
            reasons.append(f"the queue plan host-only eligibility flag {key!r} is not safe")
    grouping = plan_report.get("grouping")
    if not isinstance(grouping, Mapping) or (
        grouping.get("automatic_grouping") is not False
        or grouping.get("overlap_status") != "none"
    ):
        reasons.append("automatic package grouping or destination overlap is not permitted")
    exact_item = False
    item: Mapping[str, Any]
    try:
        item = _review_item(plan_report)
        if not isinstance(selected_ids, list) or len(selected_ids) != 1:
            reasons.append("select exactly one Library item; multiple rows are never merged")
        elif item.get("item_id") != selected_ids[0]:
            reasons.append("the selected Library item identity does not match the queue selection")
        if item.get("queue_ready") is not True:
            reasons.append("the selected Library item is not fully revalidated and queue-ready")
        if item.get("execution_eligible") is not False:
            reasons.append("the host queue item cannot advertise execution eligibility")
        exact_item, profile_reasons = _package_is_exact(item)
        reasons.extend(profile_reasons)
    except ExperimentalLibraryTransferReviewError as exc:
        item = {}
        reasons.append(str(exc))

    if not exact_item and not reasons:
        reasons.append("the selected package is outside the proven Experimental profile")
    plan_safety = plan_report.get("safety")
    for key in (
        "source_mutated",
        "catalog_mutated",
        "candidate_constructed",
        "authorization_created",
        "transaction_constructed",
        "sender_called",
        "automatic_retry",
    ):
        if not isinstance(plan_safety, Mapping) or plan_safety.get(key) is not False:
            reasons.append(f"the queue plan safety flag {key!r} is not host-only")
    bindings: dict[str, Any] = {}
    if exact_item and (preflight_report is None or bundle_report is None):
        reasons.extend(
            (
                "a fresh complete verified backup and immediate revalidation are required",
                "a sealed candidate/authorization/preflight is required before hardware readiness",
            )
        )
    elif exact_item and preflight_report is not None and bundle_report is not None:
        try:
            bindings = _sealed_ready_bindings(preflight_report, bundle_report, item)
        except ExperimentalLibraryTransferReviewError as exc:
            reasons.append(str(exc))

    prepared = item.get("prepared_artifact", {})
    destination = item.get("destination", {})
    package_children = prepared.get("ordered_children", []) if isinstance(prepared, Mapping) else []
    capacity = item.get("capacity", {})
    expected_paths = destination.get("paths", []) if isinstance(destination, Mapping) else []
    fresh_backup_destination = "allocated per attempt under the bounded external evidence namespace"
    if isinstance(preflight_report, Mapping):
        before_backup = preflight_report.get("before_backup")
        if isinstance(before_backup, Mapping) and isinstance(before_backup.get("directory"), str):
            fresh_backup_destination = before_backup["directory"]
    report = {
        "format": EXPERIMENTAL_LIBRARY_REVIEW_FORMAT,
        "state": "experimental_review",
        "notice": "EXPERIMENTAL LIBRARY TRANSFER REVIEW — no device access or device change occurred",
        "profile": EXPERIMENTAL_LIBRARY_PROFILE,
        "operation": EXPERIMENTAL_OPERATION,
        "product_exposure": "experimental_review_and_guarded_transfer_boundary",
        "selection": {
            "logical_item_id": selected_ids[0] if isinstance(selected_ids, list) and len(selected_ids) == 1 else None,
            "grouping": "explicit_one_library_item_one_package",
            "multi_selection_means_merge": False,
        },
        "package": {
            "folder_path": expected_paths[0] if expected_paths else None,
            "paths": _copy(expected_paths),
            "ordered_children": _copy(package_children),
            "prepared_manifest_sha256": prepared.get("manifest_sha256") if isinstance(prepared, Mapping) else None,
            "source_bytes": prepared.get("source_bytes") if isinstance(prepared, Mapping) else None,
            "prepared_payload_bytes": prepared.get("prepared_payload_bytes") if isinstance(prepared, Mapping) else None,
        },
        "destination": {
            "paths": _copy(expected_paths),
            "absence_rule": "all four expected paths must be absent from the fresh verified backup",
            "conflicts": _copy(item.get("conflicts", [])),
        },
        "capacity": {
            "status": capacity.get("status", "not_available") if isinstance(capacity, Mapping) else "not_available",
            "available_bytes": capacity.get("available_bytes") if isinstance(capacity, Mapping) else None,
            "lower_bound_bytes": capacity.get("lower_bound_bytes") if isinstance(capacity, Mapping) else None,
            "candidate_growth_bytes": bindings.get("candidate_growth_bytes"),
            "capacity_limit_bytes": bindings.get("capacity_limit_bytes"),
            "total_model_capacity_bytes": bindings.get("capacity_limit_bytes"),
            "baseline_model_bytes": bindings.get("baseline_model_bytes"),
            "candidate_model_bytes": bindings.get("candidate_model_bytes"),
            "remaining_after_transfer_bytes": bindings.get(
                "remaining_after_transfer_bytes"
            ),
            "remaining_growth_bytes": bindings.get("remaining_growth_bytes"),
            "fresh_native_0x0019_required": True,
        },
        "fresh_backup": {
            "required": True,
            "destination": fresh_backup_destination,
            "destination_is_safety_identity": False,
            "baseline_state_identity_sha256": bindings.get("baseline_state_identity_sha256"),
            "provenance_is_not_safety_identity": True,
        },
        "candidate": {
            "available": bool(bindings),
            "candidate_blob_sha256": bindings.get("candidate_blob_sha256"),
            "candidate_blob_length": bindings.get("candidate_blob_length"),
            "candidate_growth_bytes": bindings.get("candidate_growth_bytes"),
        },
        "operation_identity": {
            "bundle_sha256": bindings.get("bundle_sha256"),
            "transaction_sha256": bindings.get("transaction_sha256"),
            "preflight_seal_sha256": bindings.get("preflight_seal_sha256"),
            "core_preflight_seal_sha256": bindings.get("core_preflight_seal_sha256"),
            "capacity_response_sha256": bindings.get("capacity_response_sha256"),
        },
        "transfer_semantics": {
            "logical_selection": "one grouped Library package",
            "physical_protocol_scope": "complete candidate library image",
            "automatic_retry_allowed": False,
            "maximum_logical_transactions": 1,
            "request": "0x101b",
            "accepted_completion": "0x0000",
        },
        "verification": {
            "fresh_complete_post_backup_required": True,
            "independent_read_back_required": True,
            "wrapper_reconciliation": "P17-019 candidate-core disk-only verification",
            "expected_post_paths": _expected_paths(),
            "audit_location": audit_location,
        },
        "eligibility": {
            "state": "ready_for_hardware_test" if bindings and not reasons else "preview_only",
            "execution_action_exposed": False,
            "experimental_status": "ready_for_hardware_test" if bindings and not reasons else "preview_only",
            "reasons": reasons,
        },
        "safety": {
            "exact_device": "Sony 054c:001e",
            "exact_confirmation_required": True,
            "fresh_backup_and_immediate_revalidation": True,
            "no_retry_warning": "Indeterminate outcomes require read-only diagnosis; never retry automatically",
            "candidate_bytes_included": False,
            "usb_accessed": False,
            "device_change": "none",
            "contract": experimental_safety_contract(),
        },
    }
    return ExperimentalLibraryTransferReview(report)


__all__ = [
    "EXPERIMENTAL_CHILDREN",
    "EXPERIMENTAL_LIBRARY_PROFILE",
    "EXPERIMENTAL_LIBRARY_REVIEW_FORMAT",
    "EXPERIMENTAL_OPERATION",
    "EXPERIMENTAL_SAFETY_POLICY",
    "EXPERIMENTAL_TARGET_FOLDER",
    "ExperimentalLibraryTransferReview",
    "ExperimentalLibraryTransferReviewError",
    "build_experimental_library_transfer_review",
]
