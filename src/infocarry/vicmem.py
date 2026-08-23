"""Lossless parser and builder for the legacy ``VICMEM.bin`` sidecar.

The layout is recovered from preserved ``VicTwo.dll`` loader, writer,
record-append, and record-consumer routines.  The path storage and two tail
fields are exposed through read-only views; all bytes remain available for
lossless round-trips.  This module performs no device I/O.
"""

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple


VICMEM_SIGNATURE = b"VICMEMOBIN"
VICMEM_VERSION = 1
VICMEM_HEADER_SIZE = 20
VICMEM_CATEGORY_COUNT = 4
VICMEM_TAIL_BIT = 4
VICMEM_CATEGORY_RECORD_SIZE = 0x104
VICMEM_TAIL_RECORD_SIZE = 0x10C
VICMEM_PATH_STORAGE_SIZE = VICMEM_CATEGORY_RECORD_SIZE
VICMEM_TAIL_FIELD_3_OFFSET = 0x104
VICMEM_TAIL_RENDERED_LINE_OFFSET = 0x108

# These capacities are the sizes allocated by the legacy manager: 0x1450 is
# twenty 0x104-byte category records, while the static tail buffer is 0x218
# bytes (two 0x10c-byte records).  Rejecting larger counts is a safety policy
# for malformed input; the old loader did not perform this bounds check.
VICMEM_CATEGORY_RECORD_CAPACITY = 0x1450 // VICMEM_CATEGORY_RECORD_SIZE
VICMEM_TAIL_RECORD_CAPACITY = 0x218 // VICMEM_TAIL_RECORD_SIZE


class VicMemFormatError(ValueError):
    """Raised when a ``VICMEM.bin`` image violates the recovered layout."""


def _path_prefix(storage: bytes) -> Tuple[bytes, bool]:
    terminator = storage.find(b"\x00")
    if terminator < 0:
        return storage, False
    return storage[:terminator], True


@dataclass(frozen=True)
class VicMemCategoryRecordView:
    """Partially decoded, byte-preserving view of a category record.

    Static constructors copy a NUL-terminated relative path into the record at
    offset zero. Bytes following the first NUL can contain untouched scratch
    data, so they are deliberately retained only through ``raw``.
    """

    raw: bytes

    def __post_init__(self) -> None:
        if len(self.raw) != VICMEM_CATEGORY_RECORD_SIZE:
            raise VicMemFormatError(
                f"VICMEM category record is {len(self.raw)} bytes; "
                f"expected {VICMEM_CATEGORY_RECORD_SIZE}"
            )

    @property
    def path_bytes(self) -> bytes:
        return _path_prefix(self.raw)[0]

    @property
    def path_is_terminated(self) -> bool:
        return _path_prefix(self.raw)[1]

    def decode_path(self, encoding: str, errors: str = "strict") -> str:
        """Decode the path using an explicitly selected legacy encoding."""

        return self.path_bytes.decode(encoding, errors)


@dataclass(frozen=True)
class VicMemTailRecordView:
    """Partially decoded, byte-preserving view of a category-16 record.

    The first 0x104 bytes are path storage. The final dwords are copied from
    command 0x001f bookmark-group offsets +0x08 and +0x0c. Controlled device
    observations identify the latter as the rendered-line position; the
    former remains semantically unresolved and is kept as ``field_3``.
    """

    raw: bytes

    def __post_init__(self) -> None:
        if len(self.raw) != VICMEM_TAIL_RECORD_SIZE:
            raise VicMemFormatError(
                f"VICMEM tail record is {len(self.raw)} bytes; "
                f"expected {VICMEM_TAIL_RECORD_SIZE}"
            )

    @property
    def path_storage(self) -> bytes:
        return self.raw[:VICMEM_PATH_STORAGE_SIZE]

    @property
    def path_bytes(self) -> bytes:
        return _path_prefix(self.path_storage)[0]

    @property
    def path_is_terminated(self) -> bool:
        return _path_prefix(self.path_storage)[1]

    def decode_path(self, encoding: str, errors: str = "strict") -> str:
        """Decode the path using an explicitly selected legacy encoding."""

        return self.path_bytes.decode(encoding, errors)

    @property
    def field_3(self) -> int:
        return int.from_bytes(
            self.raw[VICMEM_TAIL_FIELD_3_OFFSET:VICMEM_TAIL_RENDERED_LINE_OFFSET],
            "little",
        )

    @property
    def rendered_line_position(self) -> int:
        return int.from_bytes(
            self.raw[VICMEM_TAIL_RENDERED_LINE_OFFSET:VICMEM_TAIL_RECORD_SIZE],
            "little",
        )


@dataclass(frozen=True)
class VicMemHeader:
    """The 20-byte ``VICMEM.bin`` header.

    Bytes 10..11 are copied from the legacy signature buffer and are retained
    as a reserved field.  The low five mask bits select four category sections
    and one tail section; unknown high bits are preserved for forensic
    round-trips even though the legacy writer never sets them.
    """

    reserved: bytes = b"\x00\x00"
    version: int = VICMEM_VERSION
    section_mask: int = 0

    def __post_init__(self) -> None:
        if len(self.reserved) != 2:
            raise VicMemFormatError("VICMEM reserved header field must be 2 bytes")
        if not 0 <= self.version <= 0xFFFFFFFF:
            raise VicMemFormatError("VICMEM version must fit an unsigned 32-bit value")
        if not 0 <= self.section_mask <= 0xFFFFFFFF:
            raise VicMemFormatError("VICMEM section mask must fit an unsigned 32-bit value")

    def to_bytes(self) -> bytes:
        return (
            VICMEM_SIGNATURE
            + self.reserved
            + self.version.to_bytes(4, "little")
            + self.section_mask.to_bytes(4, "little")
        )


@dataclass(frozen=True)
class VicMemSection:
    """One selected category section.

    The legacy writer emits a little-endian record count, a four-byte
    auxiliary value, then ``count`` opaque 0x104-byte records.  The loader
    reads the auxiliary value into a temporary allocation slot before loading
    the records; its semantic role is therefore intentionally unnamed.
    """

    auxiliary: bytes
    records: Sequence[bytes]

    def __post_init__(self) -> None:
        if len(self.auxiliary) != 4:
            raise VicMemFormatError("VICMEM section auxiliary value must be 4 bytes")
        records = tuple(self.records)
        if len(records) > VICMEM_CATEGORY_RECORD_CAPACITY:
            raise VicMemFormatError(
                f"VICMEM category section has {len(records)} records; "
                f"capacity is {VICMEM_CATEGORY_RECORD_CAPACITY}"
            )
        for record in records:
            if len(record) != VICMEM_CATEGORY_RECORD_SIZE:
                raise VicMemFormatError(
                    f"VICMEM category record is {len(record)} bytes; "
                    f"expected {VICMEM_CATEGORY_RECORD_SIZE}"
                )
        object.__setattr__(self, "records", records)

    @property
    def count(self) -> int:
        return len(self.records)

    def to_bytes(self) -> bytes:
        return (
            self.count.to_bytes(4, "little")
            + self.auxiliary
            + b"".join(self.records)
        )


@dataclass(frozen=True)
class VicMemTail:
    """The optional fifth section of opaque 0x10c-byte records."""

    records: Sequence[bytes]

    def __post_init__(self) -> None:
        records = tuple(self.records)
        if len(records) > VICMEM_TAIL_RECORD_CAPACITY:
            raise VicMemFormatError(
                f"VICMEM tail has {len(records)} records; "
                f"capacity is {VICMEM_TAIL_RECORD_CAPACITY}"
            )
        for record in records:
            if len(record) != VICMEM_TAIL_RECORD_SIZE:
                raise VicMemFormatError(
                    f"VICMEM tail record is {len(record)} bytes; "
                    f"expected {VICMEM_TAIL_RECORD_SIZE}"
                )
        object.__setattr__(self, "records", records)

    @property
    def count(self) -> int:
        return len(self.records)

    def to_bytes(self) -> bytes:
        return self.count.to_bytes(4, "little") + b"".join(self.records)


@dataclass(frozen=True)
class VicMemFile:
    """A complete, losslessly serializable ``VICMEM.bin`` image."""

    header: VicMemHeader
    sections: Sequence[Optional[VicMemSection]]
    tail: Optional[VicMemTail]

    def __post_init__(self) -> None:
        sections = tuple(self.sections)
        if len(sections) != VICMEM_CATEGORY_COUNT:
            raise VicMemFormatError(
                f"VICMEM requires {VICMEM_CATEGORY_COUNT} category sections"
            )
        for index, section in enumerate(sections):
            selected = bool(self.header.section_mask & (1 << index))
            if selected != (section is not None):
                state = "selected" if selected else "not selected"
                raise VicMemFormatError(
                    f"VICMEM category {index} is {state} but its section object "
                    f"is {'present' if section is not None else 'absent'}"
                )
        tail_selected = bool(self.header.section_mask & (1 << VICMEM_TAIL_BIT))
        if tail_selected != (self.tail is not None):
            state = "selected" if tail_selected else "not selected"
            raise VicMemFormatError(
                f"VICMEM tail is {state} but its section object is "
                f"{'present' if self.tail is not None else 'absent'}"
            )
        object.__setattr__(self, "sections", sections)

    def to_bytes(self) -> bytes:
        output = bytearray(self.header.to_bytes())
        for section in self.sections:
            if section is not None:
                output.extend(section.to_bytes())
        if self.tail is not None:
            output.extend(self.tail.to_bytes())
        return bytes(output)


def replace_vicmem_exact_path(
    image: VicMemFile, old_path: str, new_path: str, *, encoding: str = "cp932"
) -> VicMemFile:
    """Replace exact stored paths while preserving every other byte.

    Only category/tail records whose NUL-terminated path exactly equals
    ``old_path`` are changed. Post-NUL scratch bytes and tail fields remain
    untouched, making this suitable for an existing-file rename rather than
    directory-tree creation.
    """

    if not isinstance(image, VicMemFile):
        raise VicMemFormatError("image must be a VicMemFile")
    if not isinstance(old_path, str) or not old_path:
        raise VicMemFormatError("old_path must be a non-empty string")
    if not isinstance(new_path, str) or not new_path:
        raise VicMemFormatError("new_path must be a non-empty string")
    try:
        old_bytes = old_path.encode(encoding, errors="strict")
        new_bytes = new_path.encode(encoding, errors="strict")
    except (UnicodeEncodeError, LookupError) as exc:
        raise VicMemFormatError(f"sidecar path cannot be encoded as {encoding}") from exc
    if b"\x00" in old_bytes or b"\x00" in new_bytes:
        raise VicMemFormatError("sidecar paths cannot contain NUL")
    if len(new_bytes) >= VICMEM_PATH_STORAGE_SIZE:
        raise VicMemFormatError(
            f"new sidecar path must fit {VICMEM_PATH_STORAGE_SIZE - 1} bytes"
        )

    def replace_storage(raw: bytes, storage_size: int) -> bytes:
        storage = raw[:storage_size]
        path, _ = _path_prefix(storage)
        if path != old_bytes:
            return raw
        suffix_start = len(path) + 1
        replacement = (new_bytes + b"\x00" + storage[suffix_start:])[:storage_size]
        replacement = replacement.ljust(storage_size, b"\x00")
        return replacement + raw[storage_size:]

    sections = []
    for section in image.sections:
        if section is None:
            sections.append(None)
            continue
        sections.append(
            VicMemSection(
                auxiliary=section.auxiliary,
                records=tuple(
                    replace_storage(record, VICMEM_CATEGORY_RECORD_SIZE)
                    for record in section.records
                ),
            )
        )
    tail = None
    if image.tail is not None:
        tail = VicMemTail(
            records=tuple(
                replace_storage(record, VICMEM_PATH_STORAGE_SIZE)
                for record in image.tail.records
            )
        )
    return VicMemFile(header=image.header, sections=tuple(sections), tail=tail)


def remove_vicmem_exact_path(
    image: VicMemFile, path: str, *, encoding: str = "cp932"
) -> VicMemFile:
    """Remove exact matching selected-file paths from every VICMEM section.

    This is the conservative companion to :func:`replace_vicmem_exact_path`.
    Section headers and opaque auxiliary/tail fields are preserved; only
    records whose NUL-terminated path exactly matches ``path`` are filtered.
    It is useful when a content-file delete is known to invalidate a selected
    path. It does not infer or update ``VICLV.bin`` or ``order.vnw`` state.
    """

    if not isinstance(image, VicMemFile):
        raise VicMemFormatError("image must be a VicMemFile")
    if not isinstance(path, str) or not path:
        raise VicMemFormatError("path must be a non-empty string")
    try:
        encoded = path.encode(encoding, errors="strict")
    except (UnicodeEncodeError, LookupError) as exc:
        raise VicMemFormatError(f"sidecar path cannot be encoded as {encoding}") from exc
    if b"\x00" in encoded:
        raise VicMemFormatError("sidecar path cannot contain NUL")

    def keep(raw: bytes, storage_size: int) -> bool:
        return _path_prefix(raw[:storage_size])[0] != encoded

    sections = []
    for section in image.sections:
        if section is None:
            sections.append(None)
            continue
        sections.append(
            VicMemSection(
                auxiliary=section.auxiliary,
                records=tuple(
                    record
                    for record in section.records
                    if keep(record, VICMEM_CATEGORY_RECORD_SIZE)
                ),
            )
        )
    tail = None
    if image.tail is not None:
        tail = VicMemTail(
            records=tuple(
                record
                for record in image.tail.records
                if keep(record, VICMEM_PATH_STORAGE_SIZE)
            )
        )
    return VicMemFile(header=image.header, sections=tuple(sections), tail=tail)


def _require(data: bytes, offset: int, length: int, what: str) -> None:
    if length < 0 or offset < 0 or offset + length > len(data):
        raise VicMemFormatError(
            f"VICMEM is truncated while reading {what} at offset 0x{offset:x}"
        )


def _read_u32le(data: bytes, offset: int, what: str) -> int:
    _require(data, offset, 4, what)
    return int.from_bytes(data[offset : offset + 4], "little")


def parse_vicmem(data: bytes) -> VicMemFile:
    """Parse and validate a complete ``VICMEM.bin`` image."""

    if len(data) < VICMEM_HEADER_SIZE:
        raise VicMemFormatError(
            f"VICMEM image is {len(data)} bytes; expected at least {VICMEM_HEADER_SIZE}"
        )
    if data[: len(VICMEM_SIGNATURE)] != VICMEM_SIGNATURE:
        raise VicMemFormatError("VICMEM signature mismatch")
    version = _read_u32le(data, 12, "version")
    if version != VICMEM_VERSION:
        raise VicMemFormatError(
            f"unsupported VICMEM version {version}; expected {VICMEM_VERSION}"
        )
    section_mask = _read_u32le(data, 16, "section mask")
    header = VicMemHeader(
        reserved=data[10:12], version=version, section_mask=section_mask
    )

    offset = VICMEM_HEADER_SIZE
    sections: list[Optional[VicMemSection]] = []
    for index in range(VICMEM_CATEGORY_COUNT):
        if not (section_mask & (1 << index)):
            sections.append(None)
            continue
        count = _read_u32le(data, offset, f"category {index} count")
        if count > VICMEM_CATEGORY_RECORD_CAPACITY:
            raise VicMemFormatError(
                f"VICMEM category {index} count {count} exceeds "
                f"capacity {VICMEM_CATEGORY_RECORD_CAPACITY}"
            )
        _require(data, offset, 8, f"category {index} header")
        auxiliary = data[offset + 4 : offset + 8]
        offset += 8
        payload_length = count * VICMEM_CATEGORY_RECORD_SIZE
        _require(data, offset, payload_length, f"category {index} records")
        records = tuple(
            data[start : start + VICMEM_CATEGORY_RECORD_SIZE]
            for start in range(
                offset, offset + payload_length, VICMEM_CATEGORY_RECORD_SIZE
            )
        )
        offset += payload_length
        sections.append(VicMemSection(auxiliary=auxiliary, records=records))

    tail: Optional[VicMemTail]
    if section_mask & (1 << VICMEM_TAIL_BIT):
        count = _read_u32le(data, offset, "tail count")
        if count > VICMEM_TAIL_RECORD_CAPACITY:
            raise VicMemFormatError(
                f"VICMEM tail count {count} exceeds capacity {VICMEM_TAIL_RECORD_CAPACITY}"
            )
        offset += 4
        payload_length = count * VICMEM_TAIL_RECORD_SIZE
        _require(data, offset, payload_length, "tail records")
        records = tuple(
            data[start : start + VICMEM_TAIL_RECORD_SIZE]
            for start in range(offset, offset + payload_length, VICMEM_TAIL_RECORD_SIZE)
        )
        offset += payload_length
        tail = VicMemTail(records=records)
    else:
        tail = None

    if offset != len(data):
        raise VicMemFormatError(
            f"VICMEM has {len(data) - offset} trailing bytes after its selected sections"
        )
    return VicMemFile(header=header, sections=tuple(sections), tail=tail)


def build_vicmem(
    sections: Sequence[Optional[VicMemSection]],
    tail: Optional[VicMemTail],
    *,
    reserved: bytes = b"\x00\x00",
    section_mask: Optional[int] = None,
) -> bytes:
    """Build a deterministic version-1 image from opaque section records.

    When ``section_mask`` is omitted, presence of each supplied section sets
    the corresponding low bit.  Passing a mask explicitly is useful for
    preserving a forensic image whose high or zero-count selection bits are
    significant.
    """

    sections_tuple = tuple(sections)
    if len(sections_tuple) != VICMEM_CATEGORY_COUNT:
        raise VicMemFormatError(
            f"VICMEM requires {VICMEM_CATEGORY_COUNT} category sections"
        )
    if section_mask is None:
        section_mask = sum(
            (1 << index) for index, section in enumerate(sections_tuple) if section is not None
        )
        if tail is not None:
            section_mask |= 1 << VICMEM_TAIL_BIT
    header = VicMemHeader(
        reserved=reserved, version=VICMEM_VERSION, section_mask=section_mask
    )
    return VicMemFile(header=header, sections=sections_tuple, tail=tail).to_bytes()
