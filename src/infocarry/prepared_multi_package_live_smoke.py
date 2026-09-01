"""Isolated live runner for the P15-002 four-TXT smoke path.

This module is deliberately not imported by the normal CLI or GUI.  The
read-only :func:`prepare_prepared_multi_package_live_smoke` phase creates and
seals a fresh-backup-bound candidate.  A later explicit call to
:func:`execute_prepared_multi_package_live_smoke` requires a separate owner
approval and exact confirmation phrase before it can use the established
one-shot ``AuthorizedWriteSender`` boundary.

No USB access occurs when this module is imported.  Tests inject a fake
``WriteBackend``; a future operator-reviewed runner may inject the proven
PyUSB write backend only at the separate execution boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Optional

from .backup_format import ParsedBackupBlob
from .capacity_evidence import NativeCapacityResponse
from .prepared_multi_package_gate import (
    PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE,
    PreparedMultiPackageAuthorization,
    authorize_prepared_multi_package,
)
from .prepared_package_multi_candidate import (
    PreparedMultiPackageCandidate,
    build_prepared_multi_package_candidate,
)
from .prepared_package_multi_verify import (
    PreparedMultiPackageReadback,
    verify_prepared_multi_package_readback,
)
from .protocol import TransferCancelledError
from .write_gate import (
    DEFAULT_MAX_AGE_SECONDS,
    VerifiedBackup,
    capture_and_verify_fresh_backup,
    verify_fresh_backup,
)
from .write_protocol import (
    AuthorizedWriteSender,
    WriteBackend,
    WriteFailureAssessment,
    WritePolicy,
    assess_write_failure,
)
from .write_artifact import ProspectiveWriteTransaction


P15_002_MODERN_MULTI_TXT_OWNER_APPROVAL = (
    "APPROVE P15-002 MODERN MULTI-TXT SMOKE 01"
)
P15_002_MODERN_MULTI_TXT_CONFIRMATION = PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE
P15_002_MODERN_MULTI_TXT_RUNNER_FORMAT = (
    "infocarry-p15-002-modern-multi-txt-live-runner-v1"
)

ProgressCallback = Callable[[str, int, int], None]
CancelledCallback = Callable[[], bool]
CaptureCallback = Callable[..., None]
DetectDeviceCallback = Callable[[], tuple[int, int]]
CapacityQueryCallback = Callable[[], NativeCapacityResponse]
Clock = Callable[[], float]


class PreparedMultiPackageLiveSmokeError(RuntimeError):
    """Terminal P15-002 runner error; automatic retry is never allowed."""

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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _template_items(
    package: Any,
    template: ParsedBackupBlob,
    template_item_paths: Optional[Mapping[str, tuple[str, ...]]],
) -> dict[str, tuple[str, ...]]:
    try:
        items = tuple(package.items)
    except AttributeError as exc:
        raise PreparedMultiPackageLiveSmokeError(
            "P15-002 runner requires a prepared ordered package",
            stage="package",
            state="failed",
        ) from exc
    if len(items) != 4 or any(item.kind != "txt" for item in items):
        raise PreparedMultiPackageLiveSmokeError(
            "P15-002 runner accepts exactly four TXT children",
            stage="package",
            state="failed",
        )
    paths = dict(template_item_paths or {"txt": ("root", "Template", "chapter")})
    if "txt" not in paths or any(kind not in {"txt", "bmp"} for kind in paths) or not paths["txt"]:
        raise PreparedMultiPackageLiveSmokeError(
            "P15-002 runner requires a validated TXT template path",
            stage="template",
            state="failed",
        )
    optional_bmp_path = ("root", "Template", "page")
    if optional_bmp_path in set(template.paths.values()):
        paths.setdefault("bmp", optional_bmp_path)
    return paths


def _validate_package_name(package: Any, expected_folder_name: str) -> None:
    if not isinstance(expected_folder_name, str) or not expected_folder_name:
        raise PreparedMultiPackageLiveSmokeError(
            "P15-002 runner requires an exact expected destination folder name",
            stage="package",
            state="failed",
        )
    if getattr(package, "folder_name", None) != expected_folder_name:
        raise PreparedMultiPackageLiveSmokeError(
            "package folder does not match the exact operation destination",
            stage="package",
            state="failed",
        )
    if expected_folder_name.casefold() == "ic_p15_multi_20260828_01":
        raise PreparedMultiPackageLiveSmokeError(
            "P15-002 refuses the preserved P15-001 _01 destination",
            stage="package",
            state="failed",
        )


def _validate_callbacks(
    *,
    detect_device: Optional[DetectDeviceCallback],
    query_capacity: Optional[CapacityQueryCallback],
    capture: Optional[CaptureCallback],
    preview_callback: Optional[Callable[[PreparedMultiPackageCandidate], None]] = None,
) -> None:
    callbacks = [
        (detect_device, "detect_device"),
        (query_capacity, "query_capacity"),
        (capture, "capture"),
    ]
    if preview_callback is not None:
        callbacks.append((preview_callback, "preview_callback"))
    for callback, label in callbacks:
        if callback is None or not callable(callback):
            raise PreparedMultiPackageLiveSmokeError(
                f"isolated P15-002 runner requires {label}",
                stage="preflight",
                state="failed",
            )


def _backup_identity(backup: VerifiedBackup) -> tuple[Any, ...]:
    return (
        backup.manifest_sha256,
        backup.blob_sha256,
        backup.object_count,
        backup.object_sha256_by_key,
        backup.object_filename_by_key,
        backup.device_identity,
    )


def _sealed_backup_dict(backup: VerifiedBackup) -> dict[str, Any]:
    """Return stable backup facts for a cross-process preflight seal.

    ``verified_at_utc`` records when this process re-hashed an unchanged
    archive.  It is useful audit metadata, but it is not device state and
    must not make a valid sealed preflight fail when the archive is reloaded
    and independently verified later.
    """

    result = backup.to_dict()
    result.pop("verified_at_utc", None)
    return result


def _seal_payload(
    *,
    candidate: PreparedMultiPackageCandidate,
    before_backup: VerifiedBackup,
    capacity_response: NativeCapacityResponse,
    template: ParsedBackupBlob,
    template_folder_path: tuple[str, ...],
    template_item_paths: Mapping[str, tuple[str, ...]],
    new_record_timestamp_be32: int,
    expected_folder_name: str,
) -> dict[str, Any]:
    return {
        "candidate": candidate.audit_dict(),
        "before_backup": _sealed_backup_dict(before_backup),
        "capacity_response": capacity_response.to_dict(),
        "template_sha256": _sha256(template.data),
        "template_folder_path": list(template_folder_path),
        "template_item_paths": {
            key: list(value) for key, value in sorted(template_item_paths.items())
        },
        "new_record_timestamp_be32": f"0x{new_record_timestamp_be32:08x}",
        "expected_folder_name": expected_folder_name,
    }


def _seal_sha256(**kwargs: Any) -> str:
    return _sha256(_canonical_json(_seal_payload(**kwargs)))


@dataclass(frozen=True)
class PreparedMultiPackageLivePreflight:
    """Fresh, read-only, hash-sealed P15-002 execution input."""

    candidate: PreparedMultiPackageCandidate
    before_backup: VerifiedBackup
    capacity_response: NativeCapacityResponse
    template: ParsedBackupBlob
    template_folder_path: tuple[str, ...]
    template_item_paths: tuple[tuple[str, tuple[str, ...]], ...]
    new_record_timestamp_be32: int
    expected_folder_name: str
    seal_sha256: str
    audit: Mapping[str, Any]

    def _paths(self) -> dict[str, tuple[str, ...]]:
        return dict(self.template_item_paths)

    def verify_seal(self) -> None:
        actual = _seal_sha256(
            candidate=self.candidate,
            before_backup=self.before_backup,
            capacity_response=self.capacity_response,
            template=self.template,
            template_folder_path=self.template_folder_path,
            template_item_paths=self._paths(),
            new_record_timestamp_be32=self.new_record_timestamp_be32,
            expected_folder_name=self.expected_folder_name,
        )
        if actual != self.seal_sha256:
            raise PreparedMultiPackageLiveSmokeError(
                "sealed P15-002 preflight was modified",
                stage="preflight_seal",
                state="failed",
            )

    def to_dict(self) -> dict[str, Any]:
        return dict(self.audit)


@dataclass(frozen=True)
class PreparedMultiPackageLiveSmokeResult:
    """One live-runner result after explicit completion and read-back."""

    preflight: PreparedMultiPackageLivePreflight
    candidate: PreparedMultiPackageCandidate
    authorization: PreparedMultiPackageAuthorization
    after_backup: VerifiedBackup
    completion: int
    verification: PreparedMultiPackageReadback
    audit: Mapping[str, Any]


@dataclass(frozen=True)
class _SenderAuthorization:
    """Adapt the multi-package candidate gate to the established sender API."""

    candidate: PreparedMultiPackageCandidate
    authorization: PreparedMultiPackageAuthorization
    now: Optional[datetime]
    max_age_seconds: Optional[float]

    def revalidate(self, transaction: ProspectiveWriteTransaction) -> None:
        if transaction != self.candidate.transaction:
            raise PreparedMultiPackageLiveSmokeError(
                "sender transaction differs from sealed candidate",
                stage="authorization",
                state="failed",
            )
        self.authorization.require_same_candidate(self.candidate)
        self.authorization.revalidate(
            self.candidate,
            now=self.now,
            max_age_seconds=self.max_age_seconds,
        )


class PreparedMultiPackageLiveSender:
    """One-shot adapter over the established ``AuthorizedWriteSender``.

    The adapter is intentionally separate from ``PreparedMultiFakeTransport``
    and is never imported by the normal CLI or GUI.  Tests can provide the
    established ``WriteBackend`` fake; a future isolated runner may provide
    ``PyUsbWriteBackend`` after the separate approval boundary.
    """

    def __init__(
        self,
        backend: WriteBackend,
        bulk_out_endpoint: int,
        *,
        policy: WritePolicy = WritePolicy(),
        clock: Clock = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not hasattr(backend, "control_out") or not hasattr(backend, "bulk_write"):
            raise TypeError("P15-002 live sender requires a write-capable backend")
        self._sender = AuthorizedWriteSender(
            backend,
            bulk_out_endpoint,
            policy=policy,
            clock=clock,
            sleep=sleep,
        )
        self.calls = 0

    def send(
        self,
        transaction: ProspectiveWriteTransaction,
        candidate: PreparedMultiPackageCandidate,
        authorization: PreparedMultiPackageAuthorization,
        *,
        now: Optional[datetime],
        max_age_seconds: Optional[float],
        cancelled: Optional[CancelledCallback],
        progress: Optional[ProgressCallback],
    ) -> int:
        if self.calls:
            raise PreparedMultiPackageLiveSmokeError(
                "P15-002 live sender is one-shot; a second transaction is refused",
                stage="write_guard",
                state="failed",
                write_started=False,
            )
        self.calls = 1
        bound = _SenderAuthorization(
            candidate=candidate,
            authorization=authorization,
            now=None,
            max_age_seconds=max_age_seconds,
        )
        return self._sender.send(
            transaction,
            bound,
            cancelled=cancelled,
            progress=progress,
        )


def _failure(
    message: str,
    *,
    stage: str,
    state: str,
    sequence: list[str],
    sender: Optional[PreparedMultiPackageLiveSender] = None,
    write_started: bool = False,
    candidate: Optional[PreparedMultiPackageCandidate] = None,
    authorization: Optional[PreparedMultiPackageAuthorization] = None,
    primary_error: Optional[str] = None,
) -> PreparedMultiPackageLiveSmokeError:
    audit: dict[str, Any] = {
        "format": P15_002_MODERN_MULTI_TXT_RUNNER_FORMAT,
        "state": state,
        "stage": stage,
        "write_started": write_started,
        "device_change": (
            "indeterminate_after_transaction_start"
            if write_started
            else "none_started"
        ),
        "automatic_retry_allowed": False,
        "operation_sequence": list(sequence),
    }
    if sender is not None:
        audit["sender_calls"] = sender.calls
    if primary_error is not None:
        audit["primary_error"] = primary_error
    if candidate is not None:
        audit["candidate"] = candidate.audit_dict()
    if authorization is not None:
        audit["authorization"] = authorization.to_dict()
    return PreparedMultiPackageLiveSmokeError(
        f"{message}; no automatic retry is allowed",
        stage=stage,
        state=state,
        write_started=write_started,
        audit=audit,
    )


def prepare_prepared_multi_package_live_smoke(
    *,
    backup_destination: Path,
    package: Any,
    template: ParsedBackupBlob,
    template_folder_path: tuple[str, ...] = ("root", "Template"),
    template_item_paths: Optional[Mapping[str, tuple[str, ...]]] = None,
    new_record_timestamp_be32: int,
    expected_folder_name: str,
    detect_device: DetectDeviceCallback,
    query_capacity: CapacityQueryCallback,
    capture: CaptureCallback,
    preview_callback: Callable[[PreparedMultiPackageCandidate], None],
    cancelled: Optional[CancelledCallback] = None,
    progress: Optional[ProgressCallback] = None,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> PreparedMultiPackageLivePreflight:
    """Perform only the fresh read-only P15-002 preflight and seal it."""

    _validate_package_name(package, expected_folder_name)
    if not isinstance(template, ParsedBackupBlob):
        raise PreparedMultiPackageLiveSmokeError(
            "P15-002 runner requires a parsed native TXT template",
            stage="template",
            state="failed",
        )
    paths = _template_items(package, template, template_item_paths)
    _validate_callbacks(
        detect_device=detect_device,
        query_capacity=query_capacity,
        capture=capture,
        preview_callback=preview_callback,
    )
    sequence = ["read_only_preflight"]
    try:
        if cancelled is not None and cancelled():
            raise TransferCancelledError("P15-002 preflight was cancelled")
        detected_identity = detect_device()
        sequence.append("device_detected")
        capacity_response = query_capacity()
        if not isinstance(capacity_response, NativeCapacityResponse):
            raise ValueError("capacity query did not return parsed native 0x0019 evidence")
        if capacity_response.device_identity != detected_identity:
            raise ValueError("capacity response identity differs from detected device")
        sequence.append("capacity_queried_0x0019")
    except Exception as exc:
        raise PreparedMultiPackageLiveSmokeError(
            f"P15-002 read-only device preflight failed: {exc}",
            stage="capacity_query",
            state="failed",
            audit={"operation_sequence": sequence},
        ) from exc

    try:
        before = capture_and_verify_fresh_backup(
            Path(backup_destination),
            lambda destination: capture(
                destination, cancelled=cancelled, progress=progress
            ),
            now=None,
            max_age_seconds=max_age_seconds,
        )
        if before.device_identity != tuple(
            f"0x{value:04x}" for value in capacity_response.device_identity
        ):
            raise ValueError("fresh backup identity differs from capacity evidence")
        sequence.append("fresh_complete_backup")
    except Exception as exc:
        raise PreparedMultiPackageLiveSmokeError(
            f"P15-002 fresh read-only backup failed: {exc}",
            stage="fresh_backup",
            state="failed",
            audit={"operation_sequence": sequence},
        ) from exc

    try:
        candidate = build_prepared_multi_package_candidate(
            package,
            before,
            template,
            new_record_timestamp_be32=new_record_timestamp_be32,
            native_capacity_response=capacity_response,
            template_folder_path=template_folder_path,
            template_item_paths=paths,
        )
        if not candidate.audit["candidate"]["added_paths"]:
            raise ValueError("candidate did not contain the requested destination")
        preview_callback(candidate)
        sequence.extend(["candidate_reconstructed", "preview_presented"])
    except Exception as exc:
        raise PreparedMultiPackageLiveSmokeError(
            f"P15-002 candidate preflight failed: {exc}",
            stage="candidate",
            state="failed",
            audit={"operation_sequence": sequence},
        ) from exc

    seal = _seal_sha256(
        candidate=candidate,
        before_backup=before,
        capacity_response=capacity_response,
        template=template,
        template_folder_path=template_folder_path,
        template_item_paths=paths,
        new_record_timestamp_be32=new_record_timestamp_be32,
        expected_folder_name=expected_folder_name,
    )
    sequence.append("preflight_sealed")
    audit = {
        "format": P15_002_MODERN_MULTI_TXT_RUNNER_FORMAT,
        "state": "preflight_sealed",
        "read_only": True,
        "usb_transmission_performed": False,
        "target_absent_from_fresh_backup": True,
        "preflight_seal_sha256": seal,
        "operation_sequence": sequence,
        "candidate": candidate.audit_dict(),
        "before_backup": before.to_dict(),
        "capacity_response": capacity_response.to_dict(),
        "automatic_retry_allowed": False,
    }
    return PreparedMultiPackageLivePreflight(
        candidate=candidate,
        before_backup=before,
        capacity_response=capacity_response,
        template=template,
        template_folder_path=tuple(template_folder_path),
        template_item_paths=tuple(sorted(paths.items())),
        new_record_timestamp_be32=new_record_timestamp_be32,
        expected_folder_name=expected_folder_name,
        seal_sha256=seal,
        audit=audit,
    )


def execute_prepared_multi_package_live_smoke(
    preflight: PreparedMultiPackageLivePreflight,
    *,
    post_operation_destination: Path,
    owner_approval: str,
    confirmation: str,
    detect_device: DetectDeviceCallback,
    query_capacity: CapacityQueryCallback,
    capture: CaptureCallback,
    sender: PreparedMultiPackageLiveSender,
    cancelled: Optional[CancelledCallback] = None,
    progress: Optional[ProgressCallback] = None,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> PreparedMultiPackageLiveSmokeResult:
    """Execute one sealed preflight after separate approval and confirmation."""

    if not isinstance(preflight, PreparedMultiPackageLivePreflight):
        raise PreparedMultiPackageLiveSmokeError(
            "P15-002 execution requires a sealed read-only preflight",
            stage="preflight",
            state="failed",
        )
    if owner_approval != P15_002_MODERN_MULTI_TXT_OWNER_APPROVAL:
        raise PreparedMultiPackageLiveSmokeError(
            "separate P15-002 owner approval was not accepted; no transaction attempted",
            stage="approval",
            state="failed",
        )
    if confirmation != P15_002_MODERN_MULTI_TXT_CONFIRMATION:
        raise PreparedMultiPackageLiveSmokeError(
            "P15-002 exact confirmation phrase was not accepted; no transaction attempted",
            stage="approval",
            state="failed",
        )
    if not isinstance(sender, PreparedMultiPackageLiveSender):
        raise PreparedMultiPackageLiveSmokeError(
            "P15-002 execution requires the isolated one-shot live sender",
            stage="sender",
            state="failed",
        )
    _validate_callbacks(
        detect_device=detect_device,
        query_capacity=query_capacity,
        capture=capture,
    )
    sequence = ["preflight_seal_verified", "owner_approval", "confirmation_phrase"]
    try:
        preflight.verify_seal()
        detected_identity = detect_device()
        if detected_identity != preflight.capacity_response.device_identity:
            raise ValueError("device identity differs from sealed preflight")
        capacity_response = query_capacity()
        if capacity_response != preflight.capacity_response:
            raise ValueError("capacity response differs from sealed preflight")
        sequence.extend(["device_revalidated", "capacity_revalidated"])
    except PreparedMultiPackageLiveSmokeError:
        raise
    except Exception as exc:
        raise _failure(
            f"P15-002 execution preflight revalidation failed: {exc}",
            stage="preflight_revalidation",
            state="failed",
            sequence=sequence,
            sender=sender,
            primary_error=str(exc),
        ) from exc

    try:
        current_backup = verify_fresh_backup(
            preflight.before_backup.directory,
            now=None,
            max_age_seconds=max_age_seconds,
        )
        if _backup_identity(current_backup) != _backup_identity(preflight.before_backup):
            raise ValueError("sealed fresh backup changed before execution")
        sequence.append("fresh_backup_revalidated")
        candidate = build_prepared_multi_package_candidate(
            preflight.candidate.package,
            preflight.before_backup,
            preflight.template,
            new_record_timestamp_be32=preflight.new_record_timestamp_be32,
            native_capacity_response=preflight.capacity_response,
            template_folder_path=preflight.template_folder_path,
            template_item_paths=preflight._paths(),
        )
        if candidate.audit_dict() != preflight.candidate.audit_dict():
            raise ValueError("rebuilt candidate differs from sealed preflight")
        sequence.append("candidate_reconstructed")
    except Exception as exc:
        raise _failure(
            f"P15-002 candidate revalidation failed: {exc}",
            stage="candidate_revalidation",
            state="failed",
            sequence=sequence,
            sender=sender,
            primary_error=str(exc),
        ) from exc

    try:
        authorization = authorize_prepared_multi_package(
            candidate,
            confirmation=confirmation,
        )
        authorization.require_same_candidate(candidate)
        sequence.append("authorization_sealed")
        if cancelled is not None and cancelled():
            raise TransferCancelledError(
                "P15-002 execution cancelled before transaction start"
            )
    except TransferCancelledError as exc:
        raise _failure(
            str(exc),
            stage="pre_transaction",
            state="cancelled_before_transaction",
            sequence=sequence,
            sender=sender,
            candidate=candidate,
        ) from exc
    except Exception as exc:
        raise _failure(
            f"P15-002 authorization failed: {exc}",
            stage="authorization",
            state="failed",
            sequence=sequence,
            sender=sender,
            candidate=candidate,
            primary_error=str(exc),
        ) from exc

    try:
        completion = sender.send(
            candidate.transaction,
            candidate,
            authorization,
            now=None,
            max_age_seconds=max_age_seconds,
            cancelled=cancelled,
            progress=progress,
        )
        sequence.append("single_0x101b_transaction")
    except Exception as exc:
        assessment: WriteFailureAssessment = assess_write_failure(exc)
        if not isinstance(getattr(exc, "write_failure_assessment", None), WriteFailureAssessment):
            assessment = WriteFailureAssessment(
                primary_error=str(exc),
                write_started=False,
                device_outcome="not_started",
            )
        state = (
            "indeterminate_after_transaction_start"
            if assessment.device_outcome == "indeterminate"
            else "failed"
        )
        raise _failure(
            f"P15-002 transaction stopped: {exc}",
            stage="write",
            state=state,
            sequence=sequence,
            sender=sender,
            write_started=assessment.write_started,
            candidate=candidate,
            authorization=authorization,
            primary_error=assessment.primary_error,
        ) from exc

    if isinstance(completion, bool) or not isinstance(completion, int) or completion != 0:
        value = repr(completion) if not isinstance(completion, int) else f"0x{completion:04x}"
        raise _failure(
            f"P15-002 completion {value} is not 0x0000",
            stage="write_completion",
            state="failed",
            sequence=sequence,
            sender=sender,
            write_started=True,
            candidate=candidate,
            authorization=authorization,
            primary_error=f"completion={value}",
        )
    sequence.append("completion_0x0000")

    try:
        after = capture_and_verify_fresh_backup(
            Path(post_operation_destination),
            lambda destination: capture(
                destination, cancelled=cancelled, progress=progress
            ),
            now=None,
            max_age_seconds=max_age_seconds,
        )
        sequence.append("fresh_post_operation_backup")
        verification = verify_prepared_multi_package_readback(
            candidate,
            after.directory,
            completion=completion,
            now=None,
            max_age_seconds=max_age_seconds,
        )
        sequence.append("independent_readback_verification")
    except Exception as exc:
        raise _failure(
            f"P15-002 post-operation read-back failed: {exc}",
            stage="post_operation_readback",
            state="indeterminate_after_transaction_start",
            sequence=sequence,
            sender=sender,
            write_started=True,
            candidate=candidate,
            authorization=authorization,
            primary_error=str(exc),
        ) from exc

    authorization_audit = authorization.to_dict()
    authorization_audit["state"] = "authorized_for_live_transport"
    authorization_audit["owner_approval"] = P15_002_MODERN_MULTI_TXT_OWNER_APPROVAL
    audit = {
        "format": P15_002_MODERN_MULTI_TXT_RUNNER_FORMAT,
        "state": "readback_verified",
        "usb_transmission_performed": True,
        "candidate": candidate.audit_dict(),
        "preflight_seal_sha256": preflight.seal_sha256,
        "authorization": authorization_audit,
        "completion": "0x0000",
        "verification": verification.to_dict(),
        "workflow": {
            "isolated_live_runner": True,
            "device_change": "completed_and_verified",
            "sender_calls": sender.calls,
            "automatic_retry_allowed": False,
            "operation_sequence": sequence,
        },
    }
    return PreparedMultiPackageLiveSmokeResult(
        preflight=preflight,
        candidate=candidate,
        authorization=authorization,
        after_backup=after,
        completion=completion,
        verification=verification,
        audit=audit,
    )


__all__ = [
    "P15_002_MODERN_MULTI_TXT_CONFIRMATION",
    "P15_002_MODERN_MULTI_TXT_OWNER_APPROVAL",
    "P15_002_MODERN_MULTI_TXT_RUNNER_FORMAT",
    "PreparedMultiPackageLivePreflight",
    "PreparedMultiPackageLiveSender",
    "PreparedMultiPackageLiveSmokeError",
    "PreparedMultiPackageLiveSmokeResult",
    "execute_prepared_multi_package_live_smoke",
    "prepare_prepared_multi_package_live_smoke",
]
