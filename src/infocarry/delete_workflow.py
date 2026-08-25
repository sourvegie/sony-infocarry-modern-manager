"""Fake-transport-only guarded workflow for one modern TXT deletion.

The normal CLI and ttk application do not import this module.  A caller must
inject both backup and sender callbacks and explicitly pass ``fake_transport``
as the boolean ``True``.  The workflow sends at most once and preserves the
R15 distinction between safe pre-start cancellation and an indeterminate
post-start interruption.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from .delete_generalized import (
    DELETE_GENERALIZED_CONFIRMATION_PHRASE,
    GeneralizedDeleteAuthorization,
    GeneralizedDeleteCandidate,
    GeneralizedDeleteVerification,
    authorize_generalized_delete,
    bind_generalized_delete_sender,
    build_generalized_delete_candidate,
    verify_generalized_delete_readback,
)
from .protocol import TransferCancelledError
from .write_gate import DEFAULT_MAX_AGE_SECONDS, VerifiedBackup, capture_and_verify_fresh_backup
from .write_protocol import WriteFailureAssessment, assess_write_failure


ProgressCallback = Callable[[str, int, int], None]
CancelledCallback = Callable[[], bool]
CaptureCallback = Callable[..., None]
SendCallback = Callable[..., int]


class GeneralizedDeleteWorkflowError(RuntimeError):
    """Terminal workflow error carrying durable stage and retry information."""

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
class GeneralizedDeleteWorkflowResult:
    candidate: GeneralizedDeleteCandidate
    authorization: GeneralizedDeleteAuthorization
    before_backup: VerifiedBackup
    after_backup: VerifiedBackup
    completion: int
    verification: GeneralizedDeleteVerification
    audit: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.audit)


def _check_cancelled(cancelled: Optional[CancelledCallback]) -> None:
    if cancelled is not None and cancelled():
        raise TransferCancelledError("delete workflow cancelled before device change")


def _same_preview(left: GeneralizedDeleteCandidate, right: GeneralizedDeleteCandidate) -> bool:
    return left.to_dict() == right.to_dict()


def _safe_cancel_error(exc: BaseException, stage: str) -> GeneralizedDeleteWorkflowError:
    return GeneralizedDeleteWorkflowError(
        str(exc),
        stage=stage,
        state="cancelled_before_transaction",
        write_started=False,
        audit={
            "state": "cancelled_before_transaction",
            "stage": stage,
            "device_change": "none_started",
            "automatic_retry_allowed": False,
        },
    )


class GuardedGeneralizedDeleteWorkflow:
    """Run one complete fake deletion sequence with no live transport access."""

    def __init__(self, capture: CaptureCallback, send: SendCallback) -> None:
        if not callable(capture) or not callable(send):
            raise TypeError("capture and send callbacks are required")
        self._capture = capture
        self._send = send

    def run(
        self,
        *,
        backup_destination: Path,
        post_delete_destination: Path,
        target_path: str,
        target_record_offset: int,
        confirmation: str,
        preview: Optional[GeneralizedDeleteCandidate] = None,
        fake_transport: bool = False,
        cancelled: Optional[CancelledCallback] = None,
        progress: Optional[ProgressCallback] = None,
        now: Optional[datetime] = None,
        max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
    ) -> GeneralizedDeleteWorkflowResult:
        if fake_transport is not True:
            raise GeneralizedDeleteWorkflowError(
                "guarded generalized delete requires fake_transport=True",
                stage="transport",
                state="failed",
            )
        try:
            _check_cancelled(cancelled)
        except TransferCancelledError as exc:
            raise _safe_cancel_error(exc, "preparation") from exc

        try:
            before = capture_and_verify_fresh_backup(
                backup_destination,
                lambda destination: self._capture(
                    destination, cancelled=cancelled, progress=progress
                ),
                now=now,
                max_age_seconds=max_age_seconds,
            )
        except Exception as exc:
            if isinstance(exc, TransferCancelledError) or isinstance(exc.__cause__, TransferCancelledError):
                cause = exc if isinstance(exc, TransferCancelledError) else exc.__cause__
                raise _safe_cancel_error(cause, "fresh_backup") from exc
            raise GeneralizedDeleteWorkflowError(
                f"fresh backup failed; no transaction started: {exc}",
                stage="fresh_backup",
                state="failed",
                audit={"state": "failed", "device_change": "none_started"},
            ) from exc

        try:
            _check_cancelled(cancelled)
            current = build_generalized_delete_candidate(
                before.directory,
                target_path,
                target_record_offset,
                now=now,
                max_age_seconds=max_age_seconds,
            )
        except TransferCancelledError as exc:
            raise _safe_cancel_error(exc, "candidate") from exc
        except Exception as exc:
            raise GeneralizedDeleteWorkflowError(
                f"offline delete candidate failed: {exc}",
                stage="candidate",
                state="failed",
                audit={"state": "failed", "device_change": "none_started"},
            ) from exc

        if preview is not None and not _same_preview(preview, current):
            raise GeneralizedDeleteWorkflowError(
                "fresh backup or target no longer matches the displayed preview",
                stage="preview_revalidation",
                state="failed",
                audit={
                    "state": "failed",
                    "device_change": "none_started",
                    "preview": preview.to_dict(),
                    "fresh_candidate": current.to_dict(),
                },
            )

        try:
            _check_cancelled(cancelled)
            authorization = authorize_generalized_delete(
                current,
                confirmation=confirmation,
            )
            binding = bind_generalized_delete_sender(
                authorization,
                current,
                now=now,
                max_age_seconds=max_age_seconds,
            )
        except TransferCancelledError as exc:
            raise _safe_cancel_error(exc, "authorization") from exc
        except Exception as exc:
            raise GeneralizedDeleteWorkflowError(
                f"delete authorization failed: {exc}",
                stage="authorization",
                state="failed",
                audit={"state": "failed", "device_change": "none_started", "candidate": current.to_dict()},
            ) from exc

        if progress is not None:
            progress("Delete authorized; sending once through fake transport", 0, current.transaction.payload_length)
        try:
            completion = self._send(
                current.transaction,
                binding,
                cancelled=cancelled,
                progress=progress,
            )
            if isinstance(completion, bool) or not isinstance(completion, int):
                raise RuntimeError("fake sender returned missing or malformed completion")
            if completion != 0:
                raise RuntimeError(f"fake sender returned nonzero completion 0x{completion:04x}")
        except Exception as exc:
            assessment: WriteFailureAssessment = assess_write_failure(exc)
            # A callback was invoked after authorization.  Unless it explicitly
            # proves that the first request was not issued, its device outcome
            # is conservatively indeterminate.
            started = assessment.write_started or not hasattr(exc, "write_failure_assessment")
            state = "indeterminate_after_transaction_start" if started else "failed"
            raise GeneralizedDeleteWorkflowError(
                f"fake delete transfer stopped; no automatic retry: {exc}",
                stage="write",
                state=state,
                write_started=started,
                audit={
                    "state": state,
                    "stage": "write",
                    "device_change": assessment.device_outcome if not started else "indeterminate",
                    "write_started": started,
                    "primary_error": assessment.primary_error,
                    "automatic_retry_allowed": False,
                    "candidate": current.to_dict(),
                    "authorization": authorization.to_dict(),
                },
            ) from exc

        try:
            after = capture_and_verify_fresh_backup(
                post_delete_destination,
                lambda destination: self._capture(
                    destination, cancelled=cancelled, progress=progress
                ),
                now=now,
                max_age_seconds=max_age_seconds,
            )
            verification = verify_generalized_delete_readback(
                current,
                after.directory,
                completion=completion,
                now=now,
                max_age_seconds=max_age_seconds,
            )
        except Exception as exc:
            raise GeneralizedDeleteWorkflowError(
                f"post-delete read-back failed; no automatic retry: {exc}",
                stage="post_delete_readback",
                state="indeterminate_after_transaction_start",
                write_started=True,
                audit={
                    "state": "indeterminate_after_transaction_start",
                    "stage": "post_delete_readback",
                    "device_change": "indeterminate",
                    "write_started": True,
                    "completion": completion,
                    "primary_error": str(exc),
                    "automatic_retry_allowed": False,
                    "candidate": current.to_dict(),
                    "authorization": authorization.to_dict(),
                },
            ) from exc

        audit = current.to_dict()
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
                },
                "authorization": authorization.to_dict(),
                "completion": f"0x{completion:04x}",
                "verification": verification.to_dict(),
            }
        )
        if progress is not None:
            progress("Delete fake read-back verified", 1, 1)
        return GeneralizedDeleteWorkflowResult(
            candidate=current,
            authorization=authorization,
            before_backup=before,
            after_backup=after,
            completion=completion,
            verification=verification,
            audit=audit,
        )


__all__ = [
    "GuardedGeneralizedDeleteWorkflow",
    "GeneralizedDeleteWorkflowError",
    "GeneralizedDeleteWorkflowResult",
]
