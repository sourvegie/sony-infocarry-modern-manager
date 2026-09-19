"""UI-independent readiness model for the reviewed Library profiles.

This module describes reusable host/product eligibility only.  It deliberately
does not import the historical operation review, candidate builders, claim
stores, locks, USB access, or sender code.  A readiness result is therefore a
product explanation, never an authorization or a live-transfer request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Iterable, Mapping, Optional

from .capability_profile import (
    CAPABILITY_PROFILE_STATUS,
    CapabilityProfileError,
    INITIAL_EXPERIMENTAL_PROFILE_ID,
    VNW_V15_FOUR_LEAF_PROFILE_ID,
    capability_profile_by_id,
    initial_capability_profile,
)
from .device_model_profile import (
    DeviceModelProfile,
    MODEL_STATUS_UNCHARACTERIZED,
    VNW_V15_PROFILE,
    VNW_V15_PROFILE_ID,
)
from .prepared_content import PreparedContentArtifact, PreparedContentError
from .transfer_shape import (
    EXACT_VERIFIED_LIVE_PROFILE,
    FOUR_LEAF_VERIFIED_CHILD_KINDS,
    TransferShapeAssessment,
    assess_transfer_shape,
)


LIBRARY_TRANSFER_READINESS_FORMAT = "infocarry-library-transfer-readiness-v1"
EXPERIMENTAL_LIBRARY_PROFILE_ID = INITIAL_EXPERIMENTAL_PROFILE_ID
EXPERIMENTAL_LIBRARY_PROFILE_STATUS = CAPABILITY_PROFILE_STATUS
EXPERIMENTAL_CHILD_KINDS = ("txt", "bmp", "txt")
PREPARED_MEDIA_PACKAGE_FORMAT = "infocarry-prepared-typed-media-package-v1"
LIBRARY_TRANSFER_READINESS_STATUS = (
    "Verified VNW-V15 shape eligible — guarded live transfer requires fresh evidence"
)


class LibraryTransferReadinessError(ValueError):
    """Raised when a readiness input cannot be represented at all."""


class ReadinessReasonCode(str, Enum):
    """Stable machine-readable reason codes for the normal manager UI."""

    NO_PREPARED_CONTENT = "no_prepared_content"
    CONTENT_CHANGED = "content_changed"
    TARGET_CHANGED = "target_changed"
    DEVICE_NOT_CONNECTED = "device_not_connected"
    UNSUPPORTED_DEVICE = "unsupported_device"
    FRESH_BACKUP_REQUIRED = "fresh_backup_required"
    FRESH_CAPACITY_REQUIRED = "fresh_capacity_required"
    DESTINATION_EXISTS = "destination_exists"
    SAFETY_LOCK_ACTIVE = "safety_lock_active"
    PREVIOUS_OPERATION_INDETERMINATE = "previous_operation_indeterminate"
    UNSUPPORTED_LIVE_PROFILE = "unsupported_live_profile"
    UNSUPPORTED_SOURCE_FORMAT = "unsupported_source_format"
    PREPARATION_FAILED = "preparation_failed"
    REVIEW_REQUIRED = "review_required"
    VALIDATION_FAILED = "validation_failed"


class ReadinessAction(str, Enum):
    """The safe next step the normal UI should offer."""

    NONE = "none"
    PREPARE = "prepare"
    REPREPARE = "reprepare"
    RECONNECT = "reconnect"
    REVIEW = "review"
    DIAGNOSE = "diagnose"


_REASON_MESSAGES: dict[ReadinessReasonCode, str] = {
    ReadinessReasonCode.NO_PREPARED_CONTENT: "Add content and prepare it before reviewing transfer.",
    ReadinessReasonCode.CONTENT_CHANGED: "This content changed after preparation. Prepare it again.",
    ReadinessReasonCode.TARGET_CHANGED: "The destination changed. Review transfer again.",
    ReadinessReasonCode.DEVICE_NOT_CONNECTED: "Connect the InfoCarry device to continue.",
    ReadinessReasonCode.UNSUPPORTED_DEVICE: "This device is not supported for this transfer.",
    ReadinessReasonCode.FRESH_BACKUP_REQUIRED: "A current device backup is needed before sending.",
    ReadinessReasonCode.FRESH_CAPACITY_REQUIRED: "Current device capacity must be checked before sending.",
    ReadinessReasonCode.DESTINATION_EXISTS: "The destination already exists. Choose a new destination and review again.",
    ReadinessReasonCode.SAFETY_LOCK_ACTIVE: "A previous operation needs diagnosis before another operation can start.",
    ReadinessReasonCode.PREVIOUS_OPERATION_INDETERMINATE: "A previous operation needs diagnosis. Do not retry automatically.",
    ReadinessReasonCode.UNSUPPORTED_LIVE_PROFILE: "This prepared content is valid, but its transfer shape is not currently supported.",
    ReadinessReasonCode.UNSUPPORTED_SOURCE_FORMAT: "This format is not ready for conversion yet.",
    ReadinessReasonCode.PREPARATION_FAILED: "Preparation could not be completed. Fix the content and prepare it again.",
    ReadinessReasonCode.REVIEW_REQUIRED: "Review transfer to confirm the current state before sending.",
    ReadinessReasonCode.VALIDATION_FAILED: "The content is not ready for transfer. Review the details and prepare again.",
}

_REASON_ACTIONS: dict[ReadinessReasonCode, ReadinessAction] = {
    ReadinessReasonCode.NO_PREPARED_CONTENT: ReadinessAction.PREPARE,
    ReadinessReasonCode.CONTENT_CHANGED: ReadinessAction.REPREPARE,
    ReadinessReasonCode.TARGET_CHANGED: ReadinessAction.REVIEW,
    ReadinessReasonCode.DEVICE_NOT_CONNECTED: ReadinessAction.RECONNECT,
    ReadinessReasonCode.UNSUPPORTED_DEVICE: ReadinessAction.REVIEW,
    ReadinessReasonCode.FRESH_BACKUP_REQUIRED: ReadinessAction.REVIEW,
    ReadinessReasonCode.FRESH_CAPACITY_REQUIRED: ReadinessAction.REVIEW,
    ReadinessReasonCode.DESTINATION_EXISTS: ReadinessAction.REVIEW,
    ReadinessReasonCode.SAFETY_LOCK_ACTIVE: ReadinessAction.DIAGNOSE,
    ReadinessReasonCode.PREVIOUS_OPERATION_INDETERMINATE: ReadinessAction.DIAGNOSE,
    ReadinessReasonCode.UNSUPPORTED_LIVE_PROFILE: ReadinessAction.REVIEW,
    ReadinessReasonCode.UNSUPPORTED_SOURCE_FORMAT: ReadinessAction.PREPARE,
    ReadinessReasonCode.PREPARATION_FAILED: ReadinessAction.REPREPARE,
    ReadinessReasonCode.REVIEW_REQUIRED: ReadinessAction.REVIEW,
    ReadinessReasonCode.VALIDATION_FAILED: ReadinessAction.REVIEW,
}


@dataclass(frozen=True)
class ReadinessReason:
    """One typed explanation separated from its optional diagnostic detail."""

    code: ReadinessReasonCode
    message: str
    action: ReadinessAction
    technical_detail: Optional[str] = None

    def __post_init__(self) -> None:
        if self.message != _REASON_MESSAGES[self.code]:
            raise ValueError("readiness reason message does not match its code")
        if self.action is not _REASON_ACTIONS[self.code]:
            raise ValueError("readiness reason action does not match its code")
        if self.technical_detail is not None and not isinstance(self.technical_detail, str):
            raise ValueError("readiness technical detail must be text or None")

    def to_dict(self, *, include_technical: bool = False) -> dict[str, Any]:
        value: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
            "action": self.action.value,
        }
        if include_technical and self.technical_detail:
            value["technical_detail"] = self.technical_detail
        return value


@dataclass(frozen=True)
class ReadinessState:
    """Canonical typed state consumed by the normal manager UI."""

    state: str
    message: str
    action_allowed: bool
    next_action: ReadinessAction
    reasons: tuple[ReadinessReason, ...] = ()
    artifact_identity: Optional[str] = None
    transfer_enabled: bool = False

    def __post_init__(self) -> None:
        if self.state not in {"blocked", "needs_review", "ready"}:
            raise ValueError("unsupported readiness state")
        if not isinstance(self.message, str) or not self.message:
            raise ValueError("readiness state message is required")
        if any(not isinstance(reason, ReadinessReason) for reason in self.reasons):
            raise ValueError("readiness reasons must be typed")
        if self.transfer_enabled and not self.action_allowed:
            raise ValueError("enabled transfer must be actionable")
        if self.artifact_identity is not None and not _is_digest(self.artifact_identity):
            raise ValueError("readiness artifact identity must be a SHA-256 digest")

    @property
    def reason_codes(self) -> tuple[ReadinessReasonCode, ...]:
        return tuple(reason.code for reason in self.reasons)

    @property
    def technical_details(self) -> tuple[str, ...]:
        return tuple(
            reason.technical_detail
            for reason in self.reasons
            if reason.technical_detail
        )

    def to_dict(self, *, include_technical: bool = False) -> dict[str, Any]:
        value = {
            "state": self.state,
            "message": self.message,
            "action_allowed": self.action_allowed,
            "next_action": self.next_action.value,
            "reasons": [
                reason.to_dict(include_technical=include_technical)
                for reason in self.reasons
            ],
            "artifact_identity": self.artifact_identity,
            "transfer_enabled": self.transfer_enabled,
        }
        if include_technical:
            value["technical_details"] = list(self.technical_details)
        return value


def _reason_code_for_text(text: str) -> ReadinessReasonCode:
    """Map legacy planner prose to stable product reason codes."""

    lowered = text.casefold()
    if "indeterminate" in lowered or "may have started" in lowered:
        return ReadinessReasonCode.PREVIOUS_OPERATION_INDETERMINATE
    if "installation-wide" in lowered and "lock" in lowered or "safety lock" in lowered:
        return ReadinessReasonCode.SAFETY_LOCK_ACTIVE
    if "source changed" in lowered or "content changed" in lowered or "hash changed" in lowered:
        return ReadinessReasonCode.CONTENT_CHANGED
    if "target" in lowered and ("changed" in lowered or "differs" in lowered):
        return ReadinessReasonCode.TARGET_CHANGED
    if "not connected" in lowered or "device unavailable" in lowered:
        return ReadinessReasonCode.DEVICE_NOT_CONNECTED
    if "vnw-v10" in lowered or "device model" in lowered and "supported" in lowered:
        return ReadinessReasonCode.UNSUPPORTED_DEVICE
    if "capacity" in lowered:
        return ReadinessReasonCode.FRESH_CAPACITY_REQUIRED
    if "backup" in lowered:
        return ReadinessReasonCode.FRESH_BACKUP_REQUIRED
    if "already exists" in lowered or "conflict" in lowered or "overlap" in lowered:
        return ReadinessReasonCode.DESTINATION_EXISTS
    if "not ready for conversion" in lowered:
        return ReadinessReasonCode.UNSUPPORTED_SOURCE_FORMAT
    if (
        "unsupported" in lowered
        or "not currently supported" in lowered
        or "exactly three" in lowered
        or "txt" in lowered and "bmp" in lowered
    ):
        return ReadinessReasonCode.UNSUPPORTED_LIVE_PROFILE
    if "prepare" in lowered or "prepared artifact" in lowered:
        return ReadinessReasonCode.PREPARATION_FAILED
    if "selected" in lowered or "package" in lowered or "artifact" in lowered:
        return ReadinessReasonCode.NO_PREPARED_CONTENT
    return ReadinessReasonCode.VALIDATION_FAILED


def _typed_reasons(values: Iterable[str]) -> tuple[ReadinessReason, ...]:
    result: list[ReadinessReason] = []
    seen: set[ReadinessReasonCode] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        code = _reason_code_for_text(value)
        if code in seen:
            continue
        seen.add(code)
        result.append(
            ReadinessReason(
                code=code,
                message=_REASON_MESSAGES[code],
                action=_REASON_ACTIONS[code],
                technical_detail=value,
            )
        )
    return tuple(result)


def readiness_state_from_error(
    error: BaseException,
    *,
    artifact_identity: Optional[str] = None,
) -> ReadinessState:
    """Convert a worker/preflight exception into a safe typed UI outcome."""

    detail = str(error) or error.__class__.__name__
    state = getattr(error, "state", None)
    if state == "indeterminate_after_transaction_start":
        code = ReadinessReasonCode.PREVIOUS_OPERATION_INDETERMINATE
    else:
        code = _reason_code_for_text(detail)
    reason = ReadinessReason(
        code=code,
        message=_REASON_MESSAGES[code],
        action=_REASON_ACTIONS[code],
        technical_detail=detail,
    )
    return ReadinessState(
        state="blocked",
        message=reason.message,
        action_allowed=False,
        next_action=reason.action,
        reasons=(reason,),
        artifact_identity=artifact_identity,
        transfer_enabled=False,
    )


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
            reasons.append("the reviewed Library profile requires explicit selected-item planning")
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


def _readiness_state_from_report(
    report: Mapping[str, Any],
    *,
    reasons: Iterable[str],
    fresh_evidence: Iterable[str],
) -> ReadinessState:
    """Build the typed normal-UI state while retaining legacy report prose."""

    eligibility = report.get("eligibility", {})
    preparation = report.get("preparation", {})
    package = report.get("package", {})
    raw_reasons = [value for value in reasons if isinstance(value, str)]
    raw_fresh = [value for value in fresh_evidence if isinstance(value, str)]
    all_reasons = tuple(dict.fromkeys((*raw_reasons, *raw_fresh)))
    typed = _typed_reasons(all_reasons)

    if not typed and not isinstance(eligibility, Mapping):
        typed = _typed_reasons(("readiness report is malformed",))
    host_eligible = isinstance(eligibility, Mapping) and eligibility.get(
        "host_profile_eligible"
    ) is True
    blocked = isinstance(eligibility, Mapping) and eligibility.get("blocked") is True
    if not typed and host_eligible:
        typed = (
            ReadinessReason(
                code=ReadinessReasonCode.REVIEW_REQUIRED,
                message=_REASON_MESSAGES[ReadinessReasonCode.REVIEW_REQUIRED],
                action=ReadinessAction.REVIEW,
                technical_detail=None,
            ),
        )
    if not host_eligible and not typed:
        typed = _typed_reasons(("selected content is not ready",))

    if blocked:
        state = "blocked"
        first_message = typed[0].message
        next_action = typed[0].action
    elif raw_fresh:
        state = "needs_review"
        first_message = "Content is prepared. Review current device readiness before sending."
        next_action = ReadinessAction.REVIEW
    else:
        state = "ready"
        first_message = "Content is ready for transfer review."
        next_action = ReadinessAction.REVIEW

    artifact_identity = None
    if isinstance(preparation, Mapping):
        candidate = preparation.get("artifact_identity")
        if _is_digest(candidate):
            artifact_identity = str(candidate)
    if artifact_identity is None and isinstance(package, Mapping):
        candidate = package.get("prepared_artifact_identity")
        if _is_digest(candidate):
            artifact_identity = str(candidate)

    return ReadinessState(
        state=state,
        message=first_message,
        action_allowed=False,
        next_action=next_action,
        reasons=typed,
        artifact_identity=artifact_identity,
        transfer_enabled=False,
    )
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
        reasons.append("the reviewed Library profile requires exactly one selected Library package")
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
    canonical_artifact: Optional[PreparedContentArtifact] = None
    transfer_shape: Optional[TransferShapeAssessment] = None
    selected_profile_id = INITIAL_EXPERIMENTAL_PROFILE_ID

    generic_artifact = item.get("operation_type") in {
        "prepared_content_artifact",
        "prepared_epub_content",
    }
    if item.get("operation_type") != "prepared_flat_typed_package":
        if not generic_artifact:
            reasons.append("the selected item is not an explicitly imported prepared Library package")
        exact_package = False
    if item.get("execution_eligible") is not False:
        reasons.append("the selected package cannot advertise execution eligibility")
    if not isinstance(artifact, Mapping):
        reasons.append("the prepared package manifest is missing")
        exact_package = False
    else:
        expected_contract = (
            "infocarry-prepared-content-v1"
            if generic_artifact
            else PREPARED_MEDIA_PACKAGE_FORMAT
        )
        if artifact.get("contract") != expected_contract:
            reasons.append("the prepared content manifest contract is unsupported")
            exact_package = False
        manifest_sha256 = artifact.get("manifest_sha256")
        if not _is_digest(manifest_sha256):
            reasons.append("the prepared package manifest hash is malformed")
            exact_package = False
        canonical_value = artifact.get("canonical")
        try:
            if isinstance(canonical_value, Mapping):
                canonical_artifact = PreparedContentArtifact.from_dict(canonical_value)
                if artifact.get("artifact_identity") != canonical_artifact.artifact_identity:
                    raise PreparedContentError(
                        "prepared artifact identity differs from its canonical content"
                    )
                if artifact.get("root_name") != canonical_artifact.root_name:
                    raise PreparedContentError(
                        "prepared artifact root name differs from its canonical content"
                    )
                if artifact.get("aggregate_size") != canonical_artifact.aggregate_size:
                    raise PreparedContentError(
                        "prepared artifact aggregate size differs from its canonical content"
                    )
                canonical_children = canonical_artifact.to_legacy_children()
                # The legacy projection remains in persisted reports for
                # compatibility.  It is not an alternate source of truth:
                # tampering with it must still invalidate readiness rather
                # than being silently repaired from the canonical payload.
                if children != canonical_children:
                    raise PreparedContentError(
                        "legacy prepared child projection differs from canonical content"
                    )
                children = canonical_children
            elif isinstance(children, list) and folder_name is not None:
                # Compatibility adapter for pre-convergence queue reports.  New
                # reports always carry the canonical artifact above.
                canonical_artifact = PreparedContentArtifact.from_legacy_children(
                    root_name=folder_name,
                    children=children,
                )
            else:
                raise PreparedContentError("canonical prepared content is missing")
        except PreparedContentError as exc:
            reasons.append(f"canonical preparation/profile validation failed: {exc}")
            exact_package = False

    if canonical_artifact is not None:
        try:
            transfer_shape = assess_transfer_shape(canonical_artifact)
        except (TypeError, ValueError) as exc:
            reasons.append(f"transfer-shape assessment failed: {exc}")
            exact_package = False
        else:
            if transfer_shape.classification != EXACT_VERIFIED_LIVE_PROFILE:
                reasons.extend(transfer_shape.reasons)
                reasons.append(
                    "exact supported direct-leaf orders are TXT → BMP → TXT "
                    "and TXT → BMP → TXT → TXT"
                )
                exact_package = False
            elif transfer_shape.ordered_kinds == FOUR_LEAF_VERIFIED_CHILD_KINDS:
                selected_profile_id = VNW_V15_FOUR_LEAF_PROFILE_ID
            if paths != [
                canonical_artifact.root_path,
                *(child.path for child in canonical_artifact.children),
            ]:
                reasons.append("destination paths differ from the canonical prepared content")
                exact_package = False

    if not isinstance(children, list):
        reasons.append("the selected package ordered children are malformed")
        exact_package = False
    elif canonical_artifact is None:
        reasons.append("the canonical prepared content is missing")
        exact_package = False
    else:
        expected_kinds = (
            transfer_shape.ordered_kinds
            if transfer_shape is not None
            else ()
        )
        if (
            len(children) != len(expected_kinds)
            or transfer_shape is None
            or transfer_shape.classification != EXACT_VERIFIED_LIVE_PROFILE
        ):
            reasons.append(
                "the selected package must contain exactly three direct children "
                "or exactly four direct children in a reviewed order"
            )
            exact_package = False
        if folder_name is None:
            reasons.append("the package destination must be exactly one root-level folder")
            exact_package = False
        for index, child in enumerate(children):
            if not isinstance(child, Mapping):
                reasons.append(f"prepared package child {index + 1} is malformed")
                exact_package = False
                continue
            normalized_children.append(dict(child))
            expected_kind = expected_kinds[index] if index < len(expected_kinds) else None
            if child.get("kind") != expected_kind or child.get("order") != index:
                reasons.append(
                    "child order/kinds must match one of the two physically verified "
                    "VNW-V15 direct-leaf shapes"
                )
                exact_package = False
            if (
                folder_path is not None
                and child.get("path") != f"{folder_path}\\{child.get('name', '')}"
            ):
                reasons.append(
                    "prepared package child path is nested, missing, or outside the root folder"
                )
                exact_package = False

    if canonical_artifact is not None:
        if folder_name != canonical_artifact.root_name:
            reasons.append("destination root differs from the canonical prepared artifact")
            exact_package = False
        if canonical_artifact.aggregate_size != sum(
            child.payload_bytes for child in canonical_artifact.children
        ):
            reasons.append("canonical prepared aggregate size is inconsistent")
            exact_package = False

    if not generic_artifact and folder_name is not None and isinstance(paths, list):
        expected_paths = [
            folder_path,
            *[
                f"{folder_path}\\{child.get('name')}"
                for child in normalized_children
            ],
        ]
        if paths != expected_paths or len(paths) != 1 + len(normalized_children):
            reasons.append(
                "destination must contain exactly the root folder and its reviewed direct children"
            )
            exact_package = False
    elif not generic_artifact and not isinstance(paths, list):
        reasons.append("prepared package destination paths are malformed")
        exact_package = False

    if exact_package and folder_name is not None:
        try:
            normalized_children = list(
                capability_profile_by_id(selected_profile_id).validate_package(
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
    if host_profile_eligible:
        status_text = LIBRARY_TRANSFER_READINESS_STATUS
    elif canonical_artifact is not None and canonical_artifact.valid_preparation:
        status_text = (
            "Blocked — prepared content is valid but outside a reviewed Library "
            f"shape: {reasons[0] if reasons else 'unsupported exact shape'}"
        )
    else:
        status_text = (
            "Blocked — "
            f"{reasons[0] if reasons else 'selected package is outside a reviewed Library profile'}"
        )

    report: dict[str, Any] = {
        "format": LIBRARY_TRANSFER_READINESS_FORMAT,
        "state": state,
        "profile": {
            "id": selected_profile_id,
            "status": capability_profile_by_id(selected_profile_id).document["status"],
            "device_model_profile_id": VNW_V15_PROFILE_ID,
            "required_child_kinds": (
                list(transfer_shape.ordered_kinds)
                if transfer_shape is not None
                and transfer_shape.classification == EXACT_VERIFIED_LIVE_PROFILE
                else list(EXPERIMENTAL_CHILD_KINDS)
            ),
            "root_level_only": True,
            "exact_child_count": (
                transfer_shape.child_count
                if transfer_shape is not None
                and transfer_shape.classification == EXACT_VERIFIED_LIVE_PROFILE
                else None
            ),
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
            "prepared_content_valid": canonical_artifact is not None,
            "prepared_artifact_identity": (
                canonical_artifact.artifact_identity
                if canonical_artifact is not None
                else None
            ),
            "prepared_content": (
                canonical_artifact.to_dict()
                if canonical_artifact is not None
                else None
            ),
            "root_name": canonical_artifact.root_name if canonical_artifact is not None else None,
            "aggregate_size": canonical_artifact.aggregate_size if canonical_artifact is not None else None,
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
        "preparation": {
            "valid": canonical_artifact is not None,
            "artifact_identity": (
                canonical_artifact.artifact_identity
                if canonical_artifact is not None
                else None
            ),
            "aggregate_size": (
                canonical_artifact.aggregate_size
                if canonical_artifact is not None
                else None
            ),
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
            "prepared_content_valid": canonical_artifact is not None,
            "live_transfer_eligible": host_profile_eligible,
            "host_profile_eligible": host_profile_eligible,
            "needs_fresh_live_evidence": host_profile_eligible and bool(fresh_evidence),
            "blocked": blocked,
            "status_text": status_text,
            "reasons": reasons,
            "fresh_evidence_reasons": fresh_evidence,
        },
    }
    if transfer_shape is not None:
        report["transfer_shape"] = transfer_shape.to_dict()
    ui_state = _readiness_state_from_report(
        report,
        reasons=reasons,
        fresh_evidence=fresh_evidence,
    )
    report["eligibility"]["reason_details"] = [
        reason.to_dict(include_technical=True) for reason in ui_state.reasons
    ]
    report["ui"] = ui_state.to_dict(include_technical=True)
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
    _ui_state: ReadinessState = field(init=False, repr=False)

    def __post_init__(self) -> None:
        eligibility = self.report.get("eligibility", {})
        reasons = eligibility.get("reasons", []) if isinstance(eligibility, Mapping) else []
        fresh = (
            eligibility.get("fresh_evidence_reasons", [])
            if isinstance(eligibility, Mapping)
            else []
        )
        object.__setattr__(
            self,
            "_ui_state",
            _readiness_state_from_report(
                self.report,
                reasons=reasons if isinstance(reasons, list) else (),
                fresh_evidence=fresh if isinstance(fresh, list) else (),
            ),
        )

    @property
    def ui_state(self) -> ReadinessState:
        """Typed state used by the normal UI; report remains a compatibility view."""

        return self._ui_state

    @property
    def reason_codes(self) -> tuple[ReadinessReasonCode, ...]:
        return self._ui_state.reason_codes

    @property
    def user_message(self) -> str:
        return self._ui_state.message

    @property
    def action_allowed(self) -> bool:
        return self._ui_state.action_allowed

    @property
    def next_action(self) -> ReadinessAction:
        return self._ui_state.next_action

    @property
    def host_profile_eligible(self) -> bool:
        return bool(self.report.get("eligibility", {}).get("host_profile_eligible"))

    @property
    def prepared_content_valid(self) -> bool:
        return bool(self.report.get("preparation", {}).get("valid"))

    @property
    def live_transfer_eligible(self) -> bool:
        """Whether the exact reviewed live shape matches, never authorization."""

        return bool(self.report.get("eligibility", {}).get("live_transfer_eligible"))

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
    "ReadinessAction",
    "ReadinessReason",
    "ReadinessReasonCode",
    "ReadinessState",
    "LibraryTransferReadiness",
    "LibraryTransferReadinessError",
    "build_experimental_library_readiness",
    "build_library_transfer_readiness",
    "readiness_state_from_error",
    "validate_library_transfer_readiness",
]
