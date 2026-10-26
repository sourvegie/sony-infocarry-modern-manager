"""Fail-closed offline deletion candidate and read-back verification.

This is deliberately separate from :mod:`infocarry.delete_gate`, whose
attempt-02 helper reproduces one captured legacy transaction.  The model in
this module is the provisional modern policy: surviving timestamps are
preserved, fixed state is derived from the fresh backup, and only the proven
target-reference clearing forms are accepted.  No function here opens USB or
exposes a normal product action.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Mapping, Optional

from .backup_format import BackupFormatError, ParsedBackupBlob, parse_backup_blob
from .delete_model import (
    DeleteModelError, OfflineDeleteModel, build_one_txt_delete_model,
    build_one_root_bmp_delete_model, build_one_nested_file_delete_model,
    verify_nested_file_delete_model,
)
from .delete_state import (
    FIXED_STATE_COMMANDS,
    DeleteStateCandidate,
    DeleteStateError,
    derive_supported_delete_state,
    derive_preserved_delete_state,
)
from .write_artifact import (
    ProspectiveWriteTransaction,
    WriteArtifactError,
    build_staging_range,
)
from .write_gate import (
    DEFAULT_MAX_AGE_SECONDS,
    VerifiedBackup,
    WriteGateError,
    verify_fresh_backup,
)


DELETE_GENERALIZED_FORMAT = "infocarry-modern-delete-v1"
DELETE_GENERALIZED_CONFIRMATION_PHRASE = "DELETE ONE INFOCARRY ITEM"
_DYNAMIC_BLOB_KEY = "0x8004:backup-blob"
_PAYLOAD_DEPENDENT_KEYS = frozenset(
    {
        "0x0024:response-0024",
        "0x8004:backup-blob-probe",
        _DYNAMIC_BLOB_KEY,
    }
)
_FIXED_STATE_KEYS = {
    command: f"0x{command:04x}:response-{command:04x}"
    for command in FIXED_STATE_COMMANDS
}


class GeneralizedDeleteError(RuntimeError):
    """Raised when the provisional modern deletion scope is not met."""


class GeneralizedDeleteVerificationError(GeneralizedDeleteError):
    """Terminal read-back failure with explicit no-retry guidance."""

    def __init__(self, message: str, *, outcome: str = "indeterminate") -> None:
        self.outcome = outcome
        self.automatic_retry_allowed = False
        self.recovery_guidance = (
            "Preserve both backups and the audit; do not retry automatically; "
            "reconnect only for read-only detection and backup before assessment."
        )
        super().__init__(
            f"{message}; terminal {outcome} result; automatic retry is prohibited. "
            + self.recovery_guidance
        )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_hash(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise GeneralizedDeleteError(f"{label} hash must be a lowercase SHA-256 digest")
    return value


def _require_u32(value: Any, label: str, *, allow_zero: bool = True) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GeneralizedDeleteError(f"{label} must be an integer")
    if value < 0 or value > 0xFFFFFFFF or (not allow_zero and value == 0):
        raise GeneralizedDeleteError(f"{label} is outside the uint32 range")
    return value


def _require_fixed_hashes(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, tuple) or len(value) != len(FIXED_STATE_COMMANDS):
        raise GeneralizedDeleteError(
            f"{label} must contain exactly {len(FIXED_STATE_COMMANDS)} hashes"
        )
    return tuple(_require_hash(item, f"{label}[{index}]") for index, item in enumerate(value))


def _read_object(backup: VerifiedBackup, key: str) -> bytes:
    filename = backup.object_filename(key)
    expected = backup.object_sha256(key)
    if filename is None or expected is None:
        raise GeneralizedDeleteError(f"fresh backup is missing required object {key}")
    try:
        data = (backup.directory / filename).read_bytes()
    except OSError as exc:
        raise GeneralizedDeleteError(f"could not read fresh backup object {key}: {exc}") from exc
    if _sha256(data) != expected:
        raise GeneralizedDeleteError(f"fresh backup object {key} changed after verification")
    return data


def _record_path(parsed: ParsedBackupBlob, record: Any) -> Optional[str]:
    parts = parsed.paths.get(record.offset)
    if parts is None:
        return None
    path = "\\".join(parts)
    return f"{path}.{record.extension}" if record.extension else path


def _file_payloads(parsed: ParsedBackupBlob) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for record in parsed.records:
        if record.kind != "file" or record.offset not in parsed.paths:
            continue
        path = _record_path(parsed, record)
        if path is None or path in result:
            raise GeneralizedDeleteError("reachable file paths are missing or ambiguous")
        try:
            _prefix, payload = parsed.payload_parts(record)
        except BackupFormatError as exc:
            raise GeneralizedDeleteError(f"reachable file payload is malformed at 0x{record.offset:x}") from exc
        result[path] = payload
    return result


def _fixed_state_from_backup(backup: VerifiedBackup) -> dict[int, bytes]:
    return {
        command: _read_object(backup, _FIXED_STATE_KEYS[command])
        for command in FIXED_STATE_COMMANDS
    }


def _build_transaction(candidate_blob: bytes, state: DeleteStateCandidate) -> ProspectiveWriteTransaction:
    if len(candidate_blob) < 0x40:
        raise GeneralizedDeleteError("candidate dynamic blob is shorter than its header")
    try:
        return ProspectiveWriteTransaction(
            ranges=(
                state.range1,
                state.grouped_values,
                build_staging_range(0, len(candidate_blob)),
                b"",
                candidate_blob[:0x40],
                b"",
                b"",
                candidate_blob[0x40:],
            ),
            variable_n=0,
            variable_m=len(candidate_blob),
        )
    except (WriteArtifactError, OverflowError) as exc:
        raise GeneralizedDeleteError(f"prospective delete transaction is invalid: {exc}") from exc


@dataclass(frozen=True)
class GeneralizedDeleteCandidate:
    """One modern-policy candidate bound to a complete fresh backup."""

    backup: VerifiedBackup
    baseline: ParsedBackupBlob
    candidate_model: OfflineDeleteModel
    fixed_state: DeleteStateCandidate
    transaction: ProspectiveWriteTransaction
    audit: Mapping[str, Any]

    @property
    def candidate_blob(self) -> bytes:
        return self.candidate_model.candidate_blob

    @property
    def candidate_blob_sha256(self) -> str:
        return _sha256(self.candidate_blob)

    @property
    def target_path(self) -> str:
        return self.candidate_model.target_path

    @property
    def target_record_offset(self) -> int:
        return self.candidate_model.target_record_offset

    @property
    def target_payload_sha256(self) -> str:
        return self.candidate_model.target_payload_sha256

    @property
    def transaction_sha256(self) -> str:
        return self.transaction.concatenated_sha256

    @property
    def target_extension(self) -> str:
        """File type from bound baseline bytes, never from mutable audit data."""
        try:
            parsed = parse_backup_blob(self.baseline.data)
            record = parsed.record_at(self.target_record_offset)
        except BackupFormatError as exc:
            raise GeneralizedDeleteError("bound target record is invalid") from exc
        if (record.kind != "file" or _record_path(parsed, record) != self.target_path
                or _sha256(parsed.data) != self.backup.blob_sha256):
            raise GeneralizedDeleteError("bound baseline target identity differs")
        return record.extension

    def to_dict(self) -> dict[str, Any]:
        return dict(self.audit)


@dataclass(frozen=True)
class NestedFileDeleteCandidate:
    """Host-only nested model and protected state; deliberately no transaction.

    This is not a GeneralizedDeleteCandidate and cannot be authorized or
    bound to the guarded sender. Nested live capability remains disabled.
    """

    backup: VerifiedBackup
    baseline: ParsedBackupBlob
    candidate_model: OfflineDeleteModel
    fixed_state: DeleteStateCandidate
    audit: Mapping[str, Any]

    @property
    def candidate_blob(self) -> bytes:
        return self.candidate_model.candidate_blob

    @property
    def candidate_blob_sha256(self) -> str:
        return self.candidate_model.candidate_blob_sha256

    @property
    def target_path(self) -> str:
        return self.candidate_model.target_path

    @property
    def target_record_offset(self) -> int:
        return self.candidate_model.target_record_offset

    @property
    def target_payload_sha256(self) -> str:
        return self.candidate_model.target_payload_sha256

    def to_dict(self) -> dict[str, Any]:
        return dict(self.audit)


def build_nested_file_delete_candidate(
    backup_directory: Path, target_path: str, target_record_offset: int, *,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> NestedFileDeleteCandidate:
    """Prepare a nested leaf and preserve supported protected associations.

    Requires a complete verified backup and refuses referenced targets,
    unfamiliar state and ambiguous parent relationships. No transaction,
    authorization, claim, marker, lock or USB access is created.
    """
    try:
        backup = verify_fresh_backup(backup_directory, now=now, max_age_seconds=max_age_seconds)
        baseline = parse_backup_blob(_read_object(backup, _DYNAMIC_BLOB_KEY))
        model = build_one_nested_file_delete_model(baseline, target_path, target_record_offset)
        state = derive_preserved_delete_state(
            backup, baseline, parse_backup_blob(model.candidate_blob),
            target_record_offset=target_record_offset,
        )
    except (BackupFormatError, DeleteModelError, DeleteStateError, WriteGateError, OSError) as exc:
        raise GeneralizedDeleteError(f"could not build nested host-only delete candidate: {exc}") from exc
    audit = dict(model.audit)
    audit["fixed_state"] = state.audit
    return NestedFileDeleteCandidate(backup, baseline, model, state, audit)


def build_generalized_delete_candidate(
    backup_directory: Path,
    target_path: str,
    target_record_offset: int,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
    preserve_unreferenced_auxiliary_state: bool = False,
) -> GeneralizedDeleteCandidate:
    """Build and validate one supported deletion from a fresh backup.

    The backup's fixed state is copied and parsed before authorization.  The
    candidate never uses attempt-specific timestamps or fixed-state blocks.
    """

    return _build_delete_candidate(
        backup_directory, target_path, target_record_offset, now=now,
        max_age_seconds=max_age_seconds,
        preserve_unreferenced_auxiliary_state=preserve_unreferenced_auxiliary_state,
        bmp=False,
    )


def _validate_root_bmp_admission(parsed: ParsedBackupBlob, target_path: str,
                                 target_record_offset: int) -> None:
    """Narrow host profile; native identity and geometry must be understood."""
    if type(target_record_offset) is not int:
        raise GeneralizedDeleteError("root BMP target record offset must be an integer")
    target = parsed.record_at(target_record_offset)
    parts = parsed.paths.get(target.offset)
    if (parts is None or len(parts) != 2 or parts[0] != "root"
            or _record_path(parsed, target) != target_path
            or target.kind != "file" or target.extension != "bmp"):
        raise GeneralizedDeleteError("root BMP preparation requires one exact ordinary root-level BMP")
    if target.flag not in {0xe0, 0x20} or target.field_14_be32 not in {0x100, 0x200}:
        raise GeneralizedDeleteError("root BMP target has unsupported state or native prefix")
    name = target.name
    if (name in {"", ".", "..", "root"} or name != name.strip()
            or any(ord(c) < 32 or ord(c) == 127 or c in '\\/.:<>"|?*' for c in name)):
        raise GeneralizedDeleteError("root BMP name contains unsupported root/system/path syntax")
    try:
        encoded = name.encode("cp932", "strict")
        if not 1 <= len(encoded) <= 39 or encoded.decode("cp932", "strict") != name:
            raise UnicodeError("name must roundtrip within 39 native bytes")
    except UnicodeError as exc:
        raise GeneralizedDeleteError("root BMP name is not exactly CP932 representable") from exc
    raw_name = bytes.fromhex(target.raw_hex)[24:64]
    if b"\0" not in raw_name or raw_name.split(b"\0", 1)[0] != encoded:
        raise GeneralizedDeleteError("root BMP native name is not an exact NUL-terminated identity")
    identity = tuple(part.casefold() for part in parts)
    if (sum(tuple(part.casefold() for part in path) == identity for path in parsed.paths.values()) != 1
            or sum(_record_path(parsed, r) is not None and _record_path(parsed, r).casefold()
                   == target_path.casefold() for r in parsed.records) != 1):
        raise GeneralizedDeleteError("root BMP target has an ambiguous native identity")


def build_root_bmp_delete_candidate(
    backup_directory: Path,
    target_path: str,
    target_record_offset: int,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> GeneralizedDeleteCandidate:
    """Prepare a root BMP transaction for offline review, with execution blocked.

    Preserve protected survivor state and refuse referenced targets or active
    Marks. This creates no claim, marker, sender or Device Library action.
    """
    return _build_delete_candidate(
        backup_directory, target_path, target_record_offset, now=now,
        max_age_seconds=max_age_seconds, preserve_unreferenced_auxiliary_state=True,
        bmp=True,
    )


def _build_delete_candidate(
    backup_directory: Path, target_path: str, target_record_offset: int, *,
    now: Optional[datetime], max_age_seconds: Optional[float],
    preserve_unreferenced_auxiliary_state: bool, bmp: bool,
) -> GeneralizedDeleteCandidate:
    if type(preserve_unreferenced_auxiliary_state) is not bool:
        raise GeneralizedDeleteError("auxiliary-state preservation opt-in must be boolean")
    try:
        backup = verify_fresh_backup(
            backup_directory,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        baseline_blob = _read_object(backup, _DYNAMIC_BLOB_KEY)
        baseline = parse_backup_blob(baseline_blob)
        if bmp:
            _validate_root_bmp_admission(baseline, target_path, target_record_offset)
            model = build_one_root_bmp_delete_model(baseline, target_path, target_record_offset)
        else:
            model = build_one_txt_delete_model(baseline, target_path, target_record_offset)
        if model.source_blob_sha256 != backup.blob_sha256:
            raise GeneralizedDeleteError("fresh backup blob hash differs from parsed baseline")
        fixed_state_before = _fixed_state_from_backup(backup)
        if preserve_unreferenced_auxiliary_state:
            state = derive_preserved_delete_state(
                backup, baseline, parse_backup_blob(model.candidate_blob),
                target_record_offset=target_record_offset,
            )
        else:
            state = derive_supported_delete_state(
                fixed_state_before,
                target_record_offset=target_record_offset,
                metadata_start=baseline.header.metadata_start,
                record_size=baseline.header.record_size,
            )
        transaction = _build_transaction(model.candidate_blob, state)
    except (BackupFormatError, DeleteModelError, DeleteStateError, WriteGateError, OSError) as exc:
        raise GeneralizedDeleteError(f"could not build generalized delete candidate: {exc}") from exc

    audit = {
        "format": DELETE_GENERALIZED_FORMAT,
        "state": "offline_candidate",
        "usb_transmission_performed": False,
        "automatic_retry_allowed": False,
        "operation": "delete_one_existing_bmp" if bmp else "delete_one_existing_txt",
        "policy": {
            "timestamps": "preserve_surviving_timestamps",
            "fixed_state": (state.audit["policy"] if preserve_unreferenced_auxiliary_state
                            else "derive_from_fresh_backup_and_clear_only_proven_target_references"),
            "legacy_timestamp_rule": "unresolved",
        },
        "device": {
            "vendor_id": backup.device_identity[0],
            "product_id": backup.device_identity[1],
        },
        "baseline": {
            "manifest_sha256": backup.manifest_sha256,
            "blob_sha256": backup.blob_sha256,
            "record_count": len(baseline.records),
            "model_length": len(baseline.data),
        },
        "target": {
            "path": model.target_path,
            "record_offset_hex": f"0x{model.target_record_offset:08x}",
            "payload_sha256": model.target_payload_sha256,
        },
        "candidate": {
            "blob_sha256": model.candidate_blob_sha256,
            "transaction_sha256": transaction.concatenated_sha256,
            "record_count": len(parse_backup_blob(model.candidate_blob).records),
            "model_length": len(model.candidate_blob),
            "removed_paths": [model.target_path],
            "added_paths": [],
        },
        "fixed_state": {
            "before_sha256": dict(zip((f"0x{c:04x}" for c in FIXED_STATE_COMMANDS), state.before_hashes)),
            "after_sha256": dict(zip((f"0x{c:04x}" for c in FIXED_STATE_COMMANDS), state.after_hashes)),
            "changed_commands": [f"0x{c:04x}" for c in state.changed_commands],
            "derivation": state.audit,
        },
        "transaction": {
            "variable_n": transaction.variable_n,
            "variable_m": transaction.variable_m,
            "range_lengths": [len(data) for data in transaction.ranges],
        },
        "safety": {
            "device_accessed": False,
            "candidate_bytes_included": False,
            "automatic_retry_allowed": False,
        },
    }
    if bmp:
        audit["capability_status"] = "host_offline_not_live_enabled"
        audit["safety"].update(execution_available=False, physical_behavior_proven=False)
    return GeneralizedDeleteCandidate(
        backup=backup,
        baseline=baseline,
        candidate_model=model,
        fixed_state=state,
        transaction=transaction,
        audit=audit,
    )


@dataclass(frozen=True)
class GeneralizedDeleteAuthorization:
    """Exact binding for one provisional modern delete candidate."""

    device_identity: tuple[str, str]
    baseline_manifest_sha256: str
    baseline_blob_sha256: str
    target_path: str
    target_record_offset: int
    target_payload_sha256: str
    candidate_blob_sha256: str
    transaction_sha256: str
    fixed_state_before_sha256: tuple[str, ...]
    fixed_state_after_sha256: tuple[str, ...]
    baseline_model_length: int
    candidate_model_length: int
    metadata_start: int
    record_size: int
    transaction_variable_n: int
    transaction_variable_m: int
    confirmation_phrase: str
    baseline: VerifiedBackup
    target_extension: str = "txt"

    def __post_init__(self) -> None:
        if self.target_extension not in {"txt", "bmp"}:
            raise GeneralizedDeleteError("authorized delete file type is unsupported")
        if self.confirmation_phrase != DELETE_GENERALIZED_CONFIRMATION_PHRASE:
            raise GeneralizedDeleteError("delete confirmation phrase was not accepted")
        if self.device_identity != ("0x054c", "0x001e"):
            raise GeneralizedDeleteError("authorization device identity is not the verified InfoCarry")
        for value, label in (
            (self.baseline_manifest_sha256, "baseline manifest"),
            (self.baseline_blob_sha256, "baseline blob"),
            (self.target_payload_sha256, "target payload"),
            (self.candidate_blob_sha256, "candidate blob"),
            (self.transaction_sha256, "transaction"),
        ):
            _require_hash(value, label)
        if not isinstance(self.target_path, str) or not self.target_path or "\x00" in self.target_path:
            raise GeneralizedDeleteError("authorized target path is invalid")
        _require_u32(self.target_record_offset, "authorized target record offset")
        before_length = _require_u32(self.baseline_model_length, "baseline model length", allow_zero=False)
        after_length = _require_u32(self.candidate_model_length, "candidate model length", allow_zero=False)
        metadata_start = _require_u32(self.metadata_start, "metadata start", allow_zero=False)
        record_size = _require_u32(self.record_size, "record size", allow_zero=False)
        if metadata_start % 4 or record_size % 4:
            raise GeneralizedDeleteError("metadata start and record size must be aligned")
        if self.target_record_offset < metadata_start:
            raise GeneralizedDeleteError("authorized target record offset precedes metadata")
        if (self.target_record_offset - metadata_start) % record_size:
            raise GeneralizedDeleteError("authorized target record offset is not record-aligned")
        if self.target_record_offset + record_size > before_length:
            raise GeneralizedDeleteError("authorized target record exceeds baseline model")
        if after_length >= before_length:
            raise GeneralizedDeleteError("candidate model must be smaller than baseline model")
        variable_n = _require_u32(self.transaction_variable_n, "transaction variable N")
        variable_m = _require_u32(self.transaction_variable_m, "transaction variable M", allow_zero=False)
        if variable_n != 0:
            raise GeneralizedDeleteError("delete transaction variable N must be zero")
        if variable_m != after_length:
            raise GeneralizedDeleteError("transaction variable M must equal candidate model length")
        _require_fixed_hashes(self.fixed_state_before_sha256, "fixed-state before")
        _require_fixed_hashes(self.fixed_state_after_sha256, "fixed-state after")

    def to_dict(self) -> dict[str, Any]:
        result = {
            "format": DELETE_GENERALIZED_FORMAT,
            "state": "authorized_for_future_writer_only",
            "usb_transmission_performed": False,
            "automatic_retry_allowed": False,
            "operation": f"delete_one_existing_{self.target_extension}",
            "device": {"vendor_id": self.device_identity[0], "product_id": self.device_identity[1]},
            "baseline_manifest_sha256": self.baseline_manifest_sha256,
            "baseline_blob_sha256": self.baseline_blob_sha256,
            "target_path": self.target_path,
            "target_record_offset_hex": f"0x{self.target_record_offset:08x}",
            "target_payload_sha256": self.target_payload_sha256,
            "candidate_blob_sha256": self.candidate_blob_sha256,
            "transaction_sha256": self.transaction_sha256,
            "baseline_model_length": self.baseline_model_length,
            "candidate_model_length": self.candidate_model_length,
            "metadata_start": self.metadata_start,
            "record_size": self.record_size,
            "transaction_variable_n": self.transaction_variable_n,
            "transaction_variable_m": self.transaction_variable_m,
            "fixed_state_before_sha256": list(self.fixed_state_before_sha256),
            "fixed_state_after_sha256": list(self.fixed_state_after_sha256),
            "confirmation_phrase": self.confirmation_phrase,
        }

        if self.target_extension == "bmp":
            result.update(state="authorized_for_host_review_only",
                          target_extension="bmp", execution_available=False,
                          physical_behavior_proven=False)
        return result

    def require_same_candidate(self, candidate: GeneralizedDeleteCandidate) -> None:
        if not isinstance(candidate, GeneralizedDeleteCandidate):
            raise GeneralizedDeleteError("candidate type differs from authorization")
        if candidate.target_extension != self.target_extension:
            raise GeneralizedDeleteError("candidate file type differs from authorization")
        if self.target_extension == "bmp":
            # Reconstruct through the same builder before accepting a host
            # authorization. Parsed caches and mutable audit are not authority.
            if len(candidate.target_path.split("\\")) > 2:
                # Preserve the retained exact route; otherwise reconstruct the
                # conservative source-derived class. The generic sender still
                # refuses every nested candidate, regardless of audit labels.
                from .delete_workflow import (build_nested_bmp_validation_delete,
                    build_nested_bmp_delete, NESTED_BMP_DELETE_VALIDATION_PROFILE)
                builder = (build_nested_bmp_validation_delete
                           if candidate.to_dict().get("profile") == NESTED_BMP_DELETE_VALIDATION_PROFILE
                           else build_nested_bmp_delete)
                expected = builder(
                    candidate.backup.directory, candidate.target_path,
                    target_record_offset=candidate.target_record_offset, max_age_seconds=None)
            else:
                expected = build_root_bmp_delete_candidate(
                    candidate.backup.directory, candidate.target_path,
                    candidate.target_record_offset, max_age_seconds=None)
            if (candidate.baseline.data != expected.baseline.data
                    or candidate.candidate_blob != expected.candidate_blob
                    or candidate.target_payload_sha256 != expected.target_payload_sha256
                    or candidate.fixed_state.before != expected.fixed_state.before
                    or candidate.fixed_state.after != expected.fixed_state.after
                    or candidate.transaction != expected.transaction):
                raise GeneralizedDeleteError("BMP candidate differs from validated source reconstruction")
        checks = (
            (candidate.backup.device_identity, self.device_identity, "device identity"),
            (candidate.backup.manifest_sha256, self.baseline_manifest_sha256, "baseline manifest"),
            (candidate.backup.blob_sha256, self.baseline_blob_sha256, "baseline blob"),
            (candidate.target_path, self.target_path, "target path"),
            (candidate.target_record_offset, self.target_record_offset, "target record offset"),
            (candidate.target_payload_sha256, self.target_payload_sha256, "target payload"),
            (candidate.candidate_blob_sha256, self.candidate_blob_sha256, "candidate blob"),
            (candidate.transaction_sha256, self.transaction_sha256, "transaction"),
            (candidate.fixed_state.before_hashes, self.fixed_state_before_sha256, "fixed-state before"),
            (candidate.fixed_state.after_hashes, self.fixed_state_after_sha256, "fixed-state after"),
            (len(candidate.baseline.data), self.baseline_model_length, "baseline model length"),
            (len(candidate.candidate_blob), self.candidate_model_length, "candidate model length"),
            (candidate.baseline.header.metadata_start, self.metadata_start, "metadata start"),
            (candidate.baseline.header.record_size, self.record_size, "record size"),
            (candidate.transaction.variable_n, self.transaction_variable_n, "transaction variable N"),
            (candidate.transaction.variable_m, self.transaction_variable_m, "transaction variable M"),
        )
        for actual, expected, label in checks:
            if actual != expected:
                raise GeneralizedDeleteError(f"candidate {label} differs from authorization")

    def revalidate(
        self,
        candidate: GeneralizedDeleteCandidate,
        *,
        now: Optional[datetime] = None,
        max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
    ) -> VerifiedBackup:
        self.require_same_candidate(candidate)
        try:
            verified = verify_fresh_backup(
                self.baseline.directory,
                now=now,
                max_age_seconds=max_age_seconds,
            )
        except (WriteGateError, OSError) as exc:
            raise GeneralizedDeleteError(f"fresh backup revalidation failed: {exc}") from exc
        if verified.device_identity != self.device_identity:
            raise GeneralizedDeleteError("bound device identity changed")
        if verified.manifest_sha256 != self.baseline_manifest_sha256:
            raise GeneralizedDeleteError("bound baseline manifest changed")
        if verified.blob_sha256 != self.baseline_blob_sha256:
            raise GeneralizedDeleteError("bound baseline blob changed")
        actual_state = _fixed_state_from_backup(verified)
        if tuple(_sha256(actual_state[command]) for command in FIXED_STATE_COMMANDS) != self.fixed_state_before_sha256:
            raise GeneralizedDeleteError("bound fixed-state bytes changed")
        return verified


def authorize_generalized_delete(
    candidate: GeneralizedDeleteCandidate,
    *,
    confirmation: str,
) -> GeneralizedDeleteAuthorization:
    """Authorize one exact offline candidate; never opens USB."""

    if not isinstance(candidate, GeneralizedDeleteCandidate):
        raise GeneralizedDeleteError("nested deletion is host-only and cannot be authorized")
    if confirmation != DELETE_GENERALIZED_CONFIRMATION_PHRASE:
        raise GeneralizedDeleteError("delete confirmation phrase was not accepted")
    authorization = GeneralizedDeleteAuthorization(
        device_identity=candidate.backup.device_identity,
        baseline_manifest_sha256=candidate.backup.manifest_sha256,
        baseline_blob_sha256=candidate.backup.blob_sha256,
        target_path=candidate.target_path,
        target_record_offset=candidate.target_record_offset,
        target_payload_sha256=candidate.target_payload_sha256,
        candidate_blob_sha256=candidate.candidate_blob_sha256,
        transaction_sha256=candidate.transaction_sha256,
        fixed_state_before_sha256=candidate.fixed_state.before_hashes,
        fixed_state_after_sha256=candidate.fixed_state.after_hashes,
        baseline_model_length=len(candidate.baseline.data),
        candidate_model_length=len(candidate.candidate_blob),
        metadata_start=candidate.baseline.header.metadata_start,
        record_size=candidate.baseline.header.record_size,
        transaction_variable_n=candidate.transaction.variable_n,
        transaction_variable_m=candidate.transaction.variable_m,
        confirmation_phrase=confirmation,
        baseline=candidate.backup,
        target_extension=candidate.target_extension,
    )
    authorization.require_same_candidate(candidate)
    return authorization


@dataclass(frozen=True)
class GeneralizedDeleteSenderBinding:
    """Capability adapter for the existing one-shot sender."""

    authorization: GeneralizedDeleteAuthorization
    candidate: GeneralizedDeleteCandidate
    now: Optional[datetime] = None
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS

    @property
    def backup(self) -> VerifiedBackup:
        return self.authorization.baseline

    def _require_execution_admitted(self) -> None:
        if not isinstance(self.candidate, GeneralizedDeleteCandidate):
            raise GeneralizedDeleteError("nested deletion is host-only and cannot bind a sender")
        try:
            parsed = parse_backup_blob(self.candidate.baseline.data)
            path = parsed.paths.get(self.candidate.target_record_offset)
        except BackupFormatError as exc:
            raise GeneralizedDeleteError("sender baseline is malformed") from exc
        if path is None or len(path) != 2 or path[0] != "root":
            raise GeneralizedDeleteError("nested deletion is host-only and cannot bind a sender")
        # BMP host authorizations deliberately cannot become sender capability.
        # Derive the gate from the parsed source, not audit/operation labels.
        if self.candidate.target_extension != "txt" or self.authorization.target_extension != "txt":
            raise GeneralizedDeleteError("root BMP Delete is host-only and not physically validated")

    def __post_init__(self) -> None:
        self._require_execution_admitted()
        self.authorization.require_same_candidate(self.candidate)

    def revalidate(self, transaction: ProspectiveWriteTransaction) -> None:
        self._require_execution_admitted()
        if not isinstance(transaction, ProspectiveWriteTransaction):
            raise GeneralizedDeleteError("sender transaction is not prospective")
        if transaction.concatenated_sha256 != self.candidate.transaction_sha256:
            raise GeneralizedDeleteError("sender transaction differs from authorization")
        self.authorization.revalidate(
            self.candidate,
            now=self.now,
            max_age_seconds=self.max_age_seconds,
        )


def bind_generalized_delete_sender(
    authorization: GeneralizedDeleteAuthorization,
    candidate: GeneralizedDeleteCandidate,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> GeneralizedDeleteSenderBinding:
    binding = GeneralizedDeleteSenderBinding(
        authorization=authorization,
        candidate=candidate,
        now=now,
        max_age_seconds=max_age_seconds,
    )
    binding.revalidate(candidate.transaction)
    return binding


@dataclass(frozen=True)
class GeneralizedDeleteVerification:
    before: VerifiedBackup
    after: VerifiedBackup
    completion: int
    fixed_state_matches: bool
    dynamic_blob_matches: bool
    target_removed: bool
    unrelated_payloads_unchanged: bool
    unrelated_objects_unchanged: bool
    details: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": DELETE_GENERALIZED_FORMAT,
            "state": "readback_verified",
            "completion": f"0x{self.completion:04x}",
            "fixed_state_matches": self.fixed_state_matches,
            "dynamic_blob_matches": self.dynamic_blob_matches,
            "target_removed": self.target_removed,
            "unrelated_payloads_unchanged": self.unrelated_payloads_unchanged,
            "unrelated_objects_unchanged": self.unrelated_objects_unchanged,
            "details": dict(self.details),
            "automatic_retry_allowed": False,
        }


def verify_generalized_delete_readback(
    candidate: GeneralizedDeleteCandidate,
    post_delete_directory: Path,
    *,
    completion: int,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> GeneralizedDeleteVerification:
    """Require exact completion, candidate bytes, fixed state, and path delta."""

    if not isinstance(candidate, GeneralizedDeleteCandidate):
        raise GeneralizedDeleteVerificationError("candidate is malformed")
    return _verify_delete_readback(candidate, post_delete_directory, completion=completion,
                                   now=now, max_age_seconds=max_age_seconds)


def verify_nested_file_delete_readback(
    candidate: NestedFileDeleteCandidate, post_delete_directory: Path, *,
    completion: int, now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> GeneralizedDeleteVerification:
    """Check a simulated nested result independently; grants no live authority.

    The original complete baseline is reverified, the structural validator
    checks the candidate without invoking the repacker, and protected state
    is derived again from the original verified bytes before readback.
    """
    if not isinstance(candidate, NestedFileDeleteCandidate):
        raise GeneralizedDeleteVerificationError("nested candidate is malformed")
    try:
        backup = verify_fresh_backup(candidate.backup.directory, now=now,
                                     max_age_seconds=max_age_seconds)
        if (backup.manifest_sha256 != candidate.backup.manifest_sha256
                or backup.blob_sha256 != candidate.candidate_model.source_blob_sha256):
            raise GeneralizedDeleteError("nested bound baseline identity changed")
        baseline = parse_backup_blob(_read_object(backup, _DYNAMIC_BLOB_KEY))
        if baseline.data != candidate.baseline.data:
            raise GeneralizedDeleteError("nested bound baseline bytes changed")
        after = verify_nested_file_delete_model(baseline, candidate.candidate_blob,
                    candidate.target_path, candidate.target_record_offset)
        target = baseline.record_at(candidate.target_record_offset)
        if _sha256(baseline.payload_parts(target)[1]) != candidate.target_payload_sha256:
            raise GeneralizedDeleteError("nested bound target payload changed")
        state = derive_preserved_delete_state(backup, baseline, after,
                    target_record_offset=candidate.target_record_offset)
        if (candidate.fixed_state.before != state.before
                or candidate.fixed_state.after != state.after):
            raise GeneralizedDeleteError("nested protected-state derivation changed")
    except (BackupFormatError, DeleteModelError, DeleteStateError, GeneralizedDeleteError,
            WriteGateError, OSError) as exc:
        raise GeneralizedDeleteVerificationError(str(exc)) from exc
    return _verify_delete_readback(candidate, post_delete_directory, completion=completion,
                                   now=now, max_age_seconds=max_age_seconds)


def _verify_delete_readback(
    candidate: GeneralizedDeleteCandidate | NestedFileDeleteCandidate,
    post_delete_directory: Path, *, completion: int, now: Optional[datetime],
    max_age_seconds: Optional[float],
) -> GeneralizedDeleteVerification:
    if isinstance(completion, bool) or not isinstance(completion, int):
        raise GeneralizedDeleteVerificationError("delete completion is missing or malformed")
    if completion != 0:
        raise GeneralizedDeleteVerificationError(
            f"delete completion was 0x{completion:04x}", outcome="failed"
        )
    try:
        after = verify_fresh_backup(
            post_delete_directory,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        if after.device_identity != candidate.backup.device_identity:
            raise GeneralizedDeleteError("post-delete device identity changed")
        actual_blob = _read_object(after, _DYNAMIC_BLOB_KEY)
        if _sha256(actual_blob) != candidate.candidate_blob_sha256:
            raise GeneralizedDeleteError("post-delete dynamic blob does not match candidate")
        before = candidate.baseline
        post = parse_backup_blob(actual_blob)
        target = before.record_at(candidate.target_record_offset)
        if _record_path(before, target) != candidate.target_path:
            raise GeneralizedDeleteError("authorized target is not present at its bound path")
        before_paths = {
            _record_path(before, record) for record in before.records if record.offset in before.paths
        }
        after_paths = {
            _record_path(post, record) for record in post.records if record.offset in post.paths
        }
        if before_paths - after_paths != {candidate.target_path} or after_paths - before_paths:
            raise GeneralizedDeleteError("post-delete path delta is not exactly one authorized removal")
        if len(post.records) != len(before.records) - 1:
            raise GeneralizedDeleteError("post-delete record count did not decrease by exactly one")
        before_payloads = _file_payloads(before)
        after_payloads = _file_payloads(post)
        if set(before_payloads) - {candidate.target_path} != set(after_payloads):
            raise GeneralizedDeleteError("post-delete file path set contains an unexpected change")
        if any(before_payloads[path] != after_payloads[path] for path in after_payloads):
            raise GeneralizedDeleteError("post-delete surviving payload changed")
        actual_state = _fixed_state_from_backup(after)
        if tuple(actual_state[command] for command in FIXED_STATE_COMMANDS) != candidate.fixed_state.after:
            raise GeneralizedDeleteError("post-delete fixed state differs from derived candidate")
        before_hashes = dict(candidate.backup.object_sha256_by_key)
        after_hashes = dict(after.object_sha256_by_key)
        if set(before_hashes) != set(after_hashes):
            raise GeneralizedDeleteError("complete backup object set changed")
        unrelated = (set(before_hashes) | set(after_hashes)) - _PAYLOAD_DEPENDENT_KEYS - set(_FIXED_STATE_KEYS.values())
        if any(before_hashes[key] != after_hashes[key] for key in unrelated):
            raise GeneralizedDeleteError("an unrelated backup object changed after delete")
    except GeneralizedDeleteVerificationError:
        raise
    except (BackupFormatError, GeneralizedDeleteError, WriteGateError, OSError) as exc:
        raise GeneralizedDeleteVerificationError(str(exc)) from exc
    return GeneralizedDeleteVerification(
        before=candidate.backup,
        after=after,
        completion=0,
        fixed_state_matches=True,
        dynamic_blob_matches=True,
        target_removed=True,
        unrelated_payloads_unchanged=True,
        unrelated_objects_unchanged=True,
        details={
            "target_path": candidate.target_path,
            "target_record_offset_hex": f"0x{candidate.target_record_offset:08x}",
            "record_count_before": len(before.records),
            "record_count_after": len(post.records),
            "fixed_state_policy": "exact_derived_after_state",
            "timestamp_policy": "preserve_surviving_timestamps",
        },
    )


__all__ = [
    "DELETE_GENERALIZED_CONFIRMATION_PHRASE",
    "DELETE_GENERALIZED_FORMAT",
    "GeneralizedDeleteAuthorization",
    "GeneralizedDeleteCandidate",
    "NestedFileDeleteCandidate",
    "GeneralizedDeleteError",
    "GeneralizedDeleteSenderBinding",
    "GeneralizedDeleteVerification",
    "GeneralizedDeleteVerificationError",
    "authorize_generalized_delete",
    "bind_generalized_delete_sender",
    "build_generalized_delete_candidate",
    "build_root_bmp_delete_candidate",
    "build_nested_file_delete_candidate",
    "verify_nested_file_delete_readback",
    "verify_generalized_delete_readback",
]
