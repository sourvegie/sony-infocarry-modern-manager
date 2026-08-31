"""Offline typed package model for an ordered TXT/BMP sequence.

The model validates the conservative 237x320 one-bit Windows BMP profile and
reuses the strict TXT authoring boundary.  The 16-byte BMP record prefix is
the narrow wrapper observed in the P16-001 native transaction; the complete
Capture 01 post-backup verifies persistence for that exact package, while
other packages remain evidence-gated.  This module intentionally stops before
live authorization or USB transport.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Union

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
            "package_path": f"source/{order + 1:04d}_{self.source_path.name}",
            "prepared_path": f"prepared/{folder_path.split(chr(92), 1)[-1]}/{self.name}",
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
                "source": "P16-001 native transaction observation; exact Capture 01 post-operation persistence verified; not a generalized compatibility claim",
            },
        }


PreparedMediaItem = Union[PreparedTextSourceItem, PreparedBitmapSourceItem]


@dataclass(frozen=True)
class PreparedMediaPackage:
    """An ordered typed package with no candidate or device bytes."""

    folder_name: str
    items: tuple[PreparedMediaItem, ...]
    require_mixed_kinds: bool = True
    # Imports carry the hash of the signed on-disk manifest.  A loaded package
    # may use archive-local source paths, so regenerating a manifest from the
    # imported view is not the same identity as the manifest that was signed
    # by the exporter.  Keep this binding separate from serialization; the
    # importer is the only caller that supplies it.
    manifest_binding_sha256: str | None = None

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
        if kinds - {"txt", "bmp"}:
            raise PreparedMediaPackageError("typed package contains an unsupported item kind")
        if self.require_mixed_kinds and kinds != {"txt", "bmp"}:
            raise PreparedMediaPackageError("typed package must contain both TXT and BMP items")
        if self.manifest_binding_sha256 is not None:
            if (
                not isinstance(self.manifest_binding_sha256, str)
                or len(self.manifest_binding_sha256) != 64
                or self.manifest_binding_sha256.lower() != self.manifest_binding_sha256
            ):
                raise PreparedMediaPackageError(
                    "manifest_binding_sha256 must be a lowercase SHA-256 string"
                )
            try:
                int(self.manifest_binding_sha256, 16)
            except ValueError as exc:
                raise PreparedMediaPackageError(
                    "manifest_binding_sha256 must be a lowercase SHA-256 string"
                ) from exc

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
            "content_kinds": sorted({item.kind for item in self.items}),
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
        return self.manifest_binding_sha256 or self.manifest_dict()["prepared_manifest_sha256"]


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
    *,
    require_mixed_kinds: bool = True,
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
    return PreparedMediaPackage(folder_name, tuple(items), require_mixed_kinds=require_mixed_kinds)


def build_prepared_content_package(
    sources: Iterable[tuple[Path, str]],
    folder_name: str,
) -> PreparedMediaPackage:
    """Build a flat TXT/BMP package allowing one supported kind only.

    The existing mixed-media builder keeps its historical both-kinds default;
    this explicit name makes the broader offline content contract opt-in and
    keeps the distinction visible to callers.
    """

    return build_prepared_media_package(
        sources,
        folder_name,
        require_mixed_kinds=False,
    )


@dataclass(frozen=True)
class PreparedMediaPackageImport:
    """A verified, non-owning view of an exported prepared package."""

    root: Path
    manifest_path: Path
    manifest: Mapping[str, Any]
    manifest_sha256: str
    package: PreparedMediaPackage

    @property
    def children(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.manifest["items"])


def _safe_package_relative(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise PreparedMediaPackageError(f"{label} must be a non-empty relative package path")
    if "\\" in value:
        raise PreparedMediaPackageError(f"{label} must use forward-slash package paths")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise PreparedMediaPackageError(f"{label} escapes the package root")
    return Path(*relative.parts)


def _package_file(root: Path, relative: Path, label: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise PreparedMediaPackageError(f"{label} escapes the package root") from exc
    if not candidate.is_file():
        raise PreparedMediaPackageError(f"{label} is not a regular file: {relative}")
    return candidate


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PreparedMediaPackageError(f"{label} must be an object")
    return value


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or value.lower() != value:
        raise PreparedMediaPackageError(f"{label} must be a lowercase SHA-256 string")
    try:
        int(value, 16)
    except ValueError as exc:
        raise PreparedMediaPackageError(f"{label} must be a lowercase SHA-256 string") from exc
    return value


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PreparedMediaPackageError(f"{label} must be a non-negative integer")
    return value


def load_prepared_media_package(root: Path) -> PreparedMediaPackageImport:
    """Validate an exported flat TXT/BMP package without changing any file.

    The manifest is authoritative for order, names, kinds, and hashes.  Both
    the copied source files and the prepared children are checked, and every
    package path is resolved beneath the selected package root.  This is an
    import/review boundary only; it constructs no device candidate.
    """

    package_root = Path(root).expanduser().resolve()
    if not package_root.is_dir():
        raise PreparedMediaPackageError(f"prepared package root is not a directory: {package_root}")
    manifest_path = package_root / "manifest.json"
    if not manifest_path.is_file():
        raise PreparedMediaPackageError("prepared package manifest.json is missing")
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreparedMediaPackageError(f"prepared package manifest is unreadable: {exc}") from exc
    manifest_object = _require_mapping(manifest, "prepared package manifest")
    expected_manifest_hash = _require_sha256(
        manifest_object.get("prepared_manifest_sha256"),
        "prepared_manifest_sha256",
    )
    unsigned_manifest = dict(manifest_object)
    unsigned_manifest.pop("prepared_manifest_sha256", None)
    actual_manifest_hash = _sha256(_canonical_json(unsigned_manifest))
    if actual_manifest_hash != expected_manifest_hash:
        raise PreparedMediaPackageError("prepared package manifest hash does not match its contents")
    if manifest_object.get("format") != PREPARED_MEDIA_PACKAGE_FORMAT:
        raise PreparedMediaPackageError("unsupported prepared typed-media package format")
    if manifest_object.get("state") != "prepared_offline":
        raise PreparedMediaPackageError("prepared package is not in the offline prepared state")
    if manifest_object.get("device_change") != "none" or manifest_object.get("usb_accessed") is not False:
        raise PreparedMediaPackageError("prepared package manifest claims device access or change")

    target = _require_mapping(manifest_object.get("target"), "prepared package target")
    folder_name = target.get("folder_name")
    try:
        _validate_component(folder_name, label="folder name")
    except PreparedPackageError as exc:
        raise PreparedMediaPackageError(str(exc)) from exc
    folder_path = f"root\\{folder_name}"
    if target.get("folder_path") != folder_path or target.get("root_level") is not True:
        raise PreparedMediaPackageError("prepared package target must be one root-level folder")
    if target.get("ordered_items") is not True:
        raise PreparedMediaPackageError("prepared package target must declare ordered items")
    raw_items = manifest_object.get("items")
    if not isinstance(raw_items, list) or len(raw_items) < 2:
        raise PreparedMediaPackageError("prepared typed-media package must contain at least two items")
    target_paths = target.get("item_paths")
    if target_paths != [f"{folder_path}\\{item.get('name')}" for item in raw_items if isinstance(item, Mapping)]:
        raise PreparedMediaPackageError("prepared package target paths do not match ordered items")

    items: list[PreparedMediaItem] = []
    seen_names: set[str] = set()
    seen_source_paths: set[Path] = set()
    seen_package_paths: set[Path] = set()
    for index, raw_item in enumerate(raw_items):
        item = _require_mapping(raw_item, f"prepared package item {index}")
        if isinstance(item.get("order"), bool) or item.get("order") != index:
            raise PreparedMediaPackageError("prepared package child order is missing, duplicated, or changed")
        kind = item.get("kind")
        name = item.get("name")
        if kind not in {"txt", "bmp"}:
            raise PreparedMediaPackageError(f"prepared package item {index} has an unsupported kind")
        if not isinstance(name, str):
            raise PreparedMediaPackageError(f"prepared package item {index} name is invalid")
        try:
            _validate_component(name, label=f"item {index} name", extension=f".{kind}")
        except PreparedPackageError as exc:
            raise PreparedMediaPackageError(str(exc)) from exc
        if name.casefold() in seen_names:
            raise PreparedMediaPackageError("prepared package child names must be unique")
        seen_names.add(name.casefold())
        if item.get("path") != f"{folder_path}\\{name}":
            raise PreparedMediaPackageError("prepared package item path does not match its folder and order")
        source_info = _require_mapping(item.get("source"), f"prepared package item {index} source")
        source_hash = _require_sha256(source_info.get("sha256"), f"item {index} source sha256")
        source_size_key = "utf8_bytes" if kind == "txt" else "bytes"
        source_size = _require_int(
            source_info.get(source_size_key),
            f"item {index} source bytes",
        )
        source_path_value = source_info.get("path")
        if not isinstance(source_path_value, str) or not source_path_value:
            raise PreparedMediaPackageError(f"prepared package item {index} source path is invalid")
        package_relative = item.get("package_path")
        if package_relative is None:
            # Accept older exports whose source archive location was implied by
            # the deterministic exporter naming convention.
            source_basename = source_path_value.replace("\\", "/").rsplit("/", 1)[-1]
            package_relative = f"source/{index + 1:04d}_{source_basename}"
        source_relative = _safe_package_relative(package_relative, f"item {index} package_path")
        prepared_relative_value = item.get("prepared_path")
        if prepared_relative_value is None:
            prepared_relative_value = f"prepared/{folder_name}/{name}"
        prepared_relative = _safe_package_relative(
            prepared_relative_value,
            f"item {index} prepared_path",
        )
        source_basename = source_path_value.replace("\\", "/").rsplit("/", 1)[-1]
        expected_source_relative = Path("source") / f"{index + 1:04d}_{source_basename}"
        expected_prepared_relative = Path("prepared") / folder_name / name
        if source_relative != expected_source_relative:
            raise PreparedMediaPackageError(
                f"item {index} source archive path is not the declared flat package location"
            )
        if prepared_relative != expected_prepared_relative:
            raise PreparedMediaPackageError(
                f"item {index} prepared archive path is not the declared flat package location"
            )
        if source_relative in seen_package_paths or prepared_relative in seen_package_paths:
            raise PreparedMediaPackageError("prepared package child archive paths must be unique")
        seen_package_paths.update((source_relative, prepared_relative))
        source_path = _package_file(package_root, source_relative, f"item {index} source")
        prepared_path = _package_file(package_root, prepared_relative, f"item {index} prepared child")
        if source_path in seen_source_paths:
            raise PreparedMediaPackageError("prepared package source paths must be unique")
        seen_source_paths.add(source_path)
        source_bytes = source_path.read_bytes()
        if len(source_bytes) != source_size or _sha256(source_bytes) != source_hash:
            raise PreparedMediaPackageError(f"prepared package source hash/size mismatch for item {index}")
        try:
            if kind == "txt":
                prepared_item = _load_txt(source_path, name)
                wrapper = _require_mapping(item.get("native_wrapper"), f"item {index} native_wrapper")
                if wrapper.get("required") is not True or wrapper.get("length_bytes") != NATIVE_TEXT_PREFIX_LENGTH:
                    raise PreparedMediaPackageError("TXT native wrapper metadata is not supported")
                authoring = _require_mapping(item.get("authoring"), f"item {index} authoring")
                if (
                    authoring.get("prepared_encoding") != "cp932"
                    or authoring.get("newline_policy") != "crlf"
                    or authoring.get("unsupported_characters_replaced") is not False
                    or authoring.get("embedded_nul_rejected") is not True
                    or authoring.get("prepared_payload_bytes") != len(prepared_item.authored.payload)
                ):
                    raise PreparedMediaPackageError(f"TXT authoring metadata mismatch for item {index}")
                if authoring.get("prepared_payload_sha256") != prepared_item.payload_sha256:
                    raise PreparedMediaPackageError(f"TXT prepared payload hash mismatch for item {index}")
                if prepared_path.read_bytes() != prepared_item.authored.payload:
                    raise PreparedMediaPackageError(f"TXT prepared child bytes mismatch for item {index}")
            else:
                prepared_item = _load_bmp(source_path, name)
                wrapper = _require_mapping(item.get("native_wrapper"), f"item {index} native_wrapper")
                if wrapper.get("required") is not True or wrapper.get("length_bytes") != NATIVE_BMP_PREFIX_LENGTH:
                    raise PreparedMediaPackageError("BMP native wrapper metadata is not supported")
                bmp_info = _require_mapping(item.get("bmp"), f"item {index} bmp")
                details = _validate_bmp(source_bytes)
                for key in ("width", "height", "bits_per_pixel", "row_stride", "pixel_offset", "pixel_bytes"):
                    if bmp_info.get(key) != details[key]:
                        raise PreparedMediaPackageError(f"BMP metadata mismatch for item {index}: {key}")
                if bmp_info.get("payload_sha256") != prepared_item.payload_sha256:
                    raise PreparedMediaPackageError(f"BMP payload hash mismatch for item {index}")
                if bmp_info.get("pixel_bytes") != details["pixel_bytes"]:
                    raise PreparedMediaPackageError(f"BMP payload size metadata mismatch for item {index}")
                if prepared_path.read_bytes() != source_bytes:
                    raise PreparedMediaPackageError(f"BMP prepared child bytes mismatch for item {index}")
        except OSError as exc:
            raise PreparedMediaPackageError(f"could not read package child {index}: {exc}") from exc
        items.append(prepared_item)

    kinds = {item.kind for item in items}
    declared_kinds = manifest_object.get("content_kinds")
    if declared_kinds is not None and declared_kinds != sorted(kinds):
        raise PreparedMediaPackageError("prepared package content kinds do not match its children")
    package = PreparedMediaPackage(
        folder_name,
        tuple(items),
        require_mixed_kinds=False,
        manifest_binding_sha256=expected_manifest_hash,
    )
    return PreparedMediaPackageImport(
        root=package_root,
        manifest_path=manifest_path,
        manifest=manifest_object,
        manifest_sha256=expected_manifest_hash,
        package=package,
    )


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
    "PreparedMediaPackageImport",
    "PreparedMediaPackageError",
    "build_prepared_media_package",
    "build_prepared_content_package",
    "export_prepared_media_package",
    "load_prepared_media_package",
]
