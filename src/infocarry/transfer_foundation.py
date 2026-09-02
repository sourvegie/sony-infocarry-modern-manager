"""Framework-independent application transfer façade records.

This module defines the product-level progression
``PreparedItem[] -> TransferPlan -> CandidateLibrary -> Authorization ->
ExecuteOnce -> ReadBackVerification`` without constructing a candidate,
calling a sender, or importing USB/live-adapter code.  The initial capability
profile keeps the execution descriptor disabled; reviewed P17 components can
be attached later only at an explicitly reviewed R3 boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from .capability_profile import (
    CapabilityProfile,
    CapabilityProfileError,
    initial_capability_profile,
)
from .device_model_profile import CapacityObservation, DeviceModelProfile


TRANSFER_FOUNDATION_FORMAT = "infocarry-transfer-foundation-v1"


class TransferFoundationError(ValueError):
    """Raised when the application façade cannot bind one safe operation."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise TransferFoundationError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _copy(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy(child) for child in value]
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(child) for child in value)
    return value


@dataclass(frozen=True)
class PreparedItem:
    """One explicitly grouped Library package, still before candidate build."""

    library_item_id: str
    package_manifest_sha256: str
    folder_name: str
    children: tuple[Mapping[str, Any], ...]
    grouping_contract: str = "explicit_prepared_package"

    def __post_init__(self) -> None:
        if not isinstance(self.library_item_id, str) or not self.library_item_id:
            raise TransferFoundationError("Library item identity is required")
        if self.grouping_contract != "explicit_prepared_package":
            raise TransferFoundationError("package grouping must be explicit")
        _digest(self.package_manifest_sha256, "package_manifest_sha256")
        if not isinstance(self.children, tuple):
            raise TransferFoundationError("prepared children must remain ordered")
        profile = initial_capability_profile()
        try:
            normalized = profile.validate_package(
                folder_name=self.folder_name,
                children=self.children,
            )
        except CapabilityProfileError as exc:
            raise TransferFoundationError(str(exc)) from exc
        object.__setattr__(
            self,
            "children",
            tuple(_freeze(child) for child in normalized),
        )

    @classmethod
    def from_queue_item(cls, item: Mapping[str, Any]) -> "PreparedItem":
        if not isinstance(item, Mapping):
            raise TransferFoundationError("queue item must be an object")
        artifact = item.get("prepared_artifact")
        destination = item.get("destination")
        if not isinstance(artifact, Mapping) or not isinstance(destination, Mapping):
            raise TransferFoundationError("queue item package bindings are malformed")
        if item.get("operation_type") != "prepared_flat_typed_package":
            raise TransferFoundationError("queue item is not an explicit prepared package")
        if artifact.get("contract") != "infocarry-prepared-typed-media-package-v1":
            raise TransferFoundationError("queue item package contract is unsupported")
        paths = destination.get("paths")
        if (
            not isinstance(paths, list)
            or len(paths) < 2
            or not all(isinstance(path, str) and path for path in paths)
            or destination.get("folder_path") != paths[0]
            or destination.get("child_path") != paths[1]
        ):
            raise TransferFoundationError("queue item destination is malformed")
        prefix = "root\\"
        if not paths[0].startswith(prefix):
            raise TransferFoundationError("queue item destination is not root-level")
        children = artifact.get("ordered_children")
        if (
            not isinstance(children, list)
            or not all(isinstance(child, Mapping) for child in children)
            or artifact.get("child_order") != [child.get("name") for child in children]
        ):
            raise TransferFoundationError("queue item ordered children are missing")
        library_item_id = item.get("item_id")
        manifest_sha256 = artifact.get("manifest_sha256")
        if not isinstance(library_item_id, str) or not library_item_id:
            raise TransferFoundationError("queue item Library identity is malformed")
        if not isinstance(manifest_sha256, str):
            raise TransferFoundationError("queue item manifest identity is malformed")
        prepared = cls(
            library_item_id=library_item_id,
            package_manifest_sha256=manifest_sha256,
            folder_name=paths[0][len(prefix) :],
            children=tuple(dict(child) for child in children),
        )
        if tuple(paths) != prepared.destination_paths:
            raise TransferFoundationError("queue item destination is not bound to every child")
        return prepared

    @property
    def destination_paths(self) -> tuple[str, ...]:
        return (
            f"root\\{self.folder_name}",
            *(str(child["path"]) for child in self.children),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "library_item_id": self.library_item_id,
            "package_manifest_sha256": self.package_manifest_sha256,
            "folder_name": self.folder_name,
            "grouping_contract": self.grouping_contract,
            "ordered_children": [_copy(child) for child in self.children],
        }


@dataclass(frozen=True)
class TransferPlan:
    """Hashable offline plan for exactly one selected package."""

    profile_id: str
    prepared_items: tuple[PreparedItem, ...]
    destination_paths: tuple[str, ...]
    conflict_policy: str = "reject_any_existing_path"
    fresh_backup_required: bool = True
    capacity_validation_required: bool = True
    execution_enabled: bool = False
    capacity: CapacityObservation | None = None

    def __post_init__(self) -> None:
        reviewed_profile = initial_capability_profile()
        if self.profile_id != reviewed_profile.profile_id:
            raise TransferFoundationError("transfer plan profile is unsupported")
        if not isinstance(self.prepared_items, tuple):
            raise TransferFoundationError("transfer plan packages must remain ordered")
        if not all(isinstance(item, PreparedItem) for item in self.prepared_items):
            raise TransferFoundationError("transfer plan contains an invalid package")
        if len(self.prepared_items) != 1:
            raise TransferFoundationError(
                "the initial foundation accepts one explicitly selected package"
            )
        if self.conflict_policy != "reject_any_existing_path":
            raise TransferFoundationError("unsupported destination conflict policy")
        if self.fresh_backup_required is not True or self.capacity_validation_required is not True:
            raise TransferFoundationError("fresh backup and capacity validation are mandatory")
        if tuple(self.destination_paths) != self.prepared_items[0].destination_paths:
            raise TransferFoundationError("transfer plan destination is not package-bound")
        if self.execution_enabled:
            raise TransferFoundationError(
                "the initial foundation cannot enable live execution"
            )
        if self.capacity is not None and not isinstance(self.capacity, CapacityObservation):
            raise TransferFoundationError("capacity observation is malformed")

    @property
    def plan_sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "infocarry-transfer-plan-v1",
            "profile_id": self.profile_id,
            "selected_package_count": len(self.prepared_items),
            "prepared_items": [item.to_dict() for item in self.prepared_items],
            "destination_paths": list(self.destination_paths),
            "conflict_policy": self.conflict_policy,
            "fresh_complete_backup_required": self.fresh_backup_required,
            "capacity_validation_required": self.capacity_validation_required,
            "execution_enabled": self.execution_enabled,
            "capacity": None if self.capacity is None else self.capacity.to_dict(),
        }


@dataclass(frozen=True)
class CandidateLibrary:
    """Hash-only candidate stage supplied by a separately reviewed builder."""

    candidate_sha256: str
    transaction_sha256: str
    baseline_state_sha256: str
    expected_post_paths: tuple[str, ...]
    construction_source: str = "reviewed_builder_attached_outside_foundation"

    def __post_init__(self) -> None:
        _digest(self.candidate_sha256, "candidate_sha256")
        _digest(self.transaction_sha256, "transaction_sha256")
        _digest(self.baseline_state_sha256, "baseline_state_sha256")
        if not isinstance(self.expected_post_paths, tuple):
            raise TransferFoundationError("candidate expected paths must remain immutable")
        if not self.expected_post_paths or not all(
            isinstance(path, str) and path for path in self.expected_post_paths
        ):
            raise TransferFoundationError("expected post paths are required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_sha256": self.candidate_sha256,
            "transaction_sha256": self.transaction_sha256,
            "baseline_state_sha256": self.baseline_state_sha256,
            "expected_post_paths": list(self.expected_post_paths),
            "construction_source": self.construction_source,
            "candidate_bytes_included": False,
        }


@dataclass(frozen=True)
class Authorization:
    """Future transaction-specific in-app confirmation binding."""

    candidate_sha256: str
    transaction_sha256: str
    capacity_response_sha256: str
    capacity: CapacityObservation
    confirmation_required: bool = True
    confirmation_mode: str = "in_app_transaction_confirmation"
    status: str = "not_issued"
    maximum_logical_transactions: int = 1
    accepted_completion: str = "0x0000"
    automatic_retry_allowed: bool = False

    def __post_init__(self) -> None:
        _digest(self.candidate_sha256, "authorization candidate_sha256")
        _digest(self.transaction_sha256, "authorization transaction_sha256")
        _digest(self.capacity_response_sha256, "authorization capacity_response_sha256")
        if not isinstance(self.capacity, CapacityObservation):
            raise TransferFoundationError("authorization capacity observation is malformed")
        if self.capacity_response_sha256 != self.capacity.capacity_response_sha256:
            raise TransferFoundationError("authorization capacity response binding differs")
        if not self.confirmation_required or self.confirmation_mode != "in_app_transaction_confirmation":
            raise TransferFoundationError("authorization must require in-app confirmation")
        if self.status != "not_issued":
            raise TransferFoundationError(
                "the host-only foundation cannot consume or issue authorization"
            )
        if self.maximum_logical_transactions != 1 or self.accepted_completion != "0x0000":
            raise TransferFoundationError("unsupported authorization transaction policy")
        if self.automatic_retry_allowed:
            raise TransferFoundationError("automatic retry is not permitted")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_sha256": self.candidate_sha256,
            "transaction_sha256": self.transaction_sha256,
            "capacity_response_sha256": self.capacity_response_sha256,
            "capacity": self.capacity.to_dict(),
            "confirmation_required": self.confirmation_required,
            "confirmation_mode": self.confirmation_mode,
            "status": self.status,
            "maximum_logical_transactions": self.maximum_logical_transactions,
            "accepted_completion": self.accepted_completion,
            "automatic_retry_allowed": self.automatic_retry_allowed,
        }


@dataclass(frozen=True)
class ExecuteOnce:
    """Non-callable descriptor for the future one-shot execution boundary."""

    enabled: bool = False
    request: str = "0x101b"
    maximum_logical_sends: int = 1
    accepted_completion: str = "0x0000"
    automatic_retry_allowed: bool = False
    disabled_reason: str = "initial capability profile is defined but not live-enabled"

    def __post_init__(self) -> None:
        if self.enabled or self.maximum_logical_sends != 1:
            raise TransferFoundationError("host foundation cannot enable execution")
        if self.request != "0x101b" or self.accepted_completion != "0x0000":
            raise TransferFoundationError("unsupported execution policy")
        if self.automatic_retry_allowed or not self.disabled_reason:
            raise TransferFoundationError("invalid one-shot disabled policy")

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "request": self.request,
            "maximum_logical_sends": self.maximum_logical_sends,
            "accepted_completion": self.accepted_completion,
            "automatic_retry_allowed": self.automatic_retry_allowed,
            "disabled_reason": self.disabled_reason,
        }


@dataclass(frozen=True)
class ReadBackVerification:
    """Required terminal verification stage; no verification is run here."""

    required: bool = True
    independent_semantic_check: bool = True
    complete_post_write_backup: bool = True
    indeterminate_lock_on_ambiguous_outcome: bool = True
    status: str = "not_run"

    def __post_init__(self) -> None:
        if not all(
            (
                self.required,
                self.independent_semantic_check,
                self.complete_post_write_backup,
                self.indeterminate_lock_on_ambiguous_outcome,
            )
        ) or self.status != "not_run":
            raise TransferFoundationError("read-back verification policy is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "independent_semantic_check": self.independent_semantic_check,
            "complete_post_write_backup": self.complete_post_write_backup,
            "indeterminate_lock_on_ambiguous_outcome": self.indeterminate_lock_on_ambiguous_outcome,
            "status": self.status,
        }


@dataclass(frozen=True)
class TransferFoundation:
    """One offline façade value spanning the future application stages."""

    profile_id: str
    profile_sha256: str
    device_model_profile_id: str
    device_model_lock_key: str
    prepared_items: tuple[PreparedItem, ...]
    plan: TransferPlan
    candidate: Optional[CandidateLibrary]
    authorization: Optional[Authorization]
    execute_once: ExecuteOnce
    read_back: ReadBackVerification

    @classmethod
    def from_prepared_items(
        cls,
        prepared_items: Sequence[PreparedItem],
        *,
        profile: Optional[CapabilityProfile] = None,
        device_model_profile: DeviceModelProfile | None = None,
    ) -> "TransferFoundation":
        selected_profile = profile or initial_capability_profile()
        if not isinstance(selected_profile, CapabilityProfile):
            raise TransferFoundationError("profile must be the reviewed capability profile")
        if not isinstance(device_model_profile, DeviceModelProfile):
            raise TransferFoundationError(
                "an explicit reviewed device-model profile is required"
            )
        expected_model_profile_id = selected_profile.device_model_profile_id
        if (
            device_model_profile.profile_id != expected_model_profile_id
            or not device_model_profile.transfer_capable
            or device_model_profile.transfer_capability_profile_id
            != selected_profile.profile_id
        ):
            raise TransferFoundationError(
                "device-model profile does not authorize this capability profile"
            )
        if selected_profile.live_enabled:
            raise TransferFoundationError("live-enabled profiles are not accepted here")
        items = tuple(prepared_items)
        if not all(isinstance(item, PreparedItem) for item in items):
            raise TransferFoundationError("selected package has an invalid prepared item")
        if len(items) != 1:
            raise TransferFoundationError("one package must be selected explicitly")
        plan = TransferPlan(
            profile_id=selected_profile.profile_id,
            prepared_items=items,
            destination_paths=items[0].destination_paths,
        )
        return cls(
            profile_id=selected_profile.profile_id,
            profile_sha256=selected_profile.sha256,
            device_model_profile_id=device_model_profile.profile_id,
            device_model_lock_key=device_model_profile.lock_key.value,
            prepared_items=items,
            plan=plan,
            candidate=None,
            authorization=None,
            execute_once=ExecuteOnce(),
            read_back=ReadBackVerification(),
        )

    def attach_candidate(self, candidate: CandidateLibrary) -> "TransferFoundation":
        if tuple(candidate.expected_post_paths) != self.plan.destination_paths:
            raise TransferFoundationError("candidate expected paths differ from the plan")
        if self.authorization is not None:
            raise TransferFoundationError(
                "candidate cannot be replaced after authorization is attached"
            )
        return replace(self, candidate=candidate)

    def attach_authorization(self, authorization: Authorization) -> "TransferFoundation":
        if self.candidate is None:
            raise TransferFoundationError("candidate must be attached before authorization")
        if (
            authorization.candidate_sha256 != self.candidate.candidate_sha256
            or authorization.transaction_sha256 != self.candidate.transaction_sha256
        ):
            raise TransferFoundationError("authorization does not match the candidate")
        if self.plan.capacity is None or authorization.capacity != self.plan.capacity:
            raise TransferFoundationError(
                "authorization must bind the exact fresh model capacity observation"
            )
        return replace(self, authorization=authorization)

    def attach_capacity(self, capacity: CapacityObservation) -> "TransferFoundation":
        if not isinstance(capacity, CapacityObservation):
            raise TransferFoundationError("capacity observation is malformed")
        if capacity.model_profile_id != self.device_model_profile_id:
            raise TransferFoundationError(
                "capacity observation does not match the device-model profile"
            )
        if self.plan.capacity is not None:
            raise TransferFoundationError("capacity observation cannot be replaced")
        return replace(self, plan=replace(self.plan, capacity=capacity))

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": TRANSFER_FOUNDATION_FORMAT,
            "profile_id": self.profile_id,
            "profile_sha256": self.profile_sha256,
            "device_model_profile_id": self.device_model_profile_id,
            "device_model_lock_key": self.device_model_lock_key,
            "prepared_items": [item.to_dict() for item in self.prepared_items],
            "plan": self.plan.to_dict(),
            "candidate": None if self.candidate is None else self.candidate.to_dict(),
            "authorization": (
                None if self.authorization is None else self.authorization.to_dict()
            ),
            "execute_once": self.execute_once.to_dict(),
            "read_back": self.read_back.to_dict(),
            "usb_accessed": False,
            "device_change": "none",
        }


__all__ = [
    "Authorization",
    "CandidateLibrary",
    "ExecuteOnce",
    "PreparedItem",
    "ReadBackVerification",
    "TRANSFER_FOUNDATION_FORMAT",
    "TransferFoundation",
    "TransferFoundationError",
    "TransferPlan",
]
