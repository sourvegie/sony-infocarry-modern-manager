"""Fake-transport-only guarded workflow for one modern TXT deletion.

The normal CLI and ttk application do not import this module.  A caller must
inject both backup and sender callbacks and explicitly pass ``fake_transport``
as the boolean ``True``.  The workflow sends at most once and preserves the
R15 distinction between safe pre-start cancellation and an indeterminate
post-start interruption.  Its finite deadline is cooperative: it is checked
at workflow boundaries and passed to the fake callback, but it cannot forcibly
interrupt an arbitrary Python callback that never returns.  Bounded USB-call
timeouts belong to a future isolated live adapter; none is provided here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path
import time
from typing import Any, Callable, ClassVar, Mapping, Optional

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
from .protocol import TransferCancelledError, TransferTimeoutError
from .write_gate import DEFAULT_MAX_AGE_SECONDS, VerifiedBackup, capture_and_verify_fresh_backup


ProgressCallback = Callable[[str, int, int], None]
CancelledCallback = Callable[[], bool]
CaptureCallback = Callable[..., None]
SendCallback = Callable[..., int]


@dataclass(frozen=True)
class FakeDeleteTransport:
    """Explicit capability wrapper for the offline delete workflow.

    The wrapper is intentionally a test/simulation boundary, not a security
    boundary.  It has no USB imports or discovery path.  Requiring this
    concrete type at the workflow boundary makes accidentally passing the
    production sender harder and makes the simulated call auditable.
    """

    sender: SendCallback
    capability: ClassVar[str] = "infocarry-fake-delete-transport-v1"

    def __post_init__(self) -> None:
        if not callable(self.sender):
            raise TypeError("fake delete transport requires a callable sender")

    def send(
        self,
        transaction: Any,
        binding: Any,
        *,
        deadline: float,
        cancelled: Optional[CancelledCallback],
        progress: Optional[ProgressCallback],
    ) -> int:
        if not isinstance(deadline, (int, float)) or isinstance(deadline, bool) or not math.isfinite(deadline):
            raise ValueError("fake delete transport requires a finite deadline")
        return self.sender(
            transaction,
            binding,
            deadline=deadline,
            cancelled=cancelled,
            progress=progress,
        )


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
    """Run one complete fake deletion sequence with no live transport access.

    The injected fake transport must cooperate with the supplied deadline.
    This class does not claim to forcibly stop a callback that hangs forever.
    """

    def __init__(
        self,
        capture: CaptureCallback,
        transport: FakeDeleteTransport,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not callable(capture) or not isinstance(transport, FakeDeleteTransport):
            raise TypeError("capture and an explicit FakeDeleteTransport are required")
        if not callable(clock):
            raise TypeError("fake workflow clock must be callable")
        self._capture = capture
        self._transport = transport
        self._clock = clock

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
        timeout_seconds: float = 30.0,
    ) -> GeneralizedDeleteWorkflowResult:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise GeneralizedDeleteWorkflowError(
                "fake delete workflow requires a finite positive timeout",
                stage="transport",
                state="failed",
            )
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
            deadline = self._clock() + timeout_seconds
            if not math.isfinite(deadline) or self._clock() > deadline:
                raise TransferTimeoutError("delete transaction deadline expired before transmission")
        except Exception as exc:
            raise GeneralizedDeleteWorkflowError(
                f"delete transfer did not start before its deadline: {exc}",
                stage="write",
                state="failed",
                write_started=False,
                audit={
                    "state": "failed",
                    "stage": "write",
                    "device_change": "none_started",
                    "write_started": False,
                    "primary_error": str(exc),
                    "automatic_retry_allowed": False,
                },
            ) from exc
        try:
            completion = self._transport.send(
                current.transaction,
                binding,
                deadline=deadline,
                cancelled=cancelled,
                progress=progress,
            )
            if isinstance(completion, bool) or not isinstance(completion, int):
                raise RuntimeError("fake sender returned missing or malformed completion")
            if completion != 0:
                raise RuntimeError(f"fake sender returned nonzero completion 0x{completion:04x}")
            if self._clock() > deadline:
                raise TransferTimeoutError("delete transaction exceeded its finite deadline")
        except Exception as exc:
            assessment = getattr(exc, "write_failure_assessment", None)
            has_assessment = assessment is not None
            # A callback was invoked after authorization.  Unless it explicitly
            # proves that the first request was not issued, its device outcome
            # is conservatively indeterminate.
            started = bool(getattr(assessment, "write_started", False)) if has_assessment else True
            state = "indeterminate_after_transaction_start" if started else "failed"
            raise GeneralizedDeleteWorkflowError(
                f"fake delete transfer stopped; no automatic retry: {exc}",
                stage="write",
                state=state,
                write_started=started,
                audit={
                    "state": state,
                    "stage": "write",
                    "device_change": getattr(assessment, "device_outcome", "indeterminate" if started else "not_started"),
                    "write_started": started,
                    "primary_error": getattr(assessment, "primary_error", str(exc)),
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
    "FakeDeleteTransport",
    "GuardedGeneralizedDeleteWorkflow",
    "GeneralizedDeleteWorkflowError",
    "GeneralizedDeleteWorkflowResult",
]
