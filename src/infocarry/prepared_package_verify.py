"""Independent offline verification for one constrained package result."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Optional

from .backup_format import BackupFormatError, ParsedBackupBlob, parse_backup_blob
from .prepared_package_candidate import PreparedPackageCandidate
from .prepared_package_gate import PreparedPackageAuthorization
from .write_gate import DEFAULT_MAX_AGE_SECONDS, VerifiedBackup, verify_fresh_backup


PREPARED_PACKAGE_VERIFICATION_FORMAT = "infocarry-prepared-text-package-readback-v1"
_DYNAMIC_BLOB_KEY = "0x8004:backup-blob"
_PAYLOAD_DEPENDENT_KEYS = frozenset(
    {
        "0x0024:response-0024",
        "0x8004:backup-blob-probe",
        _DYNAMIC_BLOB_KEY,
    }
)
_FIXED_STATE_KEYS = (
    "0x001b:response-001b",
    "0x001c:response-001c",
    "0x001d:response-001d",
    "0x001e:response-001e",
    "0x001f:response-001f",
)


class PreparedPackageVerificationError(RuntimeError):
    """Terminal read-back failure with explicit recovery guidance."""

    def __init__(self, message: str, *, outcome: str = "indeterminate") -> None:
        self.outcome = outcome
        self.automatic_retry_allowed = False
        self.recovery_guidance = (
            "Preserve the before-backup and audit, do not retry automatically, "
            "reconnect only for a read-only detection/backup, and assess the device state."
        )
        super().__init__(
            f"{message}; terminal {outcome} result; automatic retry is prohibited. "
            + self.recovery_guidance
        )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_verified_object(backup: VerifiedBackup, key: str) -> bytes:
    filename = backup.object_filename(key)
    expected = backup.object_sha256(key)
    if filename is None or expected is None:
        raise PreparedPackageVerificationError(f"backup is missing required object {key}")
    try:
        data = (backup.directory / filename).read_bytes()
    except OSError as exc:
        raise PreparedPackageVerificationError(f"could not read backup object {key}: {exc}") from exc
    if _sha256(data) != expected:
        raise PreparedPackageVerificationError(f"backup object {key} changed after verification")
    return data


def _record_for_path(parsed: ParsedBackupBlob, path: tuple[str, ...]) -> Any:
    offsets = [offset for offset, value in parsed.paths.items() if value == path]
    if len(offsets) != 1:
        raise PreparedPackageVerificationError(
            f"expected exactly one reachable record at {'\\'.join(path)}"
        )
    return parsed.record_at(offsets[0])


def _compare_shared_records(before: ParsedBackupBlob, after: ParsedBackupBlob) -> int:
    shared_paths = set(before.paths.values())
    for path in sorted(shared_paths):
        old = _record_for_path(before, path)
        new = _record_for_path(after, path)
        if (
            old.kind,
            old.extension,
            old.name,
            old.field_10_be32,
            old.field_14_be32,
            old.timestamp_be32,
        ) != (
            new.kind,
            new.extension,
            new.name,
            new.field_10_be32,
            new.field_14_be32,
            new.timestamp_be32,
        ):
            raise PreparedPackageVerificationError(
                f"shared metadata changed at {'\\'.join(path)}"
            )
        if old.kind == "file":
            try:
                old_prefix, old_payload = before.payload_parts(old)
                new_prefix, new_payload = after.payload_parts(new)
            except BackupFormatError as exc:
                raise PreparedPackageVerificationError(
                    f"shared payload is malformed at {'\\'.join(path)}"
                ) from exc
            if old_prefix != new_prefix:
                raise PreparedPackageVerificationError(
                    f"shared native prefix changed at {'\\'.join(path)}"
                )
            if old_payload != new_payload:
                raise PreparedPackageVerificationError(
                    f"shared payload changed at {'\\'.join(path)}"
                )
    return len(shared_paths)


def _compare_unrelated_objects(before: VerifiedBackup, after: VerifiedBackup) -> int:
    before_hashes = dict(before.object_sha256_by_key)
    after_hashes = dict(after.object_sha256_by_key)
    if set(before_hashes) != set(after_hashes):
        raise PreparedPackageVerificationError("complete backup object set changed")
    changed = []
    for key in before_hashes:
        if key in _PAYLOAD_DEPENDENT_KEYS:
            continue
        if before_hashes[key] != after_hashes[key]:
            changed.append(key)
    if changed:
        raise PreparedPackageVerificationError(
            "unrelated backup objects changed: " + ", ".join(sorted(changed))
        )
    return len(set(before_hashes) - _PAYLOAD_DEPENDENT_KEYS)


@dataclass(frozen=True)
class PreparedPackageReadbackVerification:
    """Successful independent comparison result."""

    before: VerifiedBackup
    after: VerifiedBackup
    completion: int
    candidate_blob_sha256: str
    shared_path_count: int
    unchanged_object_count: int
    fixed_state_sha256: tuple[str, ...]
    details: dict[str, Any]

    @property
    def success(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": PREPARED_PACKAGE_VERIFICATION_FORMAT,
            "state": "readback_verified",
            "success": True,
            "completion": "0x0000",
            "before_backup": self.before.to_dict(),
            "after_backup": self.after.to_dict(),
            "candidate_blob_sha256": self.candidate_blob_sha256,
            "shared_path_count": self.shared_path_count,
            "unchanged_object_count": self.unchanged_object_count,
            "fixed_state_sha256": list(self.fixed_state_sha256),
            "details": dict(self.details),
            "automatic_retry": False,
        }


def verify_prepared_package_readback(
    authorization: PreparedPackageAuthorization,
    candidate: PreparedPackageCandidate,
    post_directory: Path,
    *,
    completion: Any,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> PreparedPackageReadbackVerification:
    """Verify one complete fake/read-only post-operation backup.

    This function does not capture, send, retry, or infer a physical device
    result.  A valid result requires the exact operation authorization and a
    complete post-operation backup whose dynamic blob equals the candidate.
    """

    if not isinstance(authorization, PreparedPackageAuthorization):
        raise PreparedPackageVerificationError("read-back authorization is invalid", outcome="failed")
    if not isinstance(candidate, PreparedPackageCandidate):
        raise PreparedPackageVerificationError("read-back candidate is invalid", outcome="failed")
    try:
        authorization.require_same_candidate(candidate)
    except Exception as exc:
        raise PreparedPackageVerificationError(f"authorization binding failed: {exc}", outcome="failed") from exc
    if isinstance(completion, bool) or not isinstance(completion, int):
        raise PreparedPackageVerificationError("completion is missing or malformed", outcome="failed")
    if completion != 0:
        raise PreparedPackageVerificationError(
            f"completion was 0x{completion:04x}; only 0x0000 is accepted",
            outcome="failed",
        )

    try:
        before = authorization.revalidate(
            candidate,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        after = verify_fresh_backup(
            Path(post_directory),
            now=now,
            max_age_seconds=max_age_seconds,
        )
    except PreparedPackageVerificationError:
        raise
    except Exception as exc:
        raise PreparedPackageVerificationError(
            f"complete post-operation backup could not be verified: {exc}"
        ) from exc

    if after.device_identity != authorization.device_identity:
        raise PreparedPackageVerificationError("post-operation device identity differs")
    actual_blob = _read_verified_object(after, _DYNAMIC_BLOB_KEY)
    if actual_blob != candidate.candidate.data:
        raise PreparedPackageVerificationError("post-operation dynamic blob does not exactly match the candidate")
    try:
        after_parsed = parse_backup_blob(actual_blob)
    except BackupFormatError as exc:
        raise PreparedPackageVerificationError("post-operation dynamic blob is malformed") from exc

    before_paths = set(before_path for before_path in candidate.baseline.paths.values())
    expected_paths = before_paths | {
        ("root", candidate.package.folder_name),
        ("root", candidate.package.folder_name, candidate.package.item.name[:-4]),
    }
    actual_paths = set(after_parsed.paths.values())
    if actual_paths != expected_paths:
        removed = sorted("\\".join(path) for path in expected_paths - actual_paths)
        added = sorted("\\".join(path) for path in actual_paths - expected_paths)
        raise PreparedPackageVerificationError(
            f"unexpected post-operation path delta; removed={removed}, added={added}"
        )
    shared_count = _compare_shared_records(candidate.baseline, after_parsed)
    folder = _record_for_path(after_parsed, ("root", candidate.package.folder_name))
    child = _record_for_path(
        after_parsed,
        ("root", candidate.package.folder_name, candidate.package.item.name[:-4]),
    )
    try:
        leading = after_parsed.record_at(folder.offset + 0x40)
    except Exception as exc:
        raise PreparedPackageVerificationError("post-operation folder marker is missing") from exc
    expected_timestamp = authorization.new_record_timestamp_be32
    if (
        folder.timestamp_be32 != expected_timestamp
        or leading.kind != "directory"
        or leading.name != ".."
        or leading.timestamp_be32 != expected_timestamp
        or child.timestamp_be32 != expected_timestamp
    ):
        raise PreparedPackageVerificationError("new package record timestamp or marker is incorrect")

    fixed_hashes = []
    for index, key in enumerate(_FIXED_STATE_KEYS):
        data = _read_verified_object(after, key)
        digest = _sha256(data)
        if digest != authorization.fixed_state_sha256[index]:
            raise PreparedPackageVerificationError(f"fixed-state object {key} differs from authorization")
        fixed_hashes.append(digest)
    unchanged_objects = _compare_unrelated_objects(before, after)
    return PreparedPackageReadbackVerification(
        before=before,
        after=after,
        completion=completion,
        candidate_blob_sha256=_sha256(actual_blob),
        shared_path_count=shared_count,
        unchanged_object_count=unchanged_objects,
        fixed_state_sha256=tuple(fixed_hashes),
        details={
            "authorized_folder_path": candidate.package.target_folder_path,
            "authorized_child_path": candidate.package.target_item_path,
            "removed_paths": [],
            "added_paths": [candidate.package.target_folder_path, candidate.package.target_item_path],
            "shared_payloads_unchanged": True,
            "shared_native_prefixes_unchanged": True,
            "shared_timestamps_unchanged": True,
            "fixed_state_exact": True,
            "unrelated_objects_unchanged": True,
        },
    )


__all__ = [
    "PREPARED_PACKAGE_VERIFICATION_FORMAT",
    "PreparedPackageReadbackVerification",
    "PreparedPackageVerificationError",
    "verify_prepared_package_readback",
]
