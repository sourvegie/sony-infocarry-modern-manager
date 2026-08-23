"""Offline, read-only reports for preserved InfoCarry manager fixtures.

The report intentionally keeps the encoded ``VICDATA.bin`` in memory only.
It verifies the observed XOR layer, parses the backup and sidecars, and
records path correlations without exporting any device content.
"""

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .backup_format import (
    BackupFormatError,
    calculate_backup_checksum,
    parse_backup_blob,
)
from .order_control import OrderControlFormatError, parse_order_control
from .viclv import VicLvFormatError, parse_viclv
from .vicmem import (
    VicMemCategoryRecordView,
    VicMemFormatError,
    VicMemTailRecordView,
    parse_vicmem,
)
from .vicdata import OBSERVED_VICDATA_XOR_KEY, xor_vicdata


FIXTURE_REPORT_FORMAT = "infocarry-fixture-report-v1"
MAX_FIXTURE_FILE_BYTES = 32 * 1024 * 1024
REQUIRED_RELATIVE_FILES = (
    Path("Backup") / "VICDATA.bin",
    Path("Memo") / "VICMEM.bin",
    Path("Memo") / "VICLV.bin",
)


class FixtureReportError(ValueError):
    """Raised when a fixture cannot be safely analyzed."""


def _inside(root: Path, path: Path) -> Path:
    """Resolve an input path and reject paths escaping the fixture root."""

    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise FixtureReportError(f"fixture path is not inside {root}: {path}") from exc
    if not resolved.is_file():
        raise FixtureReportError(f"fixture path is not a regular file: {resolved}")
    return resolved


def _read_fixture_file(root: Path, relative: Path) -> Tuple[bytes, Dict[str, Any]]:
    path = _inside(root, root / relative)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise FixtureReportError(f"could not stat fixture file {path}: {exc}") from exc
    if size > MAX_FIXTURE_FILE_BYTES:
        raise FixtureReportError(
            f"fixture file {relative.as_posix()} is {size} bytes; refusing files "
            f"larger than {MAX_FIXTURE_FILE_BYTES} bytes"
        )
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise FixtureReportError(f"could not read fixture file {path}: {exc}") from exc
    if len(data) != size:
        raise FixtureReportError(f"fixture file changed while reading: {path}")
    return data, {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _find_order_file(root: Path) -> Path:
    matches = sorted(
        path
        for path in root.rglob("order.vnw")
        if path.is_file() and not path.is_symlink()
    )
    if not matches:
        raise FixtureReportError("could not find order.vnw below the fixture root")
    if len(matches) > 1:
        names = ", ".join(str(path.relative_to(root)) for path in matches)
        raise FixtureReportError(f"found more than one order.vnw: {names}")
    return _inside(root, matches[0])


def _relative_name(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _normalize_relative_path(path: str) -> str:
    value = path.replace("/", "\\")
    while value.startswith("\\"):
        value = value[1:]
    if value == "root":
        return ""
    if value.startswith("root\\"):
        return value[5:]
    return value


def _record_path(record_path: Sequence[str], extension: str) -> str:
    components = list(record_path)
    if components and components[0] == "root":
        components = components[1:]
    if not components:
        return ""
    if extension:
        components[-1] = f"{components[-1]}.{extension}"
    return "\\".join(components)


def _backup_path_index(parsed: Any) -> Dict[str, int]:
    index: Dict[str, int] = {}
    for record in parsed.records:
        path = parsed.paths.get(record.offset)
        if path is None:
            continue
        index[_normalize_relative_path(_record_path(path, record.extension))] = record.offset
    return index


def _offset_or_none(index: Mapping[str, int], path: str) -> Optional[str]:
    offset = index.get(_normalize_relative_path(path))
    return None if offset is None else f"0x{offset:08x}"


def _correlations(
    source: str,
    entries: Iterable[Tuple[int, Optional[int], str]],
    index: Mapping[str, int],
) -> List[Dict[str, Any]]:
    result = []
    for ordinal, category, path in entries:
        result.append(
            {
                "source": source,
                "ordinal": ordinal,
                **({"category": category} if category is not None else {}),
                "path": path,
                "backup_record_offset": _offset_or_none(index, path),
            }
        )
    return result


def _vicmem_details(vicmem: Any) -> Tuple[Dict[str, Any], List[Tuple[int, Optional[int], str]]]:
    categories: List[Dict[str, Any]] = []
    correlation_entries: List[Tuple[int, Optional[int], str]] = []
    for category, section in enumerate(vicmem.sections):
        if section is None:
            continue
        paths = []
        for ordinal, raw in enumerate(section.records, start=1):
            view = VicMemCategoryRecordView(raw)
            path = view.decode_path("cp932")
            paths.append(
                {
                    "ordinal": ordinal,
                    "path": path,
                    "path_bytes_hex": view.path_bytes.hex(),
                    "path_terminated": view.path_is_terminated,
                }
            )
            correlation_entries.append((ordinal, category, path))
        categories.append(
            {
                "category": category,
                "count": section.count,
                "auxiliary_hex": section.auxiliary.hex(),
                "paths": paths,
            }
        )

    tail_details = None
    if vicmem.tail is not None:
        tail_records = []
        for ordinal, raw in enumerate(vicmem.tail.records, start=1):
            view = VicMemTailRecordView(raw)
            path = view.decode_path("cp932")
            tail_records.append(
                {
                    "ordinal": ordinal,
                    "path": path,
                    "path_bytes_hex": view.path_bytes.hex(),
                    "path_terminated": view.path_is_terminated,
                    "field_3": view.field_3,
                    "rendered_line_position": view.rendered_line_position,
                }
            )
            correlation_entries.append((ordinal, None, path))
        tail_details = {"count": vicmem.tail.count, "records": tail_records}

    return (
        {
            "header": {
                "reserved_hex": vicmem.header.reserved.hex(),
                "version": vicmem.header.version,
                "section_mask": vicmem.header.section_mask,
                "section_mask_hex": f"0x{vicmem.header.section_mask:08x}",
            },
            "categories": categories,
            "tail": tail_details,
        },
        correlation_entries,
    )


def _backup_details(
    encoded: bytes, decoded: bytes, parsed: Any, xor_key: int
) -> Dict[str, Any]:
    flags = Counter(f"0x{record.flag:02x}" for record in parsed.records)
    extensions = Counter(record.extension or "<directory>" for record in parsed.records)
    field_14 = Counter(f"0x{record.field_14_be32:08x}" for record in parsed.records)
    prefix_lengths = Counter()
    file_intervals = []
    for record in parsed.records:
        if record.kind != "file" or record.offset not in parsed.paths:
            continue
        prefix = record.payload_prefix_length
        if prefix is not None:
            prefix_lengths[str(prefix)] += 1
        start = parsed.header.content_start + record.field_04_be32
        end = start + (prefix or 0) + record.field_08_be32
        file_intervals.append((start, end))
    file_intervals.sort()
    non_overlapping = all(
        left[1] <= right[0] for left, right in zip(file_intervals, file_intervals[1:])
    )
    return {
        "encoded_sha256": hashlib.sha256(encoded).hexdigest(),
        "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
        "xor_key": f"0x{xor_key:02x}",
        "magic_verified": decoded.startswith(b"infoCarry 2.00"),
        "checksum_verified": calculate_backup_checksum(decoded)
        == parsed.header.stored_checksum,
        "header": parsed.header.to_dict(),
        "summary": {
            "records": len(parsed.records),
            "reachable_records": len(parsed.paths),
            "directories": sum(
                record.kind == "directory" and record.offset in parsed.paths
                for record in parsed.records
            ),
            "files": sum(
                record.kind == "file" and record.offset in parsed.paths
                for record in parsed.records
            ),
            "parent_records": len(parsed.parent_record_offsets),
            "orphan_records": len(parsed.orphan_record_offsets),
            "flags": dict(sorted(flags.items())),
            "extensions": dict(sorted(extensions.items())),
            "field_14": dict(sorted(field_14.items())),
            "payload_prefix_lengths": dict(sorted(prefix_lengths.items(), key=lambda item: int(item[0]))),
            "file_payloads_non_overlapping": non_overlapping,
        },
    }


def analyze_fixture(fixture_root: Path, *, xor_key: int = OBSERVED_VICDATA_XOR_KEY) -> Dict[str, Any]:
    """Analyze a preserved fixture without writing or accessing USB hardware."""

    root = fixture_root.expanduser().resolve()
    if not root.is_dir():
        raise FixtureReportError(f"fixture root is not a directory: {root}")

    files: Dict[str, Dict[str, Any]] = {}
    raw: Dict[str, bytes] = {}
    for relative in REQUIRED_RELATIVE_FILES:
        data, details = _read_fixture_file(root, relative)
        key = relative.as_posix()
        raw[key] = data
        files[key] = details

    order_path = _find_order_file(root)
    order_relative = _relative_name(root, order_path)
    try:
        order_data = order_path.read_bytes()
    except OSError as exc:
        raise FixtureReportError(f"could not read fixture file {order_path}: {exc}") from exc
    if len(order_data) > MAX_FIXTURE_FILE_BYTES:
        raise FixtureReportError(f"fixture file {order_relative} exceeds the safety size limit")
    files[order_relative] = {
        "bytes": len(order_data),
        "sha256": hashlib.sha256(order_data).hexdigest(),
    }

    try:
        decoded = xor_vicdata(raw["Backup/VICDATA.bin"], key=xor_key)
    except BackupFormatError as exc:
        raise FixtureReportError(f"fixture validation failed: {exc}") from exc
    try:
        parsed = parse_backup_blob(decoded)
        vicmem = parse_vicmem(raw["Memo/VICMEM.bin"])
        viclv = parse_viclv(raw["Memo/VICLV.bin"])
        order = parse_order_control(order_data)
    except (BackupFormatError, VicMemFormatError, VicLvFormatError, OrderControlFormatError) as exc:
        raise FixtureReportError(f"fixture validation failed: {exc}") from exc

    round_trip = {
        "VICMEM.bin": vicmem.to_bytes() == raw["Memo/VICMEM.bin"],
        "VICLV.bin": viclv.to_bytes() == raw["Memo/VICLV.bin"],
        "order.vnw": order.to_bytes() == order_data,
    }
    if not all(round_trip.values()):
        failed = ", ".join(name for name, exact in round_trip.items() if not exact)
        raise FixtureReportError(f"lossless sidecar round-trip failed: {failed}")

    backup_index = _backup_path_index(parsed)
    vicmem_details, vicmem_entries = _vicmem_details(vicmem)
    viclv_entries = [
        (ordinal, entry.category, entry.path_cp932)
        for ordinal, entry in enumerate(viclv.entries, start=1)
    ]
    order_entries = [
        (ordinal, None, path)
        for ordinal, path in enumerate(order.decode_entries("cp932"), start=1)
    ]

    report = {
        "format": FIXTURE_REPORT_FORMAT,
        "fixture_root": str(root),
        "files": dict(sorted(files.items())),
        "vicdata": _backup_details(
            raw["Backup/VICDATA.bin"], decoded, parsed, xor_key
        ),
        "sidecars": {
            "VICMEM.bin": {
                "sha256": files["Memo/VICMEM.bin"]["sha256"],
                "round_trip_exact": round_trip["VICMEM.bin"],
                **vicmem_details,
            },
            "VICLV.bin": {
                "sha256": files["Memo/VICLV.bin"]["sha256"],
                "round_trip_exact": round_trip["VICLV.bin"],
                "header": {
                    "reserved_hex": viclv.header.reserved.hex(),
                    "version": viclv.header.version,
                },
                "entries": [
                    {"ordinal": ordinal, "category": category, "path": path}
                    for ordinal, category, path in viclv_entries
                ],
            },
            "order.vnw": {
                "path": order_relative,
                "sha256": files[order_relative]["sha256"],
                "round_trip_exact": round_trip["order.vnw"],
                "entries": [
                    {"ordinal": ordinal, "path": path}
                    for ordinal, _, path in order_entries
                ],
            },
        },
        "correlations": {
            "VICMEM": _correlations("VICMEM", vicmem_entries, backup_index),
            "VICLV": _correlations("VICLV", viclv_entries, backup_index),
            "order.vnw": _correlations("order.vnw", order_entries, backup_index),
        },
        "notes": [
            "VICDATA.bin was decoded in memory with the observed single-byte XOR key; no decoded copy is written.",
            "The XOR key is an observation from the preserved fixture, not a protocol guarantee for future fixtures.",
            "Unmatched sidecar paths are retained as unresolved correlations; they are not treated as missing data.",
        ],
    }
    return report


def write_fixture_report(
    fixture_root: Path,
    destination: Path,
    *,
    xor_key: int = OBSERVED_VICDATA_XOR_KEY,
) -> Dict[str, Any]:
    """Write a new directory containing only a deterministic JSON report."""

    report = analyze_fixture(fixture_root, xor_key=xor_key)
    output = destination.expanduser().resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise FixtureReportError(f"refusing to overwrite existing report path: {output}") from exc
    except OSError as exc:
        raise FixtureReportError(f"could not create report directory {output}: {exc}") from exc
    try:
        with (output / "manifest.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise FixtureReportError(f"could not write fixture report {output}: {exc}") from exc
    return report
