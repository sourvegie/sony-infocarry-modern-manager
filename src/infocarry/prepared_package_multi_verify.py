"""Independent offline read-back verification for ordered packages."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional

from .backup_format import BackupFormatError, ParsedBackupBlob, parse_backup_blob
from .prepared_package_multi_candidate import (
    PreparedMultiCandidateError,
    PreparedMultiPackageCandidate,
    _display_path,
)
from .write_gate import DEFAULT_MAX_AGE_SECONDS, VerifiedBackup, verify_fresh_backup


class PreparedMultiVerificationError(RuntimeError):
    """Terminal independent-verification failure; retry is never allowed."""

    def __init__(self, message: str, *, outcome: str = "failed") -> None:
        self.outcome = outcome
        self.automatic_retry_allowed = False
        self.recovery_guidance = (
            "Preserve both backups and the audit; do not retry automatically; "
            "perform only a later read-only backup and assessment."
        )
        super().__init__(
            f"{message}; terminal {outcome} result; automatic retry is prohibited. "
            + self.recovery_guidance
        )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _object(backup: VerifiedBackup, key: str) -> bytes:
    filename = backup.object_filename(key)
    expected = backup.object_sha256(key)
    if filename is None or expected is None:
        raise PreparedMultiVerificationError(f"complete backup is missing {key}")
    try:
        data = (backup.directory / filename).read_bytes()
    except OSError as exc:
        raise PreparedMultiVerificationError(f"could not read {key}: {exc}") from exc
    if _sha256(data) != expected:
        raise PreparedMultiVerificationError(f"backup object {key} changed after verification")
    return data


def _path_record(parsed: ParsedBackupBlob, path: tuple[str, ...]):
    offsets = [offset for offset, value in parsed.paths.items() if value == path]
    if len(offsets) != 1:
        raise PreparedMultiVerificationError(f"expected one reachable record at {_display_path(path)}")
    return parsed.record_at(offsets[0])


def _compare_shared(before: ParsedBackupBlob, after: ParsedBackupBlob) -> int:
    for path in before.paths.values():
        old = _path_record(before, path)
        new = _path_record(after, path)
        old_raw = bytes.fromhex(old.raw_hex)
        new_raw = bytes.fromhex(new.raw_hex)
        if old_raw[:4] + old_raw[0x0C:] != new_raw[:4] + new_raw[0x0C:]:
            raise PreparedMultiVerificationError(f"shared metadata changed at {_display_path(path)}")
        if old.kind == "file":
            try:
                old_prefix, old_payload = before.payload_parts(old)
                new_prefix, new_payload = after.payload_parts(new)
            except BackupFormatError as exc:
                raise PreparedMultiVerificationError(f"shared file is malformed at {_display_path(path)}") from exc
            if old_prefix != new_prefix or old_payload != new_payload:
                raise PreparedMultiVerificationError(f"shared payload changed at {_display_path(path)}")
    return len(before.paths)


def _compare_fixed(candidate: PreparedMultiPackageCandidate, after: VerifiedBackup) -> tuple[str, ...]:
    hashes: list[str] = []
    for index, command in enumerate((0x001B, 0x001C, 0x001D, 0x001E, 0x001F)):
        key = f"0x{command:04x}:response-{command:04x}"
        data = _object(after, key)
        digest = _sha256(data)
        expected = _sha256(candidate.fixed_state.raw_blocks[index])
        if digest != expected:
            raise PreparedMultiVerificationError(f"fixed-state object {key} changed")
        hashes.append(digest)
    return tuple(hashes)


@dataclass(frozen=True)
class PreparedMultiPackageReadback:
    candidate: PreparedMultiPackageCandidate
    before: VerifiedBackup
    after: VerifiedBackup
    completion: int
    shared_path_count: int
    fixed_state_sha256: tuple[str, ...]
    details: Mapping[str, Any]

    @property
    def success(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "infocarry-ordered-package-readback-v1",
            "state": "readback_verified",
            "success": True,
            "completion": "0x0000",
            "candidate_blob_sha256": self.candidate.candidate_blob_sha256,
            "transaction_sha256": self.candidate.transaction_sha256,
            "before_backup": self.before.to_dict(),
            "after_backup": self.after.to_dict(),
            "shared_path_count": self.shared_path_count,
            "fixed_state_sha256": list(self.fixed_state_sha256),
            "details": dict(self.details),
            "automatic_retry": False,
        }


def verify_prepared_multi_package_readback(
    candidate: PreparedMultiPackageCandidate,
    post_directory: Path,
    *,
    completion: Any,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> PreparedMultiPackageReadback:
    """Verify a complete fake post-operation backup independently of the builder."""

    if not isinstance(candidate, PreparedMultiPackageCandidate):
        raise PreparedMultiVerificationError("candidate is invalid")
    if isinstance(completion, bool) or not isinstance(completion, int):
        raise PreparedMultiVerificationError("completion is missing or malformed")
    if completion != 0:
        raise PreparedMultiVerificationError(
            f"completion was 0x{completion:04x}; only 0x0000 is accepted"
        )
    try:
        before = verify_fresh_backup(candidate.backup.directory, now=now, max_age_seconds=max_age_seconds)
        after = verify_fresh_backup(Path(post_directory), now=now, max_age_seconds=max_age_seconds)
    except Exception as exc:
        raise PreparedMultiVerificationError(f"complete independent backup verification failed: {exc}") from exc
    if after.device_identity != candidate.backup.device_identity:
        raise PreparedMultiVerificationError("post-operation device identity differs")
    actual_blob = _object(after, "0x8004:backup-blob")
    if actual_blob != candidate.candidate.data:
        raise PreparedMultiVerificationError("post-operation dynamic blob does not match candidate")
    try:
        parsed = parse_backup_blob(actual_blob)
    except BackupFormatError as exc:
        raise PreparedMultiVerificationError("post-operation dynamic blob is malformed") from exc
    before_paths = set(candidate.baseline.paths.values())
    items = tuple(candidate.package.items)
    folder_path = ("root", candidate.package.folder_name)
    child_paths = tuple(folder_path + (item.name.rsplit(".", 1)[0],) for item in items)
    expected_paths = before_paths | {folder_path, *child_paths}
    if set(parsed.paths.values()) != expected_paths:
        removed = sorted(_display_path(path) for path in expected_paths - set(parsed.paths.values()))
        added = sorted(_display_path(path) for path in set(parsed.paths.values()) - expected_paths)
        raise PreparedMultiVerificationError(f"unexpected path delta; removed={removed}, added={added}")
    folder = _path_record(parsed, folder_path)
    if folder.kind != "directory" or folder.field_08_be32 != (len(items) + 1) * 0x40:
        raise PreparedMultiVerificationError("post-operation folder record is malformed")
    try:
        child_offsets = range(
            folder.offset + 0x80,
            folder.offset + folder.field_08_be32 + 0x40,
            0x40,
        )
        ordered = [parsed.record_at(offset) for offset in child_offsets]
    except BackupFormatError as exc:
        raise PreparedMultiVerificationError("post-operation child table is malformed") from exc
    expected_kinds = [item.kind for item in items]
    if [record.extension.lower() for record in ordered] != expected_kinds:
        raise PreparedMultiVerificationError("post-operation child order or type differs from package")
    for item, record in zip(items, ordered):
        expected_payload = item.authored.payload if item.kind == "txt" else item.source_bytes
        prefix, payload = parsed.payload_parts(record)
        if payload != expected_payload:
            raise PreparedMultiVerificationError(f"post-operation payload differs at {_display_path((folder_path, record.name), item.kind)}")
        if record.timestamp_be32 != int(candidate.audit["candidate"]["new_record_timestamp_be32"], 16):
            raise PreparedMultiVerificationError("new record timestamp differs from candidate policy")
        if _sha256(prefix) != candidate.audit["package"]["ordered_items"][ordered.index(record)]["native_prefix_sha256"]:
            raise PreparedMultiVerificationError("new record native prefix differs from candidate")
    shared_count = _compare_shared(candidate.baseline, parsed)
    fixed_hashes = _compare_fixed(candidate, after)
    ignored_payload_keys = {"0x0024:response-0024", "0x8004:backup-blob-probe", "0x8004:backup-blob"}
    before_hashes = dict(candidate.backup.object_sha256_by_key)
    after_hashes = dict(after.object_sha256_by_key)
    if set(before_hashes) != set(after_hashes):
        raise PreparedMultiVerificationError("complete backup object set changed")
    for key, digest in before_hashes.items():
        if key not in ignored_payload_keys and digest != after_hashes[key]:
            raise PreparedMultiVerificationError(f"unrelated backup object changed: {key}")
    return PreparedMultiPackageReadback(
        candidate=candidate,
        before=before,
        after=after,
        completion=completion,
        shared_path_count=shared_count,
        fixed_state_sha256=fixed_hashes,
        details={
            "added_paths": [_display_path(folder_path), *[_display_path(path, item.kind) for path, item in zip(child_paths, items)]],
            "removed_paths": [],
            "ordered_children_verified": True,
            "shared_payloads_unchanged": True,
            "shared_timestamps_unchanged": True,
            "fixed_state_exact": True,
            "automatic_retry": False,
        },
    )


__all__ = [
    "PreparedMultiPackageReadback",
    "PreparedMultiVerificationError",
    "verify_prepared_multi_package_readback",
]
