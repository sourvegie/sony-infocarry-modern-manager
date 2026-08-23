"""Fake-transport-only guarded workflow for one prepared text package."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from .capacity_evidence import NativeCapacityResponse
from .prepared_package_candidate import (
    PreparedPackageCandidate,
    PreparedPackageCandidateError,
    build_prepared_package_candidate,
)
from .prepared_package_gate import (
    PREPARED_PACKAGE_CONFIRMATION_PHRASE,
    PreparedPackageAuthorization,
    PreparedPackageGateError,
    bind_prepared_package_sender,
    authorize_prepared_package,
)
from .prepared_package_verify import (
    PreparedPackageReadbackVerification,
    PreparedPackageVerificationError,
    verify_prepared_package_readback,
)
from .protocol import TransferCancelledError
from .write_gate import DEFAULT_MAX_AGE_SECONDS, VerifiedBackup, capture_and_verify_fresh_backup
from .write_protocol import WriteFailureAssessment, assess_write_failure


ProgressCallback = Callable[[str, int, int], None]
CancelledCallback = Callable[[], bool]
CaptureCallback = Callable[..., None]
SendCallback = Callable[..., int]
DetectDeviceCallback = Callable[[], tuple[int, int]]
CapacityQueryCallback = Callable[[], NativeCapacityResponse]


class PreparedPackageWorkflowError(RuntimeError):
    """Terminal guarded-workflow error with a durable audit."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        state: str,
        write_started: bool = False,
        audit: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.state = state
        self.write_started = write_started
        self.audit = dict(audit or {})
        self.audit.setdefault("automatic_retry_allowed", False)


@dataclass(frozen=True)
class PreparedPackageOfflinePreview:
    """Displayed candidate snapshot; it contains no USB action."""

    candidate: PreparedPackageCandidate

    def to_dict(self) -> dict[str, Any]:
        report = self.candidate.audit_dict()
        report["preview"] = {
            "state": "previewed",
            "device_change": "none",
            "candidate_bytes_included": False,
            "notice": "OFFLINE PREVIEW ONLY — no device change has occurred",
        }
        return report


@dataclass(frozen=True)
class PreparedPackageWorkflowResult:
    """Durable result for one fake transfer and independent read-back."""

    state: str
    preview: PreparedPackageOfflinePreview
    authorization: PreparedPackageAuthorization
    before_backup: VerifiedBackup
    after_backup: VerifiedBackup
    completion: int
    verification: PreparedPackageReadbackVerification
    audit: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.audit)


def _notify(
    progress: Optional[ProgressCallback], label: str, completed: int, total: int
) -> None:
    if progress is not None:
        progress(label, completed, total)


def _check_cancelled(cancelled: Optional[CancelledCallback]) -> None:
    if cancelled is not None and cancelled():
        raise TransferCancelledError("prepared package workflow cancelled before device change")


def _cancelled_error(exc: BaseException, stage: str) -> PreparedPackageWorkflowError:
    return PreparedPackageWorkflowError(
        str(exc),
        stage=stage,
        state="cancelled_before_transaction",
        audit={
            "state": "cancelled_before_transaction",
            "stage": stage,
            "device_change": "none_started",
            "automatic_retry_allowed": False,
        },
    )


class GuardedPreparedPackageWorkflow:
    """Run one constrained package workflow using injected fake callbacks."""

    def __init__(
        self,
        capture: CaptureCallback,
        send: SendCallback,
        template: Any,
        *,
        detect_device: Optional[DetectDeviceCallback] = None,
        query_capacity: Optional[CapacityQueryCallback] = None,
    ) -> None:
        if not callable(capture) or not callable(send):
            raise TypeError("capture and send callbacks are required")
        if detect_device is not None and not callable(detect_device):
            raise TypeError("detect_device must be callable when supplied")
        if query_capacity is not None and not callable(query_capacity):
            raise TypeError("query_capacity must be callable when supplied")
        self._capture = capture
        self._send = send
        self._template = template
        self._detect_device = detect_device
        self._query_capacity = query_capacity

    def run(
        self,
        *,
        backup_destination: Path,
        post_operation_destination: Path,
        package: Any,
        preview: Optional[PreparedPackageOfflinePreview | PreparedPackageCandidate],
        new_record_timestamp_be32: int,
        available_capacity_bytes: Optional[int] = None,
        capacity_limit_bytes: Optional[int] = None,
        confirmation: str,
        fake_transport: bool = False,
        cancelled: Optional[CancelledCallback] = None,
        progress: Optional[ProgressCallback] = None,
        now: Optional[datetime] = None,
        max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
        require_native_capacity_evidence: bool = False,
    ) -> PreparedPackageWorkflowResult:
        """Capture → rebuild → bind → send once → independently verify.

        ``fake_transport`` is required to be exactly ``True``.  This module
        contains no live USB implementation and must not be connected to one.
        """

        if fake_transport is not True:
            raise PreparedPackageWorkflowError(
                "prepared package workflow requires an explicit fake transport",
                stage="transport",
                state="failed",
            )
        operation_sequence = ["fake_transport_asserted"]
        native_capacity_response: Optional[NativeCapacityResponse] = None
        if require_native_capacity_evidence:
            if self._detect_device is None or self._query_capacity is None:
                raise PreparedPackageWorkflowError(
                    "live-eligible package workflow requires injected detection and parsed 0x0019 query",
                    stage="capacity_query",
                    state="failed",
                    audit={
                        "state": "failed",
                        "stage": "capacity_query",
                        "device_change": "none_started",
                        "automatic_retry_allowed": False,
                    },
                )
            try:
                _check_cancelled(cancelled)
                detected_identity = self._detect_device()
                operation_sequence.append("device_detected")
                native_capacity_response = self._query_capacity()
                if not isinstance(native_capacity_response, NativeCapacityResponse):
                    raise ValueError("capacity callback did not return parsed 0x0019 evidence")
                if native_capacity_response.device_identity != detected_identity:
                    raise ValueError("capacity response device identity differs from fresh detection")
                operation_sequence.append("capacity_queried_0x0019")
            except Exception as exc:
                raise PreparedPackageWorkflowError(
                    f"native capacity query failed; no device transaction started: {exc}",
                    stage="capacity_query",
                    state="failed",
                    audit={
                        "state": "failed",
                        "stage": "capacity_query",
                        "device_change": "none_started",
                        "automatic_retry_allowed": False,
                        "operation_sequence": operation_sequence,
                    },
                ) from exc
        elif capacity_limit_bytes is not None:
            raise PreparedPackageWorkflowError(
                "capacity_limit_bytes is reserved for native capacity evidence",
                stage="capacity_query",
                state="failed",
                audit={
                    "state": "failed",
                    "stage": "capacity_query",
                    "device_change": "none_started",
                    "automatic_retry_allowed": False,
                },
            )
        displayed = preview.candidate if isinstance(preview, PreparedPackageOfflinePreview) else preview
        if not isinstance(displayed, PreparedPackageCandidate):
            raise PreparedPackageWorkflowError(
                "prepared package workflow requires a displayed offline candidate",
                stage="preview",
                state="failed",
            )
        try:
            _check_cancelled(cancelled)
        except TransferCancelledError as exc:
            raise _cancelled_error(exc, "preparation") from exc
        _notify(progress, "Preparing offline package operation", 0, 1)

        try:
            before = capture_and_verify_fresh_backup(
                Path(backup_destination),
                lambda destination: self._capture(
                    destination, cancelled=cancelled, progress=progress
                ),
                now=now,
                max_age_seconds=max_age_seconds,
            )
            operation_sequence.append("fresh_complete_backup")
            if native_capacity_response is not None and native_capacity_response.device_identity != tuple(int(value, 16) for value in before.device_identity):
                raise ValueError("fresh backup device identity differs from parsed 0x0019 evidence")
        except Exception as exc:
            if isinstance(exc, TransferCancelledError) or isinstance(exc.__cause__, TransferCancelledError):
                cancellation = exc if isinstance(exc, TransferCancelledError) else exc.__cause__
                raise _cancelled_error(cancellation, "fresh_backup") from exc
            raise PreparedPackageWorkflowError(
                f"fresh package backup failed; no device transaction started: {exc}",
                stage="fresh_backup",
                state="failed",
                audit={
                    "state": "failed",
                    "stage": "fresh_backup",
                    "device_change": "none_started",
                    "automatic_retry_allowed": False,
                    "operation_sequence": operation_sequence,
                },
            ) from exc

        try:
            _check_cancelled(cancelled)
        except TransferCancelledError as exc:
            raise _cancelled_error(exc, "candidate") from exc
        try:
            current = build_prepared_package_candidate(
                package,
                before,
                self._template,
                new_record_timestamp_be32=new_record_timestamp_be32,
                available_capacity_bytes=(
                    None if native_capacity_response is not None else available_capacity_bytes
                ),
                capacity_limit_bytes=(
                    None if native_capacity_response is not None else capacity_limit_bytes
                ),
                native_capacity_response=native_capacity_response,
            )
            operation_sequence.append("candidate_reconstructed")
        except Exception as exc:
            raise PreparedPackageWorkflowError(
                f"fresh package candidate failed: {exc}",
                stage="candidate",
                state="failed",
                audit={
                    "state": "failed",
                    "stage": "candidate",
                    "device_change": "none_started",
                    "automatic_retry_allowed": False,
                },
            ) from exc

        if current.audit_dict() != displayed.audit_dict():
            raise PreparedPackageWorkflowError(
                "fresh package candidate no longer matches the displayed preview",
                stage="preview_revalidation",
                state="failed",
                audit={
                    "state": "failed",
                    "stage": "preview_revalidation",
                    "device_change": "none_started",
                    "automatic_retry_allowed": False,
                    "preview": displayed.audit_dict(),
                    "fresh_candidate": current.audit_dict(),
                    "operation_sequence": operation_sequence,
                },
            )

        try:
            _check_cancelled(cancelled)
        except TransferCancelledError as exc:
            raise _cancelled_error(exc, "authorization") from exc
        try:
            authorization = authorize_prepared_package(
                current,
                confirmation=confirmation,
                require_native_capacity_evidence=require_native_capacity_evidence,
            )
            sender_authorization = bind_prepared_package_sender(
                authorization,
                current,
                now=now,
                max_age_seconds=max_age_seconds,
            )
        except Exception as exc:
            raise PreparedPackageWorkflowError(
                f"prepared package authorization failed: {exc}",
                stage="authorization",
                state="failed",
                audit={
                    "state": "failed",
                    "stage": "authorization",
                    "device_change": "none_started",
                    "automatic_retry_allowed": False,
                    "preview": current.audit_dict(),
                    "operation_sequence": operation_sequence,
                },
            ) from exc

        _notify(
            progress,
            "Package authorization accepted; sending once through fake transport",
            0,
            current.transaction.payload_length,
        )
        operation_sequence.append("authorization")
        try:
            completion = self._send(
                current.transaction,
                sender_authorization,
                cancelled=cancelled,
                progress=progress,
            )
        except Exception as exc:
            assessment: WriteFailureAssessment = assess_write_failure(exc)
            # An unannotated injected sender failure is conservatively treated
            # as post-start indeterminate because the workflow cannot know
            # whether its own 0x101b boundary was crossed.
            annotated = getattr(exc, "write_failure_assessment", None)
            if not isinstance(annotated, WriteFailureAssessment):
                assessment = WriteFailureAssessment(
                    primary_error=str(exc),
                    write_started=True,
                    device_outcome="indeterminate",
                )
            state = (
                "indeterminate_after_transaction_start"
                if assessment.device_outcome == "indeterminate"
                else "failed"
            )
            raise PreparedPackageWorkflowError(
                f"prepared package fake transfer stopped; no automatic retry: {exc}",
                stage="write",
                state=state,
                write_started=assessment.write_started,
                audit={
                    "state": state,
                    "stage": "write",
                    "device_change": assessment.device_outcome,
                    "write_started": assessment.write_started,
                    "automatic_retry_allowed": False,
                    "read_only_assessment_allowed": assessment.read_only_assessment_allowed,
                    "primary_error": assessment.primary_error,
                    "preview": current.audit_dict(),
                    "authorization": authorization.to_dict(),
                    "operation_sequence": operation_sequence,
                },
            ) from exc

        operation_sequence.append("single_0x101b_transaction")
        if isinstance(completion, bool) or not isinstance(completion, int) or completion != 0:
            value = repr(completion) if not isinstance(completion, int) else f"0x{completion:04x}"
            raise PreparedPackageWorkflowError(
                f"prepared package fake transfer returned unacceptable completion {value}; no automatic retry",
                stage="write_completion",
                state="failed",
                write_started=True,
                audit={
                    "state": "failed",
                    "stage": "write_completion",
                    "device_change": "completed_with_error",
                    "write_started": True,
                    "automatic_retry_allowed": False,
                    "completion": value,
                    "preview": current.audit_dict(),
                    "authorization": authorization.to_dict(),
                    "operation_sequence": operation_sequence,
                },
            )

        try:
            after = capture_and_verify_fresh_backup(
                Path(post_operation_destination),
                lambda destination: self._capture(
                    destination, cancelled=cancelled, progress=progress
                ),
                now=now,
                max_age_seconds=max_age_seconds,
            )
            operation_sequence.append("fresh_post_operation_backup")
            verification = verify_prepared_package_readback(
                authorization,
                current,
                after.directory,
                completion=completion,
                now=now,
                max_age_seconds=max_age_seconds,
            )
        except Exception as exc:
            raise PreparedPackageWorkflowError(
                f"prepared package post-operation read-back is terminal; no automatic retry: {exc}",
                stage="post_operation_readback",
                state="indeterminate_after_transaction_start",
                write_started=True,
                audit={
                    "state": "indeterminate_after_transaction_start",
                    "stage": "post_operation_readback",
                    "device_change": "completed_or_unknown",
                    "write_started": True,
                    "automatic_retry_allowed": False,
                    "primary_error": str(exc),
                    "completion": "0x0000",
                    "preview": current.audit_dict(),
                    "authorization": authorization.to_dict(),
                    "operation_sequence": operation_sequence,
                },
            ) from exc

        audit = current.audit_dict()
        audit.update(
            {
                "state": "readback_verified",
                "workflow": {
                    "states": [
                        "previewed",
                        "authorized",
                        "simulated_transfer_completed",
                        "readback_verified",
                    ],
                    "fake_transport": True,
                    "device_change": "simulated_only",
                    "automatic_retry_allowed": False,
                    "operation_sequence": operation_sequence + ["independent_readback_verification"],
                },
                "authorization": authorization.to_dict(),
                "completion": "0x0000",
                "verification": verification.to_dict(),
            }
        )
        _notify(progress, "Prepared package fake read-back verified", 1, 1)
        return PreparedPackageWorkflowResult(
            state="readback_verified",
            preview=PreparedPackageOfflinePreview(current),
            authorization=authorization,
            before_backup=before,
            after_backup=after,
            completion=completion,
            verification=verification,
            audit=audit,
        )


__all__ = [
    "GuardedPreparedPackageWorkflow",
    "PreparedPackageOfflinePreview",
    "PreparedPackageWorkflowError",
    "PreparedPackageWorkflowResult",
]
