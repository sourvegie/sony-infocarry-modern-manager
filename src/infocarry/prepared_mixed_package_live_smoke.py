"""Isolated P16-002 host-readiness boundary for one mixed package.

This module is intentionally absent from the normal CLI and GUI import graph.
It accepts a prepared, exact TXT/BMP/TXT package, performs a read-only
fresh-backup preflight, and seals the candidate for a later operation-specific
task.  The sender is an injected ``WriteBackend`` adapter only; this task does
not open USB or perform a device-changing operation.

The native P16-001 result supports this exact flat shape and its type-specific
prefixes.  It does not support arbitrary mixed packages, nesting, batching, or
generalized timestamp rules.  The constants and package checks below keep the
future boundary limited to the one reviewed P16-002 operation.
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
from .prepared_media_package import PreparedMediaPackage
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


P16_002_TARGET_FOLDER = "IC_P16_MIXED_20260830_02"
P16_002_NATIVE_TEMPLATE_FOLDER_PATH = (
    "root",
    "IC_P16_MIXED_20260830_01",
)
P16_002_NATIVE_TEMPLATE_ITEM_PATHS = {
    "txt": (*P16_002_NATIVE_TEMPLATE_FOLDER_PATH, "01-introduction"),
    "bmp": (*P16_002_NATIVE_TEMPLATE_FOLDER_PATH, "02-page-01"),
}
P16_002_MODERN_MIXED_OWNER_APPROVAL = (
    "APPROVE P16-002 MODERN MIXED TXT BMP SMOKE 01"
)
# Reuse the established exact multi-child confirmation vocabulary.  The
# operation-specific owner approval remains a separate P16-002 gate.
P16_002_MODERN_MIXED_CONFIRMATION = PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE
P16_002_MODERN_MIXED_RUNNER_FORMAT = (
    "infocarry-p16-002-modern-mixed-txt-bmp-live-runner-v1"
)

ProgressCallback = Callable[[str, int, int], None]
CancelledCallback = Callable[[], bool]
CaptureCallback = Callable[..., None]
DetectDeviceCallback = Callable[[], tuple[int, int]]
CapacityQueryCallback = Callable[[], NativeCapacityResponse]


class P16MixedPackageLiveSmokeError(RuntimeError):
    """Terminal P16-002 error; automatic retry is never allowed."""

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


def _validate_package(package: Any, expected_folder_name: str) -> None:
    if not isinstance(package, PreparedMediaPackage):
        raise P16MixedPackageLiveSmokeError(
            "P16-002 requires a prepared typed TXT/BMP package",
            stage="package",
            state="failed",
        )
    if expected_folder_name != P16_002_TARGET_FOLDER:
        raise P16MixedPackageLiveSmokeError(
            "P16-002 destination is fixed to the reviewed _02 folder",
            stage="package",
            state="failed",
        )
    if package.folder_name != expected_folder_name:
        raise P16MixedPackageLiveSmokeError(
            "package folder does not match the exact P16-002 destination",
            stage="package",
            state="failed",
        )
    items = tuple(package.items)
    expected_names = (
        "01-introduction.txt",
        "02-page-01.bmp",
        "03-ending.txt",
    )
    if len(items) != 3 or tuple(item.name for item in items) != expected_names:
        raise P16MixedPackageLiveSmokeError(
            "P16-002 requires exactly introduction TXT, BMP page, ending TXT in order",
            stage="package",
            state="failed",
        )
    if tuple(item.kind for item in items) != ("txt", "bmp", "txt"):
        raise P16MixedPackageLiveSmokeError(
            "P16-002 package kinds must be TXT/BMP/TXT",
            stage="package",
            state="failed",
        )


def _validate_template(
    template: ParsedBackupBlob,
    template_folder_path: tuple[str, ...],
    template_item_paths: Optional[Mapping[str, tuple[str, ...]]],
) -> dict[str, tuple[str, ...]]:
    if not isinstance(template, ParsedBackupBlob):
        raise P16MixedPackageLiveSmokeError(
            "P16-002 requires a parsed native mixed-package template",
            stage="template",
            state="failed",
        )
    paths = dict(template_item_paths or {})
    if tuple(template_folder_path) != P16_002_NATIVE_TEMPLATE_FOLDER_PATH:
        raise P16MixedPackageLiveSmokeError(
            "P16-002 template folder is not the reviewed native _01 template",
            stage="template",
            state="failed",
        )
    if paths != P16_002_NATIVE_TEMPLATE_ITEM_PATHS:
        raise P16MixedPackageLiveSmokeError(
            "P16-002 template items are not the reviewed native TXT/BMP records",
            stage="template",
            state="failed",
        )
    if "txt" not in paths or "bmp" not in paths:
        raise P16MixedPackageLiveSmokeError(
            "P16-002 requires validated native TXT and BMP template paths",
            stage="template",
            state="failed",
        )
    if len(template_folder_path) != 2 or template_folder_path[0] != "root":
        raise P16MixedPackageLiveSmokeError(
            "P16-002 template folder must be a root-level native folder",
            stage="template",
            state="failed",
        )
    for kind in ("txt", "bmp"):
        if paths[kind] not in set(template.paths.values()):
            raise P16MixedPackageLiveSmokeError(
                f"P16-002 native {kind.upper()} template path is not present",
                stage="template",
                state="failed",
            )
    return paths


def _validate_callbacks(
    *,
    detect_device: Optional[DetectDeviceCallback],
    query_capacity: Optional[CapacityQueryCallback],
    capture: Optional[CaptureCallback],
    preview_callback: Optional[Callable[[PreparedMultiPackageCandidate], None]] = None,
) -> None:
    values = (
        (detect_device, "detect_device"),
        (query_capacity, "query_capacity"),
        (capture, "capture"),
    )
    if preview_callback is not None:
        values += ((preview_callback, "preview_callback"),)
    for callback, label in values:
        if callback is None or not callable(callback):
            raise P16MixedPackageLiveSmokeError(
                f"P16-002 isolated runner requires {label}",
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
    result = backup.to_dict()
    # This is an audit observation, not device state.  It must not invalidate
    # a valid preflight when the unchanged archive is re-verified later.
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
        "format": P16_002_MODERN_MIXED_RUNNER_FORMAT,
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
class P16MixedPackageLivePreflight:
    """Fresh read-only P16-002 preflight bound to one exact package."""

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
            raise P16MixedPackageLiveSmokeError(
                "sealed P16-002 preflight was modified",
                stage="preflight_seal",
                state="failed",
            )

    def to_dict(self) -> dict[str, Any]:
        return dict(self.audit)


@dataclass(frozen=True)
class P16MixedPackageLiveSmokeResult:
    """Successful fake/approved execution result after independent read-back."""

    preflight: P16MixedPackageLivePreflight
    candidate: PreparedMultiPackageCandidate
    authorization: PreparedMultiPackageAuthorization
    after_backup: VerifiedBackup
    completion: int
    verification: PreparedMultiPackageReadback
    audit: Mapping[str, Any]


@dataclass(frozen=True)
class _SenderAuthorization:
    candidate: PreparedMultiPackageCandidate
    authorization: PreparedMultiPackageAuthorization
    now: Optional[datetime]
    max_age_seconds: Optional[float]

    def revalidate(self, transaction: ProspectiveWriteTransaction) -> None:
        if transaction != self.candidate.transaction:
            raise P16MixedPackageLiveSmokeError(
                "sender transaction differs from the sealed P16-002 candidate",
                stage="authorization",
                state="failed",
            )
        self.authorization.require_same_candidate(self.candidate)
        self.authorization.revalidate(
            self.candidate,
            now=self.now,
            max_age_seconds=self.max_age_seconds,
        )


class P16MixedPackageLiveSender:
    """One-shot adapter over ``AuthorizedWriteSender`` for injected testing."""

    def __init__(
        self,
        backend: WriteBackend,
        bulk_out_endpoint: int,
        *,
        policy: WritePolicy = WritePolicy(),
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not all(hasattr(backend, name) for name in ("control_out", "control_in", "bulk_write")):
            raise TypeError("P16-002 sender requires a write-capable injected backend")
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
        _validate_package(candidate.package, P16_002_TARGET_FOLDER)
        if self.calls:
            raise P16MixedPackageLiveSmokeError(
                "P16-002 sender is one-shot; a second transaction is refused",
                stage="write_guard",
                state="failed",
            )
        self.calls = 1
        bound = _SenderAuthorization(
            candidate=candidate,
            authorization=authorization,
            now=now,
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
    sender: Optional[P16MixedPackageLiveSender] = None,
    write_started: bool = False,
    candidate: Optional[PreparedMultiPackageCandidate] = None,
    authorization: Optional[PreparedMultiPackageAuthorization] = None,
    primary_error: Optional[str] = None,
) -> P16MixedPackageLiveSmokeError:
    audit: dict[str, Any] = {
        "format": P16_002_MODERN_MIXED_RUNNER_FORMAT,
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
    return P16MixedPackageLiveSmokeError(
        f"{message}; no automatic retry is allowed",
        stage=stage,
        state=state,
        write_started=write_started,
        audit=audit,
    )


def prepare_p16_mixed_package_live_smoke(
    *,
    backup_destination: Path,
    package: PreparedMediaPackage,
    template: ParsedBackupBlob,
    template_folder_path: tuple[str, ...],
    template_item_paths: Mapping[str, tuple[str, ...]],
    new_record_timestamp_be32: int,
    expected_folder_name: str = P16_002_TARGET_FOLDER,
    detect_device: DetectDeviceCallback,
    query_capacity: CapacityQueryCallback,
    capture: CaptureCallback,
    preview_callback: Callable[[PreparedMultiPackageCandidate], None],
    cancelled: Optional[CancelledCallback] = None,
    progress: Optional[ProgressCallback] = None,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> P16MixedPackageLivePreflight:
    """Perform only the read-only P16-002 preflight and seal its bindings."""

    _validate_package(package, expected_folder_name)
    paths = _validate_template(template, template_folder_path, template_item_paths)
    _validate_callbacks(
        detect_device=detect_device,
        query_capacity=query_capacity,
        capture=capture,
        preview_callback=preview_callback,
    )
    sequence = ["read_only_preflight"]
    try:
        if cancelled is not None and cancelled():
            raise TransferCancelledError("P16-002 preflight was cancelled")
        detected_identity = detect_device()
        capacity_response = query_capacity()
        if not isinstance(capacity_response, NativeCapacityResponse):
            raise ValueError("capacity query did not return parsed native 0x0019 evidence")
        if capacity_response.device_identity != detected_identity:
            raise ValueError("capacity response identity differs from detected device")
        sequence.extend(["device_detected", "capacity_queried_0x0019"])
    except Exception as exc:
        raise P16MixedPackageLiveSmokeError(
            f"P16-002 read-only identity/capacity preflight failed: {exc}",
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
            now=now,
            max_age_seconds=max_age_seconds,
        )
        if before.device_identity != tuple(
            f"0x{value:04x}" for value in capacity_response.device_identity
        ):
            raise ValueError("fresh backup identity differs from capacity evidence")
        sequence.append("fresh_complete_backup_verified")
    except Exception as exc:
        raise P16MixedPackageLiveSmokeError(
            f"P16-002 fresh read-only backup failed: {exc}",
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
        preview_callback(candidate)
        sequence.extend(["candidate_reconstructed", "preview_presented"])
    except Exception as exc:
        raise P16MixedPackageLiveSmokeError(
            f"P16-002 candidate preflight failed: {exc}",
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
        "format": P16_002_MODERN_MIXED_RUNNER_FORMAT,
        "state": "preflight_sealed",
        "read_only": True,
        "hardware_transaction_performed": False,
        "target_absent_from_fresh_backup": True,
        "preflight_seal_sha256": seal,
        "operation_sequence": sequence,
        "candidate": candidate.audit_dict(),
        "before_backup": before.to_dict(),
        "capacity_response": capacity_response.to_dict(),
        "timestamp_policy": {
            "existing_records": "preserve_exactly",
            "new_records": "one_explicit_operation_timestamp",
            "legacy_global_rewrite_reproduced": False,
        },
        "automatic_retry_allowed": False,
    }
    return P16MixedPackageLivePreflight(
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


def execute_p16_mixed_package_live_smoke(
    preflight: P16MixedPackageLivePreflight,
    *,
    post_operation_destination: Path,
    owner_approval: str,
    confirmation: str,
    detect_device: DetectDeviceCallback,
    query_capacity: CapacityQueryCallback,
    capture: CaptureCallback,
    sender: P16MixedPackageLiveSender,
    cancelled: Optional[CancelledCallback] = None,
    progress: Optional[ProgressCallback] = None,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> P16MixedPackageLiveSmokeResult:
    """Execute one sealed P16-002 preflight after a later approval boundary."""

    if not isinstance(preflight, P16MixedPackageLivePreflight):
        raise P16MixedPackageLiveSmokeError(
            "P16-002 execution requires a sealed read-only preflight",
            stage="preflight",
            state="failed",
        )
    if owner_approval != P16_002_MODERN_MIXED_OWNER_APPROVAL:
        raise P16MixedPackageLiveSmokeError(
            "separate P16-002 owner approval was not accepted; no transaction attempted",
            stage="approval",
            state="failed",
        )
    if confirmation != P16_002_MODERN_MIXED_CONFIRMATION:
        raise P16MixedPackageLiveSmokeError(
            "P16-002 exact confirmation phrase was not accepted; no transaction attempted",
            stage="approval",
            state="failed",
        )
    if not isinstance(sender, P16MixedPackageLiveSender):
        raise P16MixedPackageLiveSmokeError(
            "P16-002 execution requires its isolated one-shot sender",
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
        if detect_device() != preflight.capacity_response.device_identity:
            raise ValueError("device identity differs from sealed preflight")
        capacity_response = query_capacity()
        if capacity_response != preflight.capacity_response:
            raise ValueError("fresh 0x0019 capacity response differs from sealed preflight")
        sequence.extend(["device_revalidated", "capacity_revalidated"])
    except P16MixedPackageLiveSmokeError:
        raise
    except Exception as exc:
        raise _failure(
            f"P16-002 execution preflight revalidation failed: {exc}",
            stage="preflight_revalidation",
            state="failed",
            sequence=sequence,
            sender=sender,
            primary_error=str(exc),
        ) from exc

    try:
        current_backup = verify_fresh_backup(
            preflight.before_backup.directory,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        if _backup_identity(current_backup) != _backup_identity(preflight.before_backup):
            raise ValueError("sealed fresh backup changed before execution")
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
        sequence.extend(["fresh_backup_revalidated", "candidate_reconstructed"])
    except Exception as exc:
        raise _failure(
            f"P16-002 candidate revalidation failed: {exc}",
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
                "P16-002 execution cancelled before transaction start"
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
            f"P16-002 authorization failed: {exc}",
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
            now=now,
            max_age_seconds=max_age_seconds,
            cancelled=cancelled,
            progress=progress,
        )
        sequence.append("single_0x101b_transaction")
    except Exception as exc:
        assessment: WriteFailureAssessment = assess_write_failure(exc)
        state = (
            "indeterminate_after_transaction_start"
            if assessment.device_outcome == "indeterminate"
            else "failed"
        )
        raise _failure(
            f"P16-002 transaction stopped: {exc}",
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
            f"P16-002 completion {value} is not 0x0000",
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
            now=now,
            max_age_seconds=max_age_seconds,
        )
        sequence.append("fresh_post_operation_backup")
        verification = verify_prepared_multi_package_readback(
            candidate,
            after.directory,
            completion=completion,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        sequence.append("independent_readback_verification")
    except Exception as exc:
        raise _failure(
            f"P16-002 post-operation read-back failed: {exc}",
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
    authorization_audit["owner_approval"] = P16_002_MODERN_MIXED_OWNER_APPROVAL
    audit = {
        "format": P16_002_MODERN_MIXED_RUNNER_FORMAT,
        "state": "readback_verified",
        "hardware_transaction_performed": True,
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
    return P16MixedPackageLiveSmokeResult(
        preflight=preflight,
        candidate=candidate,
        authorization=authorization,
        after_backup=after,
        completion=completion,
        verification=verification,
        audit=audit,
    )


__all__ = [
    "P16_002_MODERN_MIXED_CONFIRMATION",
    "P16_002_MODERN_MIXED_OWNER_APPROVAL",
    "P16_002_NATIVE_TEMPLATE_FOLDER_PATH",
    "P16_002_NATIVE_TEMPLATE_ITEM_PATHS",
    "P16_002_MODERN_MIXED_RUNNER_FORMAT",
    "P16_002_TARGET_FOLDER",
    "P16MixedPackageLivePreflight",
    "P16MixedPackageLiveSender",
    "P16MixedPackageLiveSmokeError",
    "P16MixedPackageLiveSmokeResult",
    "execute_p16_mixed_package_live_smoke",
    "prepare_p16_mixed_package_live_smoke",
]
