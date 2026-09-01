"""Isolated, approval-gated runner for one prepared-package live smoke.

This module is intentionally absent from the normal CLI and ttk imports.  It
has no USB setup of its own; a separate runner must inject the already proven
InfoCarry session callbacks.  Importing it performs no detection, backup, or
write.  Calling :func:`run_prepared_package_live_smoke` is the only action,
and it requires both the separate owner approval token and the exact
package-specific confirmation phrase.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from .capacity_evidence import NativeCapacityResponse
from .prepared_package_candidate import (
    PreparedPackageCandidate,
    build_prepared_package_candidate,
)
from .prepared_package_gate import (
    PREPARED_PACKAGE_CONFIRMATION_PHRASE,
    PreparedPackageAuthorization,
    bind_prepared_package_sender,
    authorize_prepared_package,
)
from .prepared_package_verify import (
    PreparedPackageReadbackVerification,
    verify_prepared_package_readback,
)
from .prepared_package_workflow import (
    CaptureCallback,
    DetectDeviceCallback,
    ProgressCallback,
    SendCallback,
)
from .protocol import TransferCancelledError
from .write_gate import (
    DEFAULT_MAX_AGE_SECONDS,
    VerifiedBackup,
    capture_and_verify_fresh_backup,
)
from .write_protocol import WriteFailureAssessment, assess_write_failure


PREPARED_PACKAGE_LIVE_SMOKE_OWNER_APPROVAL = "APPROVE I6 PACKAGE LIVE SMOKE"


class PreparedPackageLiveSmokeError(RuntimeError):
    """Terminal live-smoke error; automatic retry is never permitted."""

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
class PreparedPackageLiveSmokeResult:
    """Durable result for the isolated one-package smoke."""

    candidate: PreparedPackageCandidate
    authorization: PreparedPackageAuthorization
    before_backup: VerifiedBackup
    after_backup: VerifiedBackup
    completion: int
    verification: PreparedPackageReadbackVerification
    audit: Mapping[str, Any]


def _check_cancelled(cancelled: Optional[Callable[[], bool]]) -> None:
    if cancelled is not None and cancelled():
        raise TransferCancelledError("prepared-package live smoke cancelled before device change")


def _same_preview(left: PreparedPackageCandidate, right: PreparedPackageCandidate) -> bool:
    return left.audit_dict() == right.audit_dict()


def run_prepared_package_live_smoke(
    *,
    backup_destination: Path,
    post_operation_destination: Path,
    package: Any,
    template: Any,
    new_record_timestamp_be32: int,
    confirmation: str,
    owner_approval: str,
    detect_device: DetectDeviceCallback,
    query_capacity: Callable[[], NativeCapacityResponse],
    capture: CaptureCallback,
    send: SendCallback,
    preview: Optional[PreparedPackageCandidate] = None,
    preview_callback: Optional[Callable[[PreparedPackageCandidate], None]] = None,
    cancelled: Optional[Callable[[], bool]] = None,
    progress: Optional[ProgressCallback] = None,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> PreparedPackageLiveSmokeResult:
    """Run exactly one explicitly approved package transaction.

    The function is deliberately not a general workflow.  It accepts only a
    parsed native ``0x0019`` response, exactly one candidate, and callbacks
    supplied by an isolated owner-reviewed runner.  The candidate is shown
    through ``preview_callback`` before authorization; if a previously shown
    candidate is supplied, every audit byte must match it.
    """

    if owner_approval != PREPARED_PACKAGE_LIVE_SMOKE_OWNER_APPROVAL:
        raise PreparedPackageLiveSmokeError(
            "separate owner approval was not accepted; no device operation attempted",
            stage="approval",
            state="failed",
        )
    if confirmation != PREPARED_PACKAGE_CONFIRMATION_PHRASE:
        raise PreparedPackageLiveSmokeError(
            "package confirmation phrase was not accepted; no device operation attempted",
            stage="approval",
            state="failed",
        )
    for callback, label in (
        (detect_device, "detect_device"),
        (query_capacity, "query_capacity"),
        (capture, "capture"),
        (send, "send"),
        (preview_callback, "preview_callback"),
    ):
        if callback is None or not callable(callback):
            raise PreparedPackageLiveSmokeError(
                f"isolated live smoke requires {label}",
                stage="preflight",
                state="failed",
            )

    sequence = ["owner_approval", "confirmation_phrase"]
    try:
        _check_cancelled(cancelled)
        detected_identity = detect_device()
        sequence.append("device_detected")
        response = query_capacity()
        if not isinstance(response, NativeCapacityResponse):
            raise ValueError("query callback did not return parsed native 0x0019 evidence")
        if response.device_identity != detected_identity:
            raise ValueError("capacity response identity differs from fresh device detection")
        sequence.append("capacity_queried_0x0019")
    except Exception as exc:
        raise PreparedPackageLiveSmokeError(
            f"live-smoke read-only preflight failed: {exc}",
            stage="capacity_query",
            state="failed",
            audit={"sequence": sequence},
        ) from exc

    try:
        before = capture_and_verify_fresh_backup(
            Path(backup_destination),
            lambda destination: capture(destination, cancelled=cancelled, progress=progress),
            now=None,
            max_age_seconds=max_age_seconds,
        )
        sequence.append("fresh_complete_backup")
        backup_identity = tuple(int(value, 16) for value in before.device_identity)
        if backup_identity != response.device_identity:
            raise ValueError("fresh backup identity differs from native capacity response")
    except Exception as exc:
        raise PreparedPackageLiveSmokeError(
            f"live-smoke fresh backup failed; no transaction started: {exc}",
            stage="fresh_backup",
            state="failed",
            audit={"sequence": sequence},
        ) from exc

    try:
        _check_cancelled(cancelled)
        candidate = build_prepared_package_candidate(
            package,
            before,
            template,
            new_record_timestamp_be32=new_record_timestamp_be32,
            native_capacity_response=response,
        )
        sequence.append("candidate_reconstructed")
        if preview is not None and not _same_preview(preview, candidate):
            raise ValueError("fresh candidate differs from the displayed preview")
        preview_callback(candidate)
    except Exception as exc:
        raise PreparedPackageLiveSmokeError(
            f"live-smoke candidate preflight failed; no transaction started: {exc}",
            stage="candidate",
            state="failed",
            audit={"sequence": sequence},
        ) from exc

    try:
        _check_cancelled(cancelled)
        authorization = authorize_prepared_package(
            candidate,
            confirmation=confirmation,
            require_native_capacity_evidence=True,
        )
        sender_authorization = bind_prepared_package_sender(
            authorization,
            candidate,
            now=None,
            max_age_seconds=max_age_seconds,
        )
        sequence.append("authorization")
    except Exception as exc:
        raise PreparedPackageLiveSmokeError(
            f"live-smoke authorization failed; no transaction started: {exc}",
            stage="authorization",
            state="failed",
            audit={"sequence": sequence, "candidate": candidate.audit_dict()},
        ) from exc

    try:
        completion = send(
            candidate.transaction,
            sender_authorization,
            cancelled=cancelled,
            progress=progress,
        )
        sequence.append("single_0x101b_transaction")
    except Exception as exc:
        assessment = assess_write_failure(exc)
        raise PreparedPackageLiveSmokeError(
            f"live-smoke transaction stopped; no automatic retry: {exc}",
            stage="write",
            state=(
                "indeterminate_after_transaction_start"
                if assessment.device_outcome == "indeterminate"
                else "failed"
            ),
            write_started=assessment.write_started,
            audit={
                "sequence": sequence,
                "primary_error": assessment.primary_error,
                "write_started": assessment.write_started,
                "device_change": assessment.device_outcome,
                "automatic_retry_allowed": False,
                "candidate": candidate.audit_dict(),
                "authorization": authorization.to_dict(),
            },
        ) from exc

    if isinstance(completion, bool) or not isinstance(completion, int) or completion != 0:
        value = repr(completion) if not isinstance(completion, int) else f"0x{completion:04x}"
        raise PreparedPackageLiveSmokeError(
            f"live-smoke completion {value} is not 0x0000; no automatic retry",
            stage="write_completion",
            state="failed",
            write_started=True,
            audit={
                "sequence": sequence,
                "completion": value,
                "device_change": "completed_with_error",
                "automatic_retry_allowed": False,
            },
        )
    sequence.append("completion_0x0000")

    try:
        after = capture_and_verify_fresh_backup(
            Path(post_operation_destination),
            lambda destination: capture(destination, cancelled=cancelled, progress=progress),
            now=None,
            max_age_seconds=max_age_seconds,
        )
        sequence.append("fresh_post_operation_backup")
        verification = verify_prepared_package_readback(
            authorization,
            candidate,
            after.directory,
            completion=completion,
            now=None,
            max_age_seconds=max_age_seconds,
        )
        sequence.append("independent_readback_verification")
    except Exception as exc:
        raise PreparedPackageLiveSmokeError(
            f"live-smoke read-back failed; no automatic retry: {exc}",
            stage="post_operation_readback",
            state="indeterminate_after_transaction_start",
            write_started=True,
            audit={
                "sequence": sequence,
                "completion": "0x0000",
                "device_change": "completed_or_unknown",
                "automatic_retry_allowed": False,
                "primary_error": str(exc),
            },
        ) from exc

    audit = candidate.audit_dict()
    audit.update(
        {
            "state": "readback_verified",
            "workflow": {
                "isolated_live_smoke": True,
                "device_change": "completed_and_verified",
                "automatic_retry_allowed": False,
                "sequence": sequence,
            },
            "authorization": authorization.to_dict(),
            "completion": "0x0000",
            "verification": verification.to_dict(),
        }
    )
    return PreparedPackageLiveSmokeResult(
        candidate=candidate,
        authorization=authorization,
        before_backup=before,
        after_backup=after,
        completion=completion,
        verification=verification,
        audit=audit,
    )


__all__ = [
    "PREPARED_PACKAGE_LIVE_SMOKE_OWNER_APPROVAL",
    "PreparedPackageLiveSmokeError",
    "PreparedPackageLiveSmokeResult",
    "run_prepared_package_live_smoke",
]
