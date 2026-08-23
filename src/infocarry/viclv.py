"""Lossless parser and builder for the legacy ``VICLV.bin`` sidecar.

The layout is recovered from preserved ``VicTwo.dll`` routines.  It is an
offline format module only and performs no device I/O.
"""

from dataclasses import dataclass
from typing import Sequence


VICLV_SIGNATURE = b"VICVLBIN  "
VICLV_VERSION = 1
VICLV_HEADER_SIZE = 16
VICLV_ENTRY_SIZE = 261
VICLV_PATH_FIELD_SIZE = 260


class VicLvFormatError(ValueError):
    """Raised when a ``VICLV.bin`` image violates the recovered layout."""


@dataclass(frozen=True)
class VicLvHeader:
    """The 16-byte ``VICLV.bin`` header."""

    reserved: bytes = b"\x00\x00"
    version: int = VICLV_VERSION

    def __post_init__(self) -> None:
        if len(self.reserved) != 2:
            raise VicLvFormatError("VICLV reserved header field must be 2 bytes")
        if not 0 <= self.version <= 0xFFFFFFFF:
            raise VicLvFormatError("VICLV version must fit an unsigned 32-bit value")

    def to_bytes(self) -> bytes:
        return VICLV_SIGNATURE + self.reserved + self.version.to_bytes(4, "little")


@dataclass(frozen=True)
class VicLvEntry:
    """One category byte followed by its exact 260-byte path field."""

    category: int
    path_field: bytes

    def __post_init__(self) -> None:
        if not 0 <= self.category <= 0xFF:
            raise VicLvFormatError("VICLV category must fit one byte")
        if len(self.path_field) != VICLV_PATH_FIELD_SIZE:
            raise VicLvFormatError(
                f"VICLV path field is {len(self.path_field)} bytes; "
                f"expected {VICLV_PATH_FIELD_SIZE}"
            )
        if b"\x00" not in self.path_field:
            raise VicLvFormatError("VICLV path field has no NUL terminator")

    @classmethod
    def from_path_bytes(cls, category: int, path: bytes) -> "VicLvEntry":
        """Create the canonical zero-padded form used by ``VicTwo.dll``."""

        if b"\x00" in path:
            raise VicLvFormatError("VICLV path cannot contain an embedded NUL")
        if len(path) >= VICLV_PATH_FIELD_SIZE:
            raise VicLvFormatError("VICLV path must be at most 259 bytes")
        field = path + b"\x00" + bytes(VICLV_PATH_FIELD_SIZE - len(path) - 1)
        return cls(category=category, path_field=field)

    @classmethod
    def from_cp932_path(cls, category: int, path: str) -> "VicLvEntry":
        """Encode a generated relative Windows path using legacy CP932."""

        return cls.from_path_bytes(category, path.encode("cp932"))

    @property
    def path_bytes(self) -> bytes:
        return self.path_field.split(b"\x00", 1)[0]

    @property
    def path_cp932(self) -> str:
        return self.path_bytes.decode("cp932")

    def to_bytes(self) -> bytes:
        return bytes((self.category,)) + self.path_field


@dataclass(frozen=True)
class VicLvFile:
    """A complete, losslessly serializable ``VICLV.bin`` image."""

    header: VicLvHeader
    entries: Sequence[VicLvEntry]

    def to_bytes(self) -> bytes:
        return self.header.to_bytes() + b"".join(entry.to_bytes() for entry in self.entries)


def _encode_path(path: str, encoding: str, label: str) -> bytes:
    if not isinstance(path, str) or not path:
        raise VicLvFormatError(f"{label} must be a non-empty string")
    try:
        encoded = path.encode(encoding, errors="strict")
    except (UnicodeEncodeError, LookupError) as exc:
        raise VicLvFormatError(f"{label} cannot be encoded as {encoding}") from exc
    if b"\x00" in encoded:
        raise VicLvFormatError(f"{label} cannot contain NUL")
    return encoded


def _replace_path_field(field: bytes, old_bytes: bytes, new_bytes: bytes) -> bytes:
    terminator = field.find(b"\x00")
    if terminator < 0 or field[:terminator] != old_bytes:
        return field
    if len(new_bytes) >= VICLV_PATH_FIELD_SIZE:
        raise VicLvFormatError(
            f"new path must fit {VICLV_PATH_FIELD_SIZE - 1} bytes"
        )
    # Keep post-NUL bytes exactly as they appeared in the forensic image.
    suffix = field[terminator + 1 :]
    return (new_bytes + b"\x00" + suffix)[:VICLV_PATH_FIELD_SIZE].ljust(
        VICLV_PATH_FIELD_SIZE, b"\x00"
    )


def replace_viclv_exact_path(
    image: VicLvFile,
    old_path: str,
    new_path: str,
    *,
    encoding: str = "cp932",
) -> VicLvFile:
    """Replace exact path entries without changing category/order/padding.

    This is deliberately narrower than a directory-tree synchronizer. The
    legacy lookup compares category and relative path independently, so an
    existing exact entry can be renamed while preserving its category byte
    and all opaque bytes after the terminator.
    """

    if not isinstance(image, VicLvFile):
        raise VicLvFormatError("image must be a VicLvFile")
    old_bytes = _encode_path(old_path, encoding, "old_path")
    new_bytes = _encode_path(new_path, encoding, "new_path")
    if len(new_bytes) >= VICLV_PATH_FIELD_SIZE:
        raise VicLvFormatError(
            f"new path must fit {VICLV_PATH_FIELD_SIZE - 1} bytes"
        )
    return VicLvFile(
        header=image.header,
        entries=tuple(
            VicLvEntry(
                category=entry.category,
                path_field=_replace_path_field(entry.path_field, old_bytes, new_bytes),
            )
            for entry in image.entries
        ),
    )


def remove_viclv_exact_path(
    image: VicLvFile,
    path: str,
    *,
    encoding: str = "cp932",
) -> VicLvFile:
    """Remove entries whose NUL-terminated path exactly matches ``path``."""

    if not isinstance(image, VicLvFile):
        raise VicLvFormatError("image must be a VicLvFile")
    encoded = _encode_path(path, encoding, "path")
    return VicLvFile(
        header=image.header,
        entries=tuple(entry for entry in image.entries if entry.path_bytes != encoded),
    )


def parse_viclv(data: bytes) -> VicLvFile:
    """Parse and validate a complete ``VICLV.bin`` image."""

    if len(data) < VICLV_HEADER_SIZE:
        raise VicLvFormatError(
            f"VICLV image is {len(data)} bytes; expected at least {VICLV_HEADER_SIZE}"
        )
    if data[:10] != VICLV_SIGNATURE:
        raise VicLvFormatError("VICLV signature mismatch")
    version = int.from_bytes(data[12:16], "little")
    if version != VICLV_VERSION:
        raise VicLvFormatError(
            f"unsupported VICLV version {version}; expected {VICLV_VERSION}"
        )
    payload_length = len(data) - VICLV_HEADER_SIZE
    if payload_length % VICLV_ENTRY_SIZE:
        raise VicLvFormatError(
            f"VICLV payload is {payload_length} bytes; not a multiple of "
            f"entry size {VICLV_ENTRY_SIZE}"
        )

    entries = []
    for offset in range(VICLV_HEADER_SIZE, len(data), VICLV_ENTRY_SIZE):
        raw = data[offset : offset + VICLV_ENTRY_SIZE]
        entries.append(VicLvEntry(category=raw[0], path_field=raw[1:]))
    return VicLvFile(
        header=VicLvHeader(reserved=data[10:12], version=version),
        entries=tuple(entries),
    )


def build_viclv(
    entries: Sequence[VicLvEntry],
    *,
    reserved: bytes = b"\x00\x00",
) -> bytes:
    """Build the deterministic version-1 image used by the legacy manager."""

    return VicLvFile(
        header=VicLvHeader(reserved=reserved, version=VICLV_VERSION),
        entries=tuple(entries),
    ).to_bytes()
