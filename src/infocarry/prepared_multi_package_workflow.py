"""Fake-transport-only workflow for an ordered multi-child package.

This module intentionally has no live USB adapter and is not imported by the
normal CLI or ttk application.  The transport capability is explicit so an
ordinary callback cannot accidentally be passed where a device-changing
operation might later be added.  That is an integration guard, not a security
boundary; the absence of a live adapter remains the decisive control.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Optional

from .capacity_evidence import NativeCapacityResponse
from .prepared_multi_package_gate import (
    PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE,
    PreparedMultiPackageAuthorization,
    authorize_prepared_multi_package,
)
from .prepared_package_multi_candidate import (
    PreparedMultiCandidateError,
    PreparedMultiPackageCandidate,
    build_prepared_multi_package_candidate,
)
from .prepared_package_multi_verify import (
    PreparedMultiPackageReadback,
    verify_prepared_multi_package_readback,
)
from .write_gate import DEFAULT_MAX_AGE_SECONDS, VerifiedBackup, capture_and_verify_fresh_backup


ProgressCallback = Callable[[str, int, int], None]
CancelledCallback = Callable[[], bool]
CaptureCallback = Callable[..., None]
FakeSendCallback = Callable[..., Any]
DetectDeviceCallback = Callable[[], tuple[int, int]]
CapacityQueryCallback = Callable[[], NativeCapacityResponse]
CandidateEnricher = Callable[[PreparedMultiPackageCandidate], PreparedMultiPackageCandidate]
Clock = Callable[[], float]


class PreparedMultiPackageWorkflowError(RuntimeError):
    """Terminal workflow error with explicit retry and device-outcome data."""

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
        self.automatic_retry_allowed = False
        self.audit = dict(audit or {})
        self.audit.setdefault("automatic_retry_allowed", False)


class PreparedMultiFakeTransport:
    """Explicit fake transport capability for one simulated transaction."""

    fake_transport = True

    def __init__(self, sender: FakeSendCallback) -> None:
        if not callable(sender):
            raise TypeError("fake transport requires a sender callback")
        self._sender = sender
        self.calls = 0
        self.transaction_started = False

    def send(
        self,
        transaction: Any,
        authorization: PreparedMultiPackageAuthorization,
        *,
        cancelled: Optional[CancelledCallback],
        progress: Optional[ProgressCallback],
        deadline: float,
        clock: Clock,
    ) -> Any:
        if self.calls:
            raise PreparedMultiPackageWorkflowError(
                "fake transport is one-shot and cannot send a second transaction",
                stage="write",
                state="failed",
                write_started=self.transaction_started,
            )
        self.calls = 1
        self.transaction_started = True
        return self._sender(
            transaction,
            authorization,
            cancelled=cancelled,
            progress=progress,
            deadline=deadline,
            clock=clock,
        )


@dataclass(frozen=True)
class PreparedMultiPackageWorkflowResult:
    """Successful fake transfer and independent read-back result."""

    candidate: PreparedMultiPackageCandidate
    authorization: PreparedMultiPackageAuthorization
    before_backup: VerifiedBackup
    after_backup: VerifiedBackup
    completion: int
    verification: PreparedMultiPackageReadback
    audit: Mapping[str, Any]


def _notify(
    progress: Optional[ProgressCallback], label: str, completed: int, total: int
) -> None:
    if progress is not None:
        progress(label, completed, total)


def _check_cancelled(cancelled: Optional[CancelledCallback]) -> None:
    if cancelled is not None and cancelled():
        raise PreparedMultiPackageWorkflowError(
            "multi-child package workflow cancelled before transaction start",
            stage="pre_transaction",
            state="cancelled_before_transaction",
        )


def _check_deadline(clock: Clock, deadline: float) -> None:
    if clock() >= deadline:
        raise PreparedMultiPackageWorkflowError(
            "multi-child package workflow deadline expired before transaction start",
            stage="pre_transaction",
            state="timeout_before_transaction",
        )


def _failure(
    message: str,
    *,
    stage: str,
    state: str,
    write_started: bool,
    sequence: list[str],
    transport: PreparedMultiFakeTransport,
    candidate: Optional[PreparedMultiPackageCandidate] = None,
    authorization: Optional[PreparedMultiPackageAuthorization] = None,
    primary_error: Optional[str] = None,
) -> PreparedMultiPackageWorkflowError:
    audit: dict[str, Any] = {
        "state": state,
        "stage": stage,
        "device_change": (
            "indeterminate_after_transaction_start" if write_started else "none_started"
        ),
        "write_started": write_started,
        "fake_transport": True,
        "fake_transport_calls": transport.calls,
        "automatic_retry_allowed": False,
        "operation_sequence": list(sequence),
    }
    if primary_error is not None:
        audit["primary_error"] = primary_error
    if candidate is not None:
        audit["candidate"] = candidate.audit_dict()
    if authorization is not None:
        audit["authorization"] = authorization.to_dict()
    return PreparedMultiPackageWorkflowError(
        f"{message}; no automatic retry is allowed",
        stage=stage,
        state=state,
        write_started=write_started,
        audit=audit,
    )


class GuardedPreparedMultiPackageWorkflow:
    """Run the exact ordered package path with a fake transport only."""

    def __init__(
        self,
        capture: CaptureCallback,
        transport: PreparedMultiFakeTransport,
        template: Any,
        *,
        detect_device: DetectDeviceCallback,
        query_capacity: CapacityQueryCallback,
        template_folder_path: tuple[str, ...] = ("root", "Template"),
        template_item_paths: Optional[Mapping[str, tuple[str, ...]]] = None,
        candidate_enricher: Optional[CandidateEnricher] = None,
    ) -> None:
        if not callable(capture):
            raise TypeError("capture callback is required")
        if not isinstance(transport, PreparedMultiFakeTransport):
            raise TypeError("ordered package workflow requires PreparedMultiFakeTransport")
        if not callable(detect_device) or not callable(query_capacity):
            raise TypeError("device detection and parsed capacity query callbacks are required")
        if candidate_enricher is not None and not callable(candidate_enricher):
            raise TypeError("candidate_enricher must be callable when supplied")
        self._capture = capture
        self._transport = transport
        self._template = template
        self._detect_device = detect_device
        self._query_capacity = query_capacity
        self._template_folder_path = tuple(template_folder_path)
        self._template_item_paths = (
            None
            if template_item_paths is None
            else {key: tuple(value) for key, value in template_item_paths.items()}
        )
        self._candidate_enricher = candidate_enricher

    def run(
        self,
        *,
        backup_destination: Path,
        post_operation_destination: Path,
        package: Any,
        preview: PreparedMultiPackageCandidate,
        new_record_timestamp_be32: int,
        confirmation: str,
        fake_transport: bool = False,
        cancelled: Optional[CancelledCallback] = None,
        progress: Optional[ProgressCallback] = None,
        now: Optional[datetime] = None,
        max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
        timeout_seconds: float = 60.0,
        clock: Clock = time.monotonic,
    ) -> PreparedMultiPackageWorkflowResult:
        """Capture → rebuild → authorize → send once → read back independently."""

        if fake_transport is not True or self._transport.fake_transport is not True:
            raise PreparedMultiPackageWorkflowError(
                "ordered package workflow requires explicit fake_transport=True",
                stage="transport",
                state="failed",
            )
        if not isinstance(preview, PreparedMultiPackageCandidate):
            raise PreparedMultiPackageWorkflowError(
                "ordered package workflow requires a displayed offline candidate",
                stage="preview",
                state="failed",
            )
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise PreparedMultiPackageWorkflowError(
                "ordered package workflow requires a finite positive timeout",
                stage="timeout",
                state="failed",
            )
        if not callable(clock):
            raise TypeError("clock must be callable")

        deadline = clock() + float(timeout_seconds)
        sequence = ["fake_transport_asserted"]
        _notify(progress, "Preparing ordered package operation", 0, 1)
        try:
            _check_cancelled(cancelled)
            _check_deadline(clock, deadline)
            detected_identity = self._detect_device()
            sequence.append("device_detected")
            response = self._query_capacity()
            if not isinstance(response, NativeCapacityResponse):
                raise ValueError("capacity query did not return parsed native 0x0019 evidence")
            if response.device_identity != detected_identity:
                raise ValueError("capacity response identity differs from detected device")
            sequence.append("capacity_queried_0x0019")
        except PreparedMultiPackageWorkflowError:
            raise
        except Exception as exc:
            raise _failure(
                f"ordered package read-only preflight failed: {exc}",
                stage="capacity_query",
                state="failed",
                write_started=False,
                sequence=sequence,
                transport=self._transport,
                primary_error=str(exc),
            ) from exc

        try:
            before = capture_and_verify_fresh_backup(
                Path(backup_destination),
                lambda destination: self._capture(
                    destination, cancelled=cancelled, progress=progress
                ),
                now=None,
                max_age_seconds=max_age_seconds,
            )
            sequence.append("fresh_complete_backup")
            if before.device_identity != tuple(f"0x{value:04x}" for value in response.device_identity):
                raise ValueError("fresh backup identity differs from parsed capacity evidence")
        except Exception as exc:
            raise _failure(
                f"ordered package fresh backup failed: {exc}",
                stage="fresh_backup",
                state="failed",
                write_started=False,
                sequence=sequence,
                transport=self._transport,
                primary_error=str(exc),
            ) from exc

        try:
            _check_cancelled(cancelled)
            _check_deadline(clock, deadline)
            template_item_paths = dict(self._template_item_paths or {})
            if self._template_item_paths is None:
                known_template_paths = {
                    "txt": ("root", "Template", "chapter"),
                    "bmp": ("root", "Template", "page"),
                }
                available_template_paths = set(getattr(self._template, "paths", {}).values())
                for kind, path in known_template_paths.items():
                    if any(item.kind == kind for item in package.items) or path in available_template_paths:
                        template_item_paths[kind] = path
                if any(item.kind == "txt" for item in package.items) and "txt" not in template_item_paths:
                    template_item_paths["txt"] = ("root", "Template", "chapter")
                if any(item.kind == "bmp" for item in package.items) and "bmp" not in template_item_paths:
                    template_item_paths["bmp"] = ("root", "Template", "page")
            current = build_prepared_multi_package_candidate(
                package,
                before,
                self._template,
                new_record_timestamp_be32=new_record_timestamp_be32,
                native_capacity_response=response,
                template_folder_path=self._template_folder_path,
                template_item_paths=template_item_paths,
            )
            if self._candidate_enricher is not None:
                current = self._candidate_enricher(current)
            sequence.append("candidate_reconstructed")
            if current.audit_dict() != preview.audit_dict():
                raise ValueError("fresh candidate differs from the displayed preview")
        except PreparedMultiPackageWorkflowError:
            raise
        except Exception as exc:
            raise _failure(
                f"ordered package candidate preflight failed: {exc}",
                stage="candidate",
                state="failed",
                write_started=False,
                sequence=sequence,
                transport=self._transport,
                primary_error=str(exc),
            ) from exc

        try:
            _check_cancelled(cancelled)
            _check_deadline(clock, deadline)
            authorization = authorize_prepared_multi_package(
                current,
                confirmation=confirmation,
            )
            authorization.require_same_candidate(current)
            sequence.append("authorization")
        except PreparedMultiPackageWorkflowError:
            raise
        except Exception as exc:
            raise _failure(
                f"ordered package authorization failed: {exc}",
                stage="authorization",
                state="failed",
                write_started=False,
                sequence=sequence,
                transport=self._transport,
                candidate=current,
                primary_error=str(exc),
            ) from exc

        try:
            _check_cancelled(cancelled)
            _check_deadline(clock, deadline)
        except PreparedMultiPackageWorkflowError as exc:
            exc.audit.update(
                {
                    "fake_transport": True,
                    "fake_transport_calls": self._transport.calls,
                    "operation_sequence": list(sequence),
                    "candidate": current.audit_dict(),
                    "automatic_retry_allowed": False,
                }
            )
            raise

        _notify(progress, "Sending one ordered package through fake transport", 0, current.transaction.payload_length)
        try:
            completion = self._transport.send(
                current.transaction,
                authorization,
                cancelled=cancelled,
                progress=progress,
                deadline=deadline,
                clock=clock,
            )
            sequence.append("single_0x101b_transaction")
        except Exception as exc:
            raise _failure(
                f"ordered package fake transaction stopped: {exc}",
                stage="write",
                state="indeterminate_after_transaction_start",
                write_started=True,
                sequence=sequence,
                transport=self._transport,
                candidate=current,
                authorization=authorization,
                primary_error=str(exc),
            ) from exc

        if clock() >= deadline:
            raise _failure(
                "ordered package fake transaction exceeded its finite deadline",
                stage="write_deadline",
                state="indeterminate_after_transaction_start",
                write_started=True,
                sequence=sequence,
                transport=self._transport,
                candidate=current,
                authorization=authorization,
            )
        if isinstance(completion, bool) or not isinstance(completion, int) or completion != 0:
            value = repr(completion) if not isinstance(completion, int) else f"0x{completion:04x}"
            raise _failure(
                f"ordered package completion {value} is not 0x0000",
                stage="write_completion",
                state="failed",
                write_started=True,
                sequence=sequence,
                transport=self._transport,
                candidate=current,
                authorization=authorization,
                primary_error=f"completion={value}",
            )
        sequence.append("completion_0x0000")

        try:
            _check_deadline(clock, deadline)
            after = capture_and_verify_fresh_backup(
                Path(post_operation_destination),
                lambda destination: self._capture(
                    destination, cancelled=cancelled, progress=progress
                ),
                now=None,
                max_age_seconds=max_age_seconds,
            )
            sequence.append("fresh_post_operation_backup")
            verification = verify_prepared_multi_package_readback(
                current,
                after.directory,
                completion=completion,
                now=None,
                max_age_seconds=max_age_seconds,
            )
            sequence.append("independent_readback_verification")
        except Exception as exc:
            raise _failure(
                f"ordered package fake post-operation read-back failed: {exc}",
                stage="post_operation_readback",
                state="indeterminate_after_transaction_start",
                write_started=True,
                sequence=sequence,
                transport=self._transport,
                candidate=current,
                authorization=authorization,
                primary_error=str(exc),
            ) from exc

        audit = current.audit_dict()
        audit.update(
            {
                "state": "readback_verified",
                "workflow": {
                    "fake_transport": True,
                    "device_change": "simulated_only",
                    "operation_sequence": sequence,
                    "fake_transport_calls": self._transport.calls,
                    "timeout_seconds": float(timeout_seconds),
                    "automatic_retry_allowed": False,
                },
                "authorization": authorization.to_dict(),
                "completion": "0x0000",
                "verification": verification.to_dict(),
            }
        )
        _notify(progress, "Ordered package fake read-back verified", 1, 1)
        return PreparedMultiPackageWorkflowResult(
            candidate=current,
            authorization=authorization,
            before_backup=before,
            after_backup=after,
            completion=completion,
            verification=verification,
            audit=audit,
        )


__all__ = [
    "PreparedMultiFakeTransport",
    "PreparedMultiPackageWorkflowError",
    "PreparedMultiPackageWorkflowResult",
    "GuardedPreparedMultiPackageWorkflow",
]
