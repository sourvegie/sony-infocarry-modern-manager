"""Guarded existing-text replacement workflow.

This module is the boundary between the offline safety records and an
explicitly approved live operation.  It accepts injected capture and send
callbacks so the complete sequence can be tested without USB.  The normal
desktop workflow must provide callbacks only after the user has selected one
existing TXT record and entered the operation-specific confirmation phrase.

The workflow never retries a failed send.  A post-write capture or verifier
failure is returned as a terminal error with the already-created evidence
paths left intact for review.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Callable, Dict, Optional

from .backup import parse_grouped_values_response, parse_offset_list_response
from .backup_format import BackupFormatError, parse_backup_blob
from .payload_builder import PayloadBuilderError, build_from_replacements
from .protocol import TransferCancelledError
from .text_authoring import TextAuthoringError, encode_cp932_text
from .write_artifact import ProspectiveWriteTransaction
from .write_gate import (
    DEFAULT_MAX_AGE_SECONDS,
    PostWriteVerification,
    VerifiedBackup,
    WriteAuthorization,
    WriteGateError,
    WriteTarget,
    authorize_existing_text_replacement,
    capture_and_verify_fresh_backup,
    verify_post_write_backup,
)


ProgressCallback = Callable[[str, int, int], None]
CancelledCallback = Callable[[], bool]
CaptureCallback = Callable[..., None]
SendCallback = Callable[..., int]


class GuardedWorkflowError(RuntimeError):
    """Raised when a guarded replacement stops at a named safety stage."""

    def __init__(self, message: str, *, stage: str, write_started: bool = False):
        super().__init__(message)
        self.stage = stage
        self.write_started = write_started


@dataclass(frozen=True)
class ExistingTextReplacementResult:
    """Evidence returned after one send and an independent read-back."""

    before_backup: VerifiedBackup
    after_backup: VerifiedBackup
    transaction: ProspectiveWriteTransaction
    authorization: WriteAuthorization
    completion: int
    verification: PostWriteVerification

    def to_dict(self) -> Dict[str, Any]:
        return {
            "completion": f"0x{self.completion:04x}",
            "before_backup": self.before_backup.to_dict(),
            "after_backup": self.after_backup.to_dict(),
            "authorization": self.authorization.to_dict(),
            "verification": self.verification.to_dict(),
        }


def _check_cancelled(cancelled: Optional[CancelledCallback]) -> None:
    if cancelled is not None and cancelled():
        raise TransferCancelledError("guarded replacement was cancelled")


def _read_verified_object(backup: VerifiedBackup, key: str) -> bytes:
    filename = backup.object_filename(key)
    expected = backup.object_sha256(key)
    if filename is None or expected is None:
        raise GuardedWorkflowError(
            f"fresh backup is missing required object {key}",
            stage="candidate",
        )
    path = backup.directory / filename
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise GuardedWorkflowError(
            f"could not read verified backup object {path}: {exc}",
            stage="candidate",
        ) from exc
    if hashlib.sha256(data).hexdigest() != expected:
        raise GuardedWorkflowError(
            f"verified backup object {key} changed before candidate construction",
            stage="candidate",
        )
    return data


def build_existing_text_transaction(
    backup: VerifiedBackup,
    target: WriteTarget,
    text_path: Path,
) -> ProspectiveWriteTransaction:
    """Build one existing-TXT candidate from a verified fresh backup.

    Only the target payload is changed. Fixed state ranges are reconstructed
    from the same verified backup and all other model ranges remain the
    ordinary path's empty ranges.
    """

    if not isinstance(backup, VerifiedBackup):
        raise GuardedWorkflowError("candidate source must be a VerifiedBackup", stage="candidate")
    if not isinstance(target, WriteTarget):
        raise GuardedWorkflowError("candidate target must be a WriteTarget", stage="candidate")
    source_path = Path(text_path).expanduser().resolve()
    try:
        text = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise GuardedWorkflowError(
            f"could not read UTF-8 replacement text {source_path}: {exc}",
            stage="candidate",
        ) from exc
    try:
        encoded = encode_cp932_text(text).payload
    except TextAuthoringError as exc:
        raise GuardedWorkflowError(str(exc), stage="candidate") from exc

    blob = _read_verified_object(backup, "0x8004:backup-blob")
    try:
        parsed = parse_backup_blob(blob)
        record = parsed.record_at(target.record_offset)
        if record.kind != "file" or record.extension.lower() != "txt":
            raise BackupFormatError("target is not an existing TXT record")
        path_parts = parsed.paths.get(record.offset)
        if path_parts is None:
            raise BackupFormatError("target record is not reachable")
        actual_path = "\\".join(path_parts)
        if record.extension:
            actual_path = f"{actual_path}.{record.extension}"
        if actual_path != target.path:
            raise BackupFormatError(
                f"target path is {actual_path!r}, expected {target.path!r}"
            )
    except BackupFormatError as exc:
        raise GuardedWorkflowError(
            f"fresh backup target is malformed or changed: {exc}",
            stage="candidate",
        ) from exc

    offset_states = tuple(
        parse_offset_list_response(
            _read_verified_object(backup, f"0x{command:04x}:response-00{command:02x}")
        )
        for command in range(0x1B, 0x1F)
    )
    grouped = parse_grouped_values_response(
        _read_verified_object(backup, "0x001f:response-001f")
    )
    try:
        return build_from_replacements(
            blob,
            {target.record_offset: encoded},
            offset_states,
            grouped,
        )
    except (PayloadBuilderError, BackupFormatError) as exc:
        raise GuardedWorkflowError(
            f"could not build the existing-text candidate: {exc}",
            stage="candidate",
        ) from exc


class ExistingTextReplacementWorkflow:
    """Run one guarded replacement using injected capture and send callbacks."""

    def __init__(
        self,
        capture: CaptureCallback,
        send: SendCallback,
    ) -> None:
        if not callable(capture) or not callable(send):
            raise TypeError("capture and send callbacks are required")
        self._capture = capture
        self._send = send

    def run(
        self,
        *,
        backup_destination: Path,
        post_write_destination: Path,
        preview_report: Dict[str, Any],
        text_path: Path,
        cli_write_flag: bool,
        confirmation: str,
        cancelled: Optional[CancelledCallback] = None,
        progress: Optional[ProgressCallback] = None,
        now: Optional[object] = None,
        max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
    ) -> ExistingTextReplacementResult:
        """Execute backup → authorize → send once → read back → verify."""

        def notify(label: str, completed: int, total: int) -> None:
            if progress is not None:
                progress(label, completed, total)

        _check_cancelled(cancelled)
        notify("Preparing guarded existing-text replacement", 0, 1)
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
            if isinstance(exc, (TransferCancelledError, GuardedWorkflowError)):
                raise
            raise GuardedWorkflowError(
                f"fresh backup failed: {exc}", stage="fresh_backup"
            ) from exc

        _check_cancelled(cancelled)
        try:
            target = WriteTarget.from_preview_report(preview_report)
            transaction = build_existing_text_transaction(before, target, text_path)
        except (WriteGateError, GuardedWorkflowError) as exc:
            if isinstance(exc, GuardedWorkflowError):
                raise
            raise GuardedWorkflowError(str(exc), stage="candidate") from exc

        _check_cancelled(cancelled)
        try:
            authorization = authorize_existing_text_replacement(
                before.directory,
                transaction,
                preview_report,
                cli_write_flag=cli_write_flag,
                confirmation=confirmation,
                now=None,
                max_age_seconds=max_age_seconds,
            )
        except WriteGateError as exc:
            raise GuardedWorkflowError(str(exc), stage="authorization") from exc

        _check_cancelled(cancelled)
        notify("Authorization accepted; sending exactly once", 0, transaction.payload_length)
        try:
            completion = self._send(
                transaction,
                authorization,
                cancelled=cancelled,
                progress=progress,
            )
        except Exception as exc:
            raise GuardedWorkflowError(
                f"write stopped; do not retry automatically: {exc}",
                stage="write",
                write_started=True,
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
            verification = verify_post_write_backup(
                before,
                after.directory,
                transaction,
                now=None,
                max_age_seconds=max_age_seconds,
            )
        except Exception as exc:
            raise GuardedWorkflowError(
                f"post-write read-back failed; do not retry automatically: {exc}",
                stage="post_write_readback",
                write_started=True,
            ) from exc
        notify("Read-back verified", 1, 1)
        return ExistingTextReplacementResult(
            before_backup=before,
            after_backup=after,
            transaction=transaction,
            authorization=authorization,
            completion=completion,
            verification=verification,
        )


__all__ = [
    "ExistingTextReplacementResult",
    "ExistingTextReplacementWorkflow",
    "GuardedWorkflowError",
    "build_existing_text_transaction",
]
