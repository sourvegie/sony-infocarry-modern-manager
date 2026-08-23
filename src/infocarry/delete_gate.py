"""Offline selective-delete construction, authorization, and verification.

This module is the narrow Milestone H boundary for one root-level TXT leaf.
It composes the existing structural repacker with the already validated
``0x101b`` transaction artifact and generic one-shot sender. It never opens
USB, changes a backup, updates Manager sidecars, or exposes a CLI/GUI action.

The legacy attempt-02 timestamp behavior is deliberately opaque. A caller
must provide the complete observed per-record timestamp map; no timestamp
rule is synthesized. The transmitted ``0x001d`` form is likewise fixed to the
observed attempt-02 transient and is not replaced with the later normalized
post-backup form.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from .backup_format import BackupFormatError, ParsedBackupBlob, parse_backup_blob
from .backup_repack import BackupRepackError, delete_existing_file
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


DELETE_ONE_CONFIRMATION_PHRASE = "DELETE ONE INFOCARRY ITEM"
DELETE_GATE_FORMAT = "infocarry-delete-gate-v1"
_FIXED_STATE_LENGTH = 0x40
_FIXED_STATE_COMMANDS = (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)
_FIXED_STATE_KINDS = {
    0x001B: "response-001b",
    0x001C: "response-001c",
    0x001D: "response-001d",
    0x001E: "response-001e",
    0x001F: "response-001f",
}
_DYNAMIC_BLOB_KEY = "0x8004:backup-blob"
_PAYLOAD_DEPENDENT_KEYS = frozenset(
    {
        "0x0024:response-0024",
        "0x8004:backup-blob-probe",
        _DYNAMIC_BLOB_KEY,
    }
)
_TRANSMITTED_001D = b"\x00\x00\x00\x00\x00\x01" + b"\x00" * 58


class DeleteGateError(RuntimeError):
    """Raised when the offline delete boundary cannot be satisfied safely."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value.lower())
    ):
        raise DeleteGateError(f"{label} must be a lowercase SHA-256 hex digest")
    return value.lower()


def _require_uint(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFFFFFFFF:
        raise DeleteGateError(f"{label} must fit an unsigned 32-bit integer")
    return value


def _record_path(parsed: ParsedBackupBlob, record: Any) -> Optional[str]:
    parts = parsed.paths.get(record.offset)
    if parts is None:
        return None
    path = "\\".join(parts)
    return f"{path}.{record.extension}" if record.extension else path


def _read_verified_blob(backup: VerifiedBackup) -> bytes:
    filename = backup.object_filename(_DYNAMIC_BLOB_KEY)
    if filename is None:
        raise DeleteGateError("verified backup has no dynamic backup blob")
    try:
        return (backup.directory / filename).read_bytes()
    except OSError as exc:
        raise DeleteGateError(f"could not read verified backup blob: {exc}") from exc


def _timestamp_map_sha256(metadata_timestamps: Mapping[int, int]) -> str:
    digest = hashlib.sha256()
    for offset in sorted(metadata_timestamps):
        digest.update(offset.to_bytes(4, "big"))
        digest.update(metadata_timestamps[offset].to_bytes(4, "big"))
    return digest.hexdigest()


@dataclass(frozen=True)
class DeleteFixedState:
    """The five raw fixed-state blocks transmitted in a delete candidate."""

    offset_lists: tuple[bytes, bytes, bytes, bytes]
    grouped_values: bytes

    def __post_init__(self) -> None:
        if len(self.offset_lists) != 4:
            raise DeleteGateError("delete fixed state requires four offset-list blocks")
        if any(
            not isinstance(block, bytes) or len(block) != _FIXED_STATE_LENGTH
            for block in self.offset_lists
        ):
            raise DeleteGateError("delete offset-list blocks must each be 64 bytes")
        if not isinstance(self.grouped_values, bytes) or len(self.grouped_values) != _FIXED_STATE_LENGTH:
            raise DeleteGateError("delete grouped-values block must be 64 bytes")
        if self.offset_lists[2] != _TRANSMITTED_001D:
            raise DeleteGateError(
                "delete candidate must preserve the observed attempt-02 0x001d form"
            )

    @classmethod
    def attempt02(cls) -> "DeleteFixedState":
        """Return the preserved attempt-02 transmitted fixed-state shape."""

        return cls(
            offset_lists=(b"\x00" * 0x40, b"\x00" * 0x40, _TRANSMITTED_001D, b"\x00" * 0x40),
            grouped_values=b"\x00" * 0x40,
        )

    @property
    def range1(self) -> bytes:
        return b"".join(self.offset_lists)


ATTEMPT02_TRANSMITTED_FIXED_STATE = DeleteFixedState.attempt02()


def _fixed_state_from_transaction(transaction: ProspectiveWriteTransaction) -> tuple[bytes, ...]:
    return tuple(
        transaction.ranges[0][index * _FIXED_STATE_LENGTH : (index + 1) * _FIXED_STATE_LENGTH]
        for index in range(4)
    ) + (transaction.ranges[1],)


def _file_payloads(parsed: ParsedBackupBlob) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for record in parsed.records:
        if record.kind != "file" or record.offset not in parsed.paths:
            continue
        path = _record_path(parsed, record)
        if path is None:
            continue
        try:
            _prefix, payload = parsed.payload_parts(record)
        except BackupFormatError as exc:
            raise DeleteGateError(f"file payload is malformed at 0x{record.offset:x}: {exc}") from exc
        if path in result:
            raise DeleteGateError(f"reachable file path is duplicated: {path}")
        result[path] = payload
    return result


def _resolve_parent_offset(parsed: ParsedBackupBlob, target_record: Any, target_path: str) -> int:
    parent_path = parsed.paths[target_record.offset][:-1]
    matches = [
        offset
        for offset, path in parsed.paths.items()
        if path == parent_path and parsed.record_at(offset).kind == "directory"
    ]
    if len(matches) != 1:
        raise DeleteGateError(f"could not resolve the parent of {target_path}")
    return matches[0]


def _geometry(parsed: ParsedBackupBlob, target_record: Any) -> tuple[int, int, int, int]:
    try:
        prefix, payload = parsed.payload_parts(target_record)
    except BackupFormatError as exc:
        raise DeleteGateError(f"delete target payload is malformed: {exc}") from exc
    segment_start = target_record.field_04_be32
    segment_length = len(prefix) + len(payload)
    segment_end = segment_start + segment_length
    aligned_end = segment_end + ((-segment_end) % 4)
    content_length = parsed.header.content_length
    if segment_start < 0 or aligned_end > content_length:
        raise DeleteGateError("delete target content segment is outside the content region")
    for record in parsed.records:
        if record.kind != "file" or record.offset == target_record.offset:
            continue
        try:
            other_prefix, other_payload = parsed.payload_parts(record)
        except BackupFormatError as exc:
            raise DeleteGateError(f"unrelated file payload is malformed: {exc}") from exc
        other_start = record.field_04_be32
        other_end = other_start + len(other_prefix) + len(other_payload)
        if other_start < aligned_end and other_end > segment_start:
            raise DeleteGateError("delete target overlaps another file segment or alignment gap")
    return segment_start, segment_end, aligned_end, aligned_end - segment_start


def _expected_record_after_delete(
    parsed: ParsedBackupBlob,
    record: Any,
    target_offset: int,
    aligned_end: int,
    removed_content_length: int,
    parent_offset: int,
    metadata_timestamps: Mapping[int, int],
) -> bytes:
    raw = bytearray.fromhex(record.raw_hex)
    record_size = parsed.header.record_size
    raw[0x0C:0x10] = metadata_timestamps[record.offset].to_bytes(4, "big")
    if record.kind == "directory":
        if record.field_04_be32 >= target_offset:
            raw[0x04:0x08] = (record.field_04_be32 - record_size).to_bytes(4, "big")
        if record.offset == parent_offset:
            raw[0x08:0x0C] = (record.field_08_be32 - record_size).to_bytes(4, "big")
        elif (
            record.name == ".."
            and record.field_08_be32 in {target_offset, target_offset + record_size}
        ):
            raw[0x08:0x0C] = (record.field_08_be32 - record_size).to_bytes(4, "big")
    elif record.kind == "file" and record.field_04_be32 >= aligned_end:
        raw[0x04:0x08] = (record.field_04_be32 - removed_content_length).to_bytes(4, "big")
    return bytes(raw)


def _verify_record_preservation(
    before: ParsedBackupBlob,
    after: ParsedBackupBlob,
    target_record: Any,
    target_offset: int,
    aligned_end: int,
    removed_content_length: int,
    parent_offset: int,
    metadata_timestamps: Mapping[int, int],
) -> None:
    for record in before.records:
        if record.offset == target_record.offset:
            continue
        expected_offset = record.offset if record.offset < target_offset else record.offset - 0x40
        try:
            actual = after.record_at(expected_offset)
        except BackupFormatError as exc:
            raise DeleteGateError(
                f"unrelated record 0x{record.offset:x} did not rebase to the expected offset"
            ) from exc
        expected = _expected_record_after_delete(
            before,
            record,
            target_offset,
            aligned_end,
            removed_content_length,
            parent_offset,
            metadata_timestamps,
        )
        if actual.raw_hex != expected.hex():
            raise DeleteGateError(
                f"unrelated record metadata changed at 0x{record.offset:x}"
            )


@dataclass(frozen=True)
class DeleteCandidate:
    """One exact, offline-only candidate for deleting one root TXT leaf."""

    baseline: VerifiedBackup
    transaction: ProspectiveWriteTransaction
    target_path: str
    target_record_offset: int
    target_payload_sha256: str
    audit: dict[str, Any]

    @property
    def candidate_blob(self) -> bytes:
        return self.transaction.ranges[4] + self.transaction.ranges[7]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.audit)


def build_delete_candidate(
    backup_directory: Path,
    target_path: str,
    target_record_offset: int,
    metadata_timestamps: Mapping[int, int],
    *,
    fixed_state: DeleteFixedState = ATTEMPT02_TRANSMITTED_FIXED_STATE,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> DeleteCandidate:
    """Build one root-level TXT delete candidate from a fresh verified backup.

    The timestamp map is required because attempt 02 shows a native rewrite
    but does not establish its semantic rule. Requiring the complete opaque
    map is fail-closed and makes exact reproduction auditable.
    """

    if not isinstance(target_path, str) or not target_path or "\x00" in target_path:
        raise DeleteGateError("delete target path must be a non-empty NUL-free string")
    if not target_path.startswith("root\\") or target_path.count("\\") != 1:
        raise DeleteGateError("delete target must be one root-level file")
    if not target_path.lower().endswith(".txt"):
        raise DeleteGateError("delete target must be a root-level TXT file")
    if isinstance(target_record_offset, bool) or not isinstance(target_record_offset, int):
        raise DeleteGateError("delete target record offset must be an integer")
    if not isinstance(metadata_timestamps, Mapping):
        raise DeleteGateError("metadata_timestamps are required; no timestamp rule is inferred")
    if not isinstance(fixed_state, DeleteFixedState):
        raise DeleteGateError("fixed_state must be a DeleteFixedState")

    try:
        baseline = verify_fresh_backup(
            backup_directory,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        baseline_blob = _read_verified_blob(baseline)
        before = parse_backup_blob(baseline_blob)
        target = before.record_at(target_record_offset)
    except (BackupFormatError, DeleteGateError, WriteGateError, OSError) as exc:
        raise DeleteGateError(f"could not resolve delete target from fresh backup: {exc}") from exc
    if target.kind != "file" or target.extension.lower() != "txt":
        raise DeleteGateError("delete target must be a reachable TXT file")
    if _record_path(before, target) != target_path:
        raise DeleteGateError("delete target path does not match the authorized record")
    try:
        _prefix, target_payload = before.payload_parts(target)
    except BackupFormatError as exc:
        raise DeleteGateError(f"delete target payload is malformed: {exc}") from exc

    expected_offsets = {record.offset for record in before.records if record.offset != target_record_offset}
    if set(metadata_timestamps) != expected_offsets:
        raise DeleteGateError(
            "metadata_timestamps must contain exactly every surviving record offset"
        )
    for offset, timestamp in metadata_timestamps.items():
        _require_uint(offset, "metadata timestamp record offset")
        _require_uint(timestamp, f"metadata timestamp at 0x{offset:x}")

    parent_offset = _resolve_parent_offset(before, target, target_path)
    segment_start, segment_end, aligned_end, removed_content_length = _geometry(before, target)
    try:
        candidate_blob = delete_existing_file(
            before,
            target_record_offset,
            metadata_timestamps=metadata_timestamps,
        )
    except BackupRepackError as exc:
        raise DeleteGateError(f"offline delete repacking failed: {exc}") from exc
    after_candidate = parse_backup_blob(candidate_blob)
    _verify_record_preservation(
        before,
        after_candidate,
        target,
        target_record_offset,
        aligned_end,
        removed_content_length,
        parent_offset,
        metadata_timestamps,
    )
    before_paths = {
        _record_path(before, record)
        for record in before.records
        if record.offset in before.paths
    }
    after_paths = {
        _record_path(after_candidate, record)
        for record in after_candidate.records
        if record.offset in after_candidate.paths
    }
    if before_paths - after_paths != {target_path} or after_paths - before_paths:
        raise DeleteGateError("candidate path delta is not exactly the authorized target")
    before_payloads = _file_payloads(before)
    after_payloads = _file_payloads(after_candidate)
    if set(before_payloads) - {target_path} != set(after_payloads):
        raise DeleteGateError("candidate file path set is not preserved apart from the target")
    if any(before_payloads[path] != after_payloads[path] for path in after_payloads):
        raise DeleteGateError("candidate changed an unrelated file payload")

    try:
        transaction = ProspectiveWriteTransaction(
            ranges=(
                fixed_state.range1,
                fixed_state.grouped_values,
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
    except WriteArtifactError as exc:
        raise DeleteGateError(f"delete transaction construction failed: {exc}") from exc

    target_payload_sha256 = _sha256(target_payload)
    candidate_blob_sha256 = _sha256(candidate_blob)
    audit = {
        "format": DELETE_GATE_FORMAT,
        "state": "offline_candidate",
        "usb_transmission_performed": False,
        "operation": "delete_one_root_txt",
        "device_identity": {
            "vendor_id": baseline.device_identity[0],
            "product_id": baseline.device_identity[1],
        },
        "baseline": {
            "manifest_sha256": baseline.manifest_sha256,
            "blob_sha256": baseline.blob_sha256,
            "record_count": len(before.records),
        },
        "target": {
            "path": target_path,
            "record_offset_hex": f"0x{target_record_offset:08x}",
            "payload_sha256": target_payload_sha256,
            "payload_length": len(target_payload),
        },
        "candidate": {
            "blob_sha256": candidate_blob_sha256,
            "transaction_sha256": transaction.concatenated_sha256,
            "record_count": len(after_candidate.records),
            "removed_path": target_path,
            "added_paths": [],
            "range_lengths": [len(data) for data in transaction.ranges],
        },
        "allocation": {
            "metadata_delta": -0x40,
            "content_segment_start": segment_start,
            "content_segment_end": segment_end,
            "aligned_content_end": aligned_end,
            "removed_aligned_bytes": removed_content_length,
            "parent_record_offset_hex": f"0x{parent_offset:08x}",
        },
        "timestamps": {
            "classification": "observed_opaque_map",
            "rule_inferred": False,
            "record_count": len(metadata_timestamps),
            "map_sha256": _timestamp_map_sha256(metadata_timestamps),
        },
        "fixed_state": {
            "classification": "observed_attempt_02_transmitted_form",
            "zero_completion_required": True,
            "001d_transmitted": {
                "count": 0,
                "value_04": 1,
                "record_offsets": [],
            },
            "post_backup_normalization_allowed": {
                "field": "0x001d.value_04",
                "from": 1,
                "to": 0,
            },
        },
        "sidecars": {
            "included_in_transaction": False,
            "policy": "preserve_manager_local_files_byte_for_byte",
        },
        "safety": {
            "device_accessed": False,
            "candidate_bytes_included": False,
            "automatic_retry_allowed": False,
        },
    }
    return DeleteCandidate(
        baseline=baseline,
        transaction=transaction,
        target_path=target_path,
        target_record_offset=target_record_offset,
        target_payload_sha256=target_payload_sha256,
        audit=audit,
    )


@dataclass(frozen=True)
class DeleteAuthorization:
    """Exact candidate and fresh-backup binding for a future delete sender."""

    device_identity: tuple[str, str]
    baseline_manifest_sha256: str
    baseline_blob_sha256: str
    target_path: str
    target_record_offset: int
    target_payload_sha256: str
    candidate_blob_sha256: str
    candidate_transaction_sha256: str
    confirmation_phrase: str
    baseline: VerifiedBackup

    def __post_init__(self) -> None:
        if self.confirmation_phrase != DELETE_ONE_CONFIRMATION_PHRASE:
            raise DeleteGateError("authorization does not contain the delete confirmation phrase")
        if self.device_identity != ("0x054c", "0x001e"):
            raise DeleteGateError("authorization device identity is not the verified InfoCarry")
        _require_sha256(self.baseline_manifest_sha256, "baseline manifest hash")
        _require_sha256(self.baseline_blob_sha256, "baseline blob hash")
        _require_sha256(self.target_payload_sha256, "target payload hash")
        _require_sha256(self.candidate_blob_sha256, "candidate blob hash")
        _require_sha256(self.candidate_transaction_sha256, "candidate transaction hash")
        _require_uint(self.target_record_offset, "target record offset")

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": DELETE_GATE_FORMAT,
            "state": "authorized_for_future_writer_only",
            "usb_transmission_performed": False,
            "operation": "delete_one_root_txt",
            "device": {
                "vendor_id": self.device_identity[0],
                "product_id": self.device_identity[1],
            },
            "baseline_manifest_sha256": self.baseline_manifest_sha256,
            "baseline_blob_sha256": self.baseline_blob_sha256,
            "target_path": self.target_path,
            "target_record_offset_hex": f"0x{self.target_record_offset:08x}",
            "target_payload_sha256": self.target_payload_sha256,
            "candidate_blob_sha256": self.candidate_blob_sha256,
            "candidate_transaction_sha256": self.candidate_transaction_sha256,
            "confirmation_phrase": self.confirmation_phrase,
        }

    def require_same_candidate(self, candidate: DeleteCandidate) -> None:
        if not isinstance(candidate, DeleteCandidate):
            raise DeleteGateError("candidate must be a DeleteCandidate")
        checks = (
            (candidate.baseline.device_identity, self.device_identity, "device identity"),
            (candidate.baseline.manifest_sha256, self.baseline_manifest_sha256, "baseline manifest"),
            (candidate.baseline.blob_sha256, self.baseline_blob_sha256, "baseline blob"),
            (candidate.target_path, self.target_path, "target path"),
            (candidate.target_record_offset, self.target_record_offset, "target record offset"),
            (candidate.target_payload_sha256, self.target_payload_sha256, "target payload"),
            (candidate.audit["candidate"]["blob_sha256"], self.candidate_blob_sha256, "candidate blob"),
            (candidate.transaction.concatenated_sha256, self.candidate_transaction_sha256, "candidate transaction"),
        )
        for actual, expected, label in checks:
            if actual != expected:
                raise DeleteGateError(f"candidate {label} differs from authorization")

    def revalidate(
        self,
        candidate: DeleteCandidate,
        *,
        now: Optional[datetime] = None,
        max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
    ) -> VerifiedBackup:
        self.require_same_candidate(candidate)
        verified = verify_fresh_backup(
            self.baseline.directory,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        if verified.device_identity != self.device_identity:
            raise DeleteGateError("bound device identity changed")
        if verified.manifest_sha256 != self.baseline_manifest_sha256:
            raise DeleteGateError("bound baseline manifest changed")
        if verified.blob_sha256 != self.baseline_blob_sha256:
            raise DeleteGateError("bound baseline blob changed")
        before = parse_backup_blob(_read_verified_blob(verified))
        target = before.record_at(self.target_record_offset)
        if target.kind != "file" or target.extension.lower() != "txt":
            raise DeleteGateError("fresh backup target is no longer a reachable TXT file")
        if _record_path(before, target) != self.target_path:
            raise DeleteGateError("fresh backup target path differs from authorization")
        _prefix, payload = before.payload_parts(target)
        if _sha256(payload) != self.target_payload_sha256:
            raise DeleteGateError("fresh backup target payload differs from authorization")
        return verified


def authorize_delete(
    candidate: DeleteCandidate,
    *,
    confirmation: str,
) -> DeleteAuthorization:
    """Authorize only one exact candidate after the delete-specific phrase."""

    if confirmation != DELETE_ONE_CONFIRMATION_PHRASE:
        raise DeleteGateError("delete confirmation phrase was not accepted")
    authorization = DeleteAuthorization(
        device_identity=candidate.baseline.device_identity,
        baseline_manifest_sha256=candidate.baseline.manifest_sha256,
        baseline_blob_sha256=candidate.baseline.blob_sha256,
        target_path=candidate.target_path,
        target_record_offset=candidate.target_record_offset,
        target_payload_sha256=candidate.target_payload_sha256,
        candidate_blob_sha256=candidate.audit["candidate"]["blob_sha256"],
        candidate_transaction_sha256=candidate.transaction.concatenated_sha256,
        confirmation_phrase=confirmation,
        baseline=candidate.baseline,
    )
    authorization.require_same_candidate(candidate)
    return authorization


@dataclass(frozen=True)
class DeleteTransportAuthorization:
    """Sender-compatible adapter with no USB handle or transport behavior."""

    binding: DeleteAuthorization
    candidate: DeleteCandidate
    now: Optional[datetime] = None
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS

    @property
    def backup(self) -> VerifiedBackup:
        return self.binding.baseline

    def __post_init__(self) -> None:
        if not isinstance(self.binding, DeleteAuthorization):
            raise DeleteGateError("sender binding requires DeleteAuthorization")
        self.binding.require_same_candidate(self.candidate)

    def revalidate(self, transaction: ProspectiveWriteTransaction) -> None:
        if not isinstance(transaction, ProspectiveWriteTransaction):
            raise DeleteGateError("sender transaction must be a prospective transaction")
        if transaction.concatenated_sha256 != self.candidate.transaction.concatenated_sha256:
            raise DeleteGateError("sender transaction differs from the bound candidate")
        self.binding.revalidate(
            self.candidate,
            now=self.now,
            max_age_seconds=self.max_age_seconds,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": "authorized_for_future_writer_only",
            "usb_transmission_performed": False,
            "binding": self.binding.to_dict(),
            "candidate_transaction_sha256": self.candidate.transaction.concatenated_sha256,
        }


def bind_delete_sender(
    authorization: DeleteAuthorization,
    candidate: DeleteCandidate,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> DeleteTransportAuthorization:
    adapter = DeleteTransportAuthorization(
        binding=authorization,
        candidate=candidate,
        now=now,
        max_age_seconds=max_age_seconds,
    )
    adapter.revalidate(candidate.transaction)
    return adapter


@dataclass(frozen=True)
class DeleteVerification:
    """Independent post-delete assessment with explicit normalization scope."""

    before: VerifiedBackup
    after: VerifiedBackup
    completion: int
    fixed_state_matches: bool
    dynamic_blob_matches: bool
    target_removed: bool
    no_unexpected_path_delta: bool
    unrelated_payloads_unchanged: bool
    unrelated_metadata_preserved: bool
    allowed_fixed_state_normalization: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "before_backup": self.before.to_dict(),
            "after_backup": self.after.to_dict(),
            "completion": f"0x{self.completion:04x}",
            "fixed_state_matches": self.fixed_state_matches,
            "dynamic_blob_matches": self.dynamic_blob_matches,
            "target_removed": self.target_removed,
            "no_unexpected_path_delta": self.no_unexpected_path_delta,
            "unrelated_payloads_unchanged": self.unrelated_payloads_unchanged,
            "unrelated_metadata_preserved": self.unrelated_metadata_preserved,
            "allowed_fixed_state_normalization": self.allowed_fixed_state_normalization,
        }


def _verify_fixed_state(candidate: DeleteCandidate, after: VerifiedBackup) -> None:
    actual = []
    for command in _FIXED_STATE_COMMANDS:
        kind = _FIXED_STATE_KINDS[command]
        key = f"0x{command:04x}:{kind}"
        filename = after.object_filename(key)
        if filename is None:
            raise DeleteGateError(f"post-delete backup is missing fixed state {key}")
        try:
            value = (after.directory / filename).read_bytes()
        except OSError as exc:
            raise DeleteGateError(f"could not read post-delete fixed state {key}: {exc}") from exc
        if len(value) != _FIXED_STATE_LENGTH:
            raise DeleteGateError(f"post-delete fixed state {key} is not 64 bytes")
        actual.append(value)
    expected = _fixed_state_from_transaction(candidate.transaction)
    for index, (wanted, observed) in enumerate(zip(expected, actual)):
        if index != 2:
            if observed != wanted:
                raise DeleteGateError(f"post-delete fixed state differs at {_FIXED_STATE_COMMANDS[index]:#x}")
            continue
        if wanted != _TRANSMITTED_001D:
            raise DeleteGateError("candidate 0x001d is not the observed attempt-02 form")
        if observed[:4] != wanted[:4] or observed[6:] != wanted[6:]:
            raise DeleteGateError("post-delete 0x001d differs outside the allowed normalization")
        if observed[4:6] != b"\x00\x00":
            raise DeleteGateError("post-delete 0x001d normalization is not 1 to 0")


def _verify_post_blob(candidate: DeleteCandidate, before: ParsedBackupBlob, after: ParsedBackupBlob) -> None:
    target = before.record_at(candidate.target_record_offset)
    if _record_path(before, target) != candidate.target_path:
        raise DeleteGateError("before backup target no longer matches the authorization")
    before_paths = {
        _record_path(before, record)
        for record in before.records
        if record.offset in before.paths
    }
    after_paths = {
        _record_path(after, record)
        for record in after.records
        if record.offset in after.paths
    }
    if before_paths - after_paths != {candidate.target_path} or after_paths - before_paths:
        raise DeleteGateError("post-delete path delta is not exactly the authorized removal")
    if len(after.records) != len(before.records) - 1:
        raise DeleteGateError("post-delete record count did not decrease by exactly one")
    before_payloads = _file_payloads(before)
    after_payloads = _file_payloads(after)
    if set(before_payloads) - {candidate.target_path} != set(after_payloads):
        raise DeleteGateError("post-delete file path set contains an unexpected change")
    for path, payload in after_payloads.items():
        if payload != before_payloads[path]:
            raise DeleteGateError(f"post-delete unrelated payload changed: {path}")


def verify_post_delete_backup(
    candidate: DeleteCandidate,
    post_delete_directory: Path,
    *,
    completion: int,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> DeleteVerification:
    """Verify one complete read-back and reject every unapproved difference."""

    if isinstance(completion, bool) or not isinstance(completion, int):
        raise DeleteGateError("delete completion is missing or malformed; outcome is indeterminate")
    if completion != 0:
        raise DeleteGateError(
            f"delete completion was 0x{completion:04x}; terminal failure, no retry"
        )
    if not isinstance(candidate, DeleteCandidate):
        raise DeleteGateError("candidate must be a DeleteCandidate")
    before = candidate.baseline
    try:
        after = verify_fresh_backup(
            post_delete_directory,
            now=now,
            max_age_seconds=max_age_seconds,
        )
    except (BackupFormatError, DeleteGateError, WriteGateError, OSError) as exc:
        raise DeleteGateError(
            f"post-delete backup is malformed or incomplete; outcome is indeterminate: {exc}"
        ) from exc
    if after.device_identity != before.device_identity:
        raise DeleteGateError("post-delete device identity changed")
    if after.blob_sha256 != candidate.audit["candidate"]["blob_sha256"]:
        raise DeleteGateError("post-delete dynamic blob does not match the candidate")
    try:
        before_blob = parse_backup_blob(_read_verified_blob(before))
        after_blob = parse_backup_blob(_read_verified_blob(after))
    except (BackupFormatError, DeleteGateError, OSError) as exc:
        raise DeleteGateError(
            f"post-delete backup blob is malformed or incomplete; outcome is indeterminate: {exc}"
        ) from exc
    _verify_post_blob(candidate, before_blob, after_blob)
    _verify_fixed_state(candidate, after)

    before_hashes = dict(before.object_sha256_by_key)
    after_hashes = dict(after.object_sha256_by_key)
    unrelated_keys = (set(before_hashes) | set(after_hashes)) - _PAYLOAD_DEPENDENT_KEYS - {
        f"0x{command:04x}:{_FIXED_STATE_KINDS[command]}"
        for command in _FIXED_STATE_COMMANDS
    }
    if any(before_hashes.get(key) != after_hashes.get(key) for key in unrelated_keys):
        raise DeleteGateError("an unrelated backup object changed after delete")
    return DeleteVerification(
        before=before,
        after=after,
        completion=0,
        fixed_state_matches=True,
        dynamic_blob_matches=True,
        target_removed=True,
        no_unexpected_path_delta=True,
        unrelated_payloads_unchanged=True,
        unrelated_metadata_preserved=True,
        allowed_fixed_state_normalization="0x001d.value_04: 1 -> 0 only",
    )


__all__ = [
    "ATTEMPT02_TRANSMITTED_FIXED_STATE",
    "DELETE_GATE_FORMAT",
    "DELETE_ONE_CONFIRMATION_PHRASE",
    "DeleteAuthorization",
    "DeleteCandidate",
    "DeleteFixedState",
    "DeleteGateError",
    "DeleteTransportAuthorization",
    "DeleteVerification",
    "authorize_delete",
    "bind_delete_sender",
    "build_delete_candidate",
    "verify_post_delete_backup",
]
