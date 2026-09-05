"""Offline differential primitives for the Legacy Oracle boundary.

The Oracle compares already-preserved representations; it is deliberately not
part of the candidate, authorization, or transport path.  Raw bytes are never
normalized in place.  Every comparison retains the raw changed ranges and
records any separately justified volatile-range annotation alongside the
normalized view.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

from .backup_format import ParsedBackupBlob, BackupRecord
from .protocol import build_command_header


class DifferentialError(ValueError):
    """Raised when an Oracle representation or annotation is malformed."""


CORPUS_FORMAT = "sony-infocarry-legacy-oracle-corpus-v1"
_REPRESENTATION_IDS = frozenset(
    {"legacy_candidate", "legacy_transaction", "modern_candidate", "modern_transaction"}
)


class DifferentialClassification(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    EXPLAINED_DETERMINISTIC_DIFFERENCE = "EXPLAINED_DETERMINISTIC_DIFFERENCE"
    EXPLAINED_VOLATILE_FIELD = "EXPLAINED_VOLATILE_FIELD"
    UNEXPLAINED = "UNEXPLAINED"
    NOT_COMPARABLE = "NOT_COMPARABLE"


@dataclass(frozen=True)
class DifferenceRange:
    """A half-open raw byte range that differs between two values."""

    start: int
    end: int
    differing_bytes: int
    left_length: int
    right_length: int

    def __post_init__(self) -> None:
        if not isinstance(self.start, int) or isinstance(self.start, bool) or self.start < 0:
            raise DifferentialError("difference start must be a non-negative integer")
        if not isinstance(self.end, int) or isinstance(self.end, bool) or self.end <= self.start:
            raise DifferentialError("difference end must be greater than start")
        if not isinstance(self.differing_bytes, int) or self.differing_bytes <= 0:
            raise DifferentialError("differing_bytes must be positive")

    def to_dict(self) -> dict[str, int]:
        return {
            "start": self.start,
            "end": self.end,
            "length": self.end - self.start,
            "differing_bytes": self.differing_bytes,
        }


@dataclass(frozen=True)
class DifferenceAnnotation:
    """An independently justified explanation for a byte range."""

    start: int
    end: int
    classification: DifferentialClassification
    label: str
    evidence: str

    def __post_init__(self) -> None:
        if not isinstance(self.start, int) or isinstance(self.start, bool) or self.start < 0:
            raise DifferentialError("annotation start must be a non-negative integer")
        if not isinstance(self.end, int) or isinstance(self.end, bool) or self.end <= self.start:
            raise DifferentialError("annotation end must be greater than start")
        if self.classification not in {
            DifferentialClassification.EXPLAINED_DETERMINISTIC_DIFFERENCE,
            DifferentialClassification.EXPLAINED_VOLATILE_FIELD,
        }:
            raise DifferentialError("annotations must explain a deterministic or volatile difference")
        if not isinstance(self.label, str) or not self.label.strip():
            raise DifferentialError("annotation label must be non-empty")
        if not isinstance(self.evidence, str) or not self.evidence.strip():
            raise DifferentialError("annotation evidence must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "length": self.end - self.start,
            "classification": self.classification.value,
            "label": self.label,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class ClassifiedDifference:
    raw: DifferenceRange
    classification: DifferentialClassification
    annotations: tuple[DifferenceAnnotation, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result = self.raw.to_dict()
        result["classification"] = self.classification.value
        result["annotations"] = [annotation.to_dict() for annotation in self.annotations]
        return result


@dataclass(frozen=True)
class ByteDifferential:
    """Raw and normalized comparison of two byte representations."""

    left_label: str
    right_label: str
    left_length: int
    right_length: int
    left_sha256: str
    right_sha256: str
    raw_differences: tuple[ClassifiedDifference, ...]
    normalized_differences: tuple[DifferenceRange, ...]
    annotations: tuple[DifferenceAnnotation, ...]

    @property
    def classification(self) -> DifferentialClassification:
        if not self.raw_differences:
            return DifferentialClassification.EXACT_MATCH
        if all(item.classification != DifferentialClassification.UNEXPLAINED for item in self.raw_differences):
            classes = {item.classification for item in self.raw_differences}
            if DifferentialClassification.EXPLAINED_VOLATILE_FIELD in classes:
                return DifferentialClassification.EXPLAINED_VOLATILE_FIELD
            return DifferentialClassification.EXPLAINED_DETERMINISTIC_DIFFERENCE
        return DifferentialClassification.UNEXPLAINED

    def to_dict(self) -> dict[str, Any]:
        return {
            "left": {"label": self.left_label, "length": self.left_length, "sha256": self.left_sha256},
            "right": {"label": self.right_label, "length": self.right_length, "sha256": self.right_sha256},
            "classification": self.classification.value,
            "raw": {
                "difference_count": len(self.raw_differences),
                "differing_byte_count": sum(item.raw.differing_bytes for item in self.raw_differences),
                "ranges": [item.to_dict() for item in self.raw_differences],
            },
            "normalized": {
                "difference_count": len(self.normalized_differences),
                "differing_byte_count": sum(item.differing_bytes for item in self.normalized_differences),
                "ranges": [item.to_dict() for item in self.normalized_differences],
            },
            "annotations": [annotation.to_dict() for annotation in self.annotations],
        }


def _coerce_bytes(data: bytes | bytearray | memoryview, label: str) -> bytes:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise DifferentialError(f"{label} must be bytes-like")
    return bytes(data)


def _coerce_annotation(value: DifferenceAnnotation | Mapping[str, Any]) -> DifferenceAnnotation:
    if isinstance(value, DifferenceAnnotation):
        return value
    if not isinstance(value, Mapping):
        raise DifferentialError("annotation must be a DifferenceAnnotation or mapping")
    try:
        classification = DifferentialClassification(value["classification"])
        return DifferenceAnnotation(
            start=value["start"],
            end=value["end"],
            classification=classification,
            label=value["label"],
            evidence=value["evidence"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DifferentialError(f"malformed difference annotation: {exc}") from exc


def _validate_annotations(annotations: Iterable[DifferenceAnnotation | Mapping[str, Any]]) -> tuple[DifferenceAnnotation, ...]:
    try:
        result = tuple(_coerce_annotation(item) for item in annotations)
    except TypeError as exc:
        raise DifferentialError("annotations must be iterable") from exc
    for index, current in enumerate(result):
        for previous in result[:index]:
            if current.start < previous.end and previous.start < current.end:
                raise DifferentialError("difference annotations must not overlap")
    return tuple(sorted(result, key=lambda item: (item.start, item.end, item.label)))


def _raw_ranges(left: bytes, right: bytes) -> tuple[DifferenceRange, ...]:
    common_length = min(len(left), len(right))
    ranges: list[DifferenceRange] = []
    start: int | None = None
    count = 0
    for index in range(common_length):
        if left[index] != right[index]:
            if start is None:
                start = index
                count = 0
            count += 1
        elif start is not None:
            ranges.append(DifferenceRange(start, index, count, len(left), len(right)))
            start = None
    if start is not None:
        ranges.append(DifferenceRange(start, common_length, count, len(left), len(right)))
    if len(left) != len(right):
        start = common_length
        end = max(len(left), len(right))
        ranges.append(DifferenceRange(start, end, end - start, len(left), len(right)))
    return tuple(ranges)


def _covering_annotations(raw: DifferenceRange, annotations: Sequence[DifferenceAnnotation]) -> tuple[DifferenceAnnotation, ...]:
    return tuple(
        annotation
        for annotation in annotations
        if annotation.start <= raw.start and annotation.end >= raw.end
    )


def compare_bytes(
    left: bytes | bytearray | memoryview,
    right: bytes | bytearray | memoryview,
    *,
    left_label: str = "legacy",
    right_label: str = "modern",
    annotations: Iterable[DifferenceAnnotation | Mapping[str, Any]] = (),
) -> ByteDifferential:
    """Compare bytes without erasing raw differences.

    An annotation can explain a changed range, but it cannot make bytes equal:
    the raw range is always retained.  A changed range not fully covered by an
    annotation remains ``UNEXPLAINED`` and remains in the normalized result.
    """

    left_bytes = _coerce_bytes(left, "left")
    right_bytes = _coerce_bytes(right, "right")
    if not isinstance(left_label, str) or not left_label:
        raise DifferentialError("left_label must be non-empty")
    if not isinstance(right_label, str) or not right_label:
        raise DifferentialError("right_label must be non-empty")
    normalized_annotations = _validate_annotations(annotations)
    raw_ranges = _raw_ranges(left_bytes, right_bytes)
    classified: list[ClassifiedDifference] = []
    normalized: list[DifferenceRange] = []
    for raw in raw_ranges:
        covering = _covering_annotations(raw, normalized_annotations)
        classification = (
            covering[0].classification
            if covering
            else DifferentialClassification.UNEXPLAINED
        )
        classified.append(ClassifiedDifference(raw, classification, covering))
        if not covering:
            normalized.append(raw)
    return ByteDifferential(
        left_label=left_label,
        right_label=right_label,
        left_length=len(left_bytes),
        right_length=len(right_bytes),
        left_sha256=hashlib.sha256(left_bytes).hexdigest(),
        right_sha256=hashlib.sha256(right_bytes).hexdigest(),
        raw_differences=tuple(classified),
        normalized_differences=tuple(normalized),
        annotations=normalized_annotations,
    )


def _record_semantics(parsed: ParsedBackupBlob, record: BackupRecord) -> dict[str, Any]:
    path = parsed.paths.get(record.offset)
    result: dict[str, Any] = {
        "offset": record.offset,
        "path": "\\".join(path) if path is not None else None,
        "kind": record.kind,
        "flag": record.flag,
        "extension": record.extension,
        "field_04": record.field_04_be32,
        "field_08": record.field_08_be32,
        "timestamp_be32": record.timestamp_be32,
        "field_10": record.field_10_be32,
        "field_14": record.field_14_be32,
        "name": record.name,
    }
    if record.kind == "file" and record.offset in parsed.paths:
        prefix, payload = parsed.payload_parts(record)
        result["payload_prefix_length"] = len(prefix)
        result["payload_prefix_sha256"] = hashlib.sha256(prefix).hexdigest()
        result["payload_length"] = len(payload)
        result["payload_sha256"] = hashlib.sha256(payload).hexdigest()
        result["alignment_padding"] = (-len(prefix) - len(payload)) % 4
    return result


def backup_inventory(parsed: ParsedBackupBlob) -> dict[str, Any]:
    """Return a sanitized, deterministic structural inventory of a blob."""

    if not isinstance(parsed, ParsedBackupBlob):
        raise DifferentialError("parsed must be a ParsedBackupBlob")
    records = [_record_semantics(parsed, record) for record in parsed.records]
    return {
        "format": "infocarry-legacy-oracle-backup-inventory-v1",
        "blob_length": len(parsed.data),
        "blob_sha256": hashlib.sha256(parsed.data).hexdigest(),
        "header": parsed.header.to_dict(),
        "record_count": len(parsed.records),
        "reachable_count": len(parsed.paths),
        "records": records,
        "parent_record_offsets": list(parsed.parent_record_offsets),
        "orphan_record_offsets": list(parsed.orphan_record_offsets),
    }


def compare_backup_structure(left: ParsedBackupBlob, right: ParsedBackupBlob) -> dict[str, Any]:
    """Compare parsed record/header facts without comparing raw bytes twice."""

    if not isinstance(left, ParsedBackupBlob) or not isinstance(right, ParsedBackupBlob):
        raise DifferentialError("left and right must be ParsedBackupBlob values")
    left_inventory = backup_inventory(left)
    right_inventory = backup_inventory(right)
    fields = (
        "version_major", "version_minor", "record_size", "checksum_start",
        "last_byte_offset", "optional_region_start", "optional_region_end",
        "metadata_start", "metadata_length", "content_start", "content_length",
        "total_length", "trailer_hex",
    )
    header_differences = [
        {"field": field, "left": left_inventory["header"][field], "right": right_inventory["header"][field]}
        for field in fields
        if left_inventory["header"][field] != right_inventory["header"][field]
    ]
    record_differences: list[dict[str, Any]] = []
    count = min(len(left.records), len(right.records))
    for index in range(count):
        left_record = _record_semantics(left, left.records[index])
        right_record = _record_semantics(right, right.records[index])
        changed = {
            field: {"left": left_record.get(field), "right": right_record.get(field)}
            for field in sorted(set(left_record) | set(right_record))
            if left_record.get(field) != right_record.get(field)
        }
        if changed:
            record_differences.append({"index": index, "fields": changed})
    return {
        "classification": (
            DifferentialClassification.EXACT_MATCH.value
            if not header_differences and not record_differences and len(left.records) == len(right.records)
            else DifferentialClassification.UNEXPLAINED.value
        ),
        "left": {"blob_length": len(left.data), "blob_sha256": hashlib.sha256(left.data).hexdigest(), "record_count": len(left.records), "reachable_count": len(left.paths)},
        "right": {"blob_length": len(right.data), "blob_sha256": hashlib.sha256(right.data).hexdigest(), "record_count": len(right.records), "reachable_count": len(right.paths)},
        "header_differences": header_differences,
        "record_differences": record_differences,
        "record_count_difference": len(left.records) - len(right.records),
    }


def transaction_inventory(
    ranges: Sequence[bytes | bytearray | memoryview],
    *,
    label: str = "transaction",
    command: int = 0x101B,
    variable_n: int | None = None,
    variable_m: int | None = None,
    trailer: bytes | bytearray | memoryview = b"",
    completion_status: int | None = None,
) -> dict[str, Any]:
    """Describe an offline transaction wrapper without sending it."""

    if not isinstance(ranges, Sequence) or isinstance(ranges, (str, bytes, bytearray)):
        raise DifferentialError("transaction ranges must be a sequence")
    if isinstance(command, bool) or not isinstance(command, int) or not 0 <= command <= 0xFFFF:
        raise DifferentialError("transaction command must fit uint16")
    if variable_n is not None and (isinstance(variable_n, bool) or not isinstance(variable_n, int) or variable_n < 0):
        raise DifferentialError("variable_n must be a non-negative integer")
    if variable_m is not None and (isinstance(variable_m, bool) or not isinstance(variable_m, int) or variable_m < 0):
        raise DifferentialError("variable_m must be a non-negative integer")
    payloads = tuple(_coerce_bytes(value, f"range {index + 1}") for index, value in enumerate(ranges))
    trailer_bytes = _coerce_bytes(trailer, "transaction trailer")
    header = build_command_header(command, sum(len(value) for value in payloads))
    return {
        "format": "sony-infocarry-legacy-oracle-transaction-v1",
        "label": label,
        "command": f"0x{command:04x}",
        "command_header_hex": header.hex(),
        "command_header_sha256": hashlib.sha256(header).hexdigest(),
        "payload_length": sum(len(value) for value in payloads),
        "payload_sha256": hashlib.sha256(b"".join(payloads)).hexdigest(),
        "range_count": len(payloads),
        "range_lengths": [len(value) for value in payloads],
        "range_sha256": [hashlib.sha256(value).hexdigest() for value in payloads],
        "variable_n": variable_n,
        "variable_m": variable_m,
        "trailer_length": len(trailer_bytes),
        "trailer_sha256": hashlib.sha256(trailer_bytes).hexdigest(),
        "completion_status": completion_status,
    }


def compare_transactions(
    left_ranges: Sequence[bytes | bytearray | memoryview],
    right_ranges: Sequence[bytes | bytearray | memoryview],
    *,
    left_label: str = "legacy transaction",
    right_label: str = "modern transaction",
    command: int = 0x101B,
    header_annotations: Iterable[DifferenceAnnotation | Mapping[str, Any]] = (),
    range_annotations: Mapping[int, Iterable[DifferenceAnnotation | Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Compare command framing and each range while retaining raw differences.

    ``range_annotations`` uses zero-based range indexes.  An annotation is
    applied only to that range's local byte offsets; it cannot hide a raw
    difference or explain a neighboring range.
    """

    left = tuple(_coerce_bytes(value, f"left range {index + 1}") for index, value in enumerate(left_ranges))
    right = tuple(_coerce_bytes(value, f"right range {index + 1}") for index, value in enumerate(right_ranges))
    left_inventory = transaction_inventory(left, label=left_label, command=command)
    right_inventory = transaction_inventory(right, label=right_label, command=command)
    header_difference = compare_bytes(
        bytes.fromhex(left_inventory["command_header_hex"]),
        bytes.fromhex(right_inventory["command_header_hex"]),
        left_label=f"{left_label} header",
        right_label=f"{right_label} header",
        annotations=header_annotations,
    )
    if range_annotations is not None and not isinstance(range_annotations, Mapping):
        raise DifferentialError("range_annotations must be a mapping")
    range_differences = []
    for index in range(max(len(left), len(right))):
        left_value = left[index] if index < len(left) else b""
        right_value = right[index] if index < len(right) else b""
        range_differences.append(
            compare_bytes(
                left_value,
                right_value,
                left_label=f"{left_label} range {index + 1}",
                right_label=f"{right_label} range {index + 1}",
                annotations=(range_annotations or {}).get(index, ()),
            ).to_dict()
        )
    classifications = [header_difference.classification]
    classifications.extend(
        DifferentialClassification(item["classification"])
        for item in range_differences
    )
    range_count_mismatch = len(left) != len(right)
    if range_count_mismatch or any(item == DifferentialClassification.UNEXPLAINED for item in classifications):
        aggregate_classification = DifferentialClassification.UNEXPLAINED
    elif all(item == DifferentialClassification.EXACT_MATCH for item in classifications):
        aggregate_classification = DifferentialClassification.EXACT_MATCH
    elif any(item == DifferentialClassification.EXPLAINED_VOLATILE_FIELD for item in classifications):
        aggregate_classification = DifferentialClassification.EXPLAINED_VOLATILE_FIELD
    else:
        aggregate_classification = DifferentialClassification.EXPLAINED_DETERMINISTIC_DIFFERENCE
    return {
        "format": "sony-infocarry-legacy-oracle-transaction-comparison-v1",
        "classification": aggregate_classification.value,
        "left": left_inventory,
        "right": right_inventory,
        "range_count_difference": len(left) - len(right),
        "header": header_difference.to_dict(),
        "ranges": range_differences,
    }


def canonical_json(data: Mapping[str, Any]) -> str:
    """Serialize a report deterministically for committed derived artifacts."""

    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_summary_classifications(value: Any, path: str = "raw_differential_summary") -> bool:
    """Validate classification labels and explicit non-comparability reasons."""

    found_not_comparable = False
    if isinstance(value, Mapping):
        if "classification" in value:
            try:
                classification = DifferentialClassification(value["classification"])
            except (TypeError, ValueError) as exc:
                raise DifferentialError(f"invalid classification at {path}.classification") from exc
            if classification is DifferentialClassification.NOT_COMPARABLE:
                reason = value.get("reason")
                if not isinstance(reason, str) or not reason.strip():
                    raise DifferentialError(f"NOT_COMPARABLE at {path} requires a non-empty reason")
                found_not_comparable = True
            if classification is DifferentialClassification.EXACT_MATCH:
                raw_count = value.get("raw_range_count")
                raw_bytes = value.get("raw_differing_byte_count")
                if raw_count is not None and raw_count != 0:
                    raise DifferentialError(f"EXACT_MATCH at {path} cannot retain raw differing ranges")
                if raw_bytes is not None and raw_bytes != 0:
                    raise DifferentialError(f"EXACT_MATCH at {path} cannot retain raw differing bytes")
        for key, nested in value.items():
            if key == "range_classifications":
                if not isinstance(nested, Sequence) or isinstance(nested, (str, bytes, bytearray)):
                    raise DifferentialError(f"{path}.range_classifications must be a sequence")
                for index, item in enumerate(nested):
                    try:
                        DifferentialClassification(item)
                    except (TypeError, ValueError) as exc:
                        raise DifferentialError(
                            f"invalid classification at {path}.range_classifications[{index}]"
                        ) from exc
                continue
            if _validate_summary_classifications(nested, f"{path}.{key}"):
                found_not_comparable = True
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, nested in enumerate(value):
            if _validate_summary_classifications(nested, f"{path}[{index}]"):
                found_not_comparable = True
    return found_not_comparable


def validate_corpus_metadata(
    metadata: Mapping[str, Any],
    representations: Mapping[str, bytes | bytearray | memoryview] | None = None,
) -> dict[str, Any]:
    """Validate a sanitized corpus row and optional representation bytes.

    The committed row contains only hashes, lengths, provenance, and derived
    comparison facts.  ``representations`` is an optional caller-side mapping
    used when an external artifact is available; it is never serialized by
    this validator.
    """

    if not isinstance(metadata, Mapping):
        raise DifferentialError("corpus metadata must be a mapping")
    if metadata.get("format") != CORPUS_FORMAT:
        raise DifferentialError("corpus metadata format is invalid")
    for key in (
        "fixture_id",
        "provenance",
        "logical_input_shape",
        "representations",
        "expected_volatile_fields",
        "raw_differential_summary",
        "interpretation_status",
    ):
        if key not in metadata:
            raise DifferentialError(f"corpus metadata is missing {key!r}")
    if not isinstance(metadata["fixture_id"], str) or not metadata["fixture_id"]:
        raise DifferentialError("fixture_id must be a non-empty string")
    if not isinstance(metadata["provenance"], Mapping):
        raise DifferentialError("provenance must be a mapping")
    if not isinstance(metadata["logical_input_shape"], Mapping):
        raise DifferentialError("logical_input_shape must be a mapping")
    if not isinstance(metadata["interpretation_status"], str) or not metadata["interpretation_status"]:
        raise DifferentialError("interpretation_status must be a non-empty string")
    rows = metadata["representations"]
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise DifferentialError("representations must be a sequence")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise DifferentialError("each corpus representation must be a mapping")
        identifier = row.get("id")
        availability = row.get("availability")
        if identifier not in _REPRESENTATION_IDS or identifier in seen:
            raise DifferentialError("corpus representation id is missing, unknown, or duplicated")
        seen.add(identifier)
        if availability not in {"available", "unavailable"}:
            raise DifferentialError(f"invalid availability for {identifier}")
        declared_length = row.get("length")
        declared_hash = row.get("sha256")
        if availability == "available":
            if isinstance(declared_length, bool) or not isinstance(declared_length, int) or declared_length < 0:
                raise DifferentialError(f"available {identifier} length is invalid")
            if not isinstance(declared_hash, str) or len(declared_hash) != 64:
                raise DifferentialError(f"available {identifier} SHA-256 is invalid")
            try:
                int(declared_hash, 16)
            except ValueError as exc:
                raise DifferentialError(f"available {identifier} SHA-256 is invalid") from exc
        elif declared_length is not None or declared_hash is not None:
            raise DifferentialError(f"unavailable {identifier} must not claim bytes or a hash")
        if representations is not None and identifier in representations:
            actual = _coerce_bytes(representations[identifier], identifier)
            if availability != "available":
                raise DifferentialError(f"external bytes were supplied for unavailable {identifier}")
            if len(actual) != declared_length or hashlib.sha256(actual).hexdigest() != declared_hash:
                raise DifferentialError(f"fixture/hash mismatch for {identifier}")
    if seen != _REPRESENTATION_IDS:
        missing = ", ".join(sorted(_REPRESENTATION_IDS - seen))
        raise DifferentialError(f"corpus metadata is missing representations: {missing}")
    if not isinstance(metadata["expected_volatile_fields"], Sequence) or isinstance(metadata["expected_volatile_fields"], (str, bytes, bytearray)):
        raise DifferentialError("expected_volatile_fields must be a sequence")
    summary = metadata["raw_differential_summary"]
    if not isinstance(summary, Mapping):
        raise DifferentialError("raw_differential_summary must be a mapping")
    if not isinstance(summary.get("candidate"), Mapping):
        raise DifferentialError("raw_differential_summary must contain a candidate mapping")
    if not isinstance(summary.get("transaction"), Mapping):
        raise DifferentialError("raw_differential_summary must contain a transaction mapping")
    has_not_comparable = _validate_summary_classifications(summary)
    if has_not_comparable and "NOT_COMPARABLE" not in metadata["interpretation_status"]:
        raise DifferentialError(
            "interpretation_status must explicitly retain a NOT_COMPARABLE result"
        )
    return json.loads(canonical_json(metadata))


__all__ = [
    "BackupRecord",
    "ByteDifferential",
    "CORPUS_FORMAT",
    "ClassifiedDifference",
    "DifferenceAnnotation",
    "DifferenceRange",
    "DifferentialClassification",
    "DifferentialError",
    "backup_inventory",
    "canonical_json",
    "compare_backup_structure",
    "compare_bytes",
    "compare_transactions",
    "transaction_inventory",
    "validate_corpus_metadata",
]
