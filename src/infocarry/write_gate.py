"""Pre-write safety authorization for a future InfoCarry writer.

This module deliberately stops at authorization.  It does not open USB,
claim an interface, or transmit the prospective transaction.  A future live
writer must obtain a :class:`WriteAuthorization` immediately before sending
anything and revalidate it after any delay or backup change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from .backup_format import BackupFormatError, parse_backup_blob
from .write_artifact import ProspectiveWriteTransaction


WRITE_GATE_FORMAT = "infocarry-write-gate-v1"
DEFAULT_CONFIRMATION_PHRASE = "WRITE INFOCARRY"
TEXT_REPLACEMENT_CONFIRMATION_PHRASE = "REPLACE INFOCARRY TEXT"
DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60
_EXPECTED_DEVICE = {"vendor_id": "0x054c", "product_id": "0x001e"}
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


class WriteGateError(RuntimeError):
    """Raised when a prospective write fails a safety precondition."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise WriteGateError(f"backup manifest has no valid {label}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WriteGateError(f"backup manifest {label} is not ISO-8601") from exc
    if parsed.tzinfo is None:
        raise WriteGateError(f"backup manifest {label} has no timezone")
    return parsed.astimezone(timezone.utc)


def _validate_age_limit(max_age_seconds: Optional[float]) -> Optional[float]:
    if max_age_seconds is None:
        return None
    if (
        isinstance(max_age_seconds, bool)
        or not isinstance(max_age_seconds, (int, float))
        or max_age_seconds <= 0
    ):
        raise WriteGateError("max_age_seconds must be positive or None")
    return float(max_age_seconds)


def _safe_filename(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise WriteGateError("backup manifest contains an invalid object filename")
    path = Path(value)
    if path.is_absolute() or path.name != value or value in {".", ".."}:
        raise WriteGateError(f"backup object filename is not a simple relative name: {value!r}")
    return root / path


def _object_key(entry: Dict[str, Any]) -> str:
    command = entry.get("command")
    kind = entry.get("kind")
    if not isinstance(command, str) or not isinstance(kind, str):
        raise WriteGateError("backup manifest object has no command/kind key")
    return f"{command.lower()}:{kind}"


def _candidate_fixed_state_hashes(transaction: ProspectiveWriteTransaction) -> Tuple[str, ...]:
    """Hash the five response objects represented by ranges 1 and 2."""

    range1 = transaction.ranges[0]
    return tuple(
        _sha256(range1[index * 0x40 : (index + 1) * 0x40])
        for index in range(4)
    ) + (_sha256(transaction.ranges[1]),)


def _state_hashes_from_backup(backup: "VerifiedBackup") -> Tuple[str, ...]:
    hashes = []
    for command in _FIXED_STATE_COMMANDS:
        key = f"0x{command:04x}:{_FIXED_STATE_KINDS[command]}"
        value = backup.object_sha256(key)
        if value is None:
            raise WriteGateError(
                f"fresh backup is missing required fixed state object {key}"
            )
        hashes.append(value)
    return tuple(hashes)


@dataclass(frozen=True)
class VerifiedBackup:
    """A complete backup whose manifest and every object were re-verified."""

    directory: Path
    manifest_sha256: str
    blob_sha256: str
    created_at_utc: str
    updated_at_utc: str
    object_count: int
    verified_at_utc: str
    object_sha256_by_key: Tuple[Tuple[str, str], ...]
    object_filename_by_key: Tuple[Tuple[str, str], ...]
    device_identity: Tuple[str, str]

    def object_sha256(self, key: str) -> Optional[str]:
        for object_key, digest in self.object_sha256_by_key:
            if object_key == key:
                return digest
        return None

    def object_filename(self, key: str) -> Optional[str]:
        for object_key, filename in self.object_filename_by_key:
            if object_key == key:
                return filename
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "directory": str(self.directory),
            "manifest_sha256": self.manifest_sha256,
            "blob_sha256": self.blob_sha256,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "object_count": self.object_count,
            "verified_at_utc": self.verified_at_utc,
            "device": {
                "vendor_id": self.device_identity[0],
                "product_id": self.device_identity[1],
            },
            "object_sha256_by_key": dict(self.object_sha256_by_key),
        }


def verify_fresh_backup(
    directory: Path,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> VerifiedBackup:
    """Verify a complete raw backup and enforce a freshness window.

    Every object listed in the manifest is hashed and length-checked.  The
    dynamic backup blob is also parsed, so a stale or tampered archive cannot
    authorize a future write session.  Passing ``max_age_seconds=None`` is
    allowed for offline forensic review, but a live writer should keep the
    default bounded window.
    """

    root = directory.expanduser().resolve()
    if not root.is_dir():
        raise WriteGateError(f"backup directory does not exist: {root}")
    manifest_path = root / "manifest.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WriteGateError(f"could not read backup manifest: {exc}") from exc

    if manifest.get("format") != "infocarry-raw-backup-v1":
        raise WriteGateError("source is not an InfoCarry raw backup archive")
    if manifest.get("state") != "complete":
        raise WriteGateError("write authorization requires a complete backup")
    if manifest.get("device") != _EXPECTED_DEVICE:
        raise WriteGateError("backup device identity is not the verified InfoCarry")

    created = _parse_utc(manifest.get("created_at_utc"), "created_at_utc")
    updated = _parse_utc(manifest.get("updated_at_utc"), "updated_at_utc")
    reference_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_limit = _validate_age_limit(max_age_seconds)
    if updated > reference_time:
        raise WriteGateError("backup manifest timestamp is in the future")
    if age_limit is not None and (reference_time - updated).total_seconds() > age_limit:
        raise WriteGateError(
            f"backup is older than the permitted {age_limit:g}-second freshness window"
        )
    if updated < created:
        raise WriteGateError("backup updated_at_utc predates created_at_utc")

    objects = manifest.get("objects")
    if not isinstance(objects, list) or not objects:
        raise WriteGateError("backup manifest contains no objects")
    blob_entries = []
    object_hashes = []
    object_filenames = []
    for entry in objects:
        if not isinstance(entry, dict):
            raise WriteGateError("backup manifest contains a malformed object entry")
        path = _safe_filename(root, entry.get("filename"))
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise WriteGateError(f"could not read backup object {path}: {exc}") from exc
        expected_length = entry.get("received_length")
        if not isinstance(expected_length, int) or expected_length < 0:
            raise WriteGateError(f"backup object {path} has an invalid length")
        if len(data) != expected_length:
            raise WriteGateError(f"backup object {path} length does not match its manifest")
        if _sha256(data) != entry.get("sha256"):
            raise WriteGateError(f"backup object {path} SHA-256 does not match its manifest")
        key = _object_key(entry)
        if any(existing == key for existing, _ in object_hashes):
            raise WriteGateError(f"backup manifest contains duplicate object key {key}")
        object_hashes.append((key, entry["sha256"]))
        object_filenames.append((key, path.name))
        if entry.get("kind") == "backup-blob":
            blob_entries.append((entry, data))

    if len(blob_entries) != 1:
        raise WriteGateError("backup manifest must contain exactly one dynamic blob")
    blob_entry, blob = blob_entries[0]
    try:
        parse_backup_blob(blob)
    except BackupFormatError as exc:
        raise WriteGateError(f"backup blob failed structural validation: {exc}") from exc

    return VerifiedBackup(
        directory=root,
        manifest_sha256=_sha256(manifest_bytes),
        blob_sha256=_sha256(blob),
        created_at_utc=manifest["created_at_utc"],
        updated_at_utc=manifest["updated_at_utc"],
        object_count=len(objects),
        verified_at_utc=reference_time.isoformat(),
        object_sha256_by_key=tuple(object_hashes),
        object_filename_by_key=tuple(object_filenames),
        device_identity=(manifest["device"]["vendor_id"], manifest["device"]["product_id"]),
    )


def capture_and_verify_fresh_backup(
    destination: Path,
    capture: Callable[[Path], None],
    *,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
    reference_clock: Optional[Callable[[], datetime]] = None,
) -> VerifiedBackup:
    """Run one injected backup capture and verify the resulting archive.

    The capture callback is deliberately the only integration point for a
    future read-only transport.  This function never opens USB, retries a
    failed capture, removes an incomplete archive, or replaces an existing
    path.  The freshness reference is sampled only after the callback returns,
    so a backup whose manifest is finalized after the caller began the
    operation cannot be falsely classified as future-dated.  ``now`` remains
    accepted for source compatibility but is deliberately not used as the
    authoritative post-capture reference.  Deterministic tests may inject
    ``reference_clock``; a live caller should use the default wall clock.

    Offline tests can inject a fake callback that writes a complete archive; a
    live caller must still obtain explicit approval before wiring in a
    hardware-backed callback.
    """

    if not callable(capture):
        raise WriteGateError("fresh-backup capture must be callable")
    if reference_clock is not None and not callable(reference_clock):
        raise WriteGateError("reference_clock must be callable when supplied")
    root = Path(destination).expanduser().resolve()
    if root.exists():
        raise WriteGateError(f"refusing to replace an existing backup path: {root}")
    try:
        capture(root)
    except Exception as exc:
        raise WriteGateError(
            f"fresh backup capture failed; preserve any partial archive at {root}: {exc}"
        ) from exc
    # ``now`` is intentionally not passed through: it is commonly sampled
    # before a long USB capture.  The reference must be after the callback has
    # finalized the manifest.  Keep the argument above for compatibility with
    # existing callers while making the safe behavior unconditional.
    post_capture_reference = (
        reference_clock() if reference_clock is not None else datetime.now(timezone.utc)
    )
    try:
        return verify_fresh_backup(
            root,
            now=post_capture_reference,
            max_age_seconds=max_age_seconds,
        )
    except WriteGateError:
        raise
    except Exception as exc:
        raise WriteGateError(f"fresh backup verification failed: {exc}") from exc


def _require_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value.lower())
    ):
        raise WriteGateError(f"{label} must be a lowercase SHA-256 hex digest")
    return value.lower()


@dataclass(frozen=True)
class WriteTarget:
    """The exact existing-text target bound to a future authorization."""

    record_offset: int
    path: str
    candidate_payload_sha256: str
    before_payload_sha256: Optional[str] = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.record_offset, bool)
            or not isinstance(self.record_offset, int)
            or not 0 <= self.record_offset <= 0xFFFFFFFF
        ):
            raise WriteGateError("target record offset must fit an unsigned 32-bit integer")
        if not isinstance(self.path, str) or not self.path or "\x00" in self.path:
            raise WriteGateError("target path must be a non-empty NUL-free string")
        _require_sha256(self.candidate_payload_sha256, "candidate payload hash")
        if self.before_payload_sha256 is not None:
            _require_sha256(self.before_payload_sha256, "before payload hash")

    @classmethod
    def from_preview_report(cls, report: Dict[str, Any]) -> "WriteTarget":
        """Extract and validate target metadata from an offline preview."""

        if not isinstance(report, dict):
            raise WriteGateError("replacement preview must be a mapping")
        workflow = report.get("workflow")
        target = report.get("target")
        safety = report.get("safety")
        if not isinstance(workflow, dict) or not isinstance(target, dict):
            raise WriteGateError("replacement preview is missing target metadata")
        if not isinstance(safety, dict) or safety.get("candidate_bytes_included") is not False:
            raise WriteGateError("replacement preview is not a no-candidate audit")
        if workflow.get("device_accessed") is not False:
            raise WriteGateError("replacement preview is not device-independent")
        offset_text = workflow.get("target_record_offset")
        if not isinstance(offset_text, str):
            raise WriteGateError("replacement preview has no target record offset")
        try:
            record_offset = int(offset_text, 0)
        except ValueError as exc:
            raise WriteGateError("replacement preview target record offset is invalid") from exc
        path = workflow.get("target_path")
        if not isinstance(path, str) or not path:
            raise WriteGateError("replacement preview has no target path")
        return cls(
            record_offset=record_offset,
            path=path,
            candidate_payload_sha256=target.get("after_payload_sha256"),
            before_payload_sha256=target.get("before_payload_sha256"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_offset_hex": f"0x{self.record_offset:08x}",
            "path": self.path,
            "candidate_payload_sha256": self.candidate_payload_sha256,
            "before_payload_sha256": self.before_payload_sha256,
        }


def _record_path(parsed: Any, record: Any) -> Optional[str]:
    parts = parsed.paths.get(record.offset)
    if parts is None:
        return None
    path = "\\".join(parts)
    if record.extension:
        path = f"{path}.{record.extension}"
    return path


def _validate_target_blob(
    blob: bytes,
    target: WriteTarget,
    *,
    label: str,
    expected_payload_sha256: Optional[str] = None,
) -> bytes:
    try:
        parsed = parse_backup_blob(blob)
        record = parsed.record_at(target.record_offset)
    except BackupFormatError as exc:
        raise WriteGateError(f"{label} does not contain the authorized target: {exc}") from exc
    if record.kind != "file" or record.extension.lower() != "txt":
        raise WriteGateError(f"{label} target is not an existing TXT record")
    if _record_path(parsed, record) != target.path:
        raise WriteGateError(f"{label} target path does not match the authorization")
    try:
        _prefix, payload = parsed.payload_parts(record)
    except BackupFormatError as exc:
        raise WriteGateError(f"{label} target payload is malformed: {exc}") from exc
    expected_hash = expected_payload_sha256 or target.candidate_payload_sha256
    if _sha256(payload) != expected_hash:
        raise WriteGateError(f"{label} target payload hash does not match the authorization")
    return payload


def _verified_backup_blob(backup: VerifiedBackup) -> bytes:
    filename = backup.object_filename(_DYNAMIC_BLOB_KEY)
    if filename is None:
        raise WriteGateError("verified backup has no dynamic backup blob")
    try:
        return (backup.directory / filename).read_bytes()
    except OSError as exc:
        raise WriteGateError(f"could not read verified backup blob: {exc}") from exc


@dataclass(frozen=True)
class WriteAuthorization:
    """A short-lived, backup-bound authorization for a future writer."""

    backup: VerifiedBackup
    transaction_sha256: str
    authorized_at_utc: str
    confirmation_phrase: str
    cli_write_flag: bool
    fixed_state_sha256: Tuple[str, ...]
    target: Optional[WriteTarget] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": WRITE_GATE_FORMAT,
            "state": "authorized_for_future_writer_only",
            "usb_transmission_performed": False,
            "backup": self.backup.to_dict(),
            "target": None if self.target is None else self.target.to_dict(),
            "transaction_sha256": self.transaction_sha256,
            "authorized_at_utc": self.authorized_at_utc,
            "confirmation_phrase": self.confirmation_phrase,
            "cli_write_flag": self.cli_write_flag,
            "fixed_state_sha256": list(self.fixed_state_sha256),
        }

    def require_same_transaction(self, transaction: ProspectiveWriteTransaction) -> None:
        if not isinstance(transaction, ProspectiveWriteTransaction):
            raise WriteGateError("transaction must be a ProspectiveWriteTransaction")
        if transaction.concatenated_sha256 != self.transaction_sha256:
            raise WriteGateError("transaction bytes differ from the authorized candidate")
        if self.target is not None:
            _validate_target_blob(
                transaction.ranges[4] + transaction.ranges[7],
                self.target,
                label="candidate transaction",
            )

    def revalidate(
        self,
        transaction: ProspectiveWriteTransaction,
        *,
        now: Optional[datetime] = None,
        max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
    ) -> VerifiedBackup:
        self.require_same_transaction(transaction)
        verified = verify_fresh_backup(
            self.backup.directory, now=now, max_age_seconds=max_age_seconds
        )
        if verified.device_identity != self.backup.device_identity:
            raise WriteGateError("device identity changed after authorization")
        if verified.manifest_sha256 != self.backup.manifest_sha256:
            raise WriteGateError("backup manifest changed after authorization")
        if verified.blob_sha256 != self.backup.blob_sha256:
            raise WriteGateError("backup blob changed after authorization")
        if _state_hashes_from_backup(verified) != self.fixed_state_sha256:
            raise WriteGateError("fixed state responses changed after authorization")
        if self.target is not None:
            before_payload = _validate_target_blob(
                _verified_backup_blob(verified),
                self.target,
                label="fresh backup",
                expected_payload_sha256=self.target.before_payload_sha256,
            )
            if (
                self.target.before_payload_sha256 is not None
                and _sha256(before_payload) != self.target.before_payload_sha256
            ):
                raise WriteGateError("fresh backup target payload differs from the preview")
        return verified


@dataclass(frozen=True)
class PostWriteVerification:
    """Result of comparing a fresh post-write backup with an authorized candidate."""

    before: VerifiedBackup
    after: VerifiedBackup
    fixed_state_matches: bool
    dynamic_blob_matches: bool
    unrelated_objects_unchanged: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "before_backup": self.before.to_dict(),
            "after_backup": self.after.to_dict(),
            "fixed_state_matches": self.fixed_state_matches,
            "dynamic_blob_matches": self.dynamic_blob_matches,
            "unrelated_objects_unchanged": self.unrelated_objects_unchanged,
        }


def verify_post_write_backup(
    before: VerifiedBackup,
    after_directory: Path,
    transaction: ProspectiveWriteTransaction,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> PostWriteVerification:
    """Verify a fresh read-back against the exact transaction bytes.

    This remains USB-neutral: the caller is responsible for obtaining the
    post-write raw backup. The verifier then requires the five fixed response
    objects and dynamic blob to match the candidate, while unrelated response
    objects remain unchanged from the pre-write backup.
    """

    if not isinstance(before, VerifiedBackup):
        raise WriteGateError("before must be a VerifiedBackup")
    if not isinstance(transaction, ProspectiveWriteTransaction):
        raise WriteGateError("transaction must be a ProspectiveWriteTransaction")
    after = verify_fresh_backup(
        after_directory, now=now, max_age_seconds=max_age_seconds
    )
    fixed_expected = _candidate_fixed_state_hashes(transaction)
    fixed_actual = _state_hashes_from_backup(after)
    if fixed_actual != fixed_expected:
        raise WriteGateError("post-write fixed state responses do not match the candidate")

    expected_blob = _sha256(transaction.ranges[4] + transaction.ranges[7])
    actual_blob = after.object_sha256(_DYNAMIC_BLOB_KEY)
    if actual_blob != expected_blob:
        raise WriteGateError("post-write dynamic backup blob does not match the candidate")

    changed_keys = {
        f"0x{command:04x}:{_FIXED_STATE_KINDS[command]}"
        for command in _FIXED_STATE_COMMANDS
    }
    changed_keys.update(_PAYLOAD_DEPENDENT_KEYS)
    before_hashes = dict(before.object_sha256_by_key)
    after_hashes = dict(after.object_sha256_by_key)
    unrelated_keys = (set(before_hashes) | set(after_hashes)) - changed_keys
    if any(before_hashes.get(key) != after_hashes.get(key) for key in unrelated_keys):
        raise WriteGateError("an unrelated backup object changed after the write")

    return PostWriteVerification(
        before=before,
        after=after,
        fixed_state_matches=True,
        dynamic_blob_matches=True,
        unrelated_objects_unchanged=True,
    )


def interactive_confirmation(
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    phrase: str = DEFAULT_CONFIRMATION_PHRASE,
) -> bool:
    """Ask for the exact confirmation phrase required by the write gate."""

    output_fn(
        f"This is a device-changing operation. Type {phrase!r} to continue:"
    )
    return input_fn("> ").strip() == phrase


def authorize_write_session(
    backup_directory: Path,
    transaction: ProspectiveWriteTransaction,
    *,
    cli_write_flag: bool,
    confirmation: str,
    phrase: str = DEFAULT_CONFIRMATION_PHRASE,
    target: Optional[WriteTarget] = None,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> WriteAuthorization:
    """Authorize a candidate only after backup, flag, and phrase checks.

    ``confirmation`` must be obtained from :func:`interactive_confirmation`
    by the caller.  Keeping the exact phrase as an argument makes this
    function deterministic in tests and prevents a GUI or CLI from silently
    treating a checkbox as confirmation.
    """

    if not cli_write_flag:
        raise WriteGateError("write authorization requires the explicit write flag")
    if not isinstance(confirmation, str) or confirmation != phrase:
        raise WriteGateError("interactive confirmation phrase was not accepted")
    if not isinstance(transaction, ProspectiveWriteTransaction):
        raise WriteGateError("transaction must be a ProspectiveWriteTransaction")
    if not isinstance(phrase, str) or not phrase:
        raise WriteGateError("confirmation phrase must be non-empty")
    if target is not None and not isinstance(target, WriteTarget):
        raise WriteGateError("target must be a WriteTarget")
    if target is not None:
        _validate_target_blob(
            transaction.ranges[4] + transaction.ranges[7],
            target,
            label="candidate transaction",
        )
    verified = verify_fresh_backup(
        backup_directory, now=now, max_age_seconds=max_age_seconds
    )
    if target is not None:
        before_payload = _validate_target_blob(
            _verified_backup_blob(verified),
            target,
            label="fresh backup",
            expected_payload_sha256=target.before_payload_sha256,
        )
        if (
            target.before_payload_sha256 is not None
            and _sha256(before_payload) != target.before_payload_sha256
        ):
            raise WriteGateError("fresh backup target payload differs from the preview")
    fixed_state_sha256 = _state_hashes_from_backup(verified)
    if fixed_state_sha256 != _candidate_fixed_state_hashes(transaction):
        raise WriteGateError(
            "candidate fixed state ranges do not match the fresh backup responses"
        )
    reference_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return WriteAuthorization(
        backup=verified,
        transaction_sha256=transaction.concatenated_sha256,
        authorized_at_utc=reference_time.isoformat(),
        confirmation_phrase=phrase,
        cli_write_flag=True,
        fixed_state_sha256=fixed_state_sha256,
        target=target,
    )


def authorize_existing_text_replacement(
    backup_directory: Path,
    transaction: ProspectiveWriteTransaction,
    preview_report: Dict[str, Any],
    *,
    cli_write_flag: bool,
    confirmation: str,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> WriteAuthorization:
    """Authorize only the existing-text operation represented by a preview.

    This is still an authorization record for a future writer; it does not
    open USB or transmit anything.  The operation-specific phrase prevents a
    generic write acknowledgement from being reused accidentally.
    """

    target = WriteTarget.from_preview_report(preview_report)
    workflow = preview_report.get("workflow")
    candidate = preview_report.get("candidate")
    if not isinstance(workflow, dict) or not isinstance(candidate, dict):
        raise WriteGateError("replacement preview is missing source/candidate hashes")
    source_blob_sha256 = _require_sha256(
        workflow.get("source_backup_blob_sha256"),
        "preview source backup blob hash",
    )
    candidate_blob_sha256 = _require_sha256(
        candidate.get("decoded_sha256"),
        "preview candidate blob hash",
    )
    candidate_blob = transaction.ranges[4] + transaction.ranges[7]
    if _sha256(candidate_blob) != candidate_blob_sha256:
        raise WriteGateError("candidate transaction blob differs from the preview")
    authorization = authorize_write_session(
        backup_directory,
        transaction,
        cli_write_flag=cli_write_flag,
        confirmation=confirmation,
        phrase=TEXT_REPLACEMENT_CONFIRMATION_PHRASE,
        target=target,
        now=now,
        max_age_seconds=max_age_seconds,
    )
    if authorization.backup.blob_sha256 != source_blob_sha256:
        raise WriteGateError("fresh backup blob differs from the preview source")
    return authorization


__all__ = [
    "DEFAULT_CONFIRMATION_PHRASE",
    "DEFAULT_MAX_AGE_SECONDS",
    "TEXT_REPLACEMENT_CONFIRMATION_PHRASE",
    "WRITE_GATE_FORMAT",
    "VerifiedBackup",
    "PostWriteVerification",
    "WriteTarget",
    "authorize_existing_text_replacement",
    "WriteAuthorization",
    "WriteGateError",
    "authorize_write_session",
    "capture_and_verify_fresh_backup",
    "interactive_confirmation",
    "verify_fresh_backup",
    "verify_post_write_backup",
]
