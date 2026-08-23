"""Offline logical model for one prepared root-folder TXT package.

The model intentionally stops before device transaction construction.  It
reuses the canonical UTF-8 -> strict CP932/CRLF authoring boundary and records
the native wrapper requirement observed in validated backups without
inventing wrapper bytes, directory records, sidecars, or fixed-state values.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from .offline_conversion import load_utf8_text_document
from .text_authoring import EncodedText, TextAuthoringError, encode_cp932_text


PREPARED_PACKAGE_FORMAT = "infocarry-prepared-text-package-v1"
NATIVE_TEXT_PREFIX_LENGTH = 0x20
NATIVE_TEXT_FIELD_14 = 0x00000200
METADATA_RECORD_SIZE = 0x40
PREPARED_PACKAGE_CONFIRMATION = "OFFLINE PREPARATION ONLY — NO DEVICE CHANGE"


class PreparedPackageError(ValueError):
    """Raised when a logical package cannot be prepared safely."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _align4(value: int) -> int:
    return (value + 3) & ~3


def _validate_component(value: str, *, label: str, extension: Optional[str] = None) -> bytes:
    if not isinstance(value, str) or not value:
        raise PreparedPackageError(f"{label} must be a non-empty string")
    if (
        value in {".", ".."}
        or "\x00" in value
        or "/" in value
        or "\\" in value
        or value != value.strip()
        or any(ord(char) < 0x20 for char in value)
    ):
        raise PreparedPackageError(
            f"{label} must be one trimmed non-traversal path component without NUL"
        )
    if extension is not None:
        if not value.lower().endswith(extension.lower()):
            raise PreparedPackageError(f"{label} must end with {extension}")
        basename = value[: -len(extension)]
        if not basename or "." in basename:
            raise PreparedPackageError(
                f"{label} must have one unambiguous basename and {extension}"
            )
    try:
        encoded = value.encode("cp932", errors="strict")
    except UnicodeEncodeError as exc:
        raise PreparedPackageError(f"{label} is not representable in CP932") from exc
    if len(encoded) >= 40:
        raise PreparedPackageError(
            f"{label} must leave room for the native metadata NUL terminator"
        )
    return encoded


@dataclass(frozen=True)
class PreparedTextItem:
    """One ordered TXT child in the logical package."""

    name: str
    authored: EncodedText

    def __post_init__(self) -> None:
        _validate_component(self.name, label="item name", extension=".txt")
        if not isinstance(self.authored, EncodedText):
            raise PreparedPackageError("item authored value must be EncodedText")

    def to_dict(self, order: int) -> dict[str, Any]:
        return {
            "order": order,
            "name": self.name,
            "path": self.name,
            "source_encoding": "utf-8",
            "prepared_encoding": "cp932",
            "newline_policy": "crlf",
            "source_characters": len(self.authored.original_text),
            "normalized_characters": len(self.authored.normalized_text),
            "source_utf8_bytes": len(self.authored.original_text.encode("utf-8")),
            "prepared_payload_bytes": len(self.authored.payload),
            "prepared_payload_sha256": _sha256(self.authored.payload),
            "native_wrapper": {
                "required": True,
                "length_bytes": NATIVE_TEXT_PREFIX_LENGTH,
                "field_14": f"0x{NATIVE_TEXT_FIELD_14:08x}",
                "bytes_included": False,
                "source": "existing validated TXT record template required",
            },
            "unsupported_characters_replaced": False,
            "embedded_nul_rejected": True,
        }


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True)
class PreparedTextPackage:
    """One source-bound, deterministic, device-neutral text package."""

    source_path: Path
    source_bytes: bytes
    source_text: str
    source_sha256: str
    folder_name: str
    items: tuple[PreparedTextItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_path, Path):
            raise PreparedPackageError("source_path must be a Path")
        if not isinstance(self.source_bytes, bytes):
            raise PreparedPackageError("source_bytes must be bytes")
        if not isinstance(self.source_text, str):
            raise PreparedPackageError("source_text must be a string")
        if self.source_sha256 != _sha256(self.source_bytes):
            raise PreparedPackageError("source_sha256 does not match source bytes")
        _validate_component(self.folder_name, label="folder name")
        if not isinstance(self.items, tuple):
            raise PreparedPackageError("items must be an ordered tuple")
        names = [item.name.casefold() for item in self.items]
        if len(set(names)) != len(names):
            raise PreparedPackageError("prepared item names must be unique")
        if len(self.items) != 1:
            raise PreparedPackageError(
                "the initial prepared package must contain exactly one TXT child"
            )

    @property
    def item(self) -> PreparedTextItem:
        return self.items[0]

    @property
    def target_folder_path(self) -> str:
        return f"root\\{self.folder_name}"

    @property
    def target_item_path(self) -> str:
        return f"{self.target_folder_path}\\{self.item.name}"

    @property
    def prepared_payload_bytes(self) -> int:
        return len(self.item.authored.payload)

    @property
    def aligned_content_bytes(self) -> int:
        return _align4(NATIVE_TEXT_PREFIX_LENGTH + self.prepared_payload_bytes)

    @property
    def minimum_metadata_records(self) -> int:
        # A directory, its observed parent marker, and its TXT child are the
        # smallest structural lower bound. This is an estimate, not a device
        # candidate or a proven new-folder grammar.
        return 3

    @property
    def estimated_growth_lower_bound(self) -> int:
        return self.minimum_metadata_records * METADATA_RECORD_SIZE + self.aligned_content_bytes

    def _base_manifest(self) -> dict[str, Any]:
        return {
            "format": PREPARED_PACKAGE_FORMAT,
            "state": "prepared_offline",
            "device_change": "none",
            "usb_accessed": False,
            "notice": PREPARED_PACKAGE_CONFIRMATION,
            "source": {
                "path": str(self.source_path),
                "sha256": self.source_sha256,
                "encoding": "utf-8",
                "strict": True,
                "utf8_bytes": len(self.source_bytes),
                "characters": len(self.source_text),
            },
            "target": {
                "folder_name": self.folder_name,
                "folder_path": self.target_folder_path,
                "item_path": self.target_item_path,
                "root_level": True,
            },
            "items": [item.to_dict(order=index) for index, item in enumerate(self.items)],
            "size": {
                "metadata_record_size": METADATA_RECORD_SIZE,
                "minimum_metadata_records": self.minimum_metadata_records,
                "minimum_metadata_bytes": self.minimum_metadata_records * METADATA_RECORD_SIZE,
                "native_wrapper_bytes_required": NATIVE_TEXT_PREFIX_LENGTH,
                "prepared_payload_bytes": self.prepared_payload_bytes,
                "aligned_content_bytes": self.aligned_content_bytes,
                "estimated_growth_lower_bound": self.estimated_growth_lower_bound,
                "exact_device_growth_known": False,
                "capacity_result": "not_evaluated_without_verified_backup",
            },
            "compatibility": {
                "preparation": "ready",
                "standalone_root_txt_creation": "proven_separately",
                "root_folder_creation": "unproven",
                "multi_record_creation": "unproven",
                "device_candidate": "blocked",
                "usb_operation": "none",
            },
            "safety": {
                "source_mutated": False,
                "candidate_bytes_included": False,
                "overwrite_allowed": False,
                "unsupported_characters_replaced": False,
                "embedded_nul_rejected": True,
                "category_assigned": False,
                "mark_assigned": False,
                "bookmark_assigned": False,
                "selection_assigned": False,
            },
        }

    def manifest_dict(self) -> dict[str, Any]:
        manifest = self._base_manifest()
        manifest["prepared_manifest_sha256"] = _sha256(_canonical_json(manifest))
        return manifest

    @property
    def prepared_manifest_sha256(self) -> str:
        return self.manifest_dict()["prepared_manifest_sha256"]


def build_prepared_text_package(
    source_path: Path,
    folder_name: str,
    item_name: str,
) -> PreparedTextPackage:
    """Prepare one strict UTF-8 TXT source without USB or device bytes."""

    path = Path(source_path).expanduser().resolve()
    if path.suffix.lower() != ".txt":
        raise PreparedPackageError("source_path must name one .txt file")
    try:
        source_bytes = path.read_bytes()
    except OSError as exc:
        raise PreparedPackageError(f"could not read source TXT {path}: {exc}") from exc
    try:
        source_text = source_bytes.decode("utf-8", errors="strict")
        authored = encode_cp932_text(source_text)
    except (UnicodeDecodeError, TextAuthoringError) as exc:
        raise PreparedPackageError(f"source TXT failed strict UTF-8/CP932 preparation: {exc}") from exc
    # Exercise the canonical document boundary as part of preparation. This
    # keeps logical page planning and future package callers on the same strict
    # source contract without including page/BMP output in this model.
    try:
        load_utf8_text_document(path)
    except Exception as exc:
        raise PreparedPackageError(f"canonical offline conversion rejected source: {exc}") from exc
    _validate_component(folder_name, label="folder name")
    _validate_component(item_name, label="item name", extension=".txt")
    return PreparedTextPackage(
        source_path=path,
        source_bytes=source_bytes,
        source_text=source_text,
        source_sha256=_sha256(source_bytes),
        folder_name=folder_name,
        items=(PreparedTextItem(item_name, authored),),
    )


def export_prepared_text_package(
    package: PreparedTextPackage,
    destination: Path,
) -> Path:
    """Export a new offline package directory, refusing every overwrite."""

    if not isinstance(package, PreparedTextPackage):
        raise PreparedPackageError("package must be a PreparedTextPackage")
    root = Path(destination).expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=False)
        (root / "source").mkdir()
        (root / "prepared" / package.folder_name).mkdir(parents=True)
        (root / "source" / "source.txt").write_bytes(package.source_bytes)
        (root / "prepared" / package.folder_name / package.item.name).write_bytes(
            package.item.authored.payload
        )
        (root / "manifest.json").write_bytes(
            json.dumps(package.manifest_dict(), ensure_ascii=False, indent=2).encode("utf-8")
            + b"\n"
        )
    except FileExistsError as exc:
        raise PreparedPackageError(f"refusing to overwrite existing output {root}") from exc
    except OSError as exc:
        raise PreparedPackageError(f"could not export offline package {root}: {exc}") from exc
    return root


__all__ = [
    "METADATA_RECORD_SIZE",
    "NATIVE_TEXT_FIELD_14",
    "NATIVE_TEXT_PREFIX_LENGTH",
    "PREPARED_PACKAGE_CONFIRMATION",
    "PREPARED_PACKAGE_FORMAT",
    "PreparedPackageError",
    "PreparedTextItem",
    "PreparedTextPackage",
    "build_prepared_text_package",
    "export_prepared_text_package",
]
