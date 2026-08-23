"""Safe offline workflow helpers for browsing backups and planning edits.

This module is intentionally device-independent. It builds a compact inventory
from a parsed backup and persists preview reports only into a new directory.
Preview reports contain hashes and verified metadata, never candidate payload
bytes or USB instructions.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict

from .backup_format import ParsedBackupBlob


WORKFLOW_INVENTORY_FORMAT = "infocarry-backup-inventory-v1"
WORKFLOW_PREVIEW_FORMAT = "infocarry-text-preview-report-v1"


class WorkflowError(ValueError):
    """Raised when an offline workflow artifact cannot be created safely."""


def build_backup_inventory(
    parsed: ParsedBackupBlob, source_blob_sha256: str
) -> Dict[str, Any]:
    """Return a JSON-safe browse inventory without writing any files."""

    if not isinstance(parsed, ParsedBackupBlob):
        raise WorkflowError("parsed must be a ParsedBackupBlob")
    if not isinstance(source_blob_sha256, str) or len(source_blob_sha256) != 64:
        raise WorkflowError("source_blob_sha256 must be a SHA-256 hex digest")
    try:
        int(source_blob_sha256, 16)
    except ValueError as exc:
        raise WorkflowError("source_blob_sha256 must be hexadecimal") from exc

    records = []
    by_offset = {record.offset: record for record in parsed.records}
    # ``ParsedBackupBlob.paths`` is populated by walking each directory's
    # child table in stored order.  Iterating these keys preserves the order
    # encoded by the device instead of the metadata table's physical or
    # alphabetical order.
    for record_offset, path_parts in parsed.paths.items():
        record = by_offset[record_offset]
        entry: Dict[str, Any] = {
            "record_offset": f"0x{record.offset:08x}",
            "path": "\\".join(path_parts),
            "kind": record.kind,
            "name": record.name,
            "extension": record.extension,
            "flag": f"0x{record.flag:02x}",
            "read_state": record.read_state,
            "timestamp_unix_seconds": record.timestamp_be32,
        }
        if record.kind == "file":
            prefix, payload = parsed.payload_parts(record)
            entry.update(
                {
                    "payload_bytes": len(payload),
                    "payload_sha256": hashlib.sha256(payload).hexdigest(),
                    "native_prefix_bytes": len(prefix),
                }
            )
        records.append(entry)

    return {
        "format": WORKFLOW_INVENTORY_FORMAT,
        "source_blob_sha256": source_blob_sha256,
        "summary": {
            "records": len(records),
            "directories": sum(item["kind"] == "directory" for item in records),
            "files": sum(item["kind"] == "file" for item in records),
            "unresolved": sum(item["kind"] == "unknown" for item in records),
        },
        "records": records,
        "safety": {
            "device_accessed": False,
            "candidate_bytes_included": False,
        },
    }


def save_json_report(destination: Path, report: Dict[str, Any]) -> Path:
    """Write one report to a new directory, refusing all overwrite."""

    if not isinstance(destination, Path):
        raise WorkflowError("destination must be a Path")
    if not isinstance(report, dict):
        raise WorkflowError("report must be a dictionary")
    path = destination.expanduser().resolve()
    try:
        path.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise WorkflowError(f"refusing to overwrite existing report path: {path}") from exc
    except OSError as exc:
        raise WorkflowError(f"could not create report directory {path}: {exc}") from exc
    target = path / "report.json"
    try:
        with target.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
    except (OSError, TypeError) as exc:
        raise WorkflowError(f"could not write workflow report {target}: {exc}") from exc
    return target


__all__ = [
    "WORKFLOW_INVENTORY_FORMAT",
    "WORKFLOW_PREVIEW_FORMAT",
    "WorkflowError",
    "build_backup_inventory",
    "save_json_report",
]
