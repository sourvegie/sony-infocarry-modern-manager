"""Sanitized structural comparison for an offline deletion candidate.

The comparison accepts parsed dynamic models only.  It reports hashes,
paths, counts, pointer-field locations, and byte counts; it never emits raw
backup bytes or payload text.  Surviving record timestamp fields are the only
model bytes masked.  The header checksum is reported separately because it is
derived from those timestamp bytes and is not treated as an independent
structural allowance.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

from .backup_format import BackupFormatError, ParsedBackupBlob


class DeleteEvidenceComparisonError(ValueError):
    """Raised when parsed comparison inputs are incomplete or inconsistent."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _path(parsed: ParsedBackupBlob, record: Any) -> str | None:
    parts = parsed.paths.get(record.offset)
    if parts is None:
        return None
    name = "\\".join(parts)
    return f"{name}.{record.extension}" if record.extension else name


def _paths(parsed: ParsedBackupBlob) -> set[str]:
    values = {_path(parsed, record) for record in parsed.records if record.offset in parsed.paths}
    if None in values:
        raise DeleteEvidenceComparisonError("a reachable record has no portable path")
    return {value for value in values if value is not None}


def _payloads(parsed: ParsedBackupBlob) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for record in parsed.records:
        if record.kind != "file" or record.offset not in parsed.paths:
            continue
        path = _path(parsed, record)
        if path is None or path in result:
            raise DeleteEvidenceComparisonError("reachable file paths are missing or ambiguous")
        try:
            result[path] = parsed.payload_parts(record)[1]
        except BackupFormatError as exc:
            raise DeleteEvidenceComparisonError(
                f"reachable payload is malformed at 0x{record.offset:x}"
            ) from exc
    return result


def _masked_model(candidate: ParsedBackupBlob, post: ParsedBackupBlob) -> tuple[bytes, bytes]:
    if len(candidate.data) != len(post.data):
        return candidate.data, post.data
    left = bytearray(candidate.data)
    right = bytearray(post.data)
    for record in candidate.records:
        if record.offset + 16 > len(left):
            raise DeleteEvidenceComparisonError("candidate timestamp field is outside the model")
        for offset in range(0x0C, 0x10):
            left[record.offset + offset] = 0
            right[record.offset + offset] = 0
    # This is not a structural allowance.  It is a derived checksum whose
    # value changes when the legacy model regenerates record timestamps.
    for offset in range(0x1C, 0x20):
        left[offset] = 0
        right[offset] = 0
    return bytes(left), bytes(right)


def _record_field_name(index: int) -> str:
    for start, end, name in (
        (0x04, 0x08, "field_04_be32"),
        (0x08, 0x0C, "field_08_be32"),
        (0x10, 0x14, "field_10_be32"),
        (0x14, 0x18, "field_14_be32"),
    ):
        if start <= index < end:
            return name
    return f"record_byte_0x{index:02x}"


@dataclass(frozen=True)
class DeleteEvidenceComparison:
    """Derived, raw-byte-free result of one candidate/post comparison."""

    target_path: str
    baseline_blob_sha256: str
    candidate_blob_sha256: str
    post_blob_sha256: str
    baseline_record_count: int
    candidate_record_count: int
    post_record_count: int
    removed_paths: tuple[str, ...]
    added_paths: tuple[str, ...]
    surviving_payload_count: int
    candidate_post_payload_mismatches: tuple[str, ...]
    timestamp_changed_record_count: int
    timestamp_changed_byte_count: int
    header_checksum_changed: bool
    remaining_non_timestamp_byte_count: int
    remaining_non_timestamp_offsets_hex: tuple[str, ...]
    remaining_non_timestamp_fields: tuple[Mapping[str, str], ...]
    normalized_structural_match: bool
    source_candidate_paths_valid: bool
    candidate_post_paths_equal: bool

    @property
    def exact_supported_effect(self) -> bool:
        return (
            self.removed_paths == (self.target_path,)
            and not self.added_paths
            and self.candidate_record_count == self.baseline_record_count - 1
            and self.post_record_count == self.candidate_record_count
            and self.candidate_post_payload_mismatches == ()
            and self.candidate_post_paths_equal
            and self.normalized_structural_match
            and self.remaining_non_timestamp_byte_count == 0
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "format": "infocarry-delete-evidence-comparison-v1",
            "target_path": self.target_path,
            "baseline_blob_sha256": self.baseline_blob_sha256,
            "candidate_blob_sha256": self.candidate_blob_sha256,
            "post_blob_sha256": self.post_blob_sha256,
            "record_counts": {
                "baseline": self.baseline_record_count,
                "candidate": self.candidate_record_count,
                "post": self.post_record_count,
                "candidate_delta": self.candidate_record_count - self.baseline_record_count,
            },
            "path_delta": {
                "removed": list(self.removed_paths),
                "added": list(self.added_paths),
                "candidate_post_equal": self.candidate_post_paths_equal,
            },
            "payloads": {
                "surviving_count": self.surviving_payload_count,
                "candidate_post_mismatches": list(self.candidate_post_payload_mismatches),
            },
            "timestamp_normalization": {
                "changed_record_count": self.timestamp_changed_record_count,
                "changed_byte_count": self.timestamp_changed_byte_count,
                "masked_fields": "record bytes [0x0c:0x10] only",
                "header_checksum_changed": self.header_checksum_changed,
                "header_checksum_treatment": "reported as derived from timestamp changes, not a structural allowance",
            },
            "remaining_non_timestamp_differences": {
                "byte_count": self.remaining_non_timestamp_byte_count,
                "offsets_hex": list(self.remaining_non_timestamp_offsets_hex),
                "fields": [dict(item) for item in self.remaining_non_timestamp_fields],
            },
            "structural_result": {
                "source_candidate_paths_valid": self.source_candidate_paths_valid,
                "normalized_structural_match": self.normalized_structural_match,
                "exact_supported_effect": self.exact_supported_effect,
                "live_eligibility": "fail_closed" if not self.exact_supported_effect else "offline_only",
            },
        }


def compare_delete_evidence(
    baseline: ParsedBackupBlob,
    candidate: ParsedBackupBlob,
    post: ParsedBackupBlob,
    *,
    target_path: str,
) -> DeleteEvidenceComparison:
    """Compare a modern candidate with a preserved post-operation model."""

    if not all(isinstance(value, ParsedBackupBlob) for value in (baseline, candidate, post)):
        raise DeleteEvidenceComparisonError("all comparison inputs must be parsed backup blobs")
    if not isinstance(target_path, str) or not target_path or "\x00" in target_path:
        raise DeleteEvidenceComparisonError("target path is invalid")

    baseline_paths = _paths(baseline)
    candidate_paths = _paths(candidate)
    post_paths = _paths(post)
    candidate_payloads = _payloads(candidate)
    post_payloads = _payloads(post)
    mismatches = tuple(
        sorted(path for path in set(candidate_payloads) & set(post_payloads) if candidate_payloads[path] != post_payloads[path])
    )

    if len(candidate.records) != len(post.records) or len(candidate.data) != len(post.data):
        normalized_equal = False
        remaining_offsets: list[int] = []
    else:
        normalized_candidate, normalized_post = _masked_model(candidate, post)
        normalized_equal = normalized_candidate == normalized_post
        remaining_offsets = [
            offset
            for offset, (left, right) in enumerate(zip(normalized_candidate, normalized_post))
            if left != right
        ]

    timestamp_records = 0
    timestamp_bytes = 0
    fields: list[Mapping[str, str]] = []
    if len(candidate.records) == len(post.records):
        for left, right in zip(candidate.records, post.records):
            left_raw = bytes.fromhex(left.raw_hex)
            right_raw = bytes.fromhex(right.raw_hex)
            differences = [
                index for index, (a, b) in enumerate(zip(left_raw, right_raw)) if a != b
            ]
            timestamp_differences = [index for index in differences if 0x0C <= index < 0x10]
            timestamp_bytes += len(timestamp_differences)
            if timestamp_differences:
                timestamp_records += 1
            other = [index for index in differences if index not in timestamp_differences]
            if other:
                for index in other:
                    fields.append(
                        {
                            "record_offset_hex": f"0x{left.offset:08x}",
                            "field": _record_field_name(index),
                        }
                    )

    header_checksum_changed = candidate.data[0x1C:0x20] != post.data[0x1C:0x20]
    field_offsets = {
        item["record_offset_hex"] + ":" + item["field"] for item in fields
    }
    remaining_field_offsets = {
        f"0x{offset:08x}" for offset in remaining_offsets if not 0x1C <= offset < 0x20
    }
    # Keep only offsets that are represented by a record field; content-byte
    # differences remain visible as offsets but are not assigned a meaning.
    remaining_non_timestamp_offsets = tuple(sorted(remaining_field_offsets))
    remaining_fields = tuple(
        sorted(
            (item for item in fields if item["record_offset_hex"] + ":" + item["field"] in field_offsets),
            key=lambda item: (item["record_offset_hex"], item["field"]),
        )
    )
    remaining_count = len(
        [offset for offset in remaining_offsets if not 0x1C <= offset < 0x20]
    )
    return DeleteEvidenceComparison(
        target_path=target_path,
        baseline_blob_sha256=_sha256(baseline.data),
        candidate_blob_sha256=_sha256(candidate.data),
        post_blob_sha256=_sha256(post.data),
        baseline_record_count=len(baseline.records),
        candidate_record_count=len(candidate.records),
        post_record_count=len(post.records),
        removed_paths=tuple(sorted(baseline_paths - candidate_paths)),
        added_paths=tuple(sorted(candidate_paths - baseline_paths)),
        surviving_payload_count=len(set(candidate_payloads) & set(post_payloads)) - len(mismatches),
        candidate_post_payload_mismatches=mismatches,
        timestamp_changed_record_count=timestamp_records,
        timestamp_changed_byte_count=timestamp_bytes,
        header_checksum_changed=header_checksum_changed,
        remaining_non_timestamp_byte_count=remaining_count,
        remaining_non_timestamp_offsets_hex=remaining_non_timestamp_offsets,
        remaining_non_timestamp_fields=remaining_fields,
        normalized_structural_match=normalized_equal,
        source_candidate_paths_valid=(candidate_paths == baseline_paths - {target_path}),
        candidate_post_paths_equal=(candidate_paths == post_paths),
    )


__all__ = [
    "DeleteEvidenceComparison",
    "DeleteEvidenceComparisonError",
    "compare_delete_evidence",
]
