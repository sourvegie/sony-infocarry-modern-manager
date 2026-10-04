"""Offline preparation and evidence verification for P18-041H.

This module is deliberately outside every live Manager/USB entry point.  It
can validate a local copy of the disposable fixture, record host/file-clock
observations, inspect a saved native capture, freeze an owner-approval
identity, and compare saved before/after backups.  It never discovers a
device, opens USB, creates a claim, changes a marker or lock, calls a sender,
or performs a device write.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import time
from typing import Any, Mapping, Optional, Sequence

from .backup_format import BackupFormatError, ParsedBackupBlob, calculate_backup_checksum, parse_backup_blob
from .backup_repack import BackupRepackError, delete_existing_file
from .capture_artifact import preserve_capture_artifact
from .delete_evidence_compare import compare_delete_evidence
from .usblog import UsblogParseError, extract_101b, find_101b_headers
from .write_artifact import WriteArtifactError, load_preserved_artifact
from .write_gate import WriteGateError, verify_fresh_backup


EXPERIMENT_ID = "P18-041H"
FORMAT = "infocarry-p18-041h-bounded-physical-root-delete-v1"
SUPPORTED_DEVICE = {
    "model": "VNW-V15",
    "vendor_id": "0x054c",
    "product_id": "0x001e",
    "usb_identity_boundary": "USB\\Vid_054c&Pid_001e",
}
FIXTURE_FILENAME = "IC_P18_041G_CLOCK_01.txt"
FIXTURE_PATH = rf"root\{FIXTURE_FILENAME}"
FIXTURE_BYTES = b"P18-041G timestamp probe 01\r\n"
FIXTURE_LENGTH = 29
FIXTURE_SHA256 = "9541c1b9d09ee7d4ab91c704755c4bea8b2022c3bb8f50aa15c1a990bf80c35d"
TARGET_OPERATION = "one legacy/native root-level ordinary TXT Delete Selected"
APPROVAL_PREFIX = "AUTHORIZE P18-041H PHYSICAL ROOT DELETE"
EVENTS = (
    "before_manager_initialization",
    "after_initialization_idle",
    "immediately_before_delete",
    "immediately_after_delete_return",
)
STAGES = (
    "00-identity",
    "01-fixture-prestage",
    "02-pre-delete-backup",
    "03-manager-before",
    "04-time-observations",
    "05-native-delete-capture",
    "06-manager-after",
    "07-post-delete-backup",
    "08-sealed-evidence",
    "09-recovery-decision",
    "10-analysis",
)
SAFETY_COUNTERS = {
    "hardware_usb_sessions": 0,
    "hardware_writes": 0,
    "real_0x101b": 0,
    "production_sender_calls": 0,
    "claims_consumed": 0,
    "sender_marker_mutations": 0,
    "installation_wide_lock_mutations": 0,
}
SEAL_FORMAT = "infocarry-p18-041h-evidence-seal-v1"
TERMINAL_RESULT_FORMAT = "infocarry-p18-041h-native-terminal-result-v1"
STABLE_DEVICE_IDENTITY_FORMAT = "infocarry-p18-041h-stable-device-identity-v1"
PRESTAGE_REPORT_FORMAT = "infocarry-p18-041h-separate-fixture-placement-v1"


class P18041HError(ValueError):
    """Raised when an offline P18-041H artifact cannot be accepted safely."""


class IdentityNotFrozenError(P18041HError):
    """Raised when owner approval would include a volatile or missing field."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise P18041HError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> Path:
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        with destination.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise P18041HError(f"refusing to overwrite existing output: {destination}") from exc
    except OSError as exc:
        raise P18041HError(f"could not write {destination}: {exc}") from exc
    return destination


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> Path:
    """Write one derived report without ever replacing an existing artifact."""

    return _write_json_exclusive(path, value)


def _validate_epoch_ms(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise P18041HError(f"{label} must be a non-negative integer epoch in milliseconds")
    return value


def _validate_time_map(value: Mapping[str, Any]) -> None:
    if value.get("format") != "infocarry-p18-041h-event-map-v1" or value.get("experiment_id") != EXPERIMENT_ID:
        raise P18041HError("event map format is not P18-041H v1")
    events = value.get("events")
    if not isinstance(events, dict) or set(events) != set(EVENTS):
        raise P18041HError("event map does not contain exactly the four required events")
    for event in EVENTS:
        entry = events[event]
        if not isinstance(entry, dict):
            raise P18041HError(f"event map entry {event!r} is not an object")
        for key in ("observed_at_local", "observed_at_utc"):
            raw = entry.get(key)
            if not isinstance(raw, str):
                raise P18041HError(f"event map {event!r} is missing {key}")
            try:
                datetime.fromisoformat(raw)
            except ValueError as exc:
                raise P18041HError(f"event map {event!r} has invalid {key}") from exc
        _validate_epoch_ms(entry.get("observed_at_epoch_ms"), f"event map {event!r} epoch")
        offset = entry.get("timezone_offset_minutes")
        if isinstance(offset, bool) or not isinstance(offset, int) or not -14 * 60 <= offset <= 14 * 60:
            raise P18041HError(f"event map {event!r} timezone offset is invalid")
        if not isinstance(entry.get("sha256"), str):
            raise P18041HError(f"event map {event!r} is missing its raw observation hash")


def _validate_evidence_seal(path: Path) -> dict[str, Any]:
    value, _raw = _read_json_object(path, "evidence seal")
    if value.get("format") != "infocarry-p18-041h-evidence-seal-v1":
        raise P18041HError("evidence seal format is not P18-041H v1")
    root = Path(value.get("session_root", "")).expanduser().resolve()
    if not root.is_dir():
        raise P18041HError("evidence seal session root is not a directory")
    files = value.get("files")
    if not isinstance(files, list) or not files:
        raise P18041HError("evidence seal has no file inventory")
    for entry in files:
        if not isinstance(entry, dict):
            raise P18041HError("evidence seal contains a malformed file entry")
        relative = entry.get("path")
        digest = entry.get("sha256")
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise P18041HError("evidence seal contains an unsafe relative path")
        _digest(digest, f"evidence seal hash for {relative}")
        file_path = root / relative
        if not file_path.is_file() or file_path.is_symlink():
            raise P18041HError(f"sealed evidence file is missing or symlinked: {file_path}")
        try:
            data = file_path.read_bytes()
        except OSError as exc:
            raise P18041HError(f"could not read sealed evidence file {file_path}: {exc}") from exc
        if _sha256(data) != digest or len(data) != entry.get("size_bytes"):
            raise P18041HError(f"sealed evidence file changed: {file_path}")
    return value


def write_json(destination: Path, value: Mapping[str, Any]) -> Path:
    """Write one derived JSON artifact without replacing an existing file."""

    if not isinstance(value, Mapping):
        raise P18041HError("JSON artifact must be an object")
    return _write_json_exclusive(Path(destination), value)


def _read_json_object(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    source = Path(path).expanduser().resolve()
    if not source.is_file() or source.is_symlink():
        raise P18041HError(f"{label} is not a regular file: {source}")
    try:
        raw = source.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P18041HError(f"{label} is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise P18041HError(f"{label} must be a JSON object")
    return value, raw


def _validate_time_observation(value: Mapping[str, Any], event: str) -> None:
    """Validate the typed/time-bound fields used by the event map."""

    if value.get("format") != "infocarry-p18-041h-time-observation-v1":
        raise P18041HError(f"event observation {event!r} has an unsupported format")
    if value.get("event") != event:
        raise P18041HError(f"event observation does not identify {event!r}")
    epoch_ms = value.get("observed_at_epoch_ms")
    offset_minutes = value.get("timezone_offset_minutes")
    if (
        isinstance(epoch_ms, bool)
        or not isinstance(epoch_ms, int)
        or epoch_ms < 0
        or isinstance(offset_minutes, bool)
        or not isinstance(offset_minutes, int)
        or not -14 * 60 <= offset_minutes <= 14 * 60
    ):
        raise P18041HError(f"event observation {event!r} has invalid time scalar fields")
    try:
        local = datetime.fromisoformat(str(value["observed_at_local"]))
        utc = datetime.fromisoformat(str(value["observed_at_utc"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise P18041HError(f"event observation {event!r} has invalid ISO timestamps") from exc
    if local.tzinfo is None or utc.tzinfo is None:
        raise P18041HError(f"event observation {event!r} timestamps must include timezone")
    local_offset = int((local.utcoffset() or timezone.utc.utcoffset(local)).total_seconds() // 60)
    if local_offset != offset_minutes:
        raise P18041HError(f"event observation {event!r} timezone offset disagrees with local timestamp")
    local_epoch_ms = int(local.astimezone(timezone.utc).timestamp() * 1000)
    utc_epoch_ms = int(utc.astimezone(timezone.utc).timestamp() * 1000)
    if local_epoch_ms != epoch_ms or utc_epoch_ms != epoch_ms:
        raise P18041HError(f"event observation {event!r} timestamp disagrees with epoch_ms")


def _load_event_map(path: Path) -> tuple[dict[str, Any], bytes]:
    """Load an event map and re-hash every separately stored observation."""

    event_path = Path(path).expanduser().resolve()
    value, raw = _read_json_object(event_path, "event map")
    if value.get("format") != "infocarry-p18-041h-event-map-v1" or value.get("experiment_id") != EXPERIMENT_ID:
        raise P18041HError("event map has an unsupported format")
    events = value.get("events")
    if not isinstance(events, dict) or set(events) != set(EVENTS):
        raise P18041HError("event map does not contain exactly the four required events")
    for event in EVENTS:
        entry = events[event]
        if not isinstance(entry, dict):
            raise P18041HError(f"event map entry {event!r} is not an object")
        filename = entry.get("filename")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise P18041HError(f"event map entry {event!r} has an unsafe observation filename")
        expected_hash = _digest(entry.get("sha256"), f"event map {event} observation hash")
        observation_path = event_path.parent / filename
        observation, observation_raw = _read_json_object(observation_path, f"event observation {event}")
        _validate_time_observation(observation, event)
        if _sha256(observation_raw) != expected_hash:
            raise P18041HError(f"event observation {event!r} does not match its event-map hash")
        for field in ("observed_at_local", "observed_at_utc", "observed_at_epoch_ms", "timezone_offset_minutes"):
            if entry.get(field) != observation.get(field):
                raise P18041HError(f"event map entry {event!r} does not match its raw observation")
    return value, raw


def fixture_identity() -> dict[str, Any]:
    """Return the immutable source identity; this does not create a file."""

    return {
        "filename": FIXTURE_FILENAME,
        "device_path": FIXTURE_PATH,
        "kind": "ordinary_root_level_txt",
        "content_encoding": "ASCII subset / CP932-compatible",
        "line_ending": "CRLF",
        "content_length": FIXTURE_LENGTH,
        "sha256": FIXTURE_SHA256,
    }


def operation_binding() -> dict[str, Any]:
    """Return the exact target/operation metadata bound to every candidate."""

    return {
        "operation": TARGET_OPERATION,
        "physical_operation_count": 1,
        "add_count": 0,
        "subtree_operation": False,
        "target_path": FIXTURE_PATH,
        "target_kind": "ordinary_root_level_txt",
        "target_content_length": FIXTURE_LENGTH,
        "target_content_sha256": FIXTURE_SHA256,
    }


def _validate_operation_binding(value: Any, label: str) -> dict[str, Any]:
    if value != operation_binding():
        raise P18041HError(f"{label} is not the exact one-delete fixture binding")
    return dict(value)


def recovery_plan_contract() -> dict[str, Any]:
    """Return the exact reviewed recovery plan required by owner identity."""

    return {
        "format": "infocarry-p18-041h-recovery-plan-v1",
        "plan_id": "P18-041H-recovery-plan-v1",
        "status": "prepared_no_recovery_authorized",
        "scope": "the exact VNW-V15 unit and the exact fresh pre-delete eight-object backup for P18-041H",
        "preconditions": [
            "preserve the complete fresh pre-delete backup immutably before Delete",
            "record and independently verify its manifest, all eight object hashes, and dynamic blob hash",
            "seal the complete delete evidence before any recovery or restoration attempt",
            "establish a separately reviewed recovery candidate from the retained pre-delete backup",
            "establish exact VNW-V15 device identity and fresh read-only state/capacity evidence",
            "obtain a new operation-specific owner authorization bound to the recovery candidate and transaction",
            "use one sender invocation and no automatic retry",
            "take a complete post-recovery eight-object backup and independently verify it",
        ],
        "not_assumed": [
            "modern Delete path",
            "modern Restore path",
            "unproven reconstruction of native recovery semantics",
            "recovery from an ambiguous or interrupted write",
        ],
        "operator_rule": "If no reviewed recovery path can be frozen and separately authorized, stop after sealing evidence and report the device as requiring owner-directed recovery.",
        "automatic_recovery": False,
        "separate_owner_authorization_required": True,
        "hardware_write_performed_by_preparation": False,
        "safety_counters": dict(SAFETY_COUNTERS),
    }


def _validate_fixture_prestage_report(path: Path) -> tuple[dict[str, Any], bytes]:
    """Require independently reported, separate, completed fixture placement."""

    report_path = Path(path).expanduser().resolve()
    report, raw = _read_json_object(report_path, "separate fixture-placement report")
    if report_path.name != "placement-readback-or-backup-report.json" or report_path.parent.name != "01-fixture-prestage":
        raise P18041HError("fixture placement report must be the canonical 01-fixture-prestage artifact")
    if report.get("format") != PRESTAGE_REPORT_FORMAT or report.get("experiment_id") != EXPERIMENT_ID:
        raise P18041HError("fixture placement report has an unsupported format")
    if (
        report.get("status") != "completed_and_independently_verified"
        or report.get("operation") != "separate_fixture_placement"
        or report.get("completed_before_delete") is not True
        or report.get("placement_readback_verified") is not True
        or report.get("owner_authorization_status") != "separate_owner_authorized"
    ):
        raise P18041HError("fixture placement was not separately authorized, completed, and verified")
    if (
        report.get("physical_operation_count") != 1
        or report.get("add_count") != 1
        or report.get("delete_count") != 0
        or report.get("subtree_operation") is not False
        or report.get("retry_count") != 0
        or report.get("sender_invocations") != 1
    ):
        raise P18041HError("fixture placement report does not prove one add, no delete, and no retry")
    if report.get("fixture") != fixture_identity():
        raise P18041HError("fixture placement report does not bind the exact P18-041H fixture")
    backup = report.get("post_placement_backup")
    if not isinstance(backup, Mapping):
        raise P18041HError("fixture placement report has no post-placement backup identity")
    _digest(backup.get("manifest_sha256"), "fixture placement backup manifest hash")
    _digest(backup.get("blob_sha256"), "fixture placement backup blob hash")
    return report, raw


def _load_stable_device_identity(boundary: Mapping[str, Any], boundary_path: Path) -> tuple[str, str]:
    artifact = boundary.get("stable_identity_artifact")
    if not isinstance(artifact, Mapping):
        raise IdentityNotFrozenError("stable physical-unit identity artifact is missing")
    artifact_path_value = artifact.get("path")
    if not isinstance(artifact_path_value, str):
        raise IdentityNotFrozenError("stable physical-unit identity artifact path is missing")
    artifact_path = Path(artifact_path_value).expanduser()
    if not artifact_path.is_absolute():
        artifact_path = (Path(boundary_path).expanduser().resolve().parent / artifact_path).resolve()
    else:
        artifact_path = artifact_path.resolve()
    if not artifact_path.is_file() or artifact_path.is_symlink():
        raise IdentityNotFrozenError("stable physical-unit identity artifact is not a regular file")
    try:
        raw = artifact_path.read_bytes()
        identity = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IdentityNotFrozenError(f"stable physical-unit identity artifact is unreadable: {exc}") from exc
    if _sha256(raw) != artifact.get("sha256"):
        raise IdentityNotFrozenError("stable physical-unit identity artifact hash does not match")
    if (
        not isinstance(identity, dict)
        or identity.get("format") != STABLE_DEVICE_IDENTITY_FORMAT
        or identity.get("status") != "read_only_observed"
        or identity.get("model") != SUPPORTED_DEVICE["model"]
        or identity.get("vendor_id") != SUPPORTED_DEVICE["vendor_id"]
        or identity.get("product_id") != SUPPORTED_DEVICE["product_id"]
        or not isinstance(identity.get("source"), str)
        or not identity.get("source").strip()
    ):
        raise IdentityNotFrozenError("stable physical-unit identity artifact is not a typed read-only VNW-V15 observation")
    observed = identity.get("stable_unit_identity")
    if (
        not isinstance(observed, str)
        or not observed.strip()
        or observed.lower() in {SUPPORTED_DEVICE["usb_identity_boundary"].lower(), "0x054c:0x001e"}
        or observed.lower().startswith("usb\\")
    ):
        raise IdentityNotFrozenError("stable physical-unit identity artifact contains no stable unit identity")
    try:
        observed_at = datetime.fromisoformat(str(identity["observed_at_utc"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise IdentityNotFrozenError("stable physical-unit identity artifact has no valid observation time") from exc
    if observed_at.tzinfo is None:
        raise IdentityNotFrozenError("stable physical-unit identity observation time has no timezone")
    return observed, _sha256(raw)


def validate_fixture_source(source: Path) -> dict[str, Any]:
    """Validate a local source copy without creating or modifying it."""

    path = Path(source).expanduser().resolve()
    if path.name != FIXTURE_FILENAME:
        raise P18041HError(f"fixture filename must be {FIXTURE_FILENAME!r}")
    if not path.is_file() or path.is_symlink():
        raise P18041HError(f"fixture source is not a regular file: {path}")
    try:
        data = path.read_bytes()
        stat = path.stat()
    except OSError as exc:
        raise P18041HError(f"could not read fixture source: {exc}") from exc
    digest = _sha256(data)
    if data != FIXTURE_BYTES:
        raise P18041HError(
            f"fixture bytes differ: length={len(data)}, sha256={digest}; expected "
            f"length={FIXTURE_LENGTH}, sha256={FIXTURE_SHA256}"
        )
    birthtime = getattr(stat, "st_birthtime", None)
    if isinstance(birthtime, (int, float)):
        created = birthtime
        creation_kind = "filesystem_birthtime"
    elif platform.system() == "Windows":
        created = stat.st_ctime
        creation_kind = "windows_creation_time_from_ctime"
    else:
        created = stat.st_ctime
        creation_kind = "filesystem_ctime_fallback_not_creation_time"
    return {
        **fixture_identity(),
        "source_path": str(path),
        "observed_length": len(data),
        "observed_sha256": digest,
        "filesystem_created_epoch_ms": int(created * 1000),
        "filesystem_modified_epoch_ms": int(stat.st_mtime * 1000),
        "filesystem_creation_time_kind": creation_kind,
    }


def create_session(destination: Path) -> Path:
    """Create a fresh non-overwriting evidence-session skeleton."""

    root = Path(destination).expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise P18041HError(f"refusing to reuse evidence session: {root}") from exc
    except OSError as exc:
        raise P18041HError(f"could not create evidence session: {exc}") from exc
    for stage in STAGES:
        (root / stage).mkdir()
    manifest = experiment_manifest()
    manifest.update(
        {
            "state": "blocked_offline_fixture_and_stable_identity_required",
            "usb_operation_performed": False,
            "hardware_write_performed": False,
            "fixture_presence_from_repository_evidence": "not_found",
            "owner_authorization_identity": {
                "status": "not_frozen",
                "reason": "fixture presence is unverified; stable physical-unit identity and pre-execution candidate/transaction identity are not available",
            },
            "session_root": str(root),
        }
    )
    _write_json_exclusive(root / "session-manifest.json", manifest)
    return root


def write_manifest(destination: Path) -> Path:
    """Write the immutable preparation manifest without replacing a file."""

    return _write_json_exclusive(Path(destination), experiment_manifest())


def experiment_manifest() -> dict[str, Any]:
    """Return the immutable preparation contract used by the package."""

    return {
        "format": FORMAT,
        "experiment_id": EXPERIMENT_ID,
        "disposition": "FIXTURE PRE-STAGING REQUIRED — PREPARE SEPARATE AUTHORIZED PLACEMENT FIRST",
        "device_boundary": dict(SUPPORTED_DEVICE),
        "target_operation": TARGET_OPERATION,
        "fixture": fixture_identity(),
        "fixture_prestage_contract": {
            "required": True,
            "must_be_separate_operation": True,
            "must_be_completed_before_delete": True,
            "report_format": PRESTAGE_REPORT_FORMAT,
            "canonical_report": "01-fixture-prestage/placement-readback-or-backup-report.json",
        },
        "exactly_one_physical_operation": True,
        "physical_operation_count": 1,
        "physical_operation": "delete",
        "forbidden_in_experiment": [
            "add",
            "retry",
            "subtree_operation",
            "directory_selection",
            "second_target",
            "unrelated_manager_mutation",
            "automatic_recovery",
        ],
        "required_stages": list(STAGES),
        "required_time_events": list(EVENTS),
        "plan_id": "P18-041H-capture-plan-v1",
        "no_retry": True,
        "backup_contract": {
            "object_count": 8,
            "pre_delete": "fresh complete immutable copy after fixture is present",
            "post_delete": "complete eight-object readback before any recovery",
        },
        "native_capture_contract": {
            "ordinary_0x101b_count": 1,
            "sender_invocations": 1,
            "completion": "normal native terminal success required",
            "malformed_or_ambiguous": "stop; no retry",
            "pre_execution_candidate_required_for_owner_identity": True,
            "post_execution_transaction_report_required_for_verification": True,
        },
        "time_observation_contract": {
            "host_local_time": True,
            "utc": True,
            "epoch_milliseconds": True,
            "timezone_offset": True,
            "fixture_creation_and_last_write": True,
            "device_clock": "record only through an already-safe/read-only path; never queried by this package",
            "event_mapping_separate_from_raw_observations": True,
        },
        "identity_contract": {
            "must_be_frozen_before_owner_approval": True,
            "binds": [
                "device identity/model boundary",
                "typed hash-bound stable physical-unit identity artifact beyond VID/PID",
                "fresh pre-delete backup identity",
                "target path",
                "fixture identity",
                "candidate hash when available before execution",
                "transaction hash when available before execution",
                "pre-execution candidate artifact and report",
                "candidate structural delete against the fresh fixture baseline",
                "exact one-delete target operation binding and sidecar",
                "capture plan hash",
                "no-retry policy",
                "recovery plan reference",
            ],
            "requires_independent_artifacts": [
                "complete eight-object backup",
                "exact fixture source",
                "pre-execution candidate/transaction report and preserved artifact",
                "capture plan",
                "recovery plan",
                "read-only stable device-boundary observation",
            ],
            "missing_or_post_execution_candidate": "reject approval identity; do not accept procedural approval",
            "current_blockers": [
                "exact fixture is not present in read-only repository evidence and device presence is unobserved",
                "stable physical-unit identity beyond VID/PID has not been captured",
                "pre-execution candidate/transaction identity has not been captured",
            ],
        },
        "evidence_contract": {
            "native_terminal_result": "separate immutable artifact bound to the post-execution transaction-report hash",
            "verification": "candidate/post normalized comparison is mandatory; unexplained metadata is fatal",
            "seal_before_recovery": True,
            "outputs_are_non_overwriting": True,
        },
        "safety_counters": dict(SAFETY_COUNTERS),
    }


def record_time_observation(
    destination: Path,
    event: str,
    *,
    fixture_source: Optional[Path] = None,
    device_clock_observation: Optional[Path] = None,
) -> Path:
    """Record one explicit host/file-clock point; never query a device clock."""

    if event not in EVENTS:
        raise P18041HError(f"event must be one of {EVENTS!r}")
    observed_epoch_ms = time.time_ns() // 1_000_000
    now = datetime.fromtimestamp(observed_epoch_ms / 1000, timezone.utc).astimezone()
    payload: dict[str, Any] = {
        "format": "infocarry-p18-041h-time-observation-v1",
        "experiment_id": EXPERIMENT_ID,
        "event": event,
        "observed_at_local": now.isoformat(timespec="milliseconds"),
        "observed_at_utc": now.astimezone(timezone.utc).isoformat(timespec="milliseconds"),
        "observed_at_epoch_ms": observed_epoch_ms,
        "timezone_offset_minutes": int((now.utcoffset() or timezone.utc.utcoffset(now)).total_seconds() // 60),
        "timezone_name": now.tzname(),
        "host": {
            "platform": platform.platform(),
            "hostname": platform.node(),
            "python": platform.python_version(),
        },
        "fixture": None,
        "device_clock": {
            "status": "not_queried_by_offline_tool",
            "read_only_observation_path": None,
            "sha256": None,
            "size_bytes": None,
        },
        "usb_operation_performed": False,
    }
    if fixture_source is not None:
        payload["fixture"] = validate_fixture_source(fixture_source)
    if device_clock_observation is not None:
        source = Path(device_clock_observation).expanduser().resolve()
        if not source.is_file() or source.is_symlink():
            raise P18041HError(f"device-clock observation is not a regular file: {source}")
        try:
            raw = source.read_bytes()
        except OSError as exc:
            raise P18041HError(f"could not read device-clock observation: {exc}") from exc
        payload["device_clock"] = {
            "status": "supplied_read_only_observation",
            "read_only_observation_path": str(source),
            "sha256": _sha256(raw),
            "size_bytes": len(raw),
        }
    return _write_json_exclusive(Path(destination), payload)


def write_event_mapping(destination: Path, observations: Mapping[str, Path]) -> Path:
    """Write a separate semantic event map bound to raw observation hashes."""

    if set(observations) != set(EVENTS):
        raise P18041HError("event mapping must contain exactly the four required event names")
    entries: dict[str, Any] = {}
    for event in EVENTS:
        path = Path(observations[event]).expanduser().resolve()
        try:
            raw = path.read_bytes()
            value = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise P18041HError(f"event observation {event!r} is unreadable: {exc}") from exc
        if not isinstance(value, dict):
            raise P18041HError(f"event observation {event!r} is not a JSON object")
        _validate_time_observation(value, event)
        entries[event] = {
            "filename": path.name,
            "sha256": _sha256(raw),
            "observed_at_local": value.get("observed_at_local"),
            "observed_at_utc": value.get("observed_at_utc"),
            "observed_at_epoch_ms": value.get("observed_at_epoch_ms"),
            "timezone_offset_minutes": value.get("timezone_offset_minutes"),
            "fixture": value.get("fixture"),
            "device_clock": value.get("device_clock"),
        }
    result = {
        "format": "infocarry-p18-041h-event-map-v1",
        "experiment_id": EXPERIMENT_ID,
        "events": entries,
        "raw_observations_are_separate": True,
    }
    _validate_time_map(result)
    return _write_json_exclusive(Path(destination), result)


def inspect_native_capture(
    capture_path: Path,
    *,
    artifact_destination: Optional[Path] = None,
    capture_phase: str = "post-execution-evidence",
    operation_binding_metadata: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Inspect exactly one saved ordinary native ``0x101b`` transaction."""

    if capture_phase not in {"pre-execution", "post-execution-evidence"}:
        raise P18041HError("capture_phase must identify pre-execution or post-execution-evidence")
    binding = _validate_operation_binding(operation_binding_metadata, "native capture operation binding")

    source = Path(capture_path).expanduser().resolve()
    if not source.is_file() or source.is_symlink():
        raise P18041HError(f"native capture is not a regular file: {source}")
    try:
        data = source.read_bytes()
    except OSError as exc:
        raise P18041HError(f"could not read native capture: {exc}") from exc
    try:
        offsets = find_101b_headers(data)
    except (TypeError, UsblogParseError) as exc:
        raise P18041HError(f"native capture cannot be scanned: {exc}") from exc
    if len(offsets) != 1:
        raise P18041HError(
            f"expected exactly one ordinary 0x101b transaction; observed {len(offsets)}"
        )
    try:
        capture = extract_101b(data, offsets[0])
        from .payload_builder import build_from_observed_capture

        observed = build_from_observed_capture(capture)
    except (UsblogParseError, ValueError) as exc:
        raise P18041HError(f"saved native transaction is malformed: {exc}") from exc
    command, declared_length = struct.unpack_from("<HI", data, capture.command_offset)
    if command != 0x101B or declared_length != capture.declared_length:
        raise P18041HError("native command header does not match the parsed transaction")
    result: dict[str, Any] = {
        "format": "infocarry-p18-041h-native-transaction-report-v1",
        "experiment_id": EXPERIMENT_ID,
        "capture_phase": capture_phase,
        "native_log_path": str(source),
        "native_log_size_bytes": len(data),
        "native_log_sha256": _sha256(data),
        "ordinary_0x101b_transaction_count": 1,
        "record_offset": capture.record_offset,
        "command_offset": capture.command_offset,
        "command": "0x101b",
        "command_header_hex": data[capture.command_offset : capture.command_offset + 6].hex(),
        "declared_length": capture.declared_length,
        "range_count": 8,
        "range_lengths": list(capture.range_lengths),
        "range_sha256": [_sha256(value) for value in capture.ranges],
        "candidate_blob_sha256": _sha256(capture.ranges[4] + capture.ranges[7]),
        "transaction_sha256": observed.concatenated_sha256,
        "operation_binding": binding,
        "operation_binding_sha256": _sha256(_canonical_json(binding)),
        "candidate_artifact": None,
        "completion": {
            "status": "must_be_recorded_from_normal_native_terminal_result",
            "required_value": "0x0000",
        },
        "no_retry": True,
        "usb_operation_performed_by_this_tool": False,
        "safety_counters": dict(SAFETY_COUNTERS),
    }
    if artifact_destination is not None:
        artifact_root = preserve_capture_artifact(source, Path(artifact_destination), transaction_index=0)
        manifest = artifact_root / "manifest.json"
        binding_path = _write_json_exclusive(artifact_root / "operation-binding.json", binding)
        result["candidate_artifact"] = {
            "directory": str(artifact_root),
            "manifest_sha256": _sha256(manifest.read_bytes()),
            "operation_binding_sha256": _sha256(binding_path.read_bytes()),
        }
    return result


def _load_transaction_report(path: Path, *, phase: str) -> tuple[dict[str, Any], bytes, Any]:
    """Load one immutable transaction report and re-validate its artifact."""

    report_path = Path(path).expanduser().resolve()
    report, raw = _read_json_object(report_path, "native transaction report")
    if report.get("format") != "infocarry-p18-041h-native-transaction-report-v1":
        raise P18041HError("native transaction report has an unsupported format")
    if report.get("experiment_id") != EXPERIMENT_ID or report.get("capture_phase") != phase:
        raise P18041HError(f"native transaction report must be a {phase} P18-041H report")
    if report.get("ordinary_0x101b_transaction_count") != 1 or report.get("command") != "0x101b":
        raise P18041HError("native transaction report does not prove exactly one 0x101b")
    if report.get("no_retry") is not True:
        raise P18041HError("native transaction report does not freeze no-retry")
    _validate_operation_binding(report.get("operation_binding"), "native transaction operation binding")
    if report.get("operation_binding_sha256") != _sha256(_canonical_json(report["operation_binding"])):
        raise P18041HError("native transaction operation binding hash is not self-consistent")
    _digest(report.get("native_log_sha256"), "native_log_sha256")
    _digest(report.get("candidate_blob_sha256"), "candidate_blob_sha256")
    _digest(report.get("transaction_sha256"), "transaction_sha256")
    native_log_path = report.get("native_log_path")
    if not isinstance(native_log_path, str):
        raise P18041HError("native transaction report does not name its raw capture")
    native_log = Path(native_log_path).expanduser().resolve()
    if not native_log.is_file() or native_log.is_symlink():
        raise P18041HError("native transaction raw capture is missing or symlinked")
    try:
        native_log_bytes = native_log.read_bytes()
    except OSError as exc:
        raise P18041HError(f"could not read native transaction raw capture: {exc}") from exc
    if _sha256(native_log_bytes) != report["native_log_sha256"]:
        raise P18041HError("native transaction raw capture hash is not bound to the report")
    if report.get("native_log_size_bytes") != len(native_log_bytes):
        raise P18041HError("native transaction raw capture length is not bound to the report")
    try:
        reparsed = inspect_native_capture(
            native_log,
            capture_phase=phase,
            operation_binding_metadata=report.get("operation_binding"),
        )
    except P18041HError as exc:
        raise P18041HError(f"native transaction raw capture failed independent reparse: {exc}") from exc
    for key in (
        "native_log_path",
        "native_log_size_bytes",
        "native_log_sha256",
        "ordinary_0x101b_transaction_count",
        "record_offset",
        "command_offset",
        "command",
        "command_header_hex",
        "declared_length",
        "range_count",
        "range_lengths",
        "range_sha256",
        "candidate_blob_sha256",
        "transaction_sha256",
        "operation_binding",
        "operation_binding_sha256",
        "no_retry",
    ):
        if report.get(key) != reparsed.get(key):
            raise P18041HError(f"native transaction report field {key} is not derived from the raw capture")
    candidate = report.get("candidate_artifact")
    if not isinstance(candidate, dict) or not isinstance(candidate.get("directory"), str):
        raise P18041HError("native transaction report has no preserved candidate artifact")
    try:
        transaction = load_preserved_artifact(Path(candidate["directory"]))
    except (OSError, ValueError, WriteArtifactError) as exc:
        raise P18041HError(f"native transaction candidate artifact is invalid: {exc}") from exc
    manifest = Path(candidate["directory"]).expanduser().resolve() / "manifest.json"
    if not manifest.is_file() or _sha256(manifest.read_bytes()) != candidate.get("manifest_sha256"):
        raise P18041HError("native transaction candidate manifest hash is not bound to the report")
    if report.get("candidate_blob_sha256") != _sha256(transaction.ranges[4] + transaction.ranges[7]):
        raise P18041HError("native transaction candidate blob hash is not bound to the artifact")
    if report.get("transaction_sha256") != transaction.concatenated_sha256:
        raise P18041HError("native transaction hash is not bound to the artifact")
    if report.get("range_count") != 8 or report.get("range_lengths") != [len(data) for data in transaction.ranges]:
        raise P18041HError("native transaction report does not bind all eight range lengths")
    if report.get("range_sha256") != [_sha256(data) for data in transaction.ranges]:
        raise P18041HError("native transaction report does not bind all eight range hashes")
    if report.get("declared_length") != transaction.payload_length:
        raise P18041HError("native transaction report declared length is not bound to the artifact")
    if report.get("command_header_hex") != transaction.command_header.hex():
        raise P18041HError("native transaction report command header is not bound to the artifact")
    binding_path = manifest.parent / "operation-binding.json"
    if not binding_path.is_file() or _sha256(binding_path.read_bytes()) != candidate.get("operation_binding_sha256"):
        raise P18041HError("native transaction candidate operation binding is not preserved")
    binding_value, _binding_raw = _read_json_object(binding_path, "candidate operation binding")
    _validate_operation_binding(binding_value, "candidate operation binding")
    return report, raw, transaction


def seal_evidence(session_root: Path, *, verification_report: Path, destination: Path) -> Path:
    """Seal verified evidence before any separately authorized recovery."""

    root = Path(session_root).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():
        raise P18041HError(f"evidence session is not a directory: {root}")
    verification_path = Path(verification_report).expanduser().resolve()
    try:
        verification_path.relative_to(root)
    except ValueError as exc:
        raise P18041HError("verification report must be inside the evidence session") from exc
    verification, _ = _read_json_object(verification_path, "delete-evidence verification")
    if verification_path.relative_to(root).as_posix() != "10-analysis/delete-evidence-verification.json":
        raise P18041HError("delete-evidence verification must use the canonical analysis path")
    required_paths = {
        "session-manifest.json",
        "01-fixture-prestage/placement-readback-or-backup-report.json",
        "02-pre-delete-backup/manifest.json",
        "03-manager-before/snapshot-manifest.json",
        "04-time-observations/event-map.json",
        "05-native-delete-capture/native-transaction-report.json",
        "05-native-delete-capture/native-terminal-result.json",
        "05-native-delete-capture/raw-delete.usblog",
        "06-manager-after/snapshot-manifest.json",
        "07-post-delete-backup/manifest.json",
        "10-analysis/delete-evidence-verification.json",
    }
    destination_path = Path(destination).expanduser().resolve()
    if destination_path.parent != (root / "08-sealed-evidence").resolve():
        raise P18041HError("evidence seal must be stored in the session 08-sealed-evidence stage")
    if destination_path.exists():
        raise P18041HError(f"refusing to overwrite existing evidence seal: {destination_path}")
    for required in required_paths:
        required_path = root / required
        if not required_path.is_file() or required_path.is_symlink():
            raise P18041HError(f"required evidence is missing: {required_path}")
    transaction_report_path = root / "05-native-delete-capture/native-transaction-report.json"
    terminal_result_path = root / "05-native-delete-capture/native-terminal-result.json"
    transaction_report, _transaction_raw, _transaction = _load_transaction_report(
        transaction_report_path,
        phase="post-execution-evidence",
    )
    candidate = transaction_report.get("candidate_artifact")
    if not isinstance(candidate, Mapping) or not isinstance(candidate.get("directory"), str):
        raise P18041HError("native transaction report has no candidate artifact for sealing")
    candidate_root = Path(candidate["directory"]).expanduser().resolve()
    try:
        candidate_root.relative_to(root / "05-native-delete-capture")
    except ValueError as exc:
        raise P18041HError("candidate artifact must be inside the native-capture evidence stage") from exc
    if Path(transaction_report["native_log_path"]).expanduser().resolve() != root / "05-native-delete-capture/raw-delete.usblog":
        raise P18041HError("raw native capture must be the canonical sealed raw-delete.usblog inside the session")
    recomputed = verify_delete_evidence(
        root / "02-pre-delete-backup",
        root / "07-post-delete-backup",
        candidate_artifact=candidate_root,
        fixture_prestage_report=root / "01-fixture-prestage/placement-readback-or-backup-report.json",
        time_event_map=root / "04-time-observations/event-map.json",
        native_transaction_report=transaction_report_path,
        terminal_result_path=terminal_result_path,
    )
    if _canonical_json(verification) != _canonical_json(recomputed):
        raise P18041HError("verification report is not the independently recomputed canonical result")
    if recomputed.get("verification", {}).get("offline_evidence_valid") is not True:
        raise P18041HError("only independently valid delete evidence may be sealed")
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise P18041HError(f"symlinks are not permitted in evidence: {path}")
        if not path.is_file() or path == destination_path:
            continue
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        files.append({"path": relative, "size_bytes": len(data), "sha256": _sha256(data)})
    if not files:
        raise P18041HError("cannot seal an empty evidence session")
    seal = {
        "format": SEAL_FORMAT,
        "experiment_id": EXPERIMENT_ID,
        "state": "sealed_before_recovery",
        "session_root": str(root),
        "verification_report": str(verification_path),
        "verification_report_sha256": _sha256(verification_path.read_bytes()),
        "required_paths": sorted(required_paths),
        "sealed_file_count": len(files),
        "files": files,
        "recovery": {"automatic": False, "separate_owner_authorization_required": True},
        "safety_counters": dict(SAFETY_COUNTERS),
    }
    return _write_json_exclusive(destination_path, seal)


def validate_native_terminal_result(
    transaction_report: Mapping[str, Any],
    terminal_result_path: Path,
    *,
    transaction_report_raw: Optional[bytes] = None,
) -> dict[str, Any]:
    """Validate and bind the separately preserved native terminal result."""

    if not isinstance(transaction_report, Mapping):
        raise P18041HError("native transaction report must be an object")
    required_report = (
        "format",
        "experiment_id",
        "capture_phase",
        "native_log_sha256",
        "transaction_sha256",
        "candidate_blob_sha256",
        "ordinary_0x101b_transaction_count",
    )
    for key in required_report:
        if key not in transaction_report:
            raise P18041HError(f"native transaction report is missing {key}")
    if transaction_report.get("format") != "infocarry-p18-041h-native-transaction-report-v1":
        raise P18041HError("native transaction report has an unsupported format")
    if transaction_report.get("experiment_id") != EXPERIMENT_ID:
        raise P18041HError("native transaction report is not for P18-041H")
    if transaction_report.get("capture_phase") != "post-execution-evidence":
        raise P18041HError("delete verification requires post-execution native evidence")
    if transaction_report.get("ordinary_0x101b_transaction_count") != 1:
        raise P18041HError("native transaction report does not prove exactly one 0x101b")
    _digest(transaction_report["native_log_sha256"], "native_log_sha256")
    _digest(transaction_report["transaction_sha256"], "transaction_sha256")
    _digest(transaction_report["candidate_blob_sha256"], "candidate_blob_sha256")
    native_log_path = transaction_report.get("native_log_path")
    if not isinstance(native_log_path, str):
        raise P18041HError("native transaction report does not name the preserved raw capture")
    raw_capture = Path(native_log_path).expanduser().resolve()
    if not raw_capture.is_file() or raw_capture.is_symlink() or _sha256(raw_capture.read_bytes()) != transaction_report["native_log_sha256"]:
        raise P18041HError("native transaction report raw capture is missing or hash-mismatched")
    terminal, raw = _read_json_object(Path(terminal_result_path), "native terminal result")
    if terminal.get("format") != TERMINAL_RESULT_FORMAT or terminal.get("experiment_id") != EXPERIMENT_ID:
        raise P18041HError("native terminal result has an unsupported format")
    if terminal.get("status") != "normal_terminal_success" or terminal.get("normal_return") is not True:
        raise P18041HError("native terminal result is not a normal terminal success")
    if terminal.get("sender_invocations") != 1 or terminal.get("retry_count") != 0:
        raise P18041HError("native terminal result does not prove one sender invocation and zero retries")
    if terminal.get("physical_operation_count") != 1 or terminal.get("add_count") != 0:
        raise P18041HError("native terminal result does not prove exactly one delete and no add")
    if terminal.get("subtree_operation") is not False or terminal.get("target_path") != FIXTURE_PATH:
        raise P18041HError("native terminal result is not bound to the exact ordinary root fixture")
    completion = terminal.get("native_completion", terminal.get("completion_code"))
    if completion not in {0, "0x0000", "0X0000"}:
        raise P18041HError("native terminal result is not the required explicit 0x0000")
    for key in ("native_log_sha256", "transaction_sha256", "candidate_blob_sha256"):
        if terminal.get(key) != transaction_report[key]:
            raise P18041HError(f"native terminal result {key} does not match transaction report")
    if transaction_report_raw is not None and terminal.get("transaction_report_sha256") != _sha256(transaction_report_raw):
        raise P18041HError("native terminal result is not bound to the transaction report artifact")
    return {
        "path": str(Path(terminal_result_path).expanduser().resolve()),
        "sha256": _sha256(raw),
        "native_completion": "0x0000",
        "sender_invocations": 1,
        "retry_count": 0,
        "transaction_report_sha256": None if transaction_report_raw is None else _sha256(transaction_report_raw),
        "native_log_sha256": transaction_report["native_log_sha256"],
        "transaction_sha256": transaction_report["transaction_sha256"],
        "candidate_blob_sha256": transaction_report["candidate_blob_sha256"],
    }


def _verified_backup(directory: Path) -> tuple[Any, ParsedBackupBlob, bytes, dict[str, Any]]:
    try:
        verified = verify_fresh_backup(Path(directory), now=datetime.now(timezone.utc), max_age_seconds=None)
        filename = verified.object_filename("0x8004:backup-blob")
        if filename is None:
            raise P18041HError("complete backup has no dynamic backup blob")
        blob = (verified.directory / filename).read_bytes()
        parsed = parse_backup_blob(blob)
    except (WriteGateError, BackupFormatError, OSError) as exc:
        raise P18041HError(f"complete backup is not independently valid: {exc}") from exc
    summary = {
        "directory": str(verified.directory),
        "manifest_sha256": verified.manifest_sha256,
        "blob_sha256": verified.blob_sha256,
        "blob_length": len(blob),
        "object_count": verified.object_count,
        "object_sha256_by_key": dict(verified.object_sha256_by_key),
        "device_identity": {
            "vendor_id": verified.device_identity[0],
            "product_id": verified.device_identity[1],
        },
    }
    if verified.object_count != 8:
        raise P18041HError(f"complete backup contains {verified.object_count} objects; exactly 8 are required")
    if verified.device_identity != ("0x054c", "0x001e"):
        raise P18041HError("backup device identity is not the verified VNW-V15 boundary")
    return verified, parsed, blob, summary


def _path(parsed: ParsedBackupBlob, record: Any) -> Optional[str]:
    parts = parsed.paths.get(record.offset)
    if parts is None:
        return None
    name = "\\".join(parts)
    return f"{name}.{record.extension}" if record.extension else name


def _payload(parsed: ParsedBackupBlob, record: Any) -> Optional[bytes]:
    if record.kind != "file":
        return None
    try:
        return parsed.payload_parts(record)[1]
    except BackupFormatError as exc:
        raise P18041HError(f"file payload is malformed at 0x{record.offset:x}: {exc}") from exc


def _masked_structural_model(parsed: ParsedBackupBlob) -> bytes:
    """Mask only timestamps/checksum for a structural candidate comparison."""

    model = bytearray(parsed.data)
    for record in parsed.records:
        for offset in range(0x0C, 0x10):
            model[record.offset + offset] = 0
    model[0x1C:0x20] = b"\x00" * 4
    return bytes(model)


def _validate_candidate_against_baseline(
    baseline: ParsedBackupBlob,
    candidate: ParsedBackupBlob,
    fixture_record: Any,
) -> dict[str, Any]:
    """Prove the candidate is this exact fixture delete, independent of post data."""

    try:
        expected_blob = delete_existing_file(baseline, fixture_record.offset)
        expected = parse_backup_blob(expected_blob)
    except (BackupRepackError, BackupFormatError) as exc:
        raise P18041HError(f"could not derive the offline structural delete expectation: {exc}") from exc
    if len(candidate.records) != len(expected.records) or len(candidate.data) != len(expected.data):
        raise P18041HError("native candidate does not have the expected one-record structural delete shape")
    expected_masked = _masked_structural_model(expected)
    candidate_masked = _masked_structural_model(candidate)
    if expected_masked != candidate_masked:
        raise P18041HError("native candidate is not structurally the exact delete of the fresh fixture baseline")
    return {
        "exact_structural_delete": True,
        "expected_blob_sha256": _sha256(expected.data),
        "expected_record_count": len(expected.records),
        "timestamps_and_checksum_masked_only": True,
    }


def _validate_predelete_fixture(parsed: ParsedBackupBlob) -> Any:
    matches = [
        record
        for record in parsed.records
        if _path(parsed, record) == FIXTURE_PATH
    ]
    if len(matches) != 1:
        raise P18041HError("pre-delete backup does not contain exactly one fixture path")
    fixture = matches[0]
    if fixture.kind != "file" or fixture.extension.lower() != "txt":
        raise P18041HError("pre-delete fixture is not an ordinary TXT file")
    payload = _payload(parsed, fixture)
    if payload is None or len(payload) != FIXTURE_LENGTH or _sha256(payload) != FIXTURE_SHA256:
        raise P18041HError("pre-delete fixture payload does not match the sealed source identity")
    return fixture


def _record_row(before: ParsedBackupBlob, after: ParsedBackupBlob, left: Any, right: Any) -> dict[str, Any]:
    left_raw = bytes.fromhex(left.raw_hex)
    right_raw = bytes.fromhex(right.raw_hex)
    changed_offsets = [index for index, (a, b) in enumerate(zip(left_raw, right_raw)) if a != b]
    timestamp_offsets = [index for index in changed_offsets if 0x0C <= index < 0x10]
    non_timestamp_offsets = [index for index in changed_offsets if index not in timestamp_offsets]
    left_payload = _payload(before, left)
    right_payload = _payload(after, right)
    return {
        "serialized_order_before": before.records.index(left),
        "serialized_order_after": after.records.index(right),
        "offset_before": f"0x{left.offset:08x}",
        "offset_after": f"0x{right.offset:08x}",
        "path_before": _path(before, left),
        "path_after": _path(after, right),
        "path": _path(before, left) or _path(after, right),
        "reachable_before": left.offset in before.paths,
        "reachable_after": right.offset in after.paths,
        "kind_before": left.kind,
        "kind_after": right.kind,
        "name_before": left.name,
        "name_after": right.name,
        "extension_before": left.extension,
        "extension_after": right.extension,
        "field_04_before": f"0x{left.field_04_be32:08x}",
        "field_04_after": f"0x{right.field_04_be32:08x}",
        "field_08_before": f"0x{left.field_08_be32:08x}",
        "field_08_after": f"0x{right.field_08_be32:08x}",
        "field_10_before": f"0x{left.field_10_be32:08x}",
        "field_10_after": f"0x{right.field_10_be32:08x}",
        "field_14_before": f"0x{left.field_14_be32:08x}",
        "field_14_after": f"0x{right.field_14_be32:08x}",
        "timestamp_before_be32": f"0x{left.timestamp_be32:08x}",
        "timestamp_after_be32": f"0x{right.timestamp_be32:08x}",
        "timestamp_changed": left.timestamp_be32 != right.timestamp_be32,
        "record_length_before": len(left_raw),
        "record_length_after": len(right_raw),
        "record_length_equal": len(left_raw) == len(right_raw),
        "timestamp_changed_byte_offsets": [f"0x{index:02x}" for index in timestamp_offsets],
        "non_timestamp_changed_byte_offsets": [f"0x{index:02x}" for index in non_timestamp_offsets],
        "payload_before": None if left_payload is None else {"length": len(left_payload), "sha256": _sha256(left_payload)},
        "payload_after": None if right_payload is None else {"length": len(right_payload), "sha256": _sha256(right_payload)},
        "payload_byte_identical": left_payload == right_payload,
    }


def verify_delete_evidence(
    before_directory: Path,
    after_directory: Path,
    *,
    candidate_artifact: Optional[Path] = None,
    target_path: str = FIXTURE_PATH,
    fixture_prestage_report: Optional[Path] = None,
    time_event_map: Optional[Path] = None,
    native_transaction_report: Optional[Path] = None,
    terminal_result_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Independently verify the saved one-delete before/after evidence."""

    if target_path != FIXTURE_PATH:
        raise P18041HError("P18-041H target path is immutable")
    if candidate_artifact is None:
        raise P18041HError("independent delete verification requires the preserved native candidate artifact")
    if (
        fixture_prestage_report is None
        or native_transaction_report is None
        or terminal_result_path is None
        or time_event_map is None
    ):
        raise P18041HError(
            "independent delete verification requires the separate fixture-placement report, native transaction report, terminal result, and event map"
        )
    _prestage, prestage_raw = _validate_fixture_prestage_report(fixture_prestage_report)
    native_report_path = Path(native_transaction_report).expanduser().resolve()
    transaction_report, transaction_report_raw, native_transaction = _load_transaction_report(
        native_report_path, phase="post-execution-evidence"
    )
    native_capture_path = Path(transaction_report["native_log_path"]).expanduser().resolve()
    if native_capture_path.name != "raw-delete.usblog" or native_capture_path.parent.name != "05-native-delete-capture":
        raise P18041HError("post-execution raw capture must use the canonical native-capture filename and stage")
    try:
        native_capture_path.relative_to(Path(native_transaction_report).expanduser().resolve().parent)
    except ValueError as exc:
        raise P18041HError("post-execution raw capture must be beside the native transaction report") from exc
    terminal_report = validate_native_terminal_result(
        transaction_report,
        terminal_result_path,
        transaction_report_raw=transaction_report_raw,
    )
    before_verified, before, before_blob, before_summary = _verified_backup(before_directory)
    after_verified, after, after_blob, after_summary = _verified_backup(after_directory)
    before_paths = {_path(before, record): record for record in before.records if _path(before, record) is not None}
    after_paths = {_path(after, record): record for record in after.records if _path(after, record) is not None}
    if len(before_paths) != len([record for record in before.records if record.offset in before.paths]):
        raise P18041HError("before backup has duplicate reachable paths")
    if len(after_paths) != len([record for record in after.records if record.offset in after.paths]):
        raise P18041HError("after backup has duplicate reachable paths")

    fixture_before = _validate_predelete_fixture(before)

    removed = sorted(set(before_paths) - set(after_paths))
    added = sorted(set(after_paths) - set(before_paths))
    if removed != [FIXTURE_PATH] or added:
        raise P18041HError(
            f"path delta is not exactly one removal of {FIXTURE_PATH}: removed={removed}, added={added}"
        )
    shared_paths = sorted(set(before_paths) & set(after_paths))
    payload_mismatches = []
    for path in shared_paths:
        left_payload = _payload(before, before_paths[path])
        right_payload = _payload(after, after_paths[path])
        if left_payload != right_payload:
            payload_mismatches.append(path)
    if payload_mismatches:
        raise P18041HError("shared payloads changed: " + ", ".join(payload_mismatches))

    target_index = before.records.index(fixture_before)
    if len(after.records) != len(before.records) - 1:
        raise P18041HError("post-delete record count is not exactly one lower")
    rows = []
    for index, left in enumerate(before.records):
        if index == target_index:
            continue
        after_index = index if index < target_index else index - 1
        rows.append(_record_row(before, after, left, after.records[after_index]))
    record_structural_mismatches = [
        row["path"] or f"serialized-record:{row['serialized_order_before']}"
        for row in rows
        if (
            not row["record_length_equal"]
            or row["non_timestamp_changed_byte_offsets"]
            or row["reachable_before"] != row["reachable_after"]
            or (row["reachable_before"] and row["path_before"] != row["path_after"])
            or row["kind_before"] != row["kind_after"]
            or row["name_before"] != row["name_after"]
            or row["extension_before"] != row["extension_after"]
            or row["field_04_before"] != row["field_04_after"]
            or row["field_08_before"] != row["field_08_after"]
            or row["field_10_before"] != row["field_10_after"]
            or row["field_14_before"] != row["field_14_after"]
            or not row["payload_byte_identical"]
        )
    ]
    fixed_state = {}
    fixed_keys = (
        "0x001b:response-001b",
        "0x001c:response-001c",
        "0x001d:response-001d",
        "0x001e:response-001e",
        "0x001f:response-001f",
    )
    before_objects = dict(before_verified.object_sha256_by_key)
    after_objects = dict(after_verified.object_sha256_by_key)
    for key in fixed_keys:
        before_hash = before_objects.get(key)
        after_hash = after_objects.get(key)
        fixed_state[key] = {
            "before_sha256": before_hash,
            "after_sha256": after_hash,
            "byte_identical": before_hash == after_hash,
        }
    fixed_state_changed = [key for key, value in fixed_state.items() if not value["byte_identical"]]

    try:
        transaction = load_preserved_artifact(Path(candidate_artifact))
        candidate_blob = transaction.ranges[4] + transaction.ranges[7]
        candidate_parsed = parse_backup_blob(candidate_blob)
        candidate_report = {
            "directory": str(Path(candidate_artifact).expanduser().resolve()),
            "candidate_blob_sha256": _sha256(candidate_blob),
            "transaction_sha256": transaction.concatenated_sha256,
            "declared_length": transaction.payload_length,
            "command_header_hex": transaction.command_header.hex(),
            "fixed_state_sha256": [
                *(_sha256(transaction.ranges[0][index * 0x40 : (index + 1) * 0x40]) for index in range(4)),
                _sha256(transaction.ranges[1]),
            ],
        }
        candidate_baseline_structure = _validate_candidate_against_baseline(
            before, candidate_parsed, fixture_before
        )
        if candidate_report["candidate_blob_sha256"] != transaction_report["candidate_blob_sha256"]:
            raise P18041HError("preserved candidate artifact differs from the native transaction report")
        if candidate_report["transaction_sha256"] != transaction_report["transaction_sha256"]:
            raise P18041HError("preserved candidate artifact differs from the native transaction hash")
        reported_artifact = transaction_report.get("candidate_artifact")
        if not isinstance(reported_artifact, Mapping) or reported_artifact.get("directory") != candidate_report["directory"]:
            raise P18041HError("native transaction report candidate directory is not bound to the supplied artifact")
        manifest_path = Path(candidate_report["directory"]) / "manifest.json"
        if not manifest_path.is_file() or _sha256(manifest_path.read_bytes()) != reported_artifact.get("manifest_sha256"):
            raise P18041HError("native transaction report candidate manifest hash is not valid")
        candidate_comparison = compare_delete_evidence(
            before, candidate_parsed, after, target_path=FIXTURE_PATH
        ).to_dict()
    except (ValueError, OSError, BackupFormatError, WriteArtifactError) as exc:
        raise P18041HError(f"candidate artifact is not independently valid: {exc}") from exc
    if not candidate_comparison["structural_result"]["exact_supported_effect"]:
        raise P18041HError("native candidate/post comparison contains an unexplained structural difference")

    if not fixed_state_changed:
        fixed_state_status = "unchanged"
    elif candidate_report is not None:
        candidate_fixed = candidate_report["fixed_state_sha256"]
        after_fixed = [fixed_state[key]["after_sha256"] for key in fixed_keys]
        before_fixed = [fixed_state[key]["before_sha256"] for key in fixed_keys]
        if candidate_fixed == after_fixed and candidate_fixed != before_fixed:
            fixed_state_status = "changed_demonstrated_by_native_candidate_and_matches_post"
        else:
            fixed_state_status = "changed_requires_native_demonstration"
    else:
        fixed_state_status = "changed_requires_native_demonstration"

    time_report: dict[str, Any] = {
        "supplied": False,
        "event_map_sha256": None,
        "events": None,
    }
    event_value, event_bytes = _load_event_map(time_event_map)
    time_report = {
        "supplied": True,
        "event_map_sha256": _sha256(event_bytes),
        "events": event_value["events"],
    }

    timestamp_values = sorted({int(row["timestamp_after_be32"], 16) for row in rows})
    timestamp_window = {
        "unique_post_timestamp_be32": [f"0x{value:08x}" for value in timestamp_values],
        "min_epoch_seconds": min(timestamp_values) if timestamp_values else None,
        "max_epoch_seconds": max(timestamp_values) if timestamp_values else None,
        "min_utc": None if not timestamp_values else datetime.fromtimestamp(min(timestamp_values), timezone.utc).isoformat(),
        "max_utc": None if not timestamp_values else datetime.fromtimestamp(max(timestamp_values), timezone.utc).isoformat(),
    }

    integrity = {
        "before_checksum_valid": calculate_backup_checksum(before_blob) == before.header.stored_checksum,
        "after_checksum_valid": calculate_backup_checksum(after_blob) == after.header.stored_checksum,
        "before_parse_valid": True,
        "after_parse_valid": True,
    }
    native_success = True
    result = {
        "format": "infocarry-p18-041h-delete-evidence-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "target": fixture_identity(),
        "fixture_prestage": {
            "report_path": str(Path(fixture_prestage_report).expanduser().resolve()),
            "report_sha256": _sha256(prestage_raw),
            "status": "completed_and_independently_verified",
        },
        "before": before_summary,
        "after": after_summary,
        "path_delta": {
            "removed": removed,
            "added": added,
            "exact_one_target_removed": removed == [FIXTURE_PATH] and not added,
        },
        "payloads": {
            "shared_path_count": len(shared_paths),
            "mismatches": payload_mismatches,
            "unrelated_payloads_byte_identical": not payload_mismatches,
        },
        "direct_record_pairing_non_timestamp_differences": {
            "count": len(record_structural_mismatches),
            "paths_or_serialized_records": record_structural_mismatches,
            "interpretation": "reported only; the exact native candidate/post comparison is the validity gate for normalized pointer/repack delta",
        },
        "surviving_record_timestamp_table": rows,
        "timestamp_summary": {
            "surviving_record_count": len(rows),
            "changed_record_count": sum(row["timestamp_changed"] for row in rows),
            "changed_byte_count": sum(len(row["timestamp_changed_byte_offsets"]) for row in rows),
            "changed_byte_offsets": sorted(
                {offset for row in rows for offset in row["timestamp_changed_byte_offsets"]}
            ),
        },
        "integrity": integrity,
        "fixed_state": {
            "objects": fixed_state,
            "changed_object_keys": fixed_state_changed,
            "status": fixed_state_status,
        },
        "candidate": candidate_report,
        "candidate_baseline_structural_comparison": candidate_baseline_structure,
        "candidate_post_comparison": candidate_comparison,
        "time_observations": time_report,
        "evidence_inputs": {
            "before_directory": str(Path(before_directory).expanduser().resolve()),
            "after_directory": str(Path(after_directory).expanduser().resolve()),
            "candidate_artifact": str(Path(candidate_artifact).expanduser().resolve()),
            "event_map": str(Path(time_event_map).expanduser().resolve()),
            "native_transaction_report": str(Path(native_transaction_report).expanduser().resolve()),
            "terminal_result": str(Path(terminal_result_path).expanduser().resolve()),
        },
        "timestamp_window_mapping": {
            "native_post_window": timestamp_window,
            "host_event_points": None if not time_report["supplied"] else time_report["events"],
        },
        "native_completion": {"supplied": True, **terminal_report, "normal_success": native_success},
        "evidence_seal_required_before_recovery": True,
        "recovery": {
            "automatic": False,
            "modern_delete_restore_assumed": False,
            "separate_owner_authorization_required": True,
        },
        "safety_counters": dict(SAFETY_COUNTERS),
    }
    result["verification"] = {
        "offline_evidence_valid": (
            result["path_delta"]["exact_one_target_removed"]
            and result["payloads"]["unrelated_payloads_byte_identical"]
            and integrity["before_checksum_valid"]
            and integrity["after_checksum_valid"]
            and fixed_state_status in {
                "unchanged",
                "changed_demonstrated_by_native_candidate_and_matches_post",
            }
            and native_success is True
            and time_report["supplied"]
            and candidate_comparison["structural_result"]["exact_supported_effect"]
            and candidate_comparison["remaining_non_timestamp_differences"]["byte_count"] == 0
            and candidate_baseline_structure["exact_structural_delete"]
            and fixed_state_status in {
                "unchanged",
                "changed_demonstrated_by_native_candidate_and_matches_post",
            }
        ),
        "live_success_claim": "not made by this offline verifier",
    }
    return result


def build_owner_authorization_identity(
    *,
    pre_delete_backup: Path,
    capture_plan: Path,
    recovery_plan: Path,
    candidate_report: Path,
    fixture_prestage_report: Path,
    fixture_source: Path,
    device_boundary: Path,
) -> dict[str, Any]:
    """Build the exact approval fingerprint from independently verified files."""

    plan, plan_raw = _read_json_object(capture_plan, "capture plan")
    recovery, recovery_raw = _read_json_object(recovery_plan, "recovery plan")
    candidate, candidate_raw = _read_json_object(candidate_report, "pre-execution candidate report")
    boundary, boundary_raw = _read_json_object(device_boundary, "device-boundary observation")
    prestage, prestage_raw = _validate_fixture_prestage_report(fixture_prestage_report)
    if _canonical_json(plan) != _canonical_json(experiment_manifest()):
        raise IdentityNotFrozenError("capture plan is not byte-for-byte the canonical reviewed P18-041H manifest contract")
    if _canonical_json(recovery) != _canonical_json(recovery_plan_contract()):
        raise IdentityNotFrozenError("recovery plan is not the canonical reviewed P18-041H recovery contract")
    if candidate.get("capture_phase") != "pre-execution":
        raise IdentityNotFrozenError(
            "candidate/transaction identity was not frozen before owner approval; "
            "post-execution evidence cannot authorize the delete"
        )
    if candidate.get("format") != "infocarry-p18-041h-native-transaction-report-v1":
        raise IdentityNotFrozenError("pre-execution candidate report has an unsupported format")
    if (
        candidate.get("ordinary_0x101b_transaction_count") != 1
        or candidate.get("command") != "0x101b"
        or candidate.get("no_retry") is not True
    ):
        raise IdentityNotFrozenError("pre-execution candidate report does not prove exactly one 0x101b")
    for key in ("native_log_sha256", "candidate_blob_sha256", "transaction_sha256"):
        try:
            _digest(candidate.get(key), f"pre-execution candidate {key}")
        except P18041HError as exc:
            raise IdentityNotFrozenError(str(exc)) from exc
    native_log_path = candidate.get("native_log_path")
    if not isinstance(native_log_path, str):
        raise IdentityNotFrozenError("pre-execution candidate report does not name its raw capture")
    native_log = Path(native_log_path).expanduser().resolve()
    if not native_log.is_file() or native_log.is_symlink() or _sha256(native_log.read_bytes()) != candidate.get("native_log_sha256"):
        raise IdentityNotFrozenError("pre-execution raw capture is missing or hash-mismatched")
    if native_log.name != "raw-delete.usblog" or native_log.parent.name != "05-native-delete-capture":
        raise IdentityNotFrozenError("pre-execution raw capture must be inside the native-capture evidence stage")
    try:
        reconstructed = inspect_native_capture(
            native_log,
            capture_phase="pre-execution",
            operation_binding_metadata=candidate.get("operation_binding"),
        )
    except P18041HError as exc:
        raise IdentityNotFrozenError(f"pre-execution raw capture is not independently parseable: {exc}") from exc
    for key in (
        "native_log_sha256",
        "candidate_blob_sha256",
        "transaction_sha256",
        "command_header_hex",
        "declared_length",
        "range_count",
        "range_lengths",
        "range_sha256",
        "operation_binding",
        "operation_binding_sha256",
    ):
        if candidate.get(key) != reconstructed.get(key):
            raise IdentityNotFrozenError(f"pre-execution candidate report field {key} is not derived from its raw capture")
    candidate_artifact = candidate.get("candidate_artifact")
    if not isinstance(candidate_artifact, Mapping) or not isinstance(candidate_artifact.get("directory"), str):
        raise IdentityNotFrozenError("pre-execution candidate artifact is missing")
    artifact_root = Path(candidate_artifact["directory"]).expanduser().resolve()
    try:
        transaction = load_preserved_artifact(artifact_root)
        artifact_manifest = (artifact_root / "manifest.json").read_bytes()
    except (OSError, ValueError, WriteArtifactError) as exc:
        raise IdentityNotFrozenError(f"pre-execution candidate artifact is not independently valid: {exc}") from exc
    candidate_hash = _sha256(transaction.ranges[4] + transaction.ranges[7])
    transaction_hash = transaction.concatenated_sha256
    if candidate_hash != candidate.get("candidate_blob_sha256") or transaction_hash != candidate.get("transaction_sha256"):
        raise IdentityNotFrozenError("pre-execution candidate report does not match its preserved artifact")
    if candidate.get("range_count") != 8 or candidate.get("range_lengths") != [len(data) for data in transaction.ranges]:
        raise IdentityNotFrozenError("pre-execution candidate report does not bind all eight range lengths")
    if candidate.get("range_sha256") != [_sha256(data) for data in transaction.ranges]:
        raise IdentityNotFrozenError("pre-execution candidate report does not bind all eight range hashes")
    if candidate.get("declared_length") != transaction.payload_length or candidate.get("command_header_hex") != transaction.command_header.hex():
        raise IdentityNotFrozenError("pre-execution candidate report command framing is not bound to the artifact")
    if _sha256(artifact_manifest) != candidate_artifact.get("manifest_sha256"):
        raise IdentityNotFrozenError("pre-execution candidate report does not bind its artifact manifest")
    binding_path = artifact_root / "operation-binding.json"
    if not binding_path.is_file() or _sha256(binding_path.read_bytes()) != candidate_artifact.get("operation_binding_sha256"):
        raise IdentityNotFrozenError("pre-execution candidate artifact does not preserve its operation binding")
    binding_value, _binding_raw = _read_json_object(binding_path, "pre-execution candidate operation binding")
    _validate_operation_binding(binding_value, "pre-execution candidate operation binding")
    fixture = validate_fixture_source(fixture_source)
    if fixture["observed_sha256"] != FIXTURE_SHA256:
        raise IdentityNotFrozenError("fixture source does not match the exact P18-041H identity")
    if boundary.get("format") != "infocarry-p18-041h-device-boundary-v1":
        raise IdentityNotFrozenError("device-boundary observation has an unsupported format")
    if boundary.get("model") != SUPPORTED_DEVICE["model"] or boundary.get("vendor_id") != SUPPORTED_DEVICE["vendor_id"] or boundary.get("product_id") != SUPPORTED_DEVICE["product_id"]:
        raise IdentityNotFrozenError("device-boundary observation is not the verified VNW-V15")
    if boundary.get("observation_mode") != "read_only" or not isinstance(boundary.get("identity_source"), str) or not boundary["identity_source"].strip():
        raise IdentityNotFrozenError("stable device identity must come from a named read-only observation path")
    stable_unit_identity, stable_identity_artifact_sha256 = _load_stable_device_identity(boundary, device_boundary)
    _verified, baseline_parsed, _blob, backup = _verified_backup(pre_delete_backup)
    baseline_fixture = _validate_predelete_fixture(baseline_parsed)
    try:
        candidate_blob = transaction.ranges[4] + transaction.ranges[7]
        candidate_parsed = parse_backup_blob(candidate_blob)
        candidate_effect = _validate_candidate_against_baseline(
            baseline_parsed, candidate_parsed, baseline_fixture
        )
    except (BackupFormatError, ValueError, P18041HError) as exc:
        raise IdentityNotFrozenError(
            f"pre-execution candidate does not contain a valid exact fixture-delete model: {exc}"
        ) from exc
    identity_payload = {
        "format": "infocarry-p18-041h-owner-authorization-identity-v1",
        "experiment_id": EXPERIMENT_ID,
        "device": {
            **SUPPORTED_DEVICE,
            "stable_unit_identity": stable_unit_identity,
            "stable_identity_artifact_sha256": stable_identity_artifact_sha256,
        },
        "pre_delete_backup": {
            "manifest_sha256": backup["manifest_sha256"],
            "blob_sha256": backup["blob_sha256"],
            "object_sha256_by_key": dict(sorted(backup["object_sha256_by_key"].items())),
        },
        "target_path": FIXTURE_PATH,
        "fixture_prestage": {
            "report_sha256": _sha256(prestage_raw),
            "status": prestage["status"],
            "placement_backup": dict(prestage["post_placement_backup"]),
        },
        "fixture": {
            **fixture_identity(),
            "source_sha256": fixture["observed_sha256"],
        },
        "candidate": {
            "candidate_blob_sha256": candidate_hash,
            "transaction_sha256": transaction_hash,
            "phase": "pre-execution",
            "exact_fixture_delete_model": True,
            "baseline_structural_comparison": candidate_effect,
            "report_sha256": _sha256(candidate_raw),
            "artifact_manifest_sha256": _sha256(artifact_manifest),
        },
        "device_boundary_observation_sha256": _sha256(boundary_raw),
        "capture_plan_sha256": _sha256(plan_raw),
        "capture_plan_id": plan["plan_id"],
        "no_retry_policy": "one sender invocation; any post-start ambiguity is indeterminate; never retry",
        "recovery_plan_id": recovery["plan_id"],
        "recovery_plan_sha256": _sha256(recovery_raw),
    }
    fingerprint = _sha256(_canonical_json(identity_payload))
    return {
        **identity_payload,
        "fingerprint_sha256": fingerprint,
        "exact_owner_approval_phrase": f"{APPROVAL_PREFIX} {fingerprint}",
        "status": "ready_for_owner_approval_only_after_independent_review",
        "approval_is_not_granted": True,
        "usb_operation_performed": False,
        "safety_counters": dict(SAFETY_COUNTERS),
    }


__all__ = [
    "APPROVAL_PREFIX",
    "EVENTS",
    "EXPERIMENT_ID",
    "FIXTURE_BYTES",
    "FIXTURE_FILENAME",
    "FIXTURE_LENGTH",
    "FIXTURE_PATH",
    "FIXTURE_SHA256",
    "FORMAT",
    "IdentityNotFrozenError",
    "P18041HError",
    "PRESTAGE_REPORT_FORMAT",
    "SAFETY_COUNTERS",
    "STAGES",
    "SUPPORTED_DEVICE",
    "build_owner_authorization_identity",
    "create_session",
    "experiment_manifest",
    "fixture_identity",
    "inspect_native_capture",
    "operation_binding",
    "record_time_observation",
    "recovery_plan_contract",
    "seal_evidence",
    "validate_fixture_source",
    "validate_native_terminal_result",
    "verify_delete_evidence",
    "write_json",
    "write_manifest",
    "write_event_mapping",
]
