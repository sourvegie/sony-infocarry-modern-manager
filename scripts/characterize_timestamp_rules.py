#!/usr/bin/env python3
"""Read-only comparison of native before/after backup timestamp fields.

This probe is deliberately an analysis tool.  It reads preserved backup blobs,
emits hashes and parsed metadata, and never constructs or transmits a device
transaction.  It does not copy raw evidence into the repository and it never
uses a historical timestamp map as an input to a candidate builder.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from infocarry.backup_format import (  # noqa: E402
    BackupFormatError,
    ParsedBackupBlob,
    BackupRecord,
    parse_backup_blob,
    timestamp_utc_iso8601,
)


@dataclass(frozen=True)
class CaseSpec:
    name: str
    before: Path
    after: Path
    mode: str
    target_path: str | None = None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex32(value: int) -> str:
    return f"0x{value:08x}"


def _path(parsed: ParsedBackupBlob, record: BackupRecord) -> str | None:
    parts = parsed.paths.get(record.offset)
    if parts is None:
        return None
    base = "\\".join(parts)
    return f"{base}.{record.extension}" if record.extension else base


def _parent_path(parsed: ParsedBackupBlob, record: BackupRecord) -> str | None:
    parts = parsed.paths.get(record.offset)
    if parts is None or len(parts) < 2:
        return None
    return "\\".join(parts[:-1])


def _identity(parsed: ParsedBackupBlob, record: BackupRecord) -> str:
    logical = _path(parsed, record)
    if logical is not None:
        return logical
    return f"<unreachable:{record.name}@0x{record.offset:08x}>"


def _record_index(parsed: ParsedBackupBlob, record: BackupRecord) -> int:
    return (record.offset - parsed.header.metadata_start) // parsed.header.record_size


def _timestamp_bytes(record: BackupRecord) -> str:
    raw = bytes.fromhex(record.raw_hex)
    return raw[0x0C:0x10].hex()


def _record_fields(record: BackupRecord) -> dict[str, Any]:
    return {
        "flag_hex": f"0x{record.flag:02x}",
        "kind": record.kind,
        "extension": record.extension,
        "name": record.name,
        "field_04_be32": _hex32(record.field_04_be32),
        "field_08_be32": _hex32(record.field_08_be32),
        "field_10_be32": _hex32(record.field_10_be32),
        "field_14_be32": _hex32(record.field_14_be32),
    }


def _payload_info(parsed: ParsedBackupBlob, record: BackupRecord) -> dict[str, Any] | None:
    if record.kind != "file" or record.offset not in parsed.paths:
        return None
    prefix, payload = parsed.payload_parts(record)
    return {
        "prefix_length": len(prefix),
        "payload_length": len(payload),
        "prefix_sha256": _sha256(prefix),
        "payload_sha256": _sha256(payload),
    }


def _neighbor_timestamps(
    records: Iterable[BackupRecord], index: int
) -> dict[str, str | None]:
    values = tuple(records)
    result: dict[str, str | None] = {}
    for label, position in (("previous", index - 1), ("next", index + 1)):
        if 0 <= position < len(values):
            result[label] = _hex32(values[position].timestamp_be32)
        else:
            result[label] = None
    return result


def _field_differences(before: BackupRecord, after: BackupRecord) -> dict[str, list[Any]]:
    pairs = {
        "flag": (before.flag, after.flag),
        "extension": (before.extension, after.extension),
        "field_04_be32": (before.field_04_be32, after.field_04_be32),
        "field_08_be32": (before.field_08_be32, after.field_08_be32),
        "field_10_be32": (before.field_10_be32, after.field_10_be32),
        "field_14_be32": (before.field_14_be32, after.field_14_be32),
        "name": (before.name, after.name),
    }
    return {
        key: [left, right]
        for key, (left, right) in pairs.items()
        if left != right
    }


def _row(
    before_parsed: ParsedBackupBlob,
    before: BackupRecord,
    after_parsed: ParsedBackupBlob,
    after: BackupRecord,
) -> dict[str, Any]:
    before_index = _record_index(before_parsed, before)
    after_index = _record_index(after_parsed, after)
    before_ts = before.timestamp_be32
    after_ts = after.timestamp_be32
    before_payload = _payload_info(before_parsed, before)
    after_payload = _payload_info(after_parsed, after)
    payload_equal = (
        before_payload is None
        and after_payload is None
        or before_payload is not None
        and after_payload is not None
        and before_payload["prefix_sha256"] == after_payload["prefix_sha256"]
        and before_payload["payload_sha256"] == after_payload["payload_sha256"]
    )
    return {
        "record_identity": _identity(before_parsed, before),
        "logical_path": _path(before_parsed, before),
        "parent_path": _parent_path(before_parsed, before),
        "baseline": {
            "record_index": before_index,
            "record_offset_hex": f"0x{before.offset:08x}",
            "timestamp_bytes_hex": _timestamp_bytes(before),
            "timestamp_be32": _hex32(before_ts),
            "timestamp_utc": timestamp_utc_iso8601(before_ts),
            "fields": _record_fields(before),
            "payload": before_payload,
            "neighbor_timestamps_be32": _neighbor_timestamps(
                before_parsed.records, before_index
            ),
        },
        "post": {
            "record_index": after_index,
            "record_offset_hex": f"0x{after.offset:08x}",
            "timestamp_bytes_hex": _timestamp_bytes(after),
            "timestamp_be32": _hex32(after_ts),
            "timestamp_utc": timestamp_utc_iso8601(after_ts),
            "fields": _record_fields(after),
            "payload": after_payload,
            "neighbor_timestamps_be32": _neighbor_timestamps(
                after_parsed.records, after_index
            ),
        },
        "timestamp": {
            "equal": before_ts == after_ts,
            "equality_class": (
                "equal"
                if before_ts == after_ts
                else "changed_value"
            ),
            "delta_seconds": after_ts - before_ts,
            "byte_difference_count": sum(
                left != right
                for left, right in zip(
                    bytes.fromhex(_timestamp_bytes(before)),
                    bytes.fromhex(_timestamp_bytes(after)),
                )
            ),
        },
        "ordering": {
            "record_index_shift": after_index - before_index,
            "serialized_offset_shift": after.offset - before.offset,
            "content_offset_shift": after.field_04_be32 - before.field_04_be32,
            "content_length_shift": after.field_08_be32 - before.field_08_be32,
        },
        "payload_equal": payload_equal,
        "parsed_field_differences": _field_differences(before, after),
    }


def _changed_byte_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    before_values = [
        bytes.fromhex(row["baseline"]["timestamp_bytes_hex"]) for row in rows
    ]
    after_values = [bytes.fromhex(row["post"]["timestamp_bytes_hex"]) for row in rows]
    per_position = [
        sum(left[position] != right[position] for left, right in zip(before_values, after_values))
        for position in range(4)
    ]
    histogram = Counter(row["timestamp"]["byte_difference_count"] for row in rows)
    return {
        "matched_record_count": len(rows),
        "timestamp_changed_record_count": sum(
            not row["timestamp"]["equal"] for row in rows
        ),
        "timestamp_changed_byte_count": sum(per_position),
        "timestamp_equal_byte_count": len(rows) * 4 - sum(per_position),
        "timestamp_byte_difference_count_by_field_position": {
            f"+0x{position:02x}": count for position, count in enumerate(per_position)
        },
        "field_byte_difference_histogram": {
            str(key): histogram.get(key, 0) for key in range(5)
        },
        "full_four_byte_rewrite_count": histogram.get(4, 0),
        "partial_field_rewrite_count": sum(
            histogram.get(key, 0) for key in range(1, 4)
        ),
    }


def _timestamp_mapping(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(
        (
            row["baseline"]["timestamp_be32"],
            row["post"]["timestamp_be32"],
        )
        for row in rows
    )
    return [
        {
            "baseline_timestamp_be32": before,
            "baseline_timestamp_utc": timestamp_utc_iso8601(int(before, 16)),
            "post_timestamp_be32": after,
            "post_timestamp_utc": timestamp_utc_iso8601(int(after, 16)),
            "count": count,
        }
        for (before, after), count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _order_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    post_values = [row["post"]["timestamp_be32"] for row in rows]
    runs: list[dict[str, Any]] = []
    start = 0
    for index in range(1, len(post_values) + 1):
        if index < len(post_values) and post_values[index] == post_values[start]:
            continue
        value = post_values[start]
        runs.append({"timestamp_be32": value, "start_row": start, "end_row": index - 1, "count": index - start})
        start = index
    return {
        "post_timestamp_run_count": len(runs),
        "largest_post_timestamp_run": max((run["count"] for run in runs), default=0),
        "post_timestamp_runs": runs,
        "post_timestamp_counts": dict(Counter(post_values)),
    }


def _hypothesis_stats(
    rows: list[dict[str, Any]],
    before_parsed: ParsedBackupBlob,
    after_parsed: ParsedBackupBlob,
) -> dict[str, Any]:
    post_values = Counter(row["post"]["timestamp_be32"] for row in rows)
    root = next((record for record in after_parsed.records if record.name == "root"), None)
    root_ts = _hex32(root.timestamp_be32) if root is not None else None
    baseline_neighbor_values: set[str] = set()
    for row in rows:
        for value in row["baseline"]["neighbor_timestamps_be32"].values():
            if value is not None:
                baseline_neighbor_values.add(value)
    post_in_baseline_neighbors = sum(
        row["post"]["timestamp_be32"]
        in {
            value
            for value in row["baseline"]["neighbor_timestamps_be32"].values()
            if value is not None
        }
        for row in rows
    )
    return {
        "unique_post_timestamp_count": len(post_values),
        "post_timestamp_values": dict(post_values),
        "common_operation_timestamp_falsified": len(post_values) > 1,
        "root_timestamp_copy_falsified": len(post_values) > 1,
        "root_timestamp_is_one_of_post_values": root_ts in post_values,
        "post_root_timestamp_be32": root_ts,
        "post_timestamp_values_seen_in_any_baseline_neighbor": sorted(
            set(post_values) & baseline_neighbor_values
        ),
        "post_timestamp_matches_one_of_same_record_baseline_neighbors": post_in_baseline_neighbors,
        "preserved_timestamp_falsified": any(
            not row["timestamp"]["equal"] for row in rows
        ),
        "same_kind_post_timestamp_counts": {
            kind: dict(
                Counter(
                    row["post"]["timestamp_be32"]
                    for row in rows
                    if row["post"]["fields"]["kind"] == kind
                )
            )
            for kind in sorted({row["post"]["fields"]["kind"] for row in rows})
        },
    }


def _delete_rows(
    before: ParsedBackupBlob,
    after: ParsedBackupBlob,
    target_path: str,
) -> tuple[list[dict[str, Any]], int]:
    target_candidates = [
        record for record in before.records if _path(before, record) == target_path
    ]
    if len(target_candidates) != 1:
        raise ValueError(f"target path {target_path!r} resolved to {len(target_candidates)} records")
    target_index = _record_index(before, target_candidates[0])
    rows: list[dict[str, Any]] = []
    for record in before.records:
        if record is target_candidates[0]:
            continue
        source_index = _record_index(before, record)
        post_index = source_index - 1 if source_index > target_index else source_index
        if post_index < 0 or post_index >= len(after.records):
            raise ValueError(f"cannot map baseline record 0x{record.offset:x} to post index {post_index}")
        rows.append(_row(before, record, after, after.records[post_index]))
    return rows, target_candidates[0].offset


def _add_rows(
    before: ParsedBackupBlob,
    after: ParsedBackupBlob,
) -> list[dict[str, Any]]:
    before_by_path = {
        _path(before, record): record
        for record in before.records
        if _path(before, record) is not None
    }
    after_by_path = {
        _path(after, record): record
        for record in after.records
        if _path(after, record) is not None
    }
    rows: list[dict[str, Any]] = []
    for logical_path in sorted(set(before_by_path) & set(after_by_path)):
        rows.append(_row(before, before_by_path[logical_path], after, after_by_path[logical_path]))
    return rows


def _case_report(case: CaseSpec) -> dict[str, Any]:
    before_bytes = case.before.read_bytes()
    after_bytes = case.after.read_bytes()
    before = parse_backup_blob(before_bytes)
    after = parse_backup_blob(after_bytes)
    if case.mode == "delete":
        if not case.target_path:
            raise ValueError(f"delete case {case.name!r} requires --target-path")
        rows, target_offset = _delete_rows(before, after, case.target_path)
        before_paths_for_delta = {
            _path(before, record)
            for record in before.records
            if _path(before, record) is not None
        }
        after_paths_for_delta = {
            _path(after, record)
            for record in after.records
            if _path(after, record) is not None
        }
        removed_paths = sorted(before_paths_for_delta - after_paths_for_delta)
    elif case.mode == "add":
        rows = _add_rows(before, after)
        target_offset = None
        before_paths = {_path(before, record) for record in before.records if _path(before, record)}
        after_paths = {_path(after, record) for record in after.records if _path(after, record)}
        removed_paths = sorted(before_paths - after_paths)
    else:
        raise ValueError(f"unsupported case mode {case.mode!r}")
    before_paths = {_path(before, record) for record in before.records if _path(before, record)}
    after_paths = {_path(after, record) for record in after.records if _path(after, record)}
    added_paths = sorted(after_paths - before_paths)
    payload_mismatches = [
        row["record_identity"]
        for row in rows
        if not row["payload_equal"]
        and row["baseline"]["payload"] is not None
    ]
    report: dict[str, Any] = {
        "name": case.name,
        "mode": case.mode,
        "target_path": case.target_path,
        "target_record_offset_hex": (
            f"0x{target_offset:08x}" if target_offset is not None else None
        ),
        "evidence": {
            "before_path": str(case.before),
            "after_path": str(case.after),
            "before_bytes": len(before_bytes),
            "after_bytes": len(after_bytes),
            "before_sha256": _sha256(before_bytes),
            "after_sha256": _sha256(after_bytes),
        },
        "record_counts": {
            "before": len(before.records),
            "after": len(after.records),
            "delta": len(after.records) - len(before.records),
            "before_reachable": len(before.paths),
            "after_reachable": len(after.paths),
        },
        "path_delta": {
            "removed": removed_paths,
            "added": added_paths,
            "shared_reachable_count": len(before_paths & after_paths),
        },
        "header": {
            "before_checksum_be32": _hex32(before.header.stored_checksum),
            "after_checksum_be32": _hex32(after.header.stored_checksum),
            "checksum_changed": before.header.stored_checksum != after.header.stored_checksum,
        },
        "timestamp_statistics": _changed_byte_stats(rows),
        "timestamp_mapping": _timestamp_mapping(rows),
        "ordering_statistics": _order_stats(rows),
        "hypothesis_statistics": _hypothesis_stats(rows, before, after),
        "payload_mismatches": payload_mismatches,
        "rows": rows,
    }
    return report


def _parse_case(values: list[str], target_paths: Mapping[str, str]) -> CaseSpec:
    if len(values) != 4:
        raise ValueError("--case requires NAME BEFORE AFTER MODE")
    name, before, after, mode = values
    return CaseSpec(
        name=name,
        before=Path(before),
        after=Path(after),
        mode=mode,
        target_path=target_paths.get(name),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        nargs=4,
        action="append",
        metavar=("NAME", "BEFORE", "AFTER", "MODE"),
        required=True,
        help="one read-only pair; MODE is delete or add",
    )
    parser.add_argument(
        "--target-path",
        nargs=2,
        action="append",
        default=[],
        metavar=("NAME", "PATH"),
        help="logical target path for a delete case",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    target_paths = dict(args.target_path)
    try:
        cases = [_parse_case(values, target_paths) for values in args.case]
        reports = [_case_report(case) for case in cases]
        output = {
            "format": "infocarry-timestamp-rule-characterization-v1",
            "purpose": "Read-only native before/after timestamp comparison; no production candidate generation",
            "timestamp_field": {
                "record_offset": "0x0c..0x0f",
                "integer_endian": "big",
                "integer_interpretation": "Unix-style seconds rendered in UTC",
            },
            "cases": reports,
            "safety": {
                "usb_sessions": 0,
                "hardware_writes": 0,
                "real_0x101b": 0,
                "production_sender_calls": 0,
                "claims_consumed": 0,
                "sender_marker_mutations": 0,
                "installation_wide_lock_mutations": 0,
                "preserved_evidence_modified": False,
                "historical_timestamp_map_used_as_input": False,
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, BackupFormatError, ValueError) as exc:
        print(f"timestamp characterization refused: {exc}", file=sys.stderr)
        return 2
    print(args.output)
    print(f"cases={len(reports)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
