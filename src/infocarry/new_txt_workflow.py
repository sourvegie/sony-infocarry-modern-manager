"""Offline/fake-transport guarded workflow for one new root-level TXT.

The workflow composes the existing candidate builder, new-TXT authorization,
one-shot sender, and complete read-back verifier.  Its integration points are
injected backup and send callbacks so normal CLI/ttk code cannot accidentally
turn this model into a live device action.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from .new_txt import NewTxtAddResult, build_new_root_txt_add
from .new_txt_gate import (
    NewTxtAddAuthorization,
    bind_new_txt_sender,
    authorize_new_txt_add,
    revalidate_new_txt_inputs,
)
from .protocol import TransferCancelledError
from .write_gate import (
    DEFAULT_MAX_AGE_SECONDS,
    PostWriteVerification,
    VerifiedBackup,
    capture_and_verify_fresh_backup,
)
from .write_protocol import WriteFailureAssessment, assess_write_failure


ProgressCallback = Callable[[str, int, int], None]
CancelledCallback = Callable[[], bool]
CaptureCallback = Callable[..., None]
SendCallback = Callable[..., int]


class NewTxtWorkflowError(RuntimeError):
    """Raised with a durable terminal audit for one guarded attempt."""

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


@dataclass(frozen=True)
class NewTxtOfflinePreview:
    """Hash-only preview report; candidate bytes are never serialized here."""

    result: NewTxtAddResult

    def to_dict(self) -> dict[str, Any]:
        report = dict(self.result.audit)
        report["preview"] = {
            "state": "previewed",
            "device_change": "none",
            "candidate_bytes_included": False,
            "notice": "OFFLINE PREVIEW ONLY — no device change has occurred",
        }
        return report


@dataclass(frozen=True)
class NewTxtWorkflowResult:
    """Durable result for the fake-transport guarded sequence."""

    state: str
    preview: NewTxtOfflinePreview
    authorization: NewTxtAddAuthorization
    before_backup: VerifiedBackup
    after_backup: VerifiedBackup
    completion: int
    verification: PostWriteVerification
    audit: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.audit)


def build_new_txt_preview(
    backup_directory: Path,
    source_path: Path,
    target_filename: str,
    *,
    source_template_offset: int,
    available_capacity_bytes: int,
    source_encoding: str = "utf-8",
    record_timestamp_be32: Optional[int] = None,
    metadata_timestamps: Optional[Mapping[int, int]] = None,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> NewTxtOfflinePreview:
    """Create a hash-only offline preview for one UTF-8 or CP932 source."""

    return NewTxtOfflinePreview(
        build_new_root_txt_add(
            backup_directory,
            source_path,
            target_filename,
            source_template_offset=source_template_offset,
            available_capacity_bytes=available_capacity_bytes,
            source_encoding=source_encoding,
            record_timestamp_be32=record_timestamp_be32,
            metadata_timestamps=metadata_timestamps,
            now=now,
            max_age_seconds=max_age_seconds,
        )
    )


def _notify(
    progress: Optional[ProgressCallback], label: str, completed: int, total: int
) -> None:
    if progress is not None:
        progress(label, completed, total)


def _check_cancelled(cancelled: Optional[CancelledCallback]) -> None:
    if cancelled is not None and cancelled():
        raise TransferCancelledError("new-TXT workflow cancelled before device change")


def _raise_prewrite_cancellation(exc: BaseException, *, stage: str) -> NewTxtWorkflowError:
    return NewTxtWorkflowError(
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


def _same_preview(left: NewTxtAddResult, right: NewTxtAddResult) -> bool:
    left_audit = left.audit
    right_audit = right.audit
    for section, keys in {
        "device_identity": ("vendor_id", "product_id"),
        "source": ("sha256",),
        "target": ("path",),
        "baseline": ("manifest_sha256", "blob_sha256"),
        "candidate": ("blob_sha256", "transaction_sha256"),
    }.items():
        left_section = left_audit.get(section)
        right_section = right_audit.get(section)
        if not isinstance(left_section, Mapping) or not isinstance(right_section, Mapping):
            return False
        if any(left_section.get(key) != right_section.get(key) for key in keys):
            return False
    return True


class GuardedNewTxtWorkflow:
    """Run one fake-transport-only new-TXT operation with full read-back."""

    def __init__(self, capture: CaptureCallback, send: SendCallback) -> None:
        if not callable(capture) or not callable(send):
            raise TypeError("capture and send callbacks are required")
        self._capture = capture
        self._send = send

    def run(
        self,
        *,
        backup_destination: Path,
        post_write_destination: Path,
        source_path: Path,
        target_filename: str,
        source_template_offset: int,
        available_capacity_bytes: int,
        confirmation: str,
        preview: Optional[NewTxtOfflinePreview] = None,
        source_encoding: str = "utf-8",
        record_timestamp_be32: Optional[int] = None,
        metadata_timestamps: Optional[Mapping[int, int]] = None,
        fake_transport: bool = False,
        cancelled: Optional[CancelledCallback] = None,
        progress: Optional[ProgressCallback] = None,
        now: Optional[datetime] = None,
        max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
    ) -> NewTxtWorkflowResult:
        """Capture fresh state, authorize, send once through an injected fake,
        and independently verify the complete fake read-back.

        ``fake_transport`` is a mandatory caller assertion.  There is no live
        transport implementation in this module, and the normal CLI/ttk paths
        do not import it.
        """

        if not fake_transport:
            raise NewTxtWorkflowError(
                "guarded new-TXT workflow requires an explicit fake transport",
                stage="transport",
                state="failed",
            )
        try:
            _check_cancelled(cancelled)
        except TransferCancelledError as exc:
            raise _raise_prewrite_cancellation(exc, stage="preparation") from exc
        _notify(progress, "Preparing offline new-TXT operation", 0, 1)

        try:
            before = capture_and_verify_fresh_backup(
                backup_destination,
                lambda destination: self._capture(
                    destination, cancelled=cancelled, progress=progress
                ),
                now=None,
                max_age_seconds=max_age_seconds,
            )
        except Exception as exc:
            cancellation = exc if isinstance(exc, TransferCancelledError) else exc.__cause__
            if isinstance(cancellation, TransferCancelledError):
                raise _raise_prewrite_cancellation(cancellation, stage="fresh_backup") from exc
            raise NewTxtWorkflowError(
                f"fresh backup failed; no device transaction started: {exc}",
                stage="fresh_backup",
                state="failed",
                audit={
                    "state": "failed",
                    "device_change": "none_started",
                    "automatic_retry_allowed": False,
                },
            ) from exc

        try:
            _check_cancelled(cancelled)
        except TransferCancelledError as exc:
            raise _raise_prewrite_cancellation(exc, stage="candidate") from exc
        try:
            current_preview = build_new_txt_preview(
                before.directory,
                source_path,
                target_filename,
                source_template_offset=source_template_offset,
                available_capacity_bytes=available_capacity_bytes,
                source_encoding=source_encoding,
                record_timestamp_be32=record_timestamp_be32,
                metadata_timestamps=metadata_timestamps,
                now=None,
                max_age_seconds=max_age_seconds,
            )
        except Exception as exc:
            raise NewTxtWorkflowError(
                f"offline candidate preview failed: {exc}",
                stage="preview",
                state="failed",
                audit={
                    "state": "failed",
                    "device_change": "none_started",
                    "automatic_retry_allowed": False,
                },
            ) from exc

        if preview is not None and not _same_preview(preview.result, current_preview.result):
            raise NewTxtWorkflowError(
                "fresh backup or source no longer matches the displayed preview",
                stage="preview_revalidation",
                state="failed",
                audit={
                    "state": "failed",
                    "device_change": "none_started",
                    "automatic_retry_allowed": False,
                    "preview": preview.to_dict(),
                    "fresh_preview": current_preview.to_dict(),
                },
            )

        try:
            _check_cancelled(cancelled)
        except TransferCancelledError as exc:
            raise _raise_prewrite_cancellation(exc, stage="authorization") from exc
        try:
            revalidate_new_txt_inputs(
                current_preview.result,
                before.directory,
                source_path,
                now=None,
                max_age_seconds=max_age_seconds,
            )
            authorization = authorize_new_txt_add(
                current_preview.result,
                confirmation=confirmation,
            )
            sender_authorization = bind_new_txt_sender(
                authorization,
                current_preview.result,
                before.directory,
                source_path,
                now=None,
                max_age_seconds=max_age_seconds,
            )
        except Exception as exc:
            raise NewTxtWorkflowError(
                f"new-TXT authorization failed: {exc}",
                stage="authorization",
                state="failed",
                audit={
                    "state": "failed",
                    "device_change": "none_started",
                    "automatic_retry_allowed": False,
                    "preview": current_preview.to_dict(),
                },
            ) from exc

        _notify(
            progress,
            "New-TXT authorization accepted; sending once through fake transport",
            0,
            current_preview.result.transaction.payload_length,
        )
        try:
            completion = self._send(
                current_preview.result.transaction,
                sender_authorization,
                cancelled=cancelled,
                progress=progress,
            )
        except Exception as exc:
            assessment: WriteFailureAssessment = assess_write_failure(exc)
            state = (
                "indeterminate_after_transaction_start"
                if assessment.device_outcome == "indeterminate"
                else "failed"
            )
            audit = {
                "state": state,
                "stage": "write",
                "device_change": assessment.device_outcome,
                "write_started": assessment.write_started,
                "automatic_retry_allowed": assessment.automatic_retry_allowed,
                "read_only_assessment_allowed": assessment.read_only_assessment_allowed,
                "primary_error": assessment.primary_error,
                "preview": current_preview.to_dict(),
                "authorization": authorization.to_dict(),
            }
            raise NewTxtWorkflowError(
                f"new-TXT fake transfer stopped; no automatic retry: {exc}",
                stage="write",
                state=state,
                write_started=assessment.write_started,
                audit=audit,
            ) from exc

        try:
            after = capture_and_verify_fresh_backup(
                post_write_destination,
                lambda destination: self._capture(
                    destination, cancelled=cancelled, progress=progress
                ),
                now=None,
                max_age_seconds=max_age_seconds,
            )
            verification = authorization.verify_post_add_backup(
                current_preview.result,
                before.directory,
                source_path,
                after.directory,
                now=None,
                max_age_seconds=max_age_seconds,
            )
        except Exception as exc:
            raise NewTxtWorkflowError(
                f"new-TXT fake read-back failed; no automatic retry: {exc}",
                stage="post_write_readback",
                state="failed",
                write_started=True,
                audit={
                    "state": "failed",
                    "stage": "post_write_readback",
                    "device_change": "completed_or_unknown",
                    "write_started": True,
                    "automatic_retry_allowed": False,
                    "primary_error": str(exc),
                    "completion": completion,
                    "preview": current_preview.to_dict(),
                    "authorization": authorization.to_dict(),
                },
            ) from exc

        audit = current_preview.to_dict()
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
        _notify(progress, "New-TXT fake read-back verified", 1, 1)
        return NewTxtWorkflowResult(
            state="readback_verified",
            preview=current_preview,
            authorization=authorization,
            before_backup=before,
            after_backup=after,
            completion=completion,
            verification=verification,
            audit=audit,
        )


__all__ = [
    "GuardedNewTxtWorkflow",
    "NewTxtOfflinePreview",
    "NewTxtWorkflowError",
    "NewTxtWorkflowResult",
    "build_new_txt_preview",
]
