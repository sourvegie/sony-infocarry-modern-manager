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
import json
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional
from uuid import uuid4

from .backup import parse_grouped_values_response, parse_offset_list_response
from .backup_format import BackupFormatError, parse_backup_blob
from .backup_state_identity import derive_backup_state_identity
from .execution_claim_store import (
    ExecutionClaimAlreadyConsumedError,
    ExecutionClaimRecord,
    ExecutionClaimStoreError,
    SenderInFlightHandle,
    SenderInFlightRecord,
    PERSISTENT_EXECUTION_CLAIM_PERSISTENCE_MODE,
    PERSISTENT_EXECUTION_CLAIM_STORE_FORMAT,
)
from .indeterminate_write_lock import IndeterminateWriteLockError
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
from .write_protocol import WriteFailureAssessment, assess_write_failure
from .write_safety_boundary import PersistentWriteSafetyOwner


ProgressCallback = Callable[[str, int, int], None]
CancelledCallback = Callable[[], bool]
CaptureCallback = Callable[..., None]
SendCallback = Callable[..., int]


class GuardedWorkflowError(RuntimeError):
    """Raised when a guarded replacement stops at a named safety stage."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        write_started: bool = False,
        state: str = "failed",
        audit: Optional[Mapping[str, Any]] = None,
    ):
        super().__init__(message)
        self.stage = stage
        self.write_started = write_started
        self.state = state
        self.automatic_retry_allowed = False
        self.audit = dict(audit or {})
        self.audit.setdefault("automatic_retry_allowed", False)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _replacement_claim_bindings(
    before: VerifiedBackup,
    transaction: ProspectiveWriteTransaction,
    authorization: WriteAuthorization,
    preview_report: Mapping[str, Any],
) -> dict[str, str]:
    """Bind one replacement to the same hash-only claim schema as Library."""

    baseline_identity = derive_backup_state_identity(before).sha256
    candidate_blob_sha256 = hashlib.sha256(
        transaction.ranges[4] + transaction.ranges[7]
    ).hexdigest()
    transaction_sha256 = transaction.concatenated_sha256
    authorization_sha256 = _sha256_json(
        {
            "format": "infocarry-existing-text-replacement-authorization-binding-v1",
            "transaction_sha256": transaction_sha256,
            "confirmation_phrase": authorization.confirmation_phrase,
            "cli_write_flag": authorization.cli_write_flag,
            "fixed_state_sha256": list(authorization.fixed_state_sha256),
            "target": (
                None
                if authorization.target is None
                else authorization.target.to_dict()
            ),
        }
    )
    core_seal_sha256 = _sha256_json(
        {
            "format": "infocarry-existing-text-replacement-core-preflight-v1",
            "preview": preview_report,
        }
    )
    workflow = preview_report.get("workflow")
    operation_id = (
        workflow.get("operation_id")
        if isinstance(workflow, Mapping)
        else None
    )
    if not isinstance(operation_id, str) or not operation_id:
        operation_id = core_seal_sha256
    preflight_seal_sha256 = _sha256_json(
        {
            "format": "infocarry-existing-text-replacement-preflight-v1",
            "core_preflight_seal_sha256": core_seal_sha256,
            "operation_id": operation_id,
            "candidate_blob_sha256": candidate_blob_sha256,
            "transaction_sha256": transaction_sha256,
        }
    )
    # Replacement preserves its established operation semantics and does not
    # query native capacity.  The explicit typed binding keeps that fact in
    # the shared claim record rather than pretending a capacity response was
    # observed.
    capacity_binding = _sha256_json(
        {
            "format": "infocarry-existing-text-replacement-capacity-binding-v1",
            "status": "not_queried_by_existing_replacement_semantics",
        }
    )
    return {
        "preflight_seal_sha256": preflight_seal_sha256,
        "core_preflight_seal_sha256": core_seal_sha256,
        "candidate_blob_sha256": candidate_blob_sha256,
        "transaction_sha256": transaction_sha256,
        "authorization_sha256": authorization_sha256,
        "baseline_state_identity_sha256": baseline_identity,
        "capacity_response_sha256": capacity_binding,
    }


def _replacement_claim_audit(
    claim: Optional[ExecutionClaimRecord],
    *,
    marker: Optional[Any] = None,
    marker_state: str = "not_started",
    marker_resolved: bool = False,
    attempted_bindings: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    if claim is None:
        result: dict[str, Any] = {
            "format": PERSISTENT_EXECUTION_CLAIM_STORE_FORMAT,
            "store_format": PERSISTENT_EXECUTION_CLAIM_STORE_FORMAT,
            "persistence_mode": PERSISTENT_EXECUTION_CLAIM_PERSISTENCE_MODE,
            "committed": False,
            "state": "not_committed",
            "claim_id": None,
            "sender_marker": {
                "committed": False,
                "state": "not_started",
                "resolved": False,
            },
        }
        if attempted_bindings is not None:
            result.update(dict(attempted_bindings))
        return result
    sender_marker = (
        marker.to_dict()
        if hasattr(marker, "to_dict")
        else {
            "committed": False,
            "state": marker_state,
            "resolved": marker_resolved,
        }
    )
    sender_marker["committed"] = marker is not None
    sender_marker["state"] = marker_state
    sender_marker["resolved"] = marker_resolved
    result = claim.to_dict()
    result["sender_marker"] = sender_marker
    return result


@dataclass(frozen=True)
class ExistingTextReplacementResult:
    """Evidence returned after one send and an independent read-back."""

    before_backup: VerifiedBackup
    after_backup: VerifiedBackup
    transaction: ProspectiveWriteTransaction
    authorization: WriteAuthorization
    completion: int
    verification: PostWriteVerification
    execution_claim: ExecutionClaimRecord
    sender_marker: SenderInFlightRecord

    def to_dict(self) -> Dict[str, Any]:
        return {
            "completion": f"0x{self.completion:04x}",
            "before_backup": self.before_backup.to_dict(),
            "after_backup": self.after_backup.to_dict(),
            "authorization": self.authorization.to_dict(),
            "verification": self.verification.to_dict(),
            "execution_claim": _replacement_claim_audit(
                self.execution_claim,
                marker=self.sender_marker,
                marker_state="resolved",
                marker_resolved=True,
            ),
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
    """Run one replacement behind the shared persistent safety boundary."""

    def __init__(
        self,
        capture: CaptureCallback,
        send: SendCallback,
        safety_owner: Optional[PersistentWriteSafetyOwner] = None,
    ) -> None:
        if not callable(capture) or not callable(send):
            raise TypeError("capture and send callbacks are required")
        self._capture = capture
        self._send = send
        self._safety_owner = safety_owner

    def _persist_indeterminate(
        self,
        error: GuardedWorkflowError,
        *,
        attempt_id: str,
        evidence_root: Path,
    ) -> None:
        if self._safety_owner is None:
            raise GuardedWorkflowError(
                "indeterminate replacement outcome has no persistent safety owner; "
                "writes remain blocked",
                stage="indeterminate_lock",
                state="indeterminate_after_transaction_start",
                write_started=True,
                audit={"original_error": str(error)},
            ) from error
        try:
            self._safety_owner.record_indeterminate(
                error,
                attempt_id=attempt_id,
                evidence_root=evidence_root,
                operation_label="guarded-replacement",
            )
        except Exception as lock_error:
            raise GuardedWorkflowError(
                f"indeterminate replacement outcome could not be persisted in the "
                f"global write lock: {lock_error}",
                stage="indeterminate_lock",
                state="indeterminate_after_transaction_start",
                write_started=True,
                audit={
                    "original_error": str(error),
                    "lock_error": str(lock_error),
                },
            ) from error

    def _blocked_by_safety(
        self,
        error: BaseException,
        *,
        stage: str = "write_guard",
    ) -> GuardedWorkflowError:
        return GuardedWorkflowError(
            f"existing-text replacement is blocked by application-wide write safety: {error}",
            stage=stage,
            state="blocked_by_safety",
            write_started=False,
        )

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

        if not isinstance(self._safety_owner, PersistentWriteSafetyOwner):
            raise GuardedWorkflowError(
                "existing-text replacement requires the shared persistent application-wide "
                "write safety owner",
                stage="write_guard",
                state="blocked_by_safety",
            )
        attempt_id = uuid4().hex
        evidence_root = Path(backup_destination).expanduser().resolve().parent
        try:
            self._safety_owner.assert_execution_boundary_available()
        except Exception as exc:
            raise self._blocked_by_safety(exc) from exc

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
            self._safety_owner.assert_execution_boundary_available()
        except Exception as exc:
            raise self._blocked_by_safety(exc) from exc
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
        try:
            self._safety_owner.assert_execution_boundary_available()
            claim_bindings = _replacement_claim_bindings(
                before,
                transaction,
                authorization,
                preview_report,
            )
            claim = self._safety_owner.consume_execution_claim(claim_bindings)
        except ExecutionClaimAlreadyConsumedError as exc:
            raise GuardedWorkflowError(
                "this existing-text replacement operation was already consumed; replay is rejected",
                stage="write_guard",
                state="failed",
                audit={
                    "execution_claim": _replacement_claim_audit(
                        None,
                        attempted_bindings=claim_bindings
                        if "claim_bindings" in locals()
                        else None,
                    )
                },
            ) from exc
        except Exception as exc:
            raise GuardedWorkflowError(
                f"existing-text replacement durable claim was not committed: {exc}",
                stage="write_guard",
                state="failed",
                audit={
                    "execution_claim": _replacement_claim_audit(
                        None,
                        attempted_bindings=claim_bindings
                        if "claim_bindings" in locals()
                        else None,
                    )
                },
            ) from exc

        claim_audit = _replacement_claim_audit(claim)
        sender_marker: Optional[SenderInFlightHandle] = None
        try:
            sender_marker = self._safety_owner.mark_sender_start(
                claim,
                attempt_id=attempt_id,
                evidence_root=str(evidence_root),
                operation_label="guarded-replacement",
            )
            claim_audit = _replacement_claim_audit(
                claim,
                marker=sender_marker.record,
                marker_state="in_flight",
            )
        except Exception as exc:
            raise GuardedWorkflowError(
                f"existing-text replacement sender-start marker was not committed: {exc}",
                stage="write_guard",
                state="failed",
                write_started=False,
                audit={"execution_claim": claim_audit},
            ) from exc

        notify("Authorization accepted; sending exactly once", 0, transaction.payload_length)
        try:
            completion = self._send(
                transaction,
                authorization,
                cancelled=cancelled,
                progress=progress,
            )
        except Exception as exc:
            assessment = assess_write_failure(exc)
            if not isinstance(
                getattr(exc, "write_failure_assessment", None), WriteFailureAssessment
            ):
                assessment = WriteFailureAssessment(
                    primary_error=str(exc),
                    write_started=False,
                    device_outcome="not_started",
                )
            if assessment.device_outcome != "indeterminate":
                try:
                    self._safety_owner.resolve_sender_terminal(
                        sender_marker,
                        resolution=(
                            "determinate_no_start"
                            if not assessment.write_started
                            else "determinate_completion_failure"
                        ),
                    )
                    claim_audit = _replacement_claim_audit(
                        claim,
                        marker=sender_marker.record,
                        marker_state="resolved",
                        marker_resolved=True,
                    )
                except ExecutionClaimStoreError:
                    # Keep the marker active.  A later guarded attempt will
                    # promote it to the installation-wide lock.
                    pass
            error = GuardedWorkflowError(
                f"write stopped; do not retry automatically: {exc}",
                stage="write",
                state=(
                    "indeterminate_after_transaction_start"
                    if assessment.device_outcome == "indeterminate"
                    else "failed"
                ),
                write_started=assessment.write_started,
                audit={
                    "execution_claim": claim_audit,
                    "write_failure": assessment.to_dict(),
                },
            )
            if assessment.device_outcome == "indeterminate":
                self._persist_indeterminate(
                    error,
                    attempt_id=attempt_id,
                    evidence_root=evidence_root,
                )
            raise error from exc

        if (
            isinstance(completion, bool)
            or not isinstance(completion, int)
            or completion != 0
        ):
            value = repr(completion) if not isinstance(completion, int) else f"0x{completion:04x}"
            if isinstance(completion, int) and not isinstance(completion, bool):
                try:
                    self._safety_owner.resolve_sender_terminal(
                        sender_marker,
                        resolution="determinate_completion_failure",
                    )
                    claim_audit = _replacement_claim_audit(
                        claim,
                        marker=sender_marker.record,
                        marker_state="resolved",
                        marker_resolved=True,
                    )
                except ExecutionClaimStoreError:
                    pass
            error = GuardedWorkflowError(
                f"write completion {value} is not 0x0000; do not retry automatically",
                stage="write_completion",
                state=(
                    "indeterminate_after_transaction_start"
                    if isinstance(completion, bool) or not isinstance(completion, int)
                    else "failed"
                ),
                write_started=True,
                audit={"execution_claim": claim_audit},
            )
            if error.state == "indeterminate_after_transaction_start":
                self._persist_indeterminate(
                    error,
                    attempt_id=attempt_id,
                    evidence_root=evidence_root,
                )
            raise error

        try:
            after = capture_and_verify_fresh_backup(
                post_write_destination,
                lambda destination: self._capture(
                    destination, cancelled=cancelled, progress=progress
                ),
                now=None,
                max_age_seconds=max_age_seconds,
            )
        except Exception as exc:
            error = GuardedWorkflowError(
                f"post-write read-back failed; do not retry automatically: {exc}",
                stage="post_write_readback",
                state="indeterminate_after_transaction_start",
                write_started=True,
                audit={"execution_claim": claim_audit},
            )
            self._persist_indeterminate(
                error,
                attempt_id=attempt_id,
                evidence_root=evidence_root,
            )
            raise error from exc
        try:
            verification = verify_post_write_backup(
                before,
                after.directory,
                transaction,
                now=None,
                max_age_seconds=max_age_seconds,
            )
            self._safety_owner.resolve_sender_terminal(
                sender_marker,
                resolution="verified_terminal_success",
            )
        except Exception as exc:
            error = GuardedWorkflowError(
                f"post-write read-back or safety closure failed; do not retry automatically: {exc}",
                stage="post_write_readback",
                state="indeterminate_after_transaction_start",
                write_started=True,
                audit={"execution_claim": claim_audit},
            )
            self._persist_indeterminate(
                error,
                attempt_id=attempt_id,
                evidence_root=evidence_root,
            )
            raise error from exc
        notify("Read-back verified", 1, 1)
        return ExistingTextReplacementResult(
            before_backup=before,
            after_backup=after,
            transaction=transaction,
            authorization=authorization,
            completion=completion,
            verification=verification,
            execution_claim=claim,
            sender_marker=sender_marker.record,
        )


__all__ = [
    "ExistingTextReplacementResult",
    "ExistingTextReplacementWorkflow",
    "GuardedWorkflowError",
    "build_existing_text_transaction",
]
