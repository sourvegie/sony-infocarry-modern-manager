"""Isolated preflight and approval-gated runner for one modern TXT delete.

The normal CLI and ttk application do not import this module.  The read-only
preflight builds a target-specific candidate from a verified backup and can
seal a human-reviewable, hash-bound artifact without including candidate
bytes.  The optional execute phase accepts only an explicitly sealed
preflight, the exact operation phrase, and a separate owner approval.  Any
device integration remains an injected callback; this module performs no
detection or USB access merely by import.

This is an owner/developer support boundary, not a product action.  It is
limited to one reachable root-level ordinary TXT file and sends at most one
transaction.  Failures after the sender is called are terminal and are never
retried automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Protocol

from .backup_format import BackupFormatError, ParsedBackupBlob, parse_backup_blob
from .delete_generalized import (
    DELETE_GENERALIZED_CONFIRMATION_PHRASE,
    GeneralizedDeleteAuthorization,
    GeneralizedDeleteCandidate,
    GeneralizedDeleteError,
    GeneralizedDeleteVerification,
    authorize_generalized_delete,
    bind_generalized_delete_sender,
    build_generalized_delete_candidate,
    verify_generalized_delete_readback,
)
from .delete_state import FIXED_STATE_COMMANDS
from .protocol import TransferCancelledError
from .write_gate import (
    DEFAULT_MAX_AGE_SECONDS,
    VerifiedBackup,
    WriteGateError,
    capture_and_verify_fresh_backup,
    verify_fresh_backup,
)
from .write_protocol import WriteFailureAssessment, assess_write_failure


DELETE_SMOKE_FORMAT = "infocarry-modern-delete-smoke-preflight-v1"
DELETE_SMOKE_OWNER_APPROVAL = "APPROVE H2 MODERN DELETE SMOKE 01"
_DYNAMIC_BLOB_KEY = "0x8004:backup-blob"
_EXPECTED_DEVICE = ("0x054c", "0x001e")


class DeleteSmokeError(RuntimeError):
    """Raised when the isolated delete-smoke boundary is not satisfied."""


class DeleteSmokeExecutionError(DeleteSmokeError):
    """Terminal execution failure with an explicit no-retry classification."""

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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _require_digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise DeleteSmokeError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_uint(value: Any, label: str, *, allow_zero: bool = True) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DeleteSmokeError(f"{label} must be an integer")
    if value < 0 or value > 0xFFFFFFFF or (not allow_zero and value == 0):
        raise DeleteSmokeError(f"{label} is outside the uint32 range")
    return value


@dataclass(frozen=True)
class DeleteSmokeDeviceIdentity:
    """Stable identity supplied by an injected read-only detector."""

    vendor_id: int
    product_id: int
    bus: Optional[int] = None
    address: Optional[int] = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.vendor_id, "vendor_id"),
            (self.product_id, "product_id"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFFFF:
                raise DeleteSmokeError(f"device {label} must be a uint16")
        for value, label in ((self.bus, "bus"), (self.address, "address")):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise DeleteSmokeError(f"device {label} must be a non-negative integer")

    @property
    def usb_identity(self) -> tuple[str, str]:
        return (f"0x{self.vendor_id:04x}", f"0x{self.product_id:04x}")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "vendor_id": f"0x{self.vendor_id:04x}",
            "product_id": f"0x{self.product_id:04x}",
        }
        if self.bus is not None:
            result["bus"] = self.bus
        if self.address is not None:
            result["address"] = self.address
        return result


@dataclass(frozen=True)
class DeleteSmokeTarget:
    """One explicitly selected eligible root-level TXT target."""

    path: str
    record_offset: int
    metadata_relative_offset: int
    record_type: str
    extension: str
    read_state: Optional[str]
    payload_length: int
    payload_sha256: str
    prefix_sha256: str
    parent_record_offset: int
    parent_path: str

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or self.path.count("\\") != 1 or "\x00" in self.path:
            raise DeleteSmokeError("delete-smoke target must be one root-level NUL-free path")
        for value, label in (
            (self.record_offset, "target record offset"),
            (self.metadata_relative_offset, "target metadata-relative offset"),
            (self.payload_length, "target payload length"),
            (self.parent_record_offset, "parent record offset"),
        ):
            _require_uint(value, label)
        if not self.record_type == "ordinary_txt":
            raise DeleteSmokeError("delete-smoke target record type is unsupported")
        if self.extension.lower() != "txt":
            raise DeleteSmokeError("delete-smoke target extension is not TXT")
        _require_digest(self.payload_sha256, "target payload")
        _require_digest(self.prefix_sha256, "target prefix")

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "record_offset_hex": f"0x{self.record_offset:08x}",
            "metadata_relative_offset_hex": f"0x{self.metadata_relative_offset:08x}",
            "record_type": self.record_type,
            "extension": self.extension,
            "read_state": self.read_state,
            "payload_length": self.payload_length,
            "payload_sha256": self.payload_sha256,
            "prefix_sha256": self.prefix_sha256,
            "parent_record_offset_hex": f"0x{self.parent_record_offset:08x}",
            "parent_path": self.parent_path,
        }


def _read_verified_blob(backup: VerifiedBackup) -> bytes:
    filename = backup.object_filename(_DYNAMIC_BLOB_KEY)
    expected = backup.object_sha256(_DYNAMIC_BLOB_KEY)
    if filename is None or expected is None:
        raise DeleteSmokeError("verified backup is missing its dynamic blob")
    _require_digest(expected, "dynamic blob")
    try:
        data = (backup.directory / filename).read_bytes()
    except OSError as exc:
        raise DeleteSmokeError(f"could not read verified dynamic blob: {exc}") from exc
    if _sha256(data) != expected:
        raise DeleteSmokeError("verified dynamic blob changed after backup verification")
    return data


def _path_for(parsed: ParsedBackupBlob, record: Any) -> Optional[str]:
    parts = parsed.paths.get(record.offset)
    if parts is None:
        return None
    path = "\\".join(parts)
    return f"{path}.{record.extension}" if record.extension else path


def _target_from_candidate(candidate: GeneralizedDeleteCandidate) -> DeleteSmokeTarget:
    parsed = candidate.baseline
    record = parsed.record_at(candidate.target_record_offset)
    path = _path_for(parsed, record)
    if path != candidate.target_path:
        raise DeleteSmokeError("candidate target path does not resolve uniquely")
    path_parts = parsed.paths.get(record.offset)
    if path_parts is None or len(path_parts) != 2 or path_parts[0] != "root":
        raise DeleteSmokeError("selected target is not a reachable root-level TXT leaf")
    if record.kind != "file" or record.extension.lower() != "txt":
        raise DeleteSmokeError("selected target is not an ordinary TXT file")
    try:
        prefix, payload = parsed.payload_parts(record)
    except BackupFormatError as exc:
        raise DeleteSmokeError(f"selected target payload is malformed: {exc}") from exc
    parent_offset = parsed.header.metadata_start
    parent = parsed.record_at(parent_offset)
    if parent.kind != "directory" or parent.name != "root":
        raise DeleteSmokeError("selected target parent is not the root directory")
    return DeleteSmokeTarget(
        path=path,
        record_offset=record.offset,
        metadata_relative_offset=record.offset - parsed.header.metadata_start,
        record_type="ordinary_txt",
        extension=record.extension,
        read_state=record.read_state,
        payload_length=len(payload),
        payload_sha256=_sha256(payload),
        prefix_sha256=_sha256(prefix),
        parent_record_offset=parent.offset,
        parent_path="root",
    )


def _eligible_candidate(
    backup: VerifiedBackup,
    target_path: str,
    target_record_offset: int,
    *,
    now: Optional[datetime],
    max_age_seconds: Optional[float],
) -> GeneralizedDeleteCandidate:
    try:
        candidate = build_generalized_delete_candidate(
            backup.directory,
            target_path,
            target_record_offset,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        target = _target_from_candidate(candidate)
    except (GeneralizedDeleteError, DeleteSmokeError) as exc:
        raise DeleteSmokeError(f"target is not eligible for delete smoke: {exc}") from exc
    if target.path != target_path or target.record_offset != target_record_offset:
        raise DeleteSmokeError("target identity changed during eligibility validation")
    if target.payload_sha256 != candidate.target_payload_sha256:
        raise DeleteSmokeError("target payload hash differs from the deletion candidate")
    return candidate


def list_eligible_delete_targets(
    backup: VerifiedBackup,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> tuple[DeleteSmokeTarget, ...]:
    """Return eligible targets without selecting one or invoking a sender."""

    if not isinstance(backup, VerifiedBackup):
        raise DeleteSmokeError("a verified complete backup is required")
    parsed = parse_backup_blob(_read_verified_blob(backup))
    targets: list[DeleteSmokeTarget] = []
    for record in parsed.records:
        path = _path_for(parsed, record)
        parts = parsed.paths.get(record.offset)
        if (
            path is None
            or parts is None
            or len(parts) != 2
            or parts[0] != "root"
            or record.kind != "file"
            or record.extension.lower() != "txt"
            or record.name in {".", ".."}
        ):
            continue
        try:
            candidate = _eligible_candidate(
                backup,
                path,
                record.offset,
                now=now,
                max_age_seconds=max_age_seconds,
            )
            targets.append(_target_from_candidate(candidate))
        except DeleteSmokeError:
            # The listing is intentionally eligible-only.  Unsupported fixed
            # state or an unresolved target is not silently made eligible.
            continue
    return tuple(targets)


@dataclass(frozen=True)
class DeleteSmokePreflight:
    """Candidate plus all reviewable bindings for one selected target."""

    device: DeleteSmokeDeviceIdentity
    backup: VerifiedBackup
    target: DeleteSmokeTarget
    candidate: GeneralizedDeleteCandidate
    artifact_path: Optional[Path] = None
    artifact_sha256: Optional[str] = None

    def __post_init__(self) -> None:
        if self.device.usb_identity != _EXPECTED_DEVICE:
            raise DeleteSmokeError("preflight device is not the supported InfoCarry")
        if self.backup.device_identity != _EXPECTED_DEVICE:
            raise DeleteSmokeError("preflight backup is not from the supported InfoCarry")
        if not isinstance(self.candidate, GeneralizedDeleteCandidate):
            raise DeleteSmokeError("preflight candidate is malformed")
        if self.candidate.target_path != self.target.path:
            raise DeleteSmokeError("preflight target path differs from candidate")
        if self.candidate.target_record_offset != self.target.record_offset:
            raise DeleteSmokeError("preflight target offset differs from candidate")
        try:
            derived_target = _target_from_candidate(self.candidate)
        except DeleteSmokeError as exc:
            raise DeleteSmokeError(f"preflight target cannot be derived: {exc}") from exc
        if self.target != derived_target:
            raise DeleteSmokeError("preflight target fields differ from the candidate record")
        if self.artifact_path is not None:
            if self.artifact_sha256 is None:
                raise DeleteSmokeError("sealed preflight is missing its artifact hash")
            _require_digest(self.artifact_sha256, "sealed preflight artifact")

    @property
    def is_sealed(self) -> bool:
        return self.artifact_path is not None and self.artifact_sha256 is not None

    def _payload_dict(self) -> dict[str, Any]:
        allocation = dict(self.candidate.candidate_model.audit["allocation"])
        return {
            "format": DELETE_SMOKE_FORMAT,
            # The sealed payload must remain byte-for-byte stable when the
            # in-memory object gains its artifact path and artifact digest.
            "state": "prepared_offline",
            "device": self.device.to_dict(),
            "backup": {
                "directory": str(self.backup.directory),
                "manifest_sha256": self.backup.manifest_sha256,
                "dynamic_blob_sha256": self.backup.blob_sha256,
                "updated_at_utc": self.backup.updated_at_utc,
                "object_count": self.backup.object_count,
                "model_length": len(self.candidate.baseline.data),
                "record_count": len(self.candidate.baseline.records),
            },
            "target": self.target.to_dict(),
            "candidate": {
                "dynamic_blob_sha256": self.candidate.candidate_blob_sha256,
                "model_length": len(self.candidate.candidate_blob),
                "record_count": self.candidate.candidate_model.audit["candidate"]["record_count"],
                "removed_paths": [self.target.path],
                "added_paths": [],
            },
            "transaction": {
                "sha256": self.candidate.transaction_sha256,
                "variable_n": self.candidate.transaction.variable_n,
                "variable_m": self.candidate.transaction.variable_m,
                "payload_length": self.candidate.transaction.payload_length,
                "range_lengths": [len(value) for value in self.candidate.transaction.ranges],
            },
            "fixed_state": {
                "before_sha256": {
                    f"0x{command:04x}": digest
                    for command, digest in zip(
                        FIXED_STATE_COMMANDS,
                        self.candidate.fixed_state.before_hashes,
                    )
                },
                "after_sha256": {
                    f"0x{command:04x}": digest
                    for command, digest in zip(
                        FIXED_STATE_COMMANDS,
                        self.candidate.fixed_state.after_hashes,
                    )
                },
                "changed_commands": [
                    f"0x{command:04x}" for command in self.candidate.fixed_state.changed_commands
                ],
                "classification": "exact_supported_target_reference_clear_or_preserved_zero_state",
            },
            "capacity_effect": {
                "baseline_model_bytes": len(self.candidate.baseline.data),
                "candidate_model_bytes": len(self.candidate.candidate_blob),
                "model_delta_bytes": len(self.candidate.candidate_blob)
                - len(self.candidate.baseline.data),
                "metadata_delta_bytes": allocation["metadata_delta"],
                "aligned_content_removed_bytes": allocation["removed_aligned_bytes"],
                "capacity_semantics": "deletion_reclaims_candidate_model_delta_only",
            },
            "policy": {
                "timestamps": "preserve_surviving_timestamps",
                "fixed_state": "use_exact_verified_before_and_derived_after_state",
                "completion": "0x0000_only",
                "automatic_retry_allowed": False,
            },
            "expected_path_delta": {"removed": [self.target.path], "added": []},
            "confirmation_phrase": DELETE_GENERALIZED_CONFIRMATION_PHRASE,
            "live_transaction_performed": False,
        }

    def to_dict(self) -> dict[str, Any]:
        result = self._payload_dict()
        if self.is_sealed:
            result["sealed_artifact"] = {
                "path": str(self.artifact_path),
                "sha256": self.artifact_sha256,
            }
        return result


def build_delete_smoke_preflight(
    backup: VerifiedBackup,
    device: DeleteSmokeDeviceIdentity,
    *,
    target_path: str,
    target_record_offset: int,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> DeleteSmokePreflight:
    """Build a selected-target preflight; never chooses a target automatically."""

    if not isinstance(backup, VerifiedBackup):
        raise DeleteSmokeError("a verified complete backup is required")
    if not isinstance(device, DeleteSmokeDeviceIdentity):
        raise DeleteSmokeError("an injected stable device identity is required")
    if device.usb_identity != _EXPECTED_DEVICE:
        raise DeleteSmokeError("read-only detection did not identify the supported InfoCarry")
    candidate = _eligible_candidate(
        backup,
        target_path,
        target_record_offset,
        now=now,
        max_age_seconds=max_age_seconds,
    )
    target = _target_from_candidate(candidate)
    if target not in list_eligible_delete_targets(
        backup, now=now, max_age_seconds=max_age_seconds
    ):
        raise DeleteSmokeError("selected target is not in the eligible target list")
    return DeleteSmokePreflight(device=device, backup=backup, target=target, candidate=candidate)


def create_delete_smoke_session(destination: Path) -> Path:
    """Create a new non-overwriting evidence session skeleton."""

    root = Path(destination).expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise DeleteSmokeError(f"refusing to reuse existing evidence session: {root}") from exc
    except OSError as exc:
        raise DeleteSmokeError(f"could not create evidence session {root}: {exc}") from exc
    for name in (
        "timestamp-logs",
        "pre-delete-backup",
        "manager-before",
        "snoopypro-delete",
        "manager-after",
        "manager-result",
        "post-delete-backup",
        "derived",
    ):
        (root / name).mkdir()
    return root


def seal_delete_smoke_preflight(
    preflight: DeleteSmokePreflight,
    destination: Path,
) -> DeleteSmokePreflight:
    """Write one sealed JSON artifact without overwriting an existing file."""

    if not isinstance(preflight, DeleteSmokePreflight):
        raise DeleteSmokeError("a delete-smoke preflight is required")
    if preflight.is_sealed:
        raise DeleteSmokeError("preflight is already sealed")
    path = Path(destination).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = preflight._payload_dict()
    document = {
        "format": DELETE_SMOKE_FORMAT,
        "state": "sealed_for_owner_review",
        "seal_sha256": _sha256(_canonical_json(payload)),
        "preflight": payload,
    }
    encoded = _canonical_json(document)
    try:
        with path.open("xb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError as exc:
        raise DeleteSmokeError(f"refusing to overwrite sealed preflight: {path}") from exc
    except OSError as exc:
        raise DeleteSmokeError(f"could not write sealed preflight: {exc}") from exc
    return replace(
        preflight,
        artifact_path=path,
        artifact_sha256=_sha256(encoded),
    )


def verify_sealed_delete_smoke_preflight(preflight: DeleteSmokePreflight) -> None:
    """Verify the sealed artifact and every in-memory binding before execute."""

    if not isinstance(preflight, DeleteSmokePreflight) or not preflight.is_sealed:
        raise DeleteSmokeError("execute requires a separately sealed preflight artifact")
    assert preflight.artifact_path is not None
    assert preflight.artifact_sha256 is not None
    try:
        encoded = preflight.artifact_path.read_bytes()
        document = json.loads(encoded.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeleteSmokeError(f"sealed preflight cannot be read: {exc}") from exc
    if _sha256(encoded) != preflight.artifact_sha256:
        raise DeleteSmokeError("sealed preflight artifact hash changed")
    if (
        not isinstance(document, dict)
        or document.get("format") != DELETE_SMOKE_FORMAT
        or document.get("state") != "sealed_for_owner_review"
    ):
        raise DeleteSmokeError("sealed preflight format is invalid")
    payload = document.get("preflight")
    seal = document.get("seal_sha256")
    if not isinstance(payload, dict) or not isinstance(seal, str):
        raise DeleteSmokeError("sealed preflight is missing its payload or seal")
    _require_digest(seal, "sealed preflight seal")
    if _sha256(_canonical_json(payload)) != seal:
        raise DeleteSmokeError("sealed preflight seal does not match its payload")
    if payload != preflight._payload_dict():
        raise DeleteSmokeError("sealed preflight bindings differ from the in-memory preflight")


def _check_cancelled(cancelled: Optional[Callable[[], bool]]) -> None:
    if cancelled is not None and cancelled():
        raise TransferCancelledError("delete smoke cancelled before device change")


class DeleteSmokeSender(Protocol):
    """Existing one-shot sender interface supplied only by an owner runner."""

    def send(
        self,
        transaction: Any,
        authorization: Any,
        *,
        cancelled: Optional[Callable[[], bool]] = None,
        progress: Optional[Callable[[str, int, int], None]] = None,
    ) -> int:
        ...


@dataclass(frozen=True)
class DeleteSmokeExecutionResult:
    candidate: GeneralizedDeleteCandidate
    authorization: GeneralizedDeleteAuthorization
    before_backup: VerifiedBackup
    after_backup: VerifiedBackup
    completion: int
    verification: GeneralizedDeleteVerification
    audit: Mapping[str, Any]


def run_delete_smoke(
    *,
    preflight: DeleteSmokePreflight,
    post_delete_destination: Path,
    detect_device: Callable[[], DeleteSmokeDeviceIdentity],
    capture: Callable[..., None],
    sender: DeleteSmokeSender,
    owner_approval: str,
    confirmation: str,
    cancelled: Optional[Callable[[], bool]] = None,
    progress: Optional[Callable[[str, int, int], None]] = None,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> DeleteSmokeExecutionResult:
    """Execute exactly one approved operation through injected callbacks.

    This function is intentionally not imported by the normal product.  A
    caller must present a sealed preflight and both exact approval values.
    Revalidation is read-only before the sender is called; any sender failure
    is terminal and no retry path exists.
    """

    if owner_approval != DELETE_SMOKE_OWNER_APPROVAL:
        raise DeleteSmokeExecutionError(
            "separate owner approval was not accepted; no device operation attempted",
            stage="approval",
            state="failed",
        )
    if confirmation != DELETE_GENERALIZED_CONFIRMATION_PHRASE:
        raise DeleteSmokeExecutionError(
            "delete confirmation phrase was not accepted; no device operation attempted",
            stage="approval",
            state="failed",
        )
    try:
        verify_sealed_delete_smoke_preflight(preflight)
    except DeleteSmokeError as exc:
        raise DeleteSmokeExecutionError(
            str(exc), stage="sealed_preflight", state="failed"
        ) from exc
    for callback, label in (
        (detect_device, "detect_device"),
        (capture, "capture"),
        (sender, "sender"),
    ):
        if not callable(callback) and label != "sender":
            raise DeleteSmokeExecutionError(
                f"isolated delete smoke requires {label}", stage="preflight", state="failed"
            )
    if not callable(getattr(sender, "send", None)):
        raise DeleteSmokeExecutionError(
            "isolated delete smoke requires the existing one-shot sender interface",
            stage="transport",
            state="failed",
        )

    try:
        _check_cancelled(cancelled)
        detected = detect_device()
        if not isinstance(detected, DeleteSmokeDeviceIdentity):
            raise DeleteSmokeError("device detector returned an unmarked identity")
        if detected != preflight.device:
            raise DeleteSmokeError("fresh detected device identity differs from sealed preflight")
        before = verify_fresh_backup(
            preflight.backup.directory,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        if before.manifest_sha256 != preflight.backup.manifest_sha256:
            raise DeleteSmokeError("fresh backup manifest differs from sealed preflight")
        if before.blob_sha256 != preflight.backup.blob_sha256:
            raise DeleteSmokeError("fresh backup dynamic blob differs from sealed preflight")
        current = _eligible_candidate(
            before,
            preflight.target.path,
            preflight.target.record_offset,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        if current.to_dict() != preflight.candidate.to_dict():
            raise DeleteSmokeError("fresh candidate differs from sealed preflight")
    except (DeleteSmokeError, WriteGateError, OSError, TransferCancelledError) as exc:
        raise DeleteSmokeExecutionError(
            f"delete-smoke read-only revalidation failed: {exc}",
            stage="preflight_revalidation",
            state="cancelled_before_transaction"
            if isinstance(exc, TransferCancelledError)
            else "failed",
        ) from exc

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
    except (GeneralizedDeleteError, TransferCancelledError) as exc:
        raise DeleteSmokeExecutionError(
            f"delete-smoke authorization failed: {exc}",
            stage="authorization",
            state="cancelled_before_transaction"
            if isinstance(exc, TransferCancelledError)
            else "failed",
        ) from exc

    try:
        _check_cancelled(cancelled)
    except TransferCancelledError as exc:
        raise DeleteSmokeExecutionError(
            str(exc),
            stage="before_transaction",
            state="cancelled_before_transaction",
        ) from exc

    try:
        completion = sender.send(
            current.transaction,
            binding,
            cancelled=cancelled,
            progress=progress,
        )
    except Exception as exc:
        assessment = assess_write_failure(exc)
        state = (
            "indeterminate_after_transaction_start"
            if assessment.write_started or assessment.device_outcome == "indeterminate"
            else "failed"
        )
        raise DeleteSmokeExecutionError(
            f"delete-smoke transaction stopped; no automatic retry: {exc}",
            stage="write",
            state=state,
            write_started=assessment.write_started,
            audit={
                "primary_error": assessment.primary_error,
                "device_change": assessment.device_outcome,
                "write_started": assessment.write_started,
                "automatic_retry_allowed": False,
                "target_path": current.target_path,
            },
        ) from exc

    if isinstance(completion, bool) or not isinstance(completion, int) or completion != 0:
        rendered = repr(completion) if not isinstance(completion, int) else f"0x{completion:04x}"
        raise DeleteSmokeExecutionError(
            f"delete-smoke completion {rendered} is not 0x0000; no automatic retry",
            stage="write_completion",
            state="failed",
            write_started=True,
            audit={"completion": rendered, "target_path": current.target_path},
        )

    try:
        after = capture_and_verify_fresh_backup(
            Path(post_delete_destination),
            lambda destination: capture(destination, cancelled=cancelled, progress=progress),
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
        raise DeleteSmokeExecutionError(
            f"delete-smoke read-back failed; no automatic retry: {exc}",
            stage="post_delete_readback",
            state="indeterminate_after_transaction_start",
            write_started=True,
            audit={"target_path": current.target_path, "automatic_retry_allowed": False},
        ) from exc

    return DeleteSmokeExecutionResult(
        candidate=current,
        authorization=authorization,
        before_backup=before,
        after_backup=after,
        completion=completion,
        verification=verification,
        audit={
            "format": DELETE_SMOKE_FORMAT,
            "state": "readback_verified",
            "live_transaction_performed": True,
            "automatic_retry_allowed": False,
            "target_path": current.target_path,
            "completion": "0x0000",
        },
    )


__all__ = [
    "DELETE_SMOKE_FORMAT",
    "DELETE_SMOKE_OWNER_APPROVAL",
    "DeleteSmokeDeviceIdentity",
    "DeleteSmokeError",
    "DeleteSmokeExecutionError",
    "DeleteSmokeExecutionResult",
    "DeleteSmokePreflight",
    "DeleteSmokeSender",
    "DeleteSmokeTarget",
    "build_delete_smoke_preflight",
    "create_delete_smoke_session",
    "list_eligible_delete_targets",
    "run_delete_smoke",
    "seal_delete_smoke_preflight",
    "verify_sealed_delete_smoke_preflight",
]
