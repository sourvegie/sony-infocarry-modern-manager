"""Read-only support for the I.7 legacy timestamp/state experiment.

The helpers in this module prepare and audit an owner-operated evidence
session.  They never open USB, claim an interface, start Windows software, or
construct a device-changing transaction.  Session output is deliberately
written only to a caller-selected destination and all writes refuse existing
paths.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import time
from typing import Any, Mapping, Optional, Sequence

from .backup import parse_grouped_values_response, parse_offset_list_response
from .backup_format import BackupFormatError, parse_backup_blob
from .usblog import UsblogParseError, extract_101b, find_101b_headers
from .usblog_report import summarize_capture
from .timestamp_validator import validate_timestamp_logs
from .write_gate import VerifiedBackup, WriteGateError, verify_fresh_backup


I7_EXPERIMENT_ID = "I7-LEGACY-ADD-01"
I7_TARGET_FILENAME = "IC_I7_CLOCK_01.txt"
I7_TARGET_PATH = r"root\IC_I7_CLOCK_01.txt"
SUPPORTED_DEVICE = {"vendor_id": "0x054c", "product_id": "0x001e"}
I7_SESSION_STAGES = (
    "00-source",
    "00-pre-add-backup",
    "01-manager-before-send",
    "02-snoopypro-add-capture",
    "03-manager-after-send",
    "04-post-add-backup",
    "05-analysis",
)
FIXED_STATE_COMMANDS = (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)
FIXED_STATE_KINDS = {
    0x001B: "response-001b",
    0x001C: "response-001c",
    0x001D: "response-001d",
    0x001E: "response-001e",
    0x001F: "response-001f",
}
REQUIRED_MANAGER_BASENAMES = (
    "VICDATA.bin",
    "VICMEM.bin",
    "VICLV.bin",
    "order.vnw",
)

I7_DELETE_EXPERIMENT_ID = "I7-LEGACY-DELETE-01"
I7_DELETE_SESSION_STAGES = (
    "00-timestamps",
    "01-pre-delete-backup",
    "02-manager-before-delete",
    "03-snoopypro-delete-capture",
    "04-manager-after-delete",
    "05-post-delete-backup",
    "06-analysis",
)
I7_DELETE_TARGET_RECORD_OFFSET = 0x00000380
I7_DELETE_TARGET_METADATA_REFERENCE = 0x00000340
I7_DELETE_TARGET_PAYLOAD_LENGTH = 1_863
I7_DELETE_TARGET_PAYLOAD_SHA256 = (
    "3aa626dc1e0dbd2fe13b59fbea7eddf43358a522b9f55ed15ac18556b2a69d4b"
)
I7_DELETE_TARGET_RECORD_COUNT = 374
I7_DELETE_TARGET_BLOB_SHA256 = (
    "5b081faf7cc733e9c63c13250d689d6e7beb52bcf10470503dd68684471ab61b"
)


def _expected_i7_delete_fixed_state() -> dict[int, bytes]:
    """Return the exact preserved current state, without reading evidence."""

    display_or_mark = bytearray(64)
    display_or_mark[0:4] = (1).to_bytes(4, "big")
    display_or_mark[8:12] = I7_DELETE_TARGET_METADATA_REFERENCE.to_bytes(4, "big")
    bookmark = bytearray(64)
    bookmark[0:4] = I7_DELETE_TARGET_METADATA_REFERENCE.to_bytes(4, "big")
    bookmark[12:16] = (0x80000000).to_bytes(4, "big")
    return {
        0x001B: bytes(display_or_mark),
        0x001C: bytes(display_or_mark),
        0x001D: bytes(64),
        0x001E: bytes(64),
        0x001F: bytes(bookmark),
    }


I7_DELETE_EXPECTED_FIXED_STATE = _expected_i7_delete_fixed_state()


class I7ExperimentError(ValueError):
    """Raised when an offline I.7 artifact cannot be accepted safely."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json_exclusive(path: Path, payload: Mapping[str, Any]) -> Path:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        with path.open("xb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError as exc:
        raise I7ExperimentError(f"refusing to overwrite existing output: {path}") from exc
    except OSError as exc:
        raise I7ExperimentError(f"could not write {path}: {exc}") from exc
    return path


def write_report(destination: Path, payload: Mapping[str, Any]) -> Path:
    """Persist one derived report without replacing an existing report."""

    return _write_json_exclusive(Path(destination), payload)


def _utc_from_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _filesystem_times(path: Path) -> dict[str, Any]:
    stat = path.stat()
    birthtime = getattr(stat, "st_birthtime", None)
    if isinstance(birthtime, (int, float)):
        created = birthtime
        kind = "filesystem_birthtime"
    else:
        created = stat.st_ctime
        kind = "filesystem_ctime_fallback"
    return {
        "created_at_utc": _utc_from_timestamp(created),
        "modified_at_utc": _utc_from_timestamp(stat.st_mtime),
        "creation_time_kind": kind,
    }


_FIXTURE_LINES = (
    "I7-LEGACY-ADD-01",
    "InfoCarry legacy timestamp and state experiment.",
    "Disposable ASCII source; no copyrighted content.",
    "Open this item and scroll through it before a separate delete study.",
    "Record any visible history, mark, or bookmark state without",
    "disturbing other records.",
    "Do not retry an operation or combine add and delete in one session.",
)


def synthetic_i7_fixture_bytes() -> bytes:
    """Return the deterministic CP932-compatible source for I7 add 01."""

    lines = list(_FIXTURE_LINES)
    lines.extend(f"Synthetic experiment line {index:02d}." for index in range(1, 49))
    lines.append("End of disposable I7 source.")
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


@dataclass(frozen=True)
class SyntheticFixtureReport:
    path: str
    filename: str
    size_bytes: int
    sha256: str
    encoding: str
    line_ending: str
    line_count: int
    filesystem_created_at_utc: str
    filesystem_modified_at_utc: str
    filesystem_creation_time_kind: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class I7DeleteTargetExpectation:
    """Authoritative target identity for the one planned legacy delete."""

    path: str = I7_TARGET_PATH
    record_offset: int = I7_DELETE_TARGET_RECORD_OFFSET
    metadata_relative_reference: int = I7_DELETE_TARGET_METADATA_REFERENCE
    payload_length: int = I7_DELETE_TARGET_PAYLOAD_LENGTH
    payload_sha256: str = I7_DELETE_TARGET_PAYLOAD_SHA256
    record_count: int = I7_DELETE_TARGET_RECORD_COUNT
    dynamic_blob_sha256: str = I7_DELETE_TARGET_BLOB_SHA256

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "record_offset": f"0x{self.record_offset:08x}",
            "metadata_relative_reference": f"0x{self.metadata_relative_reference:08x}",
            "payload_length": self.payload_length,
            "payload_sha256": self.payload_sha256,
            "record_count": self.record_count,
            "dynamic_blob_sha256": self.dynamic_blob_sha256,
        }


def _delete_session_manifest(root: Path) -> dict[str, Any]:
    """Read and validate a prepared deletion-session manifest."""

    manifest_path = root / "session-manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise I7ExperimentError(f"deletion session manifest is unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise I7ExperimentError("deletion session manifest is not an object")
    if payload.get("format") != "infocarry-i7-legacy-delete-session-v1":
        raise I7ExperimentError("unsupported deletion session manifest format")
    if payload.get("experiment_id") != I7_DELETE_EXPERIMENT_ID:
        raise I7ExperimentError("deletion session experiment identifier differs")
    if payload.get("usb_operation_performed") is not False:
        raise I7ExperimentError("deletion session is not marked offline-only")
    if payload.get("stages") != list(I7_DELETE_SESSION_STAGES):
        raise I7ExperimentError("deletion session stage layout differs")
    for stage in I7_DELETE_SESSION_STAGES:
        stage_path = root / stage
        if not stage_path.is_dir() or stage_path.is_symlink():
            raise I7ExperimentError(f"deletion session stage is missing: {stage}")
    return payload


def create_i7_delete_session(destination: Path) -> Path:
    """Create a new offline deletion-session skeleton, refusing reuse."""

    root = Path(destination).expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise I7ExperimentError(f"refusing to reuse deletion session root: {root}") from exc
    except OSError as exc:
        raise I7ExperimentError(f"could not create deletion session root: {exc}") from exc
    for stage in I7_DELETE_SESSION_STAGES:
        (root / stage).mkdir()
    manifest = {
        "format": "infocarry-i7-legacy-delete-session-v1",
        "experiment_id": I7_DELETE_EXPERIMENT_ID,
        "state": "prepared_offline_no_hardware_operation",
        "usb_operation_performed": False,
        "target": I7DeleteTargetExpectation().to_dict(),
        "supported_device": dict(SUPPORTED_DEVICE),
        "stages": list(I7_DELETE_SESSION_STAGES),
        "non_overwriting_policy": True,
        "no_automatic_retry": True,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    _write_json_exclusive(root / "session-manifest.json", manifest)
    return root


def _preflight_fixed_state(
    report: Mapping[str, Any], expected_state: Mapping[int, bytes]
) -> tuple[bool, list[str]]:
    """Require exact state bytes; do not normalize or infer unknown fields."""

    errors: list[str] = []
    observed = report.get("fixed_state")
    if not isinstance(observed, Mapping):
        return False, ["complete fixed-state inventory is missing"]
    for command, expected in expected_state.items():
        key = f"0x{command:04x}"
        entry = observed.get(key)
        if not isinstance(entry, Mapping):
            errors.append(f"fixed-state object {key} is missing")
            continue
        raw_hex = entry.get("raw_hex")
        if raw_hex != expected.hex():
            errors.append(f"fixed-state bytes differ at {key}")
    return not errors, errors


def preflight_i7_legacy_delete(
    backup_directory: Path,
    *,
    timestamp_directory: Optional[Path] = None,
    session_root: Optional[Path] = None,
    target: I7DeleteTargetExpectation = I7DeleteTargetExpectation(),
    expected_fixed_state: Optional[Mapping[int, bytes]] = None,
) -> dict[str, Any]:
    """Build a hash-only, fail-closed preflight for owner review.

    This function validates only a saved complete backup and optional saved
    timestamp-tool dry-run output. It never opens USB and never authorizes or
    constructs a deletion transaction.
    """

    session_layout_ok = session_root is None
    if session_root is not None:
        session = Path(session_root).expanduser().resolve()
        _delete_session_manifest(session)
        session_layout_ok = True
    backup_report = validate_complete_backup(backup_directory)
    errors: list[str] = []
    device = backup_report.get("device", {})
    if device != dict(SUPPORTED_DEVICE):
        errors.append("device identity differs from supported 054c:001e")
    if backup_report.get("record_count") != target.record_count:
        errors.append("record count differs from the authoritative pre-delete value")
    if backup_report.get("blob_sha256") != target.dynamic_blob_sha256:
        errors.append("dynamic blob hash differs from the authoritative pre-delete value")

    try:
        verified = verify_fresh_backup(
            Path(backup_directory), now=datetime.now(timezone.utc), max_age_seconds=None
        )
        blob = _backup_object(verified, "0x8004:backup-blob")
        parsed = parse_backup_blob(blob)
        path_index = _path_index(parsed)
        record = parsed.record_at(target.record_offset)
        observed_path = _record_path(parsed, record)
        prefix, payload = parsed.payload_parts(record)
    except (BackupFormatError, WriteGateError, I7ExperimentError) as exc:
        raise I7ExperimentError(f"authoritative target preflight failed: {exc}") from exc

    target_observed = {
        "path": observed_path,
        "record_offset": f"0x{record.offset:08x}",
        "metadata_relative_reference": f"0x{record.offset - parsed.header.metadata_start:08x}",
        "kind": record.kind,
        "extension": record.extension,
        "payload_length": len(payload),
        "payload_sha256": _sha256(payload),
        "prefix_length": len(prefix),
        "prefix_sha256": _sha256(prefix),
        "timestamp_be32": f"0x{record.timestamp_be32:08x}",
    }
    if observed_path != target.path:
        errors.append("authoritative record offset resolves to a different path")
    if record.kind != "file" or record.extension.lower() != "txt":
        errors.append("authoritative target is not a TXT file record")
    if observed_path not in path_index or sum(path == target.path for path in path_index) != 1:
        errors.append("authoritative target path is missing or duplicated")
    if record.offset - parsed.header.metadata_start != target.metadata_relative_reference:
        errors.append("metadata-relative target reference differs")
    if len(payload) != target.payload_length:
        errors.append("target payload length differs")
    if _sha256(payload) != target.payload_sha256:
        errors.append("target payload hash differs")

    fixed_state_ok, fixed_state_errors = _preflight_fixed_state(
        backup_report, expected_fixed_state or I7_DELETE_EXPECTED_FIXED_STATE
    )
    errors.extend(fixed_state_errors)

    timestamp_report: dict[str, Any]
    if timestamp_directory is None:
        timestamp_report = {
            "supplied": False,
            "valid": False,
            "reason": "timestamp-tool dry-run directory was not supplied",
        }
        errors.append("timestamp-tool dry-run validity is not established")
    else:
        timestamp_report = validate_timestamp_logs(Path(timestamp_directory))
        timestamp_report = {
            "supplied": True,
            "valid": bool(timestamp_report.get("valid")) and timestamp_report.get("valid_file_count", 0) >= 2,
            "source_directory": timestamp_report.get("source_directory"),
            "file_count": timestamp_report.get("file_count"),
            "valid_file_count": timestamp_report.get("valid_file_count"),
            "sequence_numbers": timestamp_report.get("sequence_numbers"),
            "errors": timestamp_report.get("errors", []),
            "warnings": timestamp_report.get("warnings", []),
        }
        if not timestamp_report["valid"]:
            errors.append("timestamp-tool dry-run is missing, invalid, or incomplete")

    checks = {
        "supported_device_identity": device == dict(SUPPORTED_DEVICE),
        "complete_backup": backup_report.get("object_count") == 8,
        "target_path": observed_path == target.path,
        "target_record_offset": record.offset == target.record_offset,
        "target_metadata_reference": record.offset - parsed.header.metadata_start == target.metadata_relative_reference,
        "target_payload": len(payload) == target.payload_length and _sha256(payload) == target.payload_sha256,
        "record_count": backup_report.get("record_count") == target.record_count,
        "dynamic_blob": backup_report.get("blob_sha256") == target.dynamic_blob_sha256,
        "fixed_state_exact": fixed_state_ok,
        "timestamp_tool_dry_run": bool(timestamp_report["valid"]),
        "session_layout": session_layout_ok,
        "no_device_operation": True,
    }
    return {
        "format": "infocarry-i7-legacy-delete-preflight-v1",
        "experiment_id": I7_DELETE_EXPERIMENT_ID,
        "state": "ready_for_owner_review_no_authorization" if not errors else "blocked_fail_closed",
        "usb_operation_performed": False,
        "no_automatic_retry": True,
        "eligible_for_live_capture": not errors,
        "checks": checks,
        "reasons": errors,
        "target_expected": target.to_dict(),
        "target_observed": target_observed,
        "backup": {
            "directory": backup_report["directory"],
            "manifest_sha256": backup_report["manifest_sha256"],
            "blob_sha256": backup_report["blob_sha256"],
            "blob_length": backup_report["blob_length"],
            "record_count": backup_report["record_count"],
            "object_count": backup_report["object_count"],
            "object_sha256_by_key": backup_report["object_sha256_by_key"],
        },
        "fixed_state": backup_report["fixed_state"],
        "timestamp_tool_dry_run": timestamp_report,
        "expected_effect": {
            "removed_paths": [target.path],
            "added_paths": [],
            "shared_payloads": "must remain byte-identical",
            "operation": "one legacy Manager Delete Selected only",
        },
        "hypotheses": [
            "state references may be removed, rebased, or transformed",
            "unused state tails may retain stale values",
            "shared metadata timestamps may be regenerated",
            "model capacity may be recovered",
            "Manager-local sidecars may remain unchanged",
            "request-4 completion may remain unavailable in the native log",
        ],
    }


def validate_synthetic_fixture(path: Path) -> SyntheticFixtureReport:
    """Validate the exact generated source without changing it."""

    source = Path(path).expanduser().resolve()
    if source.name != I7_TARGET_FILENAME:
        raise I7ExperimentError(
            f"I.7 source must be named {I7_TARGET_FILENAME}; got {source.name!r}"
        )
    if not source.is_file() or source.is_symlink():
        raise I7ExperimentError(f"I.7 source is not a regular file: {source}")
    try:
        data = source.read_bytes()
    except OSError as exc:
        raise I7ExperimentError(f"could not read I.7 source {source}: {exc}") from exc
    expected = synthetic_i7_fixture_bytes()
    digest = _sha256(data)
    if data != expected:
        raise I7ExperimentError(
            f"I.7 source bytes differ from the synthetic fixture "
            f"(actual {digest}, expected {_sha256(expected)})"
        )
    if b"\n" in data.replace(b"\r\n", b""):
        raise I7ExperimentError("I.7 source contains a non-CRLF line ending")
    decoded = data.decode("utf-8")
    times = _filesystem_times(source)
    return SyntheticFixtureReport(
        path=str(source),
        filename=source.name,
        size_bytes=len(data),
        sha256=digest,
        encoding="UTF-8 (ASCII subset; strict)",
        line_ending="CRLF",
        line_count=decoded.count("\r\n"),
        filesystem_created_at_utc=times["created_at_utc"],
        filesystem_modified_at_utc=times["modified_at_utc"],
        filesystem_creation_time_kind=times["creation_time_kind"],
    )


def create_synthetic_fixture(destination: Path) -> SyntheticFixtureReport:
    """Create the source with exclusive creation and return its audit."""

    source = Path(destination).expanduser().resolve()
    if source.name != I7_TARGET_FILENAME:
        raise I7ExperimentError(
            f"I.7 source must be named {I7_TARGET_FILENAME}; got {source.name!r}"
        )
    source.parent.mkdir(parents=True, exist_ok=True)
    data = synthetic_i7_fixture_bytes()
    try:
        with source.open("xb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError as exc:
        raise I7ExperimentError(f"refusing to overwrite existing source: {source}") from exc
    except OSError as exc:
        raise I7ExperimentError(f"could not create I.7 source {source}: {exc}") from exc
    return validate_synthetic_fixture(source)


def create_i7_session(
    destination: Path, *, fixture: Optional[SyntheticFixtureReport] = None
) -> Path:
    """Create a new non-overwriting offline evidence-session skeleton."""

    root = Path(destination).expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise I7ExperimentError(f"refusing to reuse I.7 session root: {root}") from exc
    except OSError as exc:
        raise I7ExperimentError(f"could not create I.7 session root {root}: {exc}") from exc
    for stage in I7_SESSION_STAGES:
        (root / stage).mkdir()
    manifest = {
        "format": "infocarry-i7-legacy-add-session-v1",
        "experiment_id": I7_EXPERIMENT_ID,
        "state": "prepared_offline_no_hardware_operation",
        "usb_operation_performed": False,
        "target": I7_TARGET_PATH,
        "source": None if fixture is None else fixture.to_dict(),
        "supported_device": dict(SUPPORTED_DEVICE),
        "stages": list(I7_SESSION_STAGES),
        "non_overwriting_policy": True,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    _write_json_exclusive(root / "session-manifest.json", manifest)
    return root


def record_host_clock(
    destination: Path,
    host_label: str,
    *,
    device_identity: Optional[Mapping[str, str]] = None,
) -> Path:
    """Record a host clock observation; this does not query the device."""

    if not isinstance(host_label, str) or not host_label.strip():
        raise I7ExperimentError("host_label must be non-empty")
    now = datetime.now().astimezone()
    identity = dict(device_identity or SUPPORTED_DEVICE)
    if identity != SUPPORTED_DEVICE:
        raise I7ExperimentError("device identity is not the supported InfoCarry")
    payload = {
        "format": "infocarry-i7-host-clock-v1",
        "experiment_id": I7_EXPERIMENT_ID,
        "host_label": host_label,
        "observed_at_unix_seconds": time.time(),
        "utc_iso": now.astimezone(timezone.utc).isoformat(),
        "local_iso": now.isoformat(),
        "timezone_name": now.tzname(),
        "utc_offset_seconds": now.utcoffset().total_seconds() if now.utcoffset() else None,
        "platform": platform.platform(),
        "supported_device_identity": identity,
        "device_clock_read": False,
    }
    return _write_json_exclusive(Path(destination), payload)


def _backup_object(verified: VerifiedBackup, key: str) -> bytes:
    filename = verified.object_filename(key)
    if filename is None:
        raise I7ExperimentError(f"verified backup is missing object {key}")
    try:
        return (verified.directory / filename).read_bytes()
    except OSError as exc:
        raise I7ExperimentError(f"could not read verified backup object {key}: {exc}") from exc


def _record_path(parsed: Any, record: Any) -> Optional[str]:
    parts = parsed.paths.get(record.offset)
    if parts is None:
        return None
    path = "\\".join(parts)
    return f"{path}.{record.extension}" if record.extension else path


def _state_inventory(verified: VerifiedBackup) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for command in FIXED_STATE_COMMANDS:
        key = f"0x{command:04x}:{FIXED_STATE_KINDS[command]}"
        raw = _backup_object(verified, key)
        if len(raw) != 64:
            raise I7ExperimentError(f"fixed state object {key} is not 64 bytes")
        entry: dict[str, Any] = {
            "command": f"0x{command:04x}",
            "kind": FIXED_STATE_KINDS[command],
            "length": len(raw),
            "sha256": _sha256(raw),
            "raw_hex": raw.hex(),
        }
        if command != 0x001F:
            parsed = parse_offset_list_response(raw)
            entry["parsed"] = {
                "count": parsed.count,
                "value_04_be16": parsed.value_04_be16,
                "value_06_be16": parsed.value_06_be16,
                "record_offsets": list(parsed.record_offsets),
                "unused_tail_hex": parsed.unused_tail_hex,
            }
        else:
            parsed = parse_grouped_values_response(raw)
            entry["parsed"] = {
                "groups": [list(group) for group in parsed.groups],
                "unused_tail_hex": parsed.unused_tail_hex,
            }
        result[f"0x{command:04x}"] = entry
    return result


def validate_complete_backup(directory: Path) -> dict[str, Any]:
    """Validate a complete backup and return a hash-only structural inventory."""

    try:
        verified = verify_fresh_backup(
            Path(directory), now=datetime.now(timezone.utc), max_age_seconds=None
        )
    except WriteGateError as exc:
        raise I7ExperimentError(f"complete backup validation failed: {exc}") from exc
    blob = _backup_object(verified, "0x8004:backup-blob")
    try:
        parsed = parse_backup_blob(blob)
    except BackupFormatError as exc:
        raise I7ExperimentError(f"dynamic backup blob failed validation: {exc}") from exc
    paths = []
    for record in parsed.records:
        path = _record_path(parsed, record)
        if path is None:
            continue
        item: dict[str, Any] = {
            "path": path,
            "offset": f"0x{record.offset:08x}",
            "kind": record.kind,
            "flag": f"0x{record.flag:02x}",
            "timestamp_be32": f"0x{record.timestamp_be32:08x}",
        }
        if record.kind == "file":
            try:
                prefix, payload = parsed.payload_parts(record)
                item.update(
                    {
                        "payload_length": len(payload),
                        "payload_sha256": _sha256(payload),
                        "prefix_length": len(prefix),
                        "prefix_sha256": _sha256(prefix),
                    }
                )
            except BackupFormatError as exc:
                item["payload_error"] = str(exc)
        paths.append(item)
    return {
        "format": "infocarry-i7-complete-backup-inventory-v1",
        "directory": str(verified.directory),
        "device": {
            "vendor_id": verified.device_identity[0],
            "product_id": verified.device_identity[1],
        },
        "manifest_sha256": verified.manifest_sha256,
        "blob_sha256": verified.blob_sha256,
        "blob_length": len(blob),
        "record_count": len(parsed.records),
        "reachable_path_count": len(parsed.paths),
        "object_count": verified.object_count,
        "object_sha256_by_key": dict(verified.object_sha256_by_key),
        "paths": paths,
        "fixed_state": _state_inventory(verified),
    }


def hash_manager_snapshot(snapshot_root: Path) -> dict[str, Any]:
    """Hash a Manager snapshot while preserving all actual relative paths."""

    root = Path(snapshot_root).expanduser().resolve()
    if not root.is_dir():
        raise I7ExperimentError(f"Manager snapshot is not a directory: {root}")
    files = []
    for path in sorted(root.rglob("*")):
        if path.name == "snapshot-manifest.json":
            continue
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise I7ExperimentError(f"could not read Manager snapshot file {path}: {exc}") from exc
        times = _filesystem_times(path)
        files.append(
            {
                "relative_path": relative,
                "size": len(data),
                "sha256": _sha256(data),
                "filesystem_created_at_utc": times["created_at_utc"],
                "filesystem_modified_at_utc": times["modified_at_utc"],
                "filesystem_creation_time_kind": times["creation_time_kind"],
            }
        )
    if not files:
        raise I7ExperimentError("Manager snapshot contains no regular files")
    by_name: dict[str, list[dict[str, Any]]] = {}
    for entry in files:
        by_name.setdefault(Path(entry["relative_path"]).name, []).append(entry)
    missing = [name for name in REQUIRED_MANAGER_BASENAMES if name not in by_name]
    duplicated = {
        name: entries for name, entries in by_name.items() if name in REQUIRED_MANAGER_BASENAMES and len(entries) != 1
    }
    if missing:
        raise I7ExperimentError(
            "Manager snapshot is missing required files: " + ", ".join(missing)
        )
    if duplicated:
        raise I7ExperimentError("Manager snapshot has ambiguous duplicate required files")
    required = {name: by_name[name][0] for name in REQUIRED_MANAGER_BASENAMES}
    return {
        "format": "infocarry-i7-manager-snapshot-v1",
        "root": str(root),
        "file_count": len(files),
        "files": files,
        "required_files": required,
        "additional_related_sidecars": [
            entry for entry in files
            if Path(entry["relative_path"]).name not in REQUIRED_MANAGER_BASENAMES
        ],
    }


def write_manager_snapshot_manifest(snapshot_root: Path) -> Path:
    """Write a new manifest beside a validated snapshot, never replacing one."""

    report = hash_manager_snapshot(snapshot_root)
    return _write_json_exclusive(Path(snapshot_root) / "snapshot-manifest.json", report)


def ingest_snoopy_log(capture_path: Path) -> dict[str, Any]:
    """Parse saved SnoopyPro bytes without changing or replaying them."""

    source = Path(capture_path).expanduser().resolve()
    if not source.is_file() or source.is_symlink():
        raise I7ExperimentError(f"native SnoopyPro log is not a regular file: {source}")
    try:
        data = source.read_bytes()
    except OSError as exc:
        raise I7ExperimentError(f"could not read native log {source}: {exc}") from exc
    try:
        offsets = find_101b_headers(data)
        captures = [extract_101b(data, offset) for offset in offsets]
    except (UsblogParseError, ValueError) as exc:
        raise I7ExperimentError(f"native SnoopyPro log is not a valid ordinary capture: {exc}") from exc
    return {
        "format": "infocarry-i7-snoopypro-report-v1",
        "native_log_path": str(source),
        "native_log_size": len(data),
        "native_log_sha256": _sha256(data),
        "ordinary_101b_transaction_count": len(captures),
        "transactions": [summarize_capture(capture) for capture in captures],
        "completion": {
            "status": "not_decoded_by_offline_101b_parser",
            "note": "Request-4 completion must be recorded separately from the Manager result or a protocol-specific parser.",
        },
        "usb_target_requires_owner_confirmation": "USB\\Vid_054c&Pid_001e",
    }


def _path_index(parsed: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for record in parsed.records:
        path = _record_path(parsed, record)
        if path is not None:
            if path in result:
                raise I7ExperimentError(f"backup contains duplicate reachable path: {path}")
            result[path] = record
    return result


def _record_summary(parsed: Any, record: Any) -> dict[str, Any]:
    result = {
        "offset": f"0x{record.offset:08x}",
        "kind": record.kind,
        "flag": f"0x{record.flag:02x}",
        "timestamp_be32": f"0x{record.timestamp_be32:08x}",
        "field_04_be32": f"0x{record.field_04_be32:08x}",
        "field_08_be32": f"0x{record.field_08_be32:08x}",
        "field_10_be32": f"0x{record.field_10_be32:08x}",
        "field_14_be32": f"0x{record.field_14_be32:08x}",
    }
    if record.kind == "file":
        try:
            prefix, payload = parsed.payload_parts(record)
            result.update(
                {
                    "payload_length": len(payload),
                    "payload_sha256": _sha256(payload),
                    "prefix_length": len(prefix),
                    "prefix_sha256": _sha256(prefix),
                }
            )
        except BackupFormatError as exc:
            result["payload_error"] = str(exc)
    return result


def _load_backup_pair(before: Path, after: Path) -> tuple[VerifiedBackup, Any, bytes, VerifiedBackup, Any, bytes]:
    before_report = validate_complete_backup(before)
    after_report = validate_complete_backup(after)
    try:
        before_verified = verify_fresh_backup(Path(before), now=datetime.now(timezone.utc), max_age_seconds=None)
        after_verified = verify_fresh_backup(Path(after), now=datetime.now(timezone.utc), max_age_seconds=None)
        before_blob = _backup_object(before_verified, "0x8004:backup-blob")
        after_blob = _backup_object(after_verified, "0x8004:backup-blob")
        return (
            before_verified,
            parse_backup_blob(before_blob),
            before_blob,
            after_verified,
            parse_backup_blob(after_blob),
            after_blob,
        )
    except (WriteGateError, BackupFormatError, I7ExperimentError) as exc:
        raise I7ExperimentError(f"could not load verified backup pair: {exc}") from exc


def compare_i7_backups(
    before: Path,
    after: Path,
    *,
    expected_target_path: str = I7_TARGET_PATH,
    source_sha256: Optional[str] = None,
    time_sources: Optional[Mapping[str, Any]] = None,
    manager_before: Optional[Mapping[str, Any]] = None,
    manager_after: Optional[Mapping[str, Any]] = None,
    snoopy_report: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Compare two complete backups and report only structural/hash facts."""

    before_verified, before_parsed, before_blob, after_verified, after_parsed, after_blob = _load_backup_pair(before, after)
    before_paths = _path_index(before_parsed)
    after_paths = _path_index(after_parsed)
    before_names = set(before_paths)
    after_names = set(after_paths)
    added = sorted(after_names - before_names)
    removed = sorted(before_names - after_names)
    shared = sorted(before_names & after_names)
    timestamp_changes = []
    shared_payload_changes = []
    for path in shared:
        left = before_paths[path]
        right = after_paths[path]
        if left.timestamp_be32 != right.timestamp_be32:
            timestamp_changes.append(
                {
                    "path": path,
                    "before": f"0x{left.timestamp_be32:08x}",
                    "after": f"0x{right.timestamp_be32:08x}",
                }
            )
        if left.kind == right.kind == "file":
            try:
                left_payload = before_parsed.payload_parts(left)[1]
                right_payload = after_parsed.payload_parts(right)[1]
                if left_payload != right_payload:
                    shared_payload_changes.append(
                        {
                            "path": path,
                            "before_sha256": _sha256(left_payload),
                            "after_sha256": _sha256(right_payload),
                            "before_length": len(left_payload),
                            "after_length": len(right_payload),
                        }
                    )
            except BackupFormatError as exc:
                shared_payload_changes.append({"path": path, "error": str(exc)})

    new_records = []
    for path in added:
        new_records.append({"path": path, **_record_summary(after_parsed, after_paths[path])})
    source_match = None
    target_observation = None
    if expected_target_path:
        target = after_paths.get(expected_target_path)
        if target is not None and target.kind == "file":
            try:
                payload = after_parsed.payload_parts(target)[1]
                target_observation = {
                    "path": expected_target_path,
                    "offset": f"0x{target.offset:08x}",
                    "payload_length": len(payload),
                    "payload_sha256": _sha256(payload),
                }
                if source_sha256 is not None:
                    source_match = _sha256(payload) == source_sha256.lower()
            except BackupFormatError as exc:
                target_observation = {"path": expected_target_path, "error": str(exc)}
        else:
            target_observation = {"path": expected_target_path, "present": False}

    before_state = _state_inventory(before_verified)
    after_state = _state_inventory(after_verified)
    state_comparison = {}
    for command in FIXED_STATE_COMMANDS:
        key = f"0x{command:04x}"
        left = before_state[key]
        right = after_state[key]
        left_raw = bytes.fromhex(left["raw_hex"])
        right_raw = bytes.fromhex(right["raw_hex"])
        state_comparison[key] = {
            "byte_identical": left_raw == right_raw,
            "differing_byte_count": sum(a != b for a, b in zip(left_raw, right_raw)),
            "before_sha256": left["sha256"],
            "after_sha256": right["sha256"],
            "before_parsed": left["parsed"],
            "after_parsed": right["parsed"],
        }

    result: dict[str, Any] = {
        "format": "infocarry-i7-backup-comparison-v1",
        "experiment_id": I7_EXPERIMENT_ID,
        "device_identity_match": before_verified.device_identity == after_verified.device_identity == tuple(SUPPORTED_DEVICE.values()),
        "before": {
            "directory": str(before_verified.directory),
            "manifest_sha256": before_verified.manifest_sha256,
            "blob_sha256": _sha256(before_blob),
            "blob_length": len(before_blob),
            "record_count": len(before_parsed.records),
        },
        "after": {
            "directory": str(after_verified.directory),
            "manifest_sha256": after_verified.manifest_sha256,
            "blob_sha256": _sha256(after_blob),
            "blob_length": len(after_blob),
            "record_count": len(after_parsed.records),
        },
        "model_growth_bytes": len(after_blob) - len(before_blob),
        "paths": {
            "added": added,
            "removed": removed,
            "shared_count": len(shared),
            "expected_single_add": added == [expected_target_path] and not removed,
        },
        "new_records": new_records,
        "target": target_observation,
        "source_payload_matches": source_match,
        "shared_timestamp_changes": timestamp_changes,
        "shared_file_payload_changes": shared_payload_changes,
        "unrelated_file_payloads_unchanged": not shared_payload_changes,
        "fixed_state": state_comparison,
        "time_sources": dict(time_sources or {}),
        "completion": {
            "status": "not_decoded_unless_owner_recorded",
            "native_request_4_value": None,
        },
        "manager_sidecars": None,
        "snoopypro": dict(snoopy_report) if snoopy_report is not None else None,
    }
    if manager_before is not None or manager_after is not None:
        if manager_before is None or manager_after is None:
            raise I7ExperimentError("both Manager before and after reports are required")
        left = {entry["relative_path"]: entry for entry in manager_before.get("files", [])}
        right = {entry["relative_path"]: entry for entry in manager_after.get("files", [])}
        result["manager_sidecars"] = {
            "byte_identical": left == right,
            "added_files": sorted(set(right) - set(left)),
            "removed_files": sorted(set(left) - set(right)),
            "changed_files": sorted(
                path for path in set(left) & set(right)
                if left[path]["sha256"] != right[path]["sha256"]
            ),
        }
    return result


__all__ = [
    "I7_EXPERIMENT_ID",
    "I7_SESSION_STAGES",
    "I7_DELETE_EXPERIMENT_ID",
    "I7_DELETE_SESSION_STAGES",
    "I7_DELETE_EXPECTED_FIXED_STATE",
    "I7DeleteTargetExpectation",
    "I7_TARGET_FILENAME",
    "I7_TARGET_PATH",
    "I7ExperimentError",
    "SUPPORTED_DEVICE",
    "SyntheticFixtureReport",
    "compare_i7_backups",
    "create_i7_delete_session",
    "create_i7_session",
    "create_synthetic_fixture",
    "hash_manager_snapshot",
    "ingest_snoopy_log",
    "record_host_clock",
    "preflight_i7_legacy_delete",
    "synthetic_i7_fixture_bytes",
    "validate_complete_backup",
    "validate_synthetic_fixture",
    "write_report",
    "write_manager_snapshot_manifest",
]
