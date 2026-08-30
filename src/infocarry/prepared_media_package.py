"""Offline typed package model for an ordered TXT/BMP sequence.

The model validates the conservative 237x320 one-bit Windows BMP profile and
reuses the strict TXT authoring boundary.  The 16-byte BMP record prefix is
the narrow wrapper observed in the P16-001 native transaction; post-operation
device persistence is still an evidence gate.  This module intentionally
stops before live authorization or USB transport.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Union

from .bitmap import BitmapFormatError, decode_monochrome_bmp
from .offline_conversion import load_utf8_text_document
from .prepared_package import (
    METADATA_RECORD_SIZE,
    NATIVE_TEXT_PREFIX_LENGTH,
    PreparedPackageError,
    _align4,
    _canonical_json,
    _validate_component,
)
from .prepared_multi_text import PreparedTextSourceItem
from .text_authoring import TextAuthoringError, encode_cp932_text


EXPECTED_BMP_WIDTH = 237
EXPECTED_BMP_HEIGHT = 320
EXPECTED_BMP_BITS_PER_PIXEL = 1
NATIVE_BMP_PREFIX_LENGTH = 0x10
PREPARED_MEDIA_PACKAGE_FORMAT = "infocarry-prepared-typed-media-package-v1"
PREPARED_MEDIA_CONFIRMATION = "OFFLINE PREPARATION ONLY — NO DEVICE CHANGE"


class PreparedMediaPackageError(PreparedPackageError):
    """Raised when a typed TXT/BMP package is not safely representable."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def _i32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _validate_bmp(payload: bytes) -> dict[str, int]:
    if len(payload) < 62 or payload[:2] != b"BM":
        raise PreparedMediaPackageError("BMP is too short or lacks the Windows BM signature")
    if _u32(payload, 2) != len(payload):
        raise PreparedMediaPackageError("BMP declared length does not match source length")
    pixel_offset = _u32(payload, 10)
    dib_size = _u32(payload, 14)
    width = _i32(payload, 18)
    signed_height = _i32(payload, 22)
    planes = _u16(payload, 26)
    bits_per_pixel = _u16(payload, 28)
    compression = _u32(payload, 30)
    colors_used = _u32(payload, 46)
    if dib_size != 40:
        raise PreparedMediaPackageError("BMP must use a 40-byte BITMAPINFOHEADER")
    if width != EXPECTED_BMP_WIDTH or abs(signed_height) != EXPECTED_BMP_HEIGHT:
        raise PreparedMediaPackageError(
            f"BMP must be exactly {EXPECTED_BMP_WIDTH}x{EXPECTED_BMP_HEIGHT} pixels"
        )
    if planes != 1 or bits_per_pixel != EXPECTED_BMP_BITS_PER_PIXEL or compression != 0:
        raise PreparedMediaPackageError("BMP must be uncompressed one-bit Windows BMP")
    if colors_used not in (0, 2):
        raise PreparedMediaPackageError("one-bit BMP must use a two-entry palette")
    palette_end = 14 + dib_size + 2 * 4
    if pixel_offset != palette_end:
        raise PreparedMediaPackageError("BMP pixel offset must follow the 40-byte header and palette")
    row_stride = ((width + 31) // 32) * 4
    pixel_end = pixel_offset + row_stride * abs(signed_height)
    if pixel_end != len(payload):
        raise PreparedMediaPackageError("BMP pixel bounds must exactly cover the source payload")
    try:
        preview = decode_monochrome_bmp(payload)
    except BitmapFormatError as exc:
        raise PreparedMediaPackageError(f"BMP failed the canonical monochrome validator: {exc}") from exc
    if (preview.width, preview.height) != (EXPECTED_BMP_WIDTH, EXPECTED_BMP_HEIGHT):
        raise PreparedMediaPackageError("BMP canonical preview dimensions differ from the required profile")
    return {
        "width": width,
        "height": abs(signed_height),
        "bits_per_pixel": bits_per_pixel,
        "row_stride": row_stride,
        "pixel_offset": pixel_offset,
        "pixel_bytes": row_stride * abs(signed_height),
    }


@dataclass(frozen=True)
class PreparedBitmapSourceItem:
    """One source-bound validated BMP child."""

    source_path: Path
    name: str
    source_bytes: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.source_path, Path) or self.source_path.suffix.lower() != ".bmp":
            raise PreparedMediaPackageError("BMP source must be a .bmp Path")
        _validate_component(self.name, label="item name", extension=".bmp")
        if not isinstance(self.source_bytes, bytes):
            raise PreparedMediaPackageError("BMP source bytes must be bytes")
        _validate_bmp(self.source_bytes)

    @property
    def source_sha256(self) -> str:
        return _sha256(self.source_bytes)

    @property
    def payload_sha256(self) -> str:
        return self.source_sha256

    @property
    def aligned_content_bytes(self) -> int:
        return _align4(NATIVE_BMP_PREFIX_LENGTH + len(self.source_bytes))

    @property
    def kind(self) -> str:
        return "bmp"

    def to_dict(self, order: int, folder_path: str) -> dict[str, Any]:
        details = _validate_bmp(self.source_bytes)
        return {
            "order": order,
            "kind": self.kind,
            "name": self.name,
            "path": f"{folder_path}\\{self.name}",
            "source": {
                "path": str(self.source_path),
                "sha256": self.source_sha256,
                "bytes": len(self.source_bytes),
            },
            "bmp": {
                "width": details["width"],
                "height": details["height"],
                "bits_per_pixel": details["bits_per_pixel"],
                "compression": "BI_RGB",
                "row_stride": details["row_stride"],
                "pixel_offset": details["pixel_offset"],
                "pixel_bytes": details["pixel_bytes"],
                "payload_sha256": self.payload_sha256,
            },
            "native_wrapper": {
                "required": True,
                "length_bytes": NATIVE_BMP_PREFIX_LENGTH,
                "bytes_included": False,
                "source": "P16-001 native transaction observation; post-operation persistence remains unverified",
            },
        }


PreparedMediaItem = Union[PreparedTextSourceItem, PreparedBitmapSourceItem]


@dataclass(frozen=True)
class PreparedMediaPackage:
    """An ordered typed package with no candidate or device bytes."""

    folder_name: str
    items: tuple[PreparedMediaItem, ...]

    def __post_init__(self) -> None:
        _validate_component(self.folder_name, label="folder name")
        if not isinstance(self.items, tuple) or len(self.items) < 2:
            raise PreparedMediaPackageError("typed package must contain at least two items")
        if any(not isinstance(item, (PreparedTextSourceItem, PreparedBitmapSourceItem)) for item in self.items):
            raise PreparedMediaPackageError("items must be typed TXT or BMP source items")
        names = [item.name.casefold() for item in self.items]
        if len(set(names)) != len(names):
            raise PreparedMediaPackageError("typed item names must be unique case-insensitively")
        source_paths = [item.source_path for item in self.items]
        if len(set(source_paths)) != len(source_paths):
            raise PreparedMediaPackageError("typed source paths must be unique")
        kinds = {item.kind for item in self.items}
        if kinds != {"txt", "bmp"}:
            raise PreparedMediaPackageError("typed package must contain both TXT and BMP items")

    @property
    def target_folder_path(self) -> str:
        return f"root\\{self.folder_name}"

    @property
    def target_item_paths(self) -> tuple[str, ...]:
        return tuple(f"{self.target_folder_path}\\{item.name}" for item in self.items)

    @property
    def minimum_metadata_records(self) -> int:
        return len(self.items) + 2

    @property
    def prepared_payload_bytes(self) -> int:
        return sum(
            len(item.authored.payload) if isinstance(item, PreparedTextSourceItem) else len(item.source_bytes)
            for item in self.items
        )

    @property
    def aligned_content_bytes(self) -> int:
        return sum(item.aligned_content_bytes for item in self.items)

    @property
    def estimated_growth_lower_bound(self) -> int:
        return self.minimum_metadata_records * METADATA_RECORD_SIZE + self.aligned_content_bytes

    def manifest_dict(self) -> dict[str, Any]:
        manifest: dict[str, Any] = {
            "format": PREPARED_MEDIA_PACKAGE_FORMAT,
            "state": "prepared_offline",
            "device_change": "none",
            "usb_accessed": False,
            "notice": PREPARED_MEDIA_CONFIRMATION,
            "target": {
                "folder_name": self.folder_name,
                "folder_path": self.target_folder_path,
                "item_paths": list(self.target_item_paths),
                "root_level": True,
                "ordered_items": True,
            },
            "items": [
                item.to_dict(index, self.target_folder_path)
                for index, item in enumerate(self.items)
            ],
            "size": {
                "metadata_record_size": METADATA_RECORD_SIZE,
                "minimum_metadata_records": self.minimum_metadata_records,
                "minimum_metadata_bytes": self.minimum_metadata_records * METADATA_RECORD_SIZE,
                "native_wrapper_bytes_required": sum(
                    NATIVE_TEXT_PREFIX_LENGTH
                    if isinstance(item, PreparedTextSourceItem)
                    else NATIVE_BMP_PREFIX_LENGTH
                    for item in self.items
                ),
                "prepared_payload_bytes": self.prepared_payload_bytes,
                "aligned_content_bytes": self.aligned_content_bytes,
                "estimated_growth_lower_bound": self.estimated_growth_lower_bound,
                "exact_device_growth_known": False,
                "capacity_result": "not_evaluated_without_verified_backup",
            },
            "compatibility": {
                "preparation": "ready",
                "ordered_txt_bmp": "ready_offline",
                "device_candidate": "blocked",
                "usb_operation": "none",
            },
            "safety": {
                "source_mutated": False,
                "candidate_bytes_included": False,
                "overwrite_allowed": False,
                "unsupported_characters_replaced": False,
                "embedded_nul_rejected": True,
            },
        }
        manifest["prepared_manifest_sha256"] = _sha256(_canonical_json(manifest))
        return manifest

    @property
    def prepared_manifest_sha256(self) -> str:
        return self.manifest_dict()["prepared_manifest_sha256"]


def _load_txt(path: Path, name: str) -> PreparedTextSourceItem:
    resolved = Path(path).expanduser().resolve()
    if resolved.suffix.lower() != ".txt":
        raise PreparedMediaPackageError("TXT item source must end with .txt")
    try:
        _validate_component(name, label="item name", extension=".txt")
    except PreparedPackageError as exc:
        raise PreparedMediaPackageError(str(exc)) from exc
    try:
        source_bytes = resolved.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        authored = encode_cp932_text(source_text)
        load_utf8_text_document(resolved)
    except Exception as exc:
        raise PreparedMediaPackageError(f"TXT source failed strict preparation: {resolved}: {exc}") from exc
    return PreparedTextSourceItem(resolved, name, source_bytes, source_text, authored)


def _load_bmp(path: Path, name: str) -> PreparedBitmapSourceItem:
    resolved = Path(path).expanduser().resolve()
    if resolved.suffix.lower() != ".bmp":
        raise PreparedMediaPackageError("BMP item source must end with .bmp")
    try:
        _validate_component(name, label="item name", extension=".bmp")
    except PreparedPackageError as exc:
        raise PreparedMediaPackageError(str(exc)) from exc
    try:
        source_bytes = resolved.read_bytes()
    except OSError as exc:
        raise PreparedMediaPackageError(f"could not read BMP source {resolved}: {exc}") from exc
    return PreparedBitmapSourceItem(resolved, name, source_bytes)


def build_prepared_media_package(
    sources: Iterable[tuple[Path, str]],
    folder_name: str,
) -> PreparedMediaPackage:
    """Build an ordered TXT/BMP package using only local offline validation."""

    if isinstance(sources, (str, bytes)):
        raise PreparedMediaPackageError("sources must be an ordered iterable of (Path, item_name) pairs")
    try:
        source_specs = list(sources)
    except TypeError as exc:
        raise PreparedMediaPackageError("sources must be an ordered iterable") from exc
    if len(source_specs) < 2:
        raise PreparedMediaPackageError("typed package must contain at least two items")
    items: list[PreparedMediaItem] = []
    for spec in source_specs:
        if not isinstance(spec, (tuple, list)) or len(spec) != 2:
            raise PreparedMediaPackageError("each item must be a (Path, item_name) pair")
        path = Path(spec[0]).expanduser().resolve()
        name = spec[1]
        if path.suffix.lower() == ".txt":
            items.append(_load_txt(path, name))
        elif path.suffix.lower() == ".bmp":
            items.append(_load_bmp(path, name))
        else:
            raise PreparedMediaPackageError("only .txt and .bmp sources are supported")
    return PreparedMediaPackage(folder_name, tuple(items))


def export_prepared_media_package(
    package: PreparedMediaPackage,
    destination: Path,
) -> Path:
    """Export validated source copies and typed prepared files without overwrite."""

    if not isinstance(package, PreparedMediaPackage):
        raise PreparedMediaPackageError("package must be a PreparedMediaPackage")
    root = Path(destination).expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=False)
        source_root = root / "source"
        prepared_root = root / "prepared" / package.folder_name
        source_root.mkdir()
        prepared_root.mkdir(parents=True)
        for index, item in enumerate(package.items, start=1):
            source_bytes = item.source_bytes
            (source_root / f"{index:04d}_{item.source_path.name}").write_bytes(source_bytes)
            prepared_bytes = (
                item.authored.payload
                if isinstance(item, PreparedTextSourceItem)
                else item.source_bytes
            )
            (prepared_root / item.name).write_bytes(prepared_bytes)
        (root / "manifest.json").write_bytes(
            json.dumps(package.manifest_dict(), ensure_ascii=False, indent=2).encode("utf-8")
            + b"\n"
        )
    except FileExistsError as exc:
        raise PreparedMediaPackageError(f"refusing to overwrite existing output {root}") from exc
    except OSError as exc:
        raise PreparedMediaPackageError(f"could not export offline package {root}: {exc}") from exc
    return root


__all__ = [
    "EXPECTED_BMP_BITS_PER_PIXEL",
    "EXPECTED_BMP_HEIGHT",
    "EXPECTED_BMP_WIDTH",
    "NATIVE_BMP_PREFIX_LENGTH",
    "PREPARED_MEDIA_CONFIRMATION",
    "PREPARED_MEDIA_PACKAGE_FORMAT",
    "PreparedBitmapSourceItem",
    "PreparedMediaItem",
    "PreparedMediaPackage",
    "PreparedMediaPackageError",
    "build_prepared_media_package",
    "export_prepared_media_package",
]
