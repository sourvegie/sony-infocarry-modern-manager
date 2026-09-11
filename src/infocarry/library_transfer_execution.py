"""Product-facing orchestration for the guarded Library transfer lifecycle.

The normal ttk surface imports this module, which contains only readiness,
operation-binding, and presentation orchestration types.  The canonical live
coordinator and adapter are imported lazily by the execution method so merely
opening the manager cannot open USB or construct a sender.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from .capability_profile import INITIAL_EXPERIMENTAL_PROFILE_ID
from .capacity_evidence import NativeCapacityResponse
from .device_model_profile import VNW_V15_PROFILE_ID
from .experimental_library_transfer_review import (
    ExperimentalLibraryTransferReview,
    build_experimental_library_transfer_review,
)
from .execution_claim_store import PersistentExecutionClaimStore
from .indeterminate_write_lock import PersistentIndeterminateWriteLock
from .library_transfer_readiness import (
    LibraryTransferReadiness,
    LibraryTransferReadinessError,
    build_library_transfer_readiness,
    validate_library_transfer_readiness,
)
from .library_transfer_plan import (
    LibraryTransferPlanError,
    SELECTION_SELECTED,
    build_library_transfer_queue_plan,
)
from .prepared_library_package_operation_bundle import (
    PreparedLibraryPackageOperationBundle,
)
from .prepared_multi_package_gate import (
    PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_EXPLICIT,
)
from .write_gate import DEFAULT_MAX_AGE_SECONDS


FRESH_VALIDATION_TARGET = "IC_P18_LIBRARY_20260910_01"
HISTORICAL_P18_015_TARGET = "IC_P18_LIBRARY_20260907_01"
FRESH_CONFIRMATION = f"ADD {FRESH_VALIDATION_TARGET} ONCE"
FRESH_OPERATION_ID = "vnw-v15-library-ui-validation-20260910-01"
FRESH_AUXILIARY_STATE_POLICY = (
    "verified_display_history_0x001b_and_bookmark_0x001f_semantic_rebase_plus_zero_count_0x001c_to_0x001e"
)
FRESH_CHILD_KINDS = ("txt", "bmp", "txt")
HISTORICAL_P18_015_OWNER_APPROVAL = (
    "APPROVE P18-015 V15 PHYSICAL VALIDATION 01"
)
HISTORICAL_P18_015_CONFIRMATION = (
    f"ADD {HISTORICAL_P18_015_TARGET} ONCE"
)


class LibraryTransferExecutionError(RuntimeError):
    """Raised when the product execution state cannot proceed safely."""

    def __init__(
        self,
        message: str,
        *,
        stage: str = "execution",
        state: str = "failed",
        audit: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.state = state
        self.audit = dict(audit or {})
        self.automatic_retry_allowed = False


def _require_phrase(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or "\x00" in value
        or "\n" in value
        or "\r" in value
    ):
        raise ValueError(f"{label} is invalid")
    return value


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


@dataclass(frozen=True)
class LibraryTransferOperationBinding:
    """Immutable fresh operation identity accepted by the live coordinator.

    The owner approval is deliberately optional at construction time so a
    normal product instance can render the workflow without carrying an
    authorization.  A sender-capable instance must call ``require_authorized``
    after a separately authorized operation supplies that approval.
    """

    target_folder_name: str = FRESH_VALIDATION_TARGET
    owner_approval_phrase: Optional[str] = None
    confirmation_phrase: str = FRESH_CONFIRMATION
    operation_id: str = FRESH_OPERATION_ID
    profile_id: str = INITIAL_EXPERIMENTAL_PROFILE_ID
    device_model_profile_id: str = VNW_V15_PROFILE_ID
    device_identity: tuple[str, str] = ("0x054c", "0x001e")
    child_kinds: tuple[str, str, str] = FRESH_CHILD_KINDS
    confirmation_policy: str = PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_EXPLICIT
    fixed_state_policy: str = FRESH_AUXILIARY_STATE_POLICY
    maximum_logical_transactions: int = 1
    maximum_sender_calls: int = 1
    automatic_retry_allowed: bool = False

    def __post_init__(self) -> None:
        if self.target_folder_name != FRESH_VALIDATION_TARGET:
            raise ValueError(
                "the guarded UI validation is fixed to IC_P18_LIBRARY_20260910_01"
            )
        if self.target_folder_name == HISTORICAL_P18_015_TARGET:
            raise ValueError("the consumed P18-015 target cannot be reused")
        if self.profile_id != INITIAL_EXPERIMENTAL_PROFILE_ID:
            raise ValueError("only the reviewed Experimental Library profile is supported")
        if self.device_model_profile_id != VNW_V15_PROFILE_ID:
            raise ValueError("only the reviewed VNW-V15 model profile is supported")
        if self.device_identity != ("0x054c", "0x001e"):
            raise ValueError("only the reviewed Sony VNW-V15 identity is supported")
        if self.operation_id != FRESH_OPERATION_ID:
            raise ValueError("the guarded UI validation requires its fresh operation identity")
        if tuple(self.child_kinds) != FRESH_CHILD_KINDS:
            raise ValueError("the guarded UI validation requires TXT/BMP/TXT")
        if self.confirmation_policy != PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_EXPLICIT:
            raise ValueError("the guarded UI validation requires explicit confirmation")
        if self.confirmation_phrase != FRESH_CONFIRMATION:
            raise ValueError("confirmation must bind the fresh validation target")
        if self.fixed_state_policy != FRESH_AUXILIARY_STATE_POLICY:
            raise ValueError("the reviewed auxiliary-state policy is required")
        if self.maximum_logical_transactions != 1 or self.maximum_sender_calls != 1:
            raise ValueError("the guarded UI validation is one-shot")
        if self.automatic_retry_allowed is not False:
            raise ValueError("automatic retry is forbidden")
        _require_phrase(self.confirmation_phrase, "confirmation phrase")
        _require_phrase(self.operation_id, "operation id")
        if self.owner_approval_phrase is not None:
            _require_phrase(self.owner_approval_phrase, "owner approval phrase")
            if self.owner_approval_phrase == HISTORICAL_P18_015_OWNER_APPROVAL:
                raise ValueError("the consumed P18-015 owner approval cannot be reused")
        if self.confirmation_phrase == HISTORICAL_P18_015_CONFIRMATION:
            raise ValueError("the consumed P18-015 confirmation cannot be reused")

    @property
    def authorized(self) -> bool:
        return self.owner_approval_phrase is not None

    def require_authorized(self) -> None:
        if not self.authorized:
            raise LibraryTransferExecutionError(
                "a fresh separately authorized operation identity is required"
            )

    def to_dict(self, *, include_authorization: bool = False) -> dict[str, Any]:
        value: dict[str, Any] = {
            "operation_id": self.operation_id,
            "profile_id": self.profile_id,
            "device_model_profile_id": self.device_model_profile_id,
            "device_identity": list(self.device_identity),
            "target_folder_name": self.target_folder_name,
            "child_kinds": list(self.child_kinds),
            "confirmation_policy": self.confirmation_policy,
            "fixed_state_policy": self.fixed_state_policy,
            "maximum_logical_transactions": self.maximum_logical_transactions,
            "maximum_sender_calls": self.maximum_sender_calls,
            "automatic_retry_allowed": self.automatic_retry_allowed,
            "historical_p18_015_identity_reused": False,
        }
        if include_authorization:
            value["owner_approval_phrase"] = self.owner_approval_phrase
            value["confirmation_phrase"] = self.confirmation_phrase
        return value


@dataclass(frozen=True)
class LibraryTransferExecutionRuntime:
    """Injected read-only/live boundaries used by the canonical runner.

    Tests supply deterministic fakes.  A future hardware task may supply the
    existing session-backed callbacks after separate owner authorization; this
    type does not open a device and does not implement protocol semantics.
    """

    template: Any
    template_path: Path
    evidence_namespace: Path
    detect_device: Callable[[], tuple[int, int]]
    query_capacity: Callable[[], Any]
    capture: Callable[..., None]
    backend: Any = None
    execution_claim_store: Optional[PersistentExecutionClaimStore] = None
    indeterminate_write_lock: Optional[PersistentIndeterminateWriteLock] = None
    new_record_timestamp_be32: int = 0
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS


@dataclass(frozen=True)
class PreparedLibraryTransferOperation:
    """The reviewed immutable operation handed from the UI to execution."""

    readiness: LibraryTransferReadiness
    review: ExperimentalLibraryTransferReview
    preflight: Any
    operation_bundle: PreparedLibraryPackageOperationBundle
    plan_report: Mapping[str, Any]
    preflight_report_path: Path
    bundle_path: Path
    plan_sha256: str

    @property
    def ready(self) -> bool:
        return self.review.ready_for_hardware_test


def _write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    path = Path(path).expanduser().resolve()
    if path.exists():
        raise LibraryTransferExecutionError(
            f"refusing to overwrite reviewed operation artifact: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class LibraryTransferExecutionFacade:
    """Single product service used by ttk and deterministic host tests."""

    def __init__(
        self,
        *,
        operation_binding: Optional[LibraryTransferOperationBinding] = None,
        runtime: Optional[LibraryTransferExecutionRuntime] = None,
    ) -> None:
        if operation_binding is not None and not isinstance(
            operation_binding, LibraryTransferOperationBinding
        ):
            raise LibraryTransferExecutionError("operation binding is malformed")
        if runtime is not None and not isinstance(runtime, LibraryTransferExecutionRuntime):
            raise LibraryTransferExecutionError("execution runtime is malformed")
        self.operation_binding = operation_binding
        self.runtime = runtime
        self._prepared_operation: Optional[PreparedLibraryTransferOperation] = None

    @property
    def can_prepare_live(self) -> bool:
        return self.operation_binding is not None and self.runtime is not None

    @property
    def transfer_actionable(self) -> bool:
        return bool(
            self._prepared_operation is not None
            and self._prepared_operation.ready
            and self.operation_binding is not None
            and self.operation_binding.authorized
            and self.runtime is not None
        )

    @property
    def prepared_operation(self) -> Optional[PreparedLibraryTransferOperation]:
        return self._prepared_operation

    def review_readiness(
        self, plan_report: Mapping[str, Any]
    ) -> LibraryTransferReadiness:
        try:
            return build_library_transfer_readiness(plan_report)
        except LibraryTransferReadinessError:
            raise

    def _require_target(self, readiness: LibraryTransferReadiness) -> None:
        binding = self.operation_binding
        if binding is None:
            raise LibraryTransferExecutionError(
                "no separately authorized fresh operation is configured"
            )
        package = readiness.report.get("package", {})
        folder_path = package.get("folder_path") if isinstance(package, Mapping) else None
        expected_path = f"root\\{binding.target_folder_name}"
        if folder_path != expected_path:
            raise LibraryTransferExecutionError(
                "the selected package is not bound to the fresh validation target"
            )
        destination = readiness.report.get("destination", {})
        if isinstance(destination, Mapping) and destination.get("conflicts"):
            raise LibraryTransferExecutionError(
                "the fresh validation target already exists; no replacement target is selected"
            )
        if not readiness.host_profile_eligible:
            raise LibraryTransferExecutionError(
                "the selected package is outside the exact VNW-V15 host profile"
            )

    def refresh_live_preflight(
        self,
        plan_report: Mapping[str, Any],
        *,
        catalog: Any,
        preflight_report_path: Path,
        bundle_path: Path,
        audit_location: Optional[str] = None,
        cancelled: Optional[Callable[[], bool]] = None,
        progress: Optional[Callable[[str, int, int], None]] = None,
    ) -> PreparedLibraryTransferOperation:
        """Obtain fresh read-only evidence and seal one future operation.

        This method performs no send, claim consumption, marker creation, or
        lock mutation.  The injected runtime is responsible only for the
        existing read-only detection/capacity/backup boundaries.
        """

        binding = self.operation_binding
        runtime = self.runtime
        if binding is None or runtime is None:
            raise LibraryTransferExecutionError(
                "live preflight is unavailable until a fresh authorized operation and runtime are supplied"
            )
        binding.require_authorized()
        readiness = self.review_readiness(plan_report)
        self._require_target(readiness)

        from .backup_format import parse_backup_blob
        from .prepared_library_package_live_adapter import (
            prepare_prepared_library_package_live_preflight,
        )

        try:
            template_path = Path(runtime.template_path).expanduser().resolve()
            template = runtime.template
            if template is None:
                template = parse_backup_blob(template_path.read_bytes())
            operation_root = Path(preflight_report_path).expanduser().resolve().parent
            operation_root.mkdir(parents=True, exist_ok=True)
            preflight = prepare_prepared_library_package_live_preflight(
                catalog=catalog,
                selected_item_id=self._selected_item_id(plan_report),
                backup_destination=operation_root / "backup-before-preflight",
                template=template,
                new_record_timestamp_be32=runtime.new_record_timestamp_be32,
                expected_folder_name=binding.target_folder_name,
                operation_binding=binding,
                detect_device=runtime.detect_device,
                query_capacity=runtime.query_capacity,
                capture=runtime.capture,
                preview_callback=lambda _audit: None,
                cancelled=cancelled,
                progress=progress,
                max_age_seconds=runtime.max_age_seconds,
            )
            fresh_plan_report = self._build_fresh_plan(
                plan_report,
                catalog=catalog,
                preflight=preflight,
            )
            fresh_readiness = self.review_readiness(fresh_plan_report)
            self._require_target(fresh_readiness)
            candidate_policy = preflight.candidate.core.audit_dict().get("policy", {})
            if (
                not isinstance(candidate_policy, Mapping)
                or candidate_policy.get("fixed_state")
                != binding.fixed_state_policy
            ):
                raise LibraryTransferExecutionError(
                    "fresh evidence does not provide the reviewed auxiliary-state policy"
                )
            _write_new_json(Path(preflight_report_path), preflight.to_dict())
            capacity_path = self._capacity_artifact_path(
                preflight.capacity_response,
                operation_root,
            )
            operation_bundle = PreparedLibraryPackageOperationBundle.from_sealed_report(
                Path(preflight_report_path),
                template_path=template_path,
                capacity_response_path=capacity_path,
                operation_id=binding.operation_id,
            )
            bundle_written = operation_bundle.write(Path(bundle_path))
            review = build_experimental_library_transfer_review(
                fresh_plan_report,
                preflight_report=preflight.to_dict(),
                bundle_report=operation_bundle.to_dict(),
                audit_location=audit_location or str(runtime.evidence_namespace),
                operation_binding=binding,
            )
            if not review.ready_for_hardware_test:
                raise LibraryTransferExecutionError(
                    "fresh operation review is not ready for hardware test"
                )
        except LibraryTransferExecutionError:
            raise
        except Exception as exc:
            raise LibraryTransferExecutionError(
                f"fresh live preflight could not be sealed: {exc}"
            ) from exc
        prepared = PreparedLibraryTransferOperation(
            readiness=fresh_readiness,
            review=review,
            preflight=preflight,
            operation_bundle=operation_bundle,
            plan_report=fresh_plan_report,
            preflight_report_path=Path(preflight_report_path).expanduser().resolve(),
            bundle_path=Path(bundle_written).expanduser().resolve(),
            plan_sha256=_sha256_json(fresh_plan_report),
        )
        self._prepared_operation = prepared
        return prepared

    def _selected_item_id(self, plan_report: Mapping[str, Any]) -> str:
        selection = plan_report.get("selection")
        values = selection.get("selected_item_ids") if isinstance(selection, Mapping) else None
        if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], str):
            raise LibraryTransferExecutionError("exactly one selected Library package is required")
        return values[0]

    def _capacity_artifact_path(self, response: Any, root: Path) -> Path:
        capacity_path = root / "capacity-response.bin"
        if capacity_path.exists():
            return capacity_path
        raw = getattr(response, "raw_response", None)
        if not isinstance(raw, bytes):
            raise LibraryTransferExecutionError(
                "fresh capacity callback did not expose parsed native response bytes"
            )
        capacity_path.write_bytes(raw)
        return capacity_path

    def _build_fresh_plan(
        self,
        plan_report: Mapping[str, Any],
        *,
        catalog: Any,
        preflight: Any,
    ) -> dict[str, Any]:
        """Rebuild the canonical queue plan from this fresh preflight."""

        capacity_response = preflight.capacity_response
        if not isinstance(capacity_response, NativeCapacityResponse):
            raise LibraryTransferExecutionError(
                "fresh preflight capacity evidence is malformed"
            )
        try:
            fresh_plan = build_library_transfer_queue_plan(
                catalog,
                selected_item_ids=[self._selected_item_id(plan_report)],
                selection_mode=SELECTION_SELECTED,
                backup=preflight.before_backup,
                capacity_evidence=capacity_response,
            )
        except LibraryTransferPlanError as exc:
            raise LibraryTransferExecutionError(
                f"fresh capacity could not be propagated into the Library review: {exc}"
            ) from exc
        return fresh_plan.to_dict()

    def execute_once(
        self,
        plan_report: Mapping[str, Any],
        *,
        confirmation_interaction: Callable[[Mapping[str, Any]], str],
        low_level_bulk_write_calls: Optional[int] = None,
        **runner_overrides: Any,
    ) -> Any:
        """Enter the existing guarded coordinator once; never retry."""

        binding = self.operation_binding
        runtime = self.runtime
        prepared = self._prepared_operation
        if binding is None or runtime is None or prepared is None:
            raise LibraryTransferExecutionError(
                "Transfer once is blocked until the reviewed fresh operation is ready"
            )
        try:
            binding.require_authorized()
        except LibraryTransferExecutionError:
            self._prepared_operation = None
            raise
        if not prepared.ready or not self.transfer_actionable:
            self._prepared_operation = None
            raise LibraryTransferExecutionError(
                "Transfer once is blocked by incomplete or stale reviewed state"
            )
        if _sha256_json(plan_report) != prepared.plan_sha256:
            self._prepared_operation = None
            raise LibraryTransferExecutionError(
                "the Library plan changed after review; obtain a new fresh preflight"
            )
        try:
            validate_library_transfer_readiness(prepared.readiness.report)
        except LibraryTransferReadinessError as exc:
            self._prepared_operation = None
            raise LibraryTransferExecutionError(
                f"readiness review integrity failed: {exc}"
            ) from exc
        if runner_overrides.get("retry") or runner_overrides.get("automatic_retry"):
            self._prepared_operation = None
            raise LibraryTransferExecutionError("automatic retry is not supported")
        if runtime.execution_claim_store is None or runtime.indeterminate_write_lock is None:
            self._prepared_operation = None
            raise LibraryTransferExecutionError(
                "persistent claim store and indeterminate-write lock are required"
            )

        from .experimental_library_transfer import GuardedLibraryExecutionCoordinator

        coordinator = GuardedLibraryExecutionCoordinator(
            indeterminate_write_lock=runtime.indeterminate_write_lock,
            execution_claim_store=runtime.execution_claim_store,
            operation_binding=binding,
        )
        runner_kwargs = {
            "detect_device": runtime.detect_device,
            "query_capacity": runtime.query_capacity,
            "backend": runtime.backend,
            "capture": runtime.capture,
            "evidence_namespace": runtime.evidence_namespace,
            "now": runner_overrides.pop("now", None),
            "max_age_seconds": runtime.max_age_seconds,
        }
        runner_kwargs.update(runner_overrides)
        try:
            result = coordinator.execute(
                prepared.operation_bundle,
                plan_report=plan_report,
                confirmation_interaction=confirmation_interaction,
                low_level_bulk_write_calls=low_level_bulk_write_calls,
                **runner_kwargs,
            )
            self._prepared_operation = None
            return result
        except LibraryTransferExecutionError:
            self._prepared_operation = None
            raise
        except Exception as exc:
            self._prepared_operation = None
            raise LibraryTransferExecutionError(
                str(exc),
                stage=str(getattr(exc, "stage", "execution")),
                state=str(getattr(exc, "state", "failed")),
                audit=(
                    getattr(exc, "audit")
                    if isinstance(getattr(exc, "audit", None), Mapping)
                    else None
                ),
            ) from exc


__all__ = [
    "FRESH_AUXILIARY_STATE_POLICY",
    "FRESH_CONFIRMATION",
    "FRESH_OPERATION_ID",
    "FRESH_VALIDATION_TARGET",
    "LibraryTransferExecutionError",
    "LibraryTransferExecutionFacade",
    "LibraryTransferExecutionRuntime",
    "LibraryTransferOperationBinding",
    "PreparedLibraryTransferOperation",
]
