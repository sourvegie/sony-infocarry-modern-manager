"""Offline parser and lossless exporter for a raw InfoCarry backup blob."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .capture import CaptureError
from .view_wrapper import parse_text_view_wrapper


INFOCARRY_BLOB_MAGIC = b"infoCarry 2.00"
DIRECTORY_RECORD_FLAG = 0xD0
KNOWN_FILE_FLAGS = frozenset({0x20, 0xE0})
FILE_READ_STATES = {0x20: "read", 0xE0: "unread"}

# Semantic roles stated directly by the Japanese manual embedded in the live
# backup. These labels describe purpose, not the unavailable visual glyph.
DEVICE_SEQUENCE_MANUAL_MEANINGS = {
    "8123": "unread file icon",
    "8124": "read file icon",
    "8125": "mark 1 on unread file",
    "8126": "mark 1 on read file",
    "8127": "mark 2 on unread file",
    "8128": "mark 2 on read file",
    "8129": "mark 3 on unread file",
    "812a": "mark 3 on read file",
    "812b": "PC-acquired folder, closed",
    "812c": "PC-acquired folder, open",
    "812d": "device-created folder, closed",
    "812e": "device-created folder, open",
    "8133": "external-power indicator, component 1 of 3",
    "8134": "external-power indicator, component 2 of 3",
    "8135": "external-power indicator, component 3 of 3",
    "8136": "battery level 4 indicator, left component",
    "8137": "battery level 4 indicator, right component",
    "8138": "battery level 3 indicator, left component",
    "8139": "battery level 3 indicator, right component",
    "813a": "battery level 2 indicator, left component",
    "813b": "battery level 2 indicator, right component",
    "813c": "low-battery indicator, left component",
    "813d": "low-battery indicator, right component",
    "822c": "vertical line scrolling",
    "822f": "horizontal line scrolling",
    "8232": "vertical page scrolling",
    "8235": "horizontal page scrolling",
    "8236": "locked file icon",
    "8237": "temporarily unlocked file icon",
    "8238": "cancel or return control",
    "823d": "delete previous character control",
    "823f": "character-unit cursor movement mode",
    "8726": "input-mode selector, left component",
    "8727": "input-mode selector, right component",
    "8728": "candidate paging control A, left component",
    "8729": "candidate paging control A, right component",
    "8828": "candidate paging control B, left component",
    "8829": "candidate paging control B, right component",
}


class BackupFormatError(ValueError):
    """Raised when a raw blob violates a required structural invariant."""


@dataclass(frozen=True)
class BackupBlobHeader:
    version_major: int
    version_minor: int
    record_size: int
    checksum_start: int
    last_byte_offset: int
    stored_checksum: int
    optional_region_start: int
    optional_region_end: int
    metadata_start: int
    metadata_length: int
    content_start: int
    content_length: int
    total_length: int
    trailer_hex: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BackupRecord:
    offset: int
    flag: int
    extension: str
    field_04_be32: int
    field_08_be32: int
    timestamp_be32: int
    field_10_be32: int
    field_14_be32: int
    name: str
    raw_hex: str

    @property
    def kind(self) -> str:
        if self.flag == DIRECTORY_RECORD_FLAG:
            return "directory"
        if self.flag in KNOWN_FILE_FLAGS:
            return "file"
        return "unknown"

    @property
    def payload_prefix_length(self) -> Optional[int]:
        if self.kind != "file":
            return None
        units = (self.field_14_be32 >> 8) & 0xFF
        # The low 16 bits select the prefix length.  A manager-produced
        # backup fixture contains 0x00010200: it has the same 0x00000200
        # selector (a 0x20-byte prefix) plus a high state bit. Preserve that
        # bit in the raw field while using only the validated low-byte unit
        # count for payload slicing.
        if units not in (1, 2) or (self.field_14_be32 & 0xFFFF) != units << 8:
            return None
        return units * 16

    @property
    def read_state(self) -> Optional[str]:
        if self.kind != "file":
            return None
        return FILE_READ_STATES.get(self.flag)


@dataclass(frozen=True)
class ParsedBackupBlob:
    data: bytes
    header: BackupBlobHeader
    records: Sequence[BackupRecord]
    paths: Mapping[int, Tuple[str, ...]]
    parent_record_offsets: Sequence[int]
    orphan_record_offsets: Sequence[int]

    def record_at(self, offset: int) -> BackupRecord:
        index = (offset - self.header.metadata_start) // self.header.record_size
        if index < 0 or index >= len(self.records):
            raise BackupFormatError(f"record offset 0x{offset:x} is outside metadata")
        record = self.records[index]
        if record.offset != offset:
            raise BackupFormatError(f"record offset 0x{offset:x} is not aligned")
        return record

    def payload_parts(self, record: BackupRecord) -> Tuple[bytes, bytes]:
        prefix_length = record.payload_prefix_length
        if prefix_length is None:
            raise BackupFormatError(
                f"record 0x{record.offset:x} has unsupported payload prefix field "
                f"0x{record.field_14_be32:08x}"
            )
        start = self.header.content_start + record.field_04_be32
        payload_start = start + prefix_length
        payload_end = payload_start + record.field_08_be32
        if start < self.header.content_start or payload_end > (
            self.header.content_start + self.header.content_length
        ):
            raise BackupFormatError(
                f"record 0x{record.offset:x} payload exceeds the content region"
            )
        return self.data[start:payload_start], self.data[payload_start:payload_end]


def _be16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "big")


def _be32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "big")


def _decode_name(raw: bytes, offset: int) -> str:
    encoded = raw.split(b"\x00", 1)[0]
    try:
        return encoded.decode("cp932")
    except UnicodeDecodeError as exc:
        raise BackupFormatError(
            f"record 0x{offset:x} name is not valid CP932: {exc}"
        ) from exc


def _parse_record(raw: bytes, offset: int) -> BackupRecord:
    try:
        extension = raw[1:4].rstrip(b"\x00").decode("ascii")
    except UnicodeDecodeError as exc:
        raise BackupFormatError(
            f"record 0x{offset:x} extension is not ASCII"
        ) from exc
    return BackupRecord(
        offset=offset,
        flag=raw[0],
        extension=extension,
        field_04_be32=_be32(raw, 0x04),
        field_08_be32=_be32(raw, 0x08),
        timestamp_be32=_be32(raw, 0x0C),
        field_10_be32=_be32(raw, 0x10),
        field_14_be32=_be32(raw, 0x14),
        name=_decode_name(raw[0x18:0x40], offset),
        raw_hex=raw.hex(),
    )


def calculate_backup_checksum(data: bytes) -> int:
    """Reproduce the 32-bit checksum calculation in VicTwo.dll 0x10005550."""

    if len(data) < 0x40:
        raise BackupFormatError("backup blob is too short for checksum fields")
    record_size = _be16(data, 0x10)
    checksum_start = _be32(data, 0x14)
    optional_start = _be32(data, 0x20)
    optional_end = _be32(data, 0x24)
    metadata_start = _be32(data, 0x28)
    metadata_length = _be32(data, 0x2C)
    content_start = _be32(data, 0x30)
    total_length = _be32(data, 0x38)

    ranges = [(checksum_start, record_size), (content_start, total_length)]
    if optional_start and optional_end and optional_start < optional_end:
        ranges.insert(1, (optional_start, optional_end))
    for start, end in ranges:
        if start > end or start % 4 or end % 4 or end > len(data):
            raise BackupFormatError("checksum range is invalid or not 4-byte aligned")
    if (
        metadata_start % 4
        or metadata_length % record_size
        or metadata_start + metadata_length > len(data)
    ):
        raise BackupFormatError("metadata checksum range is invalid")

    checksum = 0
    for start, end in ranges:
        for offset in range(start, end, 4):
            checksum = (checksum + _be32(data, offset)) & 0xFFFFFFFF

    alignment_base = optional_start
    for offset in range(metadata_start, metadata_start + metadata_length, 4):
        value = _be32(data, offset)
        if (offset - alignment_base) % record_size == 0:
            flag = data[offset]
            field_10 = _be32(data, offset + 0x10)
            adjustment = ((flag & 0xC0) << 24) + field_10
            value = (value - adjustment) & 0xFFFFFFFF
        checksum = (checksum + value) & 0xFFFFFFFF
    return checksum


def parse_backup_blob(data: bytes) -> ParsedBackupBlob:
    """Parse only structure supported by static analysis and live invariants."""

    if len(data) < 0x44:
        raise BackupFormatError("backup blob is too short for its header and trailer")
    if data[: len(INFOCARRY_BLOB_MAGIC)] != INFOCARRY_BLOB_MAGIC:
        raise BackupFormatError("backup blob magic is not 'infoCarry 2.00'")
    header = BackupBlobHeader(
        version_major=data[0x0E],
        version_minor=data[0x0F],
        record_size=_be16(data, 0x10),
        checksum_start=_be32(data, 0x14),
        last_byte_offset=_be32(data, 0x18),
        stored_checksum=_be32(data, 0x1C),
        optional_region_start=_be32(data, 0x20),
        optional_region_end=_be32(data, 0x24),
        metadata_start=_be32(data, 0x28),
        metadata_length=_be32(data, 0x2C),
        content_start=_be32(data, 0x30),
        content_length=_be32(data, 0x34),
        total_length=_be32(data, 0x38),
        trailer_hex=data[-4:].hex(),
    )
    if (header.version_major, header.version_minor) != (1, 0):
        raise BackupFormatError(
            f"unsupported backup version {header.version_major}.{header.version_minor}"
        )
    if header.record_size != 64:
        raise BackupFormatError(f"unsupported record size {header.record_size}")
    if header.metadata_start != 0x40:
        raise BackupFormatError(
            f"unexpected metadata start 0x{header.metadata_start:x}"
        )
    if header.metadata_length == 0 or header.metadata_length % header.record_size:
        raise BackupFormatError("metadata length is empty or not record-aligned")
    if header.metadata_start + header.metadata_length != header.content_start:
        raise BackupFormatError("metadata and content regions are not contiguous")
    if header.content_start + header.content_length + 4 != header.total_length:
        raise BackupFormatError("header region lengths do not reproduce total length")
    if header.total_length != len(data):
        raise BackupFormatError(
            f"header declares {header.total_length} bytes; received {len(data)}"
        )
    if header.last_byte_offset != header.total_length - 1:
        raise BackupFormatError("header last-byte offset does not match total length")
    calculated_checksum = calculate_backup_checksum(data)
    if calculated_checksum != header.stored_checksum:
        raise BackupFormatError(
            f"backup checksum is 0x{calculated_checksum:08x}; header stores "
            f"0x{header.stored_checksum:08x}"
        )

    records = tuple(
        _parse_record(data[offset : offset + header.record_size], offset)
        for offset in range(
            header.metadata_start, header.content_start, header.record_size
        )
    )
    by_offset = {record.offset: record for record in records}
    root = by_offset.get(header.metadata_start)
    if root is None or root.kind != "directory" or root.name != "root":
        raise BackupFormatError("first metadata record is not the root directory")

    paths: Dict[int, Tuple[str, ...]] = {}
    active: set[int] = set()

    def walk(record: BackupRecord, components: Tuple[str, ...]) -> None:
        if record.offset in active:
            raise BackupFormatError(f"directory cycle reaches record 0x{record.offset:x}")
        if record.offset in paths:
            raise BackupFormatError(f"record 0x{record.offset:x} is linked more than once")
        paths[record.offset] = components
        if record.kind != "directory":
            return
        if record.field_08_be32 % header.record_size:
            raise BackupFormatError(
                f"directory 0x{record.offset:x} child table is not record-aligned"
            )
        child_start = record.field_04_be32 + header.record_size
        child_end = child_start + record.field_08_be32
        if (
            child_start < header.metadata_start
            or child_end > header.content_start
        ):
            raise BackupFormatError(
                f"directory 0x{record.offset:x} child table is outside metadata"
            )
        active.add(record.offset)
        for child_offset in range(child_start, child_end, header.record_size):
            child = by_offset.get(child_offset)
            if child is None:
                raise BackupFormatError(
                    f"directory 0x{record.offset:x} references missing record "
                    f"0x{child_offset:x}"
                )
            if child.kind == "directory" and child.name == "..":
                continue
            walk(child, components + (child.name,))
        active.remove(record.offset)

    walk(root, ("root",))

    parent_offsets = tuple(
        record.offset
        for record in records
        if record.kind == "directory" and record.name == ".."
    )
    orphan_offsets = tuple(
        record.offset
        for record in records
        if record.offset not in paths and record.offset not in parent_offsets
    )

    for record in records:
        if record.kind == "file" and record.offset in paths:
            prefix, payload = ParsedBackupBlob(
                data, header, records, paths, parent_offsets, orphan_offsets
            ).payload_parts(record)
            if record.extension == "bmp":
                if len(payload) < 54 or payload[:2] != b"BM":
                    raise BackupFormatError(
                        f"record 0x{record.offset:x} does not contain a BMP payload"
                    )
                declared = int.from_bytes(payload[2:6], "little")
                if declared != len(payload):
                    raise BackupFormatError(
                        f"record 0x{record.offset:x} BMP declares {declared} bytes; "
                        f"record contains {len(payload)}"
                    )

    return ParsedBackupBlob(
        data=data,
        header=header,
        records=records,
        paths=paths,
        parent_record_offsets=parent_offsets,
        orphan_record_offsets=orphan_offsets,
    )


def decode_cp932_with_escapes(data: bytes) -> Tuple[str, Sequence[int]]:
    """Decode valid CP932 and make each invalid source byte explicit."""

    output: List[str] = []
    invalid_offsets: List[int] = []
    position = 0
    while position < len(data):
        try:
            output.append(data[position:].decode("cp932"))
            break
        except UnicodeDecodeError as exc:
            valid_end = position + exc.start
            output.append(data[position:valid_end].decode("cp932"))
            bad_start = position + exc.start
            bad_end = position + max(exc.end, exc.start + 1)
            for index in range(bad_start, bad_end):
                output.append(f"\\x{data[index]:02x}")
                invalid_offsets.append(index)
            position = bad_end
    return "".join(output), tuple(invalid_offsets)


def timestamp_utc_iso8601(value: int) -> str:
    """Render the legacy 32-bit Unix-time field without applying local time."""

    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def find_unmapped_cp932_sequences(data: bytes) -> Sequence[Dict[str, Any]]:
    """Inventory likely two-byte device glyph codes rejected by CP932.

    The shipped manual repeatedly uses a CP932 lead-byte range followed by a
    byte below the normal CP932 trail-byte range.  Preserve both bytes as one
    *candidate* device sequence. Assign a semantic role only where the embedded
    manual states one directly; exact glyph shapes still require display/font
    correlation.
    """

    _, invalid_offsets = decode_cp932_with_escapes(data)
    sequences: List[Dict[str, Any]] = []
    for offset in invalid_offsets:
        lead = data[offset]
        if offset + 1 < len(data) and (
            0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC
        ):
            raw = data[offset : offset + 2]
        else:
            raw = data[offset : offset + 1]
        raw_hex = raw.hex()
        entry: Dict[str, Any] = {"offset": offset, "raw_hex": raw_hex}
        manual_meaning = DEVICE_SEQUENCE_MANUAL_MEANINGS.get(raw_hex)
        if manual_meaning is not None:
            entry["manual_meaning"] = manual_meaning
        sequences.append(entry)
    return tuple(sequences)


def _safe_component(offset: int, name: str) -> str:
    cleaned = name.replace("/", "_").replace("\\", "_").replace("\x00", "_")
    if cleaned in ("", ".", ".."):
        cleaned = "unnamed"
    return f"{offset:06x}_{cleaned}"


def _write_exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except OSError as exc:
        raise CaptureError(f"could not write exported file {path}: {exc}") from exc


class BackupExporter:
    """Extract standard payloads while retaining hashes and raw provenance."""

    def __init__(self, parsed: ParsedBackupBlob, source_sha256: str):
        self.parsed = parsed
        self.source_sha256 = source_sha256

    def export(
        self,
        destination: Path,
        *,
        selected_offsets: Optional[Sequence[int]] = None,
    ) -> Dict[str, Any]:
        """Export the complete backup or a selected reachable subtree.

        ``selected_offsets`` contains metadata offsets from ``ParsedBackupBlob``.
        Selecting a directory includes its reachable descendants; selecting a
        file includes only that file.  The default remains the historical full
        export behavior.
        """

        included_offsets = set(self.parsed.paths)
        selected_metadata: Optional[List[str]] = None
        if selected_offsets is not None:
            if not selected_offsets:
                raise BackupFormatError("at least one reachable record must be selected")
            selected_paths: List[Tuple[str, ...]] = []
            for raw_offset in selected_offsets:
                try:
                    offset = int(raw_offset)
                except (TypeError, ValueError) as exc:
                    raise BackupFormatError("selected record offsets must be integers") from exc
                if offset not in self.parsed.paths:
                    raise BackupFormatError(
                        f"selected record 0x{offset:x} is not reachable in the backup"
                    )
                selected_paths.append(self.parsed.paths[offset])
            included_offsets = {
                offset
                for offset, path_parts in self.parsed.paths.items()
                if any(
                    path_parts[: len(selected_path)] == selected_path
                    for selected_path in selected_paths
                )
            }
            selected_metadata = [f"0x{offset:08x}" for offset in sorted(included_offsets)]

        path = destination.expanduser().resolve()
        try:
            path.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise CaptureError(f"refusing to overwrite existing export path: {path}") from exc
        except OSError as exc:
            raise CaptureError(f"could not create export directory {path}: {exc}") from exc

        record_entries: List[Dict[str, Any]] = []
        unmapped_sequence_counts: Dict[str, int] = {}
        for record in self.parsed.records:
            if record.offset not in included_offsets:
                continue
            entry: Dict[str, Any] = {
                "record_offset": f"0x{record.offset:08x}",
                "kind": record.kind,
                "flag": f"0x{record.flag:02x}",
                "read_state": record.read_state,
                "extension": record.extension,
                "name": record.name,
                "field_04_be32": record.field_04_be32,
                "field_08_be32": record.field_08_be32,
                "timestamp_be32": record.timestamp_be32,
                "timestamp_unix_seconds": record.timestamp_be32,
                "timestamp_utc": timestamp_utc_iso8601(record.timestamp_be32),
                "field_10_be32": f"0x{record.field_10_be32:08x}",
                "field_14_be32": f"0x{record.field_14_be32:08x}",
                "raw_record_hex": record.raw_hex,
                "reachable_path": list(self.parsed.paths[record.offset])
                if record.offset in self.parsed.paths
                else None,
            }
            if record.kind == "file" and record.offset in self.parsed.paths:
                wrapper, payload = self.parsed.payload_parts(record)
                components = []
                current_path = self.parsed.paths[record.offset]
                directory_names = current_path[1:-1]
                # Resolve directory offsets from the unique reachable paths.
                for depth, directory_name in enumerate(directory_names, start=2):
                    prefix = current_path[:depth]
                    directory_offset = next(
                        item_offset
                        for item_offset, item_path in self.parsed.paths.items()
                        if item_path == prefix
                    )
                    components.append(_safe_component(directory_offset, directory_name))
                filename = _safe_component(record.offset, record.name)
                if record.extension:
                    filename += f".{record.extension}"
                relative = Path("native", *components, filename)
                _write_exclusive(path / relative, payload)
                entry.update(
                    {
                        "payload_prefix_hex": wrapper.hex(),
                        "payload_length": len(payload),
                        "payload_sha256": hashlib.sha256(payload).hexdigest(),
                        "native_path": relative.as_posix(),
                    }
                )
                if record.extension == "txt" and len(wrapper) == 0x20:
                    entry["payload_prefix_fields"] = parse_text_view_wrapper(
                        wrapper
                    ).to_dict()
                if record.extension == "txt":
                    decoded, invalid = decode_cp932_with_escapes(payload)
                    decoded_relative = Path(
                        "decoded-text", *components, filename
                    )
                    _write_exclusive(
                        path / decoded_relative, decoded.encode("utf-8")
                    )
                    entry["decoded_text_path"] = decoded_relative.as_posix()
                    entry["decoded_as"] = "CP932 with invalid bytes escaped as \\xNN"
                    entry["invalid_byte_offsets"] = list(invalid)
                    sequences = find_unmapped_cp932_sequences(payload)
                    entry["unmapped_cp932_sequences"] = list(sequences)
                    for sequence in sequences:
                        raw_hex = sequence["raw_hex"]
                        unmapped_sequence_counts[raw_hex] = (
                            unmapped_sequence_counts.get(raw_hex, 0) + 1
                        )
            record_entries.append(entry)

        manifest = {
            "format": "infocarry-export-v1",
            "source_blob_sha256": self.source_sha256,
            "header": self.parsed.header.to_dict(),
            "summary": {
                "records": len(record_entries),
                "reachable_records": len(included_offsets),
                "directories": sum(
                    record.kind == "directory" and record.offset in included_offsets
                    for record in self.parsed.records
                ),
                "files": sum(
                    record.kind == "file" and record.offset in included_offsets
                    for record in self.parsed.records
                ),
                "parent_records": sum(
                    offset in included_offsets for offset in self.parsed.parent_record_offsets
                ),
                "orphan_records": sum(
                    offset in included_offsets for offset in self.parsed.orphan_record_offsets
                ),
                "unmapped_cp932_sequence_occurrences": sum(
                    unmapped_sequence_counts.values()
                ),
                "unmapped_cp932_sequence_types": len(unmapped_sequence_counts),
                "private_sequence_occurrences": sum(
                    unmapped_sequence_counts.values()
                ),
                "private_sequence_types": len(unmapped_sequence_counts),
                "manual_mapped_private_sequence_types": sum(
                    raw_hex in DEVICE_SEQUENCE_MANUAL_MEANINGS
                    for raw_hex in unmapped_sequence_counts
                ),
                "unresolved_private_sequence_types": sum(
                    raw_hex not in DEVICE_SEQUENCE_MANUAL_MEANINGS
                    for raw_hex in unmapped_sequence_counts
                ),
            },
            "unmapped_cp932_sequence_catalog": [
                {
                    "raw_hex": raw_hex,
                    "occurrences": count,
                    **(
                        {"manual_meaning": DEVICE_SEQUENCE_MANUAL_MEANINGS[raw_hex]}
                        if raw_hex in DEVICE_SEQUENCE_MANUAL_MEANINGS
                        else {}
                    ),
                }
                for raw_hex, count in sorted(unmapped_sequence_counts.items())
            ],
            "records": record_entries,
        }
        if selected_metadata is not None:
            manifest["selection"] = {
                "selected_reachable_offsets": [
                    f"0x{int(raw_offset):08x}" for raw_offset in selected_offsets or ()
                ],
                "included_reachable_offsets": selected_metadata,
            }
        _write_exclusive(
            path / "manifest.json",
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
        return manifest


def load_complete_backup_bytes(directory: Path) -> Tuple[bytes, str]:
    """Load and hash the dynamic blob from a complete raw backup archive."""

    root = directory.expanduser().resolve()
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupFormatError(f"could not read backup manifest: {exc}") from exc
    if manifest.get("format") != "infocarry-raw-backup-v1":
        raise BackupFormatError("source is not an InfoCarry raw backup archive")
    if manifest.get("state") != "complete":
        raise BackupFormatError("refusing to export an incomplete backup archive")
    matches = [
        entry
        for entry in manifest.get("objects", [])
        if entry.get("kind") == "backup-blob"
    ]
    if len(matches) != 1:
        raise BackupFormatError("backup manifest must contain exactly one dynamic blob")
    entry = matches[0]
    blob_path = root / entry["filename"]
    try:
        data = blob_path.read_bytes()
    except OSError as exc:
        raise BackupFormatError(f"could not read backup blob: {exc}") from exc
    digest = hashlib.sha256(data).hexdigest()
    if digest != entry.get("sha256"):
        raise BackupFormatError("backup blob SHA-256 does not match its manifest")
    if len(data) != entry.get("received_length"):
        raise BackupFormatError("backup blob length does not match its manifest")
    return data, digest


def load_complete_backup(directory: Path) -> Tuple[ParsedBackupBlob, str]:
    """Load, validate, and parse the dynamic blob from a complete archive."""

    data, digest = load_complete_backup_bytes(directory)
    return parse_backup_blob(data), digest
