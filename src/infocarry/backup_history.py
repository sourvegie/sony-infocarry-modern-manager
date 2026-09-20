"""Small index for complete backups created in the application data folder."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Optional

from .app_paths import ApplicationPaths
from .backup_format import BackupFormatError, load_complete_backup


BACKUP_HISTORY_FORMAT = "infocarry-last-complete-backup-v1"


class BackupHistoryError(RuntimeError):
    """Raised when the saved pointer cannot safely identify a complete backup."""


@dataclass(frozen=True)
class BackupSnapshotSummary:
    directory: Path
    created_at_utc: str
    model_bytes: int
    blob_sha256: str


def summarize_complete_backup(directory: Path) -> BackupSnapshotSummary:
    """Revalidate a complete backup before presenting it as a snapshot."""

    root = Path(directory).expanduser().resolve()
    try:
        parsed, digest = load_complete_backup(root)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, BackupFormatError, ValueError) as exc:
        raise BackupHistoryError(f"complete backup could not be verified: {exc}") from exc
    if manifest.get("state") != "complete":
        raise BackupHistoryError("backup is not marked complete")
    created_at = manifest.get("created_at_utc")
    if not isinstance(created_at, str) or not created_at.strip():
        raise BackupHistoryError("complete backup timestamp is missing")
    model_bytes = parsed.header.total_length
    if type(model_bytes) is not int or model_bytes < 0:
        raise BackupHistoryError("complete backup model length is malformed")
    return BackupSnapshotSummary(root, created_at, model_bytes, digest)


def _within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def remember_complete_backup(
    paths: ApplicationPaths, directory: Path
) -> BackupSnapshotSummary:
    """Remember an immutable app-owned backup only after it validates complete."""

    summary = summarize_complete_backup(directory)
    if not _within_root(summary.directory, paths.backup_root.resolve()):
        raise BackupHistoryError("only backups inside the application Backups folder are registered")
    document = {
        "format": BACKUP_HISTORY_FORMAT,
        "directory": str(summary.directory),
        "created_at_utc": summary.created_at_utc,
        "model_bytes": summary.model_bytes,
        "blob_sha256": summary.blob_sha256,
    }
    record_path = paths.latest_backup_record
    try:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{record_path.name}.", dir=record_path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(document, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, record_path)
        finally:
            if temporary.exists():
                temporary.unlink()
    except OSError as exc:
        raise BackupHistoryError(f"could not remember the completed backup: {exc}") from exc
    return summary


def latest_complete_backup(paths: ApplicationPaths) -> Optional[BackupSnapshotSummary]:
    """Load and revalidate the most recently registered complete backup."""

    try:
        document: Any = json.loads(
            paths.latest_backup_record.read_text(encoding="utf-8")
        )
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupHistoryError(f"saved backup reference could not be read: {exc}") from exc
    if not isinstance(document, Mapping) or document.get("format") != BACKUP_HISTORY_FORMAT:
        raise BackupHistoryError("saved backup reference has an unsupported format")
    raw_directory = document.get("directory")
    if not isinstance(raw_directory, str) or not raw_directory:
        raise BackupHistoryError("saved backup reference has no directory")
    directory = Path(raw_directory).expanduser().resolve()
    if not _within_root(directory, paths.backup_root.resolve()):
        raise BackupHistoryError("saved backup reference points outside application Backups")
    summary = summarize_complete_backup(directory)
    expected = (
        document.get("created_at_utc"),
        document.get("model_bytes"),
        document.get("blob_sha256"),
    )
    actual = (summary.created_at_utc, summary.model_bytes, summary.blob_sha256)
    if expected != actual:
        raise BackupHistoryError("saved backup reference does not match its immutable backup")
    return summary


__all__ = [
    "BACKUP_HISTORY_FORMAT",
    "BackupHistoryError",
    "BackupSnapshotSummary",
    "latest_complete_backup",
    "remember_complete_backup",
    "summarize_complete_backup",
]
