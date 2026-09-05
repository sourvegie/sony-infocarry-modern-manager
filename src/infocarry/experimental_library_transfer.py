"""Isolated guarded Experimental Library transfer entrypoint.

This is the only product-facing integration shim for the exact P17 Library
profile. The coordinator binds the offline Select/Arrange/Prepare/Preview
review, transaction-specific confirmation, model profile, and persistent
indeterminate-write lock to the already reviewed P17 runner and P17-019
reconciler. It is not imported by the normal CLI or ttk GUI import graph.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Optional
from uuid import uuid4

from .capability_profile import INITIAL_EXPERIMENTAL_PROFILE_ID
from .device_model_profile import DeviceModelProfile, VNW_V15_PROFILE
from .experimental_library_transfer_review import (
    ExperimentalLibraryTransferReview,
    ExperimentalLibraryTransferReviewError,
    build_experimental_library_transfer_review,
)
from .execution_claim_store import (
    ExecutionClaimStoreError,
    PersistentExecutionClaimStore,
)
from .indeterminate_write_lock import (
    IndeterminateWriteLockError,
    PersistentIndeterminateWriteLock,
)
from .prepared_library_package_live_adapter import (
    P17_005_OWNER_APPROVAL,
    PreparedLibraryPackageLiveResult,
    PreparedLibraryPackageLiveResultReconciliationError,
    PreparedLibraryPackageLiveWrapperResult,
    execute_prepared_library_package_live,
    reconcile_prepared_library_package_live_result,
)
from .prepared_library_package_operation_bundle import PreparedLibraryPackageOperationBundle


class GuardedLibraryExecutionError(RuntimeError):
    """Terminal guarded-lifecycle failure; it is never automatically retried."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        state: str = "failed",
        audit: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.state = state
        self.automatic_retry_allowed = False
        self.audit = dict(audit or {})
        self.audit.setdefault("automatic_retry_allowed", False)


ConfirmationInteraction = Callable[[Mapping[str, Any]], str]


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _strict_json_object(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    if not isinstance(value, dict):
        raise ValueError("sealed preflight report must be a JSON object")
    return value


def _report_from_bundle(
    operation_bundle: PreparedLibraryPackageOperationBundle,
) -> dict[str, Mapping[str, Any]]:
    try:
        report = _strict_json_object(Path(operation_bundle.sealed_report.path))
        bundle_report = operation_bundle.to_dict()
    except Exception as exc:
        raise GuardedLibraryExecutionError(
            f"could not resolve the sealed review bindings: {exc}",
            stage="review_bindings",
        ) from exc
    return {"preflight": report, "bundle": bundle_report}


def _evidence_root(audit: Mapping[str, Any], fallback: Path) -> str:
    outputs = audit.get("evidence_outputs")
    if isinstance(outputs, Mapping) and isinstance(outputs.get("root"), str):
        return outputs["root"]
    return str(fallback)


class GuardedLibraryExecutionCoordinator:
    """Reusable Select-to-Execute guard around the reviewed P17 runner.

    Candidate bytes, transaction construction, USB I/O, completion handling,
    and read-back remain in the canonical P17 adapter and wrapper. This
    coordinator owns only lifecycle gates and lock recovery policy.
    """

    def __init__(
        self,
        *,
        indeterminate_write_lock: PersistentIndeterminateWriteLock,
        execution_claim_store: PersistentExecutionClaimStore,
        device_model_profile: DeviceModelProfile = VNW_V15_PROFILE,
        capability_profile_id: str = INITIAL_EXPERIMENTAL_PROFILE_ID,
    ) -> None:
        if not isinstance(indeterminate_write_lock, PersistentIndeterminateWriteLock):
            raise GuardedLibraryExecutionError(
                "the guarded Library lifecycle requires a persistent indeterminate-write lock",
                stage="lock_configuration",
            )
        if (
            not isinstance(device_model_profile, DeviceModelProfile)
            or device_model_profile != VNW_V15_PROFILE
            or not device_model_profile.transfer_capable
        ):
            raise GuardedLibraryExecutionError(
                "only the reviewed VNW-V15 transfer-capable model profile is actionable",
                stage="model_profile",
            )
        if capability_profile_id != INITIAL_EXPERIMENTAL_PROFILE_ID:
            raise GuardedLibraryExecutionError(
                "only the exact Experimental flat package capability profile is actionable",
                stage="capability_profile",
            )
        self.indeterminate_write_lock = indeterminate_write_lock
        if not isinstance(execution_claim_store, PersistentExecutionClaimStore):
            raise GuardedLibraryExecutionError(
                "the guarded Library lifecycle requires a persistent execution claim store",
                stage="claim_configuration",
            )
        self.execution_claim_store = execution_claim_store
        self.device_model_profile = device_model_profile
        self.capability_profile_id = capability_profile_id

    def _assert_execution_boundary_available(self) -> None:
        """Fail closed when a prior process died around sender entry."""

        self.indeterminate_write_lock.assert_unlocked(self.device_model_profile.lock_key)
        try:
            marker = self.execution_claim_store.read_sender_in_flight()
            if marker is None:
                return
            lock_record = self.indeterminate_write_lock.read(
                self.device_model_profile.lock_key
            )
            if (
                lock_record is not None
                and not lock_record.locked
                and lock_record.attempt_id == marker.attempt_id
                and lock_record.incident_id == marker.incident_id
            ):
                self.execution_claim_store.resolve_sender_after_diagnostic(
                    marker,
                    lock_record=lock_record,
                )
                return
            self.indeterminate_write_lock.record_indeterminate(
                reason=(
                    "abandoned sender-start marker found after process restart; "
                    "physical outcome is indeterminate"
                ),
                evidence_root=marker.evidence_root,
                model_key=self.device_model_profile.lock_key,
                incident_id=marker.incident_id,
                attempt_id=marker.attempt_id,
            )
            self.execution_claim_store.mark_sender_lock_recorded(marker)
        except (ExecutionClaimStoreError, IndeterminateWriteLockError, OSError, ValueError) as exc:
            raise GuardedLibraryExecutionError(
                f"abandoned sender-start state could not be safely resolved: {exc}",
                stage="indeterminate_lock",
                state="indeterminate_after_transaction_start",
            ) from exc
        raise IndeterminateWriteLockError(
            "InfoCarry writes are globally locked after an abandoned sender-start boundary; "
            "read-only diagnosis is required"
        )

    def _review(
        self,
        plan_report: Mapping[str, Any],
        *,
        bindings: Mapping[str, Mapping[str, Any]],
        audit_location: str,
    ) -> ExperimentalLibraryTransferReview:
        try:
            review = build_experimental_library_transfer_review(
                plan_report,
                preflight_report=bindings["preflight"],
                bundle_report=bindings["bundle"],
                audit_location=audit_location,
            )
        except (ExperimentalLibraryTransferReviewError, TypeError, ValueError) as exc:
            raise GuardedLibraryExecutionError(
                f"Library review could not be validated: {exc}",
                stage="eligibility",
            ) from exc
        if not review.ready_for_hardware_test:
            raise GuardedLibraryExecutionError(
                "Library review is preview-only and cannot enter the guarded execution lifecycle",
                stage="eligibility",
                audit=review.to_dict(),
            )
        return review

    def _record_indeterminate(
        self,
        exc: BaseException,
        *,
        attempt_id: str,
        evidence_root: Path,
    ) -> None:
        audit = getattr(exc, "audit", {})
        if not isinstance(audit, Mapping):
            audit = {}
        claim_audit = audit.get("execution_claim")
        marker_audit = (
            claim_audit.get("sender_marker")
            if isinstance(claim_audit, Mapping)
            else None
        )
        lock_incident_id = (
            marker_audit.get("incident_id")
            if isinstance(marker_audit, Mapping)
            else None
        )
        lock_attempt_id = (
            marker_audit.get("attempt_id")
            if isinstance(marker_audit, Mapping)
            else None
        )
        try:
            record = self.indeterminate_write_lock.record_indeterminate(
                reason=str(exc),
                evidence_root=_evidence_root(audit, evidence_root),
                model_key=self.device_model_profile.lock_key,
                incident_id=lock_incident_id or f"guarded-library-{uuid4().hex}",
                attempt_id=lock_attempt_id or attempt_id,
            )
        except (IndeterminateWriteLockError, OSError, ValueError) as lock_exc:
            raise GuardedLibraryExecutionError(
                f"indeterminate outcome could not be persisted in the global write lock: {lock_exc}",
                stage="indeterminate_lock",
                state="indeterminate_after_transaction_start",
                audit={
                    "original_error": str(exc),
                    "original_audit": dict(audit),
                    "lock_error": str(lock_exc),
                },
            ) from exc
        if hasattr(exc, "audit") and isinstance(getattr(exc, "audit"), dict):
            getattr(exc, "audit")["indeterminate_write_lock"] = record.to_dict()
        try:
            marker = self.execution_claim_store.read_sender_in_flight()
            if marker is not None:
                self.execution_claim_store.mark_sender_lock_recorded(marker)
        except ExecutionClaimStoreError:
            # The global JSON lock is already committed. Retaining the
            # SQLite marker is fail-closed and allows recovery to bind it
            # to the same incident after an interrupted cleanup.
            pass
        setattr(exc, "indeterminate_write_lock_record", record)

    def execute(
        self,
        operation_bundle: PreparedLibraryPackageOperationBundle,
        *,
        plan_report: Optional[Mapping[str, Any]],
        confirmation_interaction: Optional[ConfirmationInteraction],
        low_level_bulk_write_calls: int | None = None,
        **runner_kwargs: Any,
    ) -> PreparedLibraryPackageLiveResult | PreparedLibraryPackageLiveWrapperResult:
        """Run one confirmed operation through the canonical P17 lifecycle."""

        self._assert_execution_boundary_available()
        if not isinstance(operation_bundle, PreparedLibraryPackageOperationBundle):
            raise GuardedLibraryExecutionError(
                "the guarded lifecycle requires one immutable prepared Library operation bundle",
                stage="operation_bundle",
            )
        if runner_kwargs.get("preflight_only", False):
            raise GuardedLibraryExecutionError(
                "the guarded integration does not expose a sender-adjacent preflight mode",
                stage="lifecycle",
            )
        if plan_report is None or not isinstance(plan_report, Mapping):
            raise GuardedLibraryExecutionError(
                "a current offline Library plan is required before confirmation",
                stage="plan",
            )
        if confirmation_interaction is None or not callable(confirmation_interaction):
            raise GuardedLibraryExecutionError(
                "a transaction-specific in-app confirmation interaction is required",
                stage="confirmation",
            )
        if "confirmation" in runner_kwargs or "owner_approval" in runner_kwargs:
            raise GuardedLibraryExecutionError(
                "approval and confirmation are owned by the guarded lifecycle",
                stage="confirmation",
            )
        if "pre_send_revalidator" in runner_kwargs:
            raise GuardedLibraryExecutionError(
                "the guarded lifecycle owns the final pre-send revalidation",
                stage="pre_send_revalidation",
            )
        if any(
            name in runner_kwargs
            for name in ("execution_claim_store", "indeterminate_write_lock", "attempt_id")
        ):
            raise GuardedLibraryExecutionError(
                "execution claim and sender recovery state are owned by the guarded lifecycle",
                stage="claim_configuration",
            )

        attempt_id = uuid4().hex
        bindings = _report_from_bundle(operation_bundle)
        audit_location = str(runner_kwargs.get("evidence_namespace", ""))
        review = self._review(
            plan_report,
            bindings=bindings,
            audit_location=audit_location,
        )
        plan_digest = _sha256_json(plan_report)
        review_digest = _sha256_json(review.to_dict())
        try:
            confirmation = confirmation_interaction(deepcopy(review.to_dict()))
        except Exception as exc:
            raise GuardedLibraryExecutionError(
                f"transaction confirmation interaction failed: {exc}",
                stage="confirmation",
                audit={"review_sha256": review_digest},
            ) from exc
        if type(confirmation) is not str or not confirmation.strip():
            raise GuardedLibraryExecutionError(
                "confirmation interaction did not return a transaction confirmation phrase",
                stage="confirmation",
                audit={"review_sha256": review_digest},
            )
        if _sha256_json(plan_report) != plan_digest:
            raise GuardedLibraryExecutionError(
                "Library plan changed after confirmation; no transaction attempted",
                stage="confirmation_revalidation",
                audit={"review_sha256": review_digest},
            )

        def pre_send_revalidate() -> None:
            self.indeterminate_write_lock.assert_unlocked(self.device_model_profile.lock_key)
            if _sha256_json(plan_report) != plan_digest:
                raise GuardedLibraryExecutionError(
                    "Library plan changed after confirmation; no transaction attempted",
                    stage="pre_send_revalidation",
                )
            current_bindings = _report_from_bundle(operation_bundle)
            current_review = self._review(
                plan_report,
                bindings=current_bindings,
                audit_location=audit_location,
            )
            if _sha256_json(current_review.to_dict()) != review_digest:
                raise GuardedLibraryExecutionError(
                    "sealed Library review bindings changed after confirmation; no transaction attempted",
                    stage="pre_send_revalidation",
                )

        runner_kwargs["owner_approval"] = P17_005_OWNER_APPROVAL
        runner_kwargs["confirmation"] = confirmation
        runner_kwargs["pre_send_revalidator"] = pre_send_revalidate
        runner_kwargs["execution_claim_store"] = self.execution_claim_store
        runner_kwargs["indeterminate_write_lock"] = self.indeterminate_write_lock
        runner_kwargs["attempt_id"] = attempt_id
        try:
            result = execute_prepared_library_package_live(operation_bundle, **runner_kwargs)
            reconciliation_kwargs: dict[str, Any] = {
                "low_level_bulk_write_calls": low_level_bulk_write_calls,
            }
            for name in ("now", "max_age_seconds"):
                if name in runner_kwargs:
                    reconciliation_kwargs[name] = runner_kwargs[name]
            reconciled = reconcile_prepared_library_package_live_result(
                result,
                **reconciliation_kwargs,
            )
        except Exception as exc:
            if getattr(exc, "state", None) == "indeterminate_after_transaction_start":
                self._record_indeterminate(
                    exc,
                    attempt_id=attempt_id,
                    evidence_root=Path(audit_location or "."),
                )
            elif isinstance(exc, PreparedLibraryPackageLiveResultReconciliationError):
                self._record_indeterminate(
                    exc,
                    attempt_id=attempt_id,
                    evidence_root=Path(audit_location or "."),
                )
            raise
        return reconciled


def run_experimental_library_transfer(
    operation_bundle: PreparedLibraryPackageOperationBundle,
    *,
    indeterminate_write_lock: PersistentIndeterminateWriteLock,
    execution_claim_store: PersistentExecutionClaimStore,
    plan_report: Optional[Mapping[str, Any]],
    confirmation_interaction: Optional[ConfirmationInteraction],
    low_level_bulk_write_calls: int | None = None,
    **runner_kwargs: Any,
) -> PreparedLibraryPackageLiveResult | PreparedLibraryPackageLiveWrapperResult:
    """Run one exact, confirmed operation from one immutable bundle."""

    return GuardedLibraryExecutionCoordinator(
        indeterminate_write_lock=indeterminate_write_lock,
        execution_claim_store=execution_claim_store,
    ).execute(
        operation_bundle,
        plan_report=plan_report,
        confirmation_interaction=confirmation_interaction,
        low_level_bulk_write_calls=low_level_bulk_write_calls,
        **runner_kwargs,
    )


__all__ = [
    "ConfirmationInteraction",
    "GuardedLibraryExecutionCoordinator",
    "GuardedLibraryExecutionError",
    "run_experimental_library_transfer",
]
