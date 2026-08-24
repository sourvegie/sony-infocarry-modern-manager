"""Strict, read-only validation for Windows 2000 timestamp-tool output.

The validator reads numbered ``stamp-*.txt`` files and an optional separate
event mapping. It hashes every raw file, validates that all representations
describe the same instant, and writes only a derived JSON report when the
caller requests one. Raw timestamp text is never copied into the report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


TIMESTAMP_FORMAT = "infocarry-experiment-timestamp-v1"
VALIDATION_FORMAT = "infocarry-timestamp-validation-v1"
EVENT_MAPPING_FORMAT = "infocarry-experiment-event-map-v1"
DEFAULT_MAX_GAP_MS = 24 * 60 * 60 * 1000

_FILENAME_RE = re.compile(r"^stamp-(\d{4,})\.txt$", re.IGNORECASE)
_INTEGER_RE = re.compile(r"^-?\d+$")
_DECIMAL_INTEGER_RE = re.compile(r"^\d+$")
_LOCAL_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})"
    r"\.(\d{3})([+-])(\d{2}):(\d{2})$"
)
_UTC_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.(\d{3})Z$"
)
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_REQUIRED_FIELDS = (
    "format",
    "sequence",
    "local_timestamp",
    "utc_timestamp",
    "epoch_ms",
    "timezone_offset_minutes",
    "computer_name",
    "tool_version",
)
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class TimestampValidationError(ValueError):
    """Raised for a timestamp file or event mapping that cannot be parsed."""


@dataclass(frozen=True)
class TimestampRecord:
    path: Path
    sequence: int
    local_timestamp: str
    utc_timestamp: str
    epoch_ms: int
    timezone_offset_minutes: int
    computer_name: str
    tool_version: str
    sha256: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.path.name,
            "sequence": self.sequence,
            "local_timestamp": self.local_timestamp,
            "utc_timestamp": self.utc_timestamp,
            "epoch_ms": self.epoch_ms,
            "timezone_offset_minutes": self.timezone_offset_minutes,
            "computer_name": self.computer_name,
            "tool_version": self.tool_version,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


def _epoch_ms(value: datetime) -> int:
    delta = value.astimezone(timezone.utc) - _EPOCH
    return (
        delta.days * 86_400_000
        + delta.seconds * 1_000
        + delta.microseconds // 1_000
    )


def _parse_datetime_parts(match: re.Match[str], offset_minutes: int | None) -> datetime:
    year, month, day, hour, minute, second, millisecond = (
        int(match.group(index)) for index in range(1, 8)
    )
    try:
        naive = datetime(
            year, month, day, hour, minute, second, millisecond * 1_000
        )
    except ValueError as exc:
        raise TimestampValidationError(f"invalid calendar value: {exc}") from exc
    if offset_minutes is None:
        return naive.replace(tzinfo=timezone.utc)
    return naive.replace(tzinfo=timezone(timedelta(minutes=offset_minutes)))


def _parse_fields(path: Path, data: bytes, filename_sequence: int) -> TimestampRecord:
    digest = hashlib.sha256(data).hexdigest()
    if not data.endswith(b"\r\n"):
        raise TimestampValidationError("file must end with CRLF")
    if b"\n" in data.replace(b"\r\n", b""):
        raise TimestampValidationError("file contains a non-CRLF line ending")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TimestampValidationError("file is not strict UTF-8 text") from exc
    lines = text[:-2].split("\r\n")
    fields: dict[str, str] = {}
    for line in lines:
        if not line or line.count("=") != 1:
            raise TimestampValidationError("each line must be one non-empty key=value pair")
        key, value = line.split("=", 1)
        if key not in _REQUIRED_FIELDS or key in fields:
            raise TimestampValidationError(f"unexpected or duplicate field: {key!r}")
        fields[key] = value
    if tuple(sorted(fields)) != tuple(sorted(_REQUIRED_FIELDS)):
        missing = sorted(set(_REQUIRED_FIELDS) - set(fields))
        extra = sorted(set(fields) - set(_REQUIRED_FIELDS))
        raise TimestampValidationError(f"field set mismatch; missing={missing}, extra={extra}")
    if fields["format"] != TIMESTAMP_FORMAT:
        raise TimestampValidationError("unsupported timestamp format")
    if not _DECIMAL_INTEGER_RE.fullmatch(fields["sequence"]):
        raise TimestampValidationError("sequence must be a positive decimal integer")
    sequence = int(fields["sequence"])
    if sequence <= 0:
        raise TimestampValidationError("sequence must be a positive decimal integer")
    if sequence != filename_sequence:
        raise TimestampValidationError(
            f"sequence {sequence} does not match filename sequence {filename_sequence}"
        )
    if not _INTEGER_RE.fullmatch(fields["epoch_ms"]):
        raise TimestampValidationError("epoch_ms must be a decimal integer")
    epoch_ms = int(fields["epoch_ms"])
    if not _INTEGER_RE.fullmatch(fields["timezone_offset_minutes"]):
        raise TimestampValidationError("timezone_offset_minutes must be a decimal integer")
    timezone_offset_minutes = int(fields["timezone_offset_minutes"])
    if not -14 * 60 <= timezone_offset_minutes <= 14 * 60:
        raise TimestampValidationError("timezone offset is outside the supported ±14-hour range")

    local_match = _LOCAL_RE.fullmatch(fields["local_timestamp"])
    utc_match = _UTC_RE.fullmatch(fields["utc_timestamp"])
    if local_match is None or utc_match is None:
        raise TimestampValidationError("timestamp fields do not use the required ISO format")
    sign = -1 if local_match.group(8) == "-" else 1
    offset_hours = int(local_match.group(9))
    offset_minutes = int(local_match.group(10))
    if offset_minutes > 59 or offset_hours > 14 or (
        offset_hours == 14 and offset_minutes != 0
    ):
        raise TimestampValidationError("local timestamp has an invalid UTC offset")
    encoded_offset = sign * (offset_hours * 60 + offset_minutes)
    if encoded_offset != timezone_offset_minutes:
        raise TimestampValidationError(
            "timezone_offset_minutes disagrees with local_timestamp"
        )
    local_dt = _parse_datetime_parts(local_match, encoded_offset)
    utc_dt = _parse_datetime_parts(utc_match, None)
    if local_dt.astimezone(timezone.utc) != utc_dt:
        raise TimestampValidationError("local_timestamp and utc_timestamp disagree")
    if _epoch_ms(local_dt) != epoch_ms or _epoch_ms(utc_dt) != epoch_ms:
        raise TimestampValidationError("epoch_ms disagrees with the ISO timestamps")
    if not _VERSION_RE.fullmatch(fields["tool_version"]):
        raise TimestampValidationError("tool_version must be a dotted numeric version")
    return TimestampRecord(
        path=path,
        sequence=sequence,
        local_timestamp=fields["local_timestamp"],
        utc_timestamp=fields["utc_timestamp"],
        epoch_ms=epoch_ms,
        timezone_offset_minutes=timezone_offset_minutes,
        computer_name=fields["computer_name"],
        tool_version=fields["tool_version"],
        sha256=digest,
        size_bytes=len(data),
    )


def parse_timestamp_file(path: Path) -> TimestampRecord:
    """Parse one raw file without changing it."""

    file_path = Path(path).expanduser().resolve()
    match = _FILENAME_RE.fullmatch(file_path.name)
    if match is None:
        raise TimestampValidationError(
            f"unexpected timestamp filename: {file_path.name!r}"
        )
    if not file_path.is_file() or file_path.is_symlink():
        raise TimestampValidationError(f"not a regular timestamp file: {file_path}")
    try:
        data = file_path.read_bytes()
    except OSError as exc:
        raise TimestampValidationError(f"could not read {file_path}: {exc}") from exc
    return _parse_fields(file_path, data, int(match.group(1)))


def _load_event_mapping(value: Path | Mapping[str, Any]) -> Mapping[str, int]:
    if isinstance(value, (str, Path)):
        mapping_path = Path(value).expanduser().resolve()
        try:
            value = json.loads(mapping_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TimestampValidationError(f"could not read event mapping: {exc}") from exc
    if not isinstance(value, Mapping):
        raise TimestampValidationError("event mapping must be a JSON object")
    if "format" in value and value["format"] != EVENT_MAPPING_FORMAT:
        raise TimestampValidationError("unsupported event mapping format")
    events = value.get("events", value)
    if not isinstance(events, Mapping):
        raise TimestampValidationError("event mapping events must be an object")
    normalized: dict[str, int] = {}
    for name, raw in events.items():
        if name == "format":
            continue
        if not isinstance(name, str) or not name.strip():
            raise TimestampValidationError("event names must be non-empty strings")
        if isinstance(raw, Mapping):
            raw = raw.get("sequence")
        if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
            raise TimestampValidationError(f"event {name!r} must map to a positive sequence")
        if raw in normalized.values():
            raise TimestampValidationError(f"event sequence {raw} is mapped more than once")
        normalized[name] = raw
    if not normalized:
        raise TimestampValidationError("event mapping contains no events")
    return normalized


def validate_timestamp_logs(
    directory: Path,
    *,
    event_mapping: Path | Mapping[str, Any] | None = None,
    required_events: Sequence[str] = (),
    max_gap_ms: int = DEFAULT_MAX_GAP_MS,
) -> dict[str, Any]:
    """Return a derived validation report for a timestamp logs directory."""

    root = Path(directory).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if isinstance(max_gap_ms, bool) or not isinstance(max_gap_ms, int) or max_gap_ms < 0:
        raise ValueError("max_gap_ms must be a nonnegative integer")
    if not root.is_dir() or root.is_symlink():
        errors.append(f"timestamp directory is not a regular directory: {root}")
        children: list[Path] = []
    else:
        children = sorted(root.iterdir(), key=lambda item: item.name.lower())

    file_reports: list[dict[str, Any]] = []
    records: list[TimestampRecord] = []
    for child in children:
        if not child.is_file() or child.is_symlink():
            errors.append(f"unexpected non-file entry: {child.name}")
            continue
        match = _FILENAME_RE.fullmatch(child.name)
        if match is None:
            try:
                digest = hashlib.sha256(child.read_bytes()).hexdigest()
                size = child.stat().st_size
            except OSError as exc:
                digest, size = None, None
                errors.append(f"could not hash unexpected file {child.name}: {exc}")
            file_reports.append(
                {"filename": child.name, "sha256": digest, "size_bytes": size, "valid": False}
            )
            errors.append(f"unexpected timestamp filename: {child.name}")
            continue
        try:
            record = parse_timestamp_file(child)
        except TimestampValidationError as exc:
            try:
                data = child.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                size = len(data)
            except OSError as read_error:
                digest, size = None, None
                errors.append(f"could not hash {child.name}: {read_error}")
            file_reports.append(
                {
                    "filename": child.name,
                    "filename_sequence": int(match.group(1)),
                    "sha256": digest,
                    "size_bytes": size,
                    "valid": False,
                    "error": str(exc),
                }
            )
            errors.append(f"{child.name}: {exc}")
            continue
        records.append(record)
        file_reports.append({**record.to_dict(), "valid": True})

    records.sort(key=lambda item: item.sequence)
    sequences = [record.sequence for record in records]
    duplicates = sorted({sequence for sequence in sequences if sequences.count(sequence) > 1})
    for sequence in duplicates:
        errors.append(f"duplicate sequence number: {sequence}")
    if not records:
        errors.append("no valid timestamp files found")

    gaps: list[int] = []
    if sequences:
        for previous, current in zip(sequences, sequences[1:]):
            if current > previous + 1:
                gaps.extend(range(previous + 1, current))
    chronology: list[dict[str, int]] = []
    for previous, current in zip(records, records[1:]):
        gap = current.epoch_ms - previous.epoch_ms
        chronology.append(
            {
                "from_sequence": previous.sequence,
                "to_sequence": current.sequence,
                "gap_ms": gap,
            }
        )
        if gap < 0:
            errors.append(
                f"clock reversal: sequence {current.sequence} is earlier than {previous.sequence}"
            )
        elif gap > max_gap_ms:
            warnings.append(
                f"unreasonable gap: {gap} ms between sequences {previous.sequence} and {current.sequence}"
            )

    normalized_mapping: dict[str, int] | None = None
    if event_mapping is None:
        if required_events:
            errors.append(
                "event mapping is required for: " + ", ".join(str(item) for item in required_events)
            )
    else:
        try:
            normalized_mapping = dict(_load_event_mapping(event_mapping))
        except TimestampValidationError as exc:
            errors.append(str(exc))
        if normalized_mapping is not None:
            available = set(sequences)
            for event in required_events:
                if event not in normalized_mapping:
                    errors.append(f"event mapping is missing required event: {event}")
            for event, sequence in normalized_mapping.items():
                if sequence not in available:
                    errors.append(f"event {event!r} references missing sequence {sequence}")

    return {
        "format": VALIDATION_FORMAT,
        "valid": not errors,
        "source_directory": str(root),
        "file_count": len(file_reports),
        "valid_file_count": len(records),
        "sequence_numbers": sequences,
        "sequence_gaps": gaps,
        "files": file_reports,
        "chronology": chronology,
        "event_mapping": normalized_mapping,
        "max_gap_ms": max_gap_ms,
        "errors": errors,
        "warnings": warnings,
    }


def write_validation_report(destination: Path, report: Mapping[str, Any]) -> Path:
    """Write one derived report exclusively; never replace an existing file."""

    output = Path(destination).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(dict(report), indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        with output.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise TimestampValidationError(f"refusing to overwrite report: {output}") from exc
    except OSError as exc:
        raise TimestampValidationError(f"could not write report {output}: {exc}") from exc
    return output


__all__ = [
    "DEFAULT_MAX_GAP_MS",
    "EVENT_MAPPING_FORMAT",
    "TIMESTAMP_FORMAT",
    "TimestampRecord",
    "TimestampValidationError",
    "parse_timestamp_file",
    "validate_timestamp_logs",
    "write_validation_report",
]
