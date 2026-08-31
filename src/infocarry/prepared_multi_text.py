"""Offline logical model for an ordered package with multiple TXT children.

This extends the proven strict text-authoring boundary without extending the
device transaction model.  The package is source-bound and deterministic, but
its multi-record device candidate remains blocked until independent native
evidence supports the required folder/child construction and state handling.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Optional

from .offline_conversion import load_utf8_text_document
from .prepared_package import (
    METADATA_RECORD_SIZE,
    NATIVE_TEXT_PREFIX_LENGTH,
    PreparedPackageError,
    _align4,
    _canonical_json,
    _validate_component,
)
from .text_authoring import EncodedText, TextAuthoringError, encode_cp932_text


PREPARED_MULTI_TEXT_PACKAGE_FORMAT = "infocarry-prepared-multiple-text-package-v1"
PREPARED_MULTI_TEXT_CONFIRMATION = "OFFLINE PREPARATION ONLY — NO DEVICE CHANGE"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class PreparedTextSourceItem:
    """One source-bound, ordered TXT child in a logical package."""

    source_path: Path
    name: str
    source_bytes: bytes
    source_text: str
    authored: EncodedText

    def __post_init__(self) -> None:
        if not isinstance(self.source_path, Path):
            raise PreparedPackageError("source_path must be a Path")
        if self.source_path.suffix.lower() != ".txt":
            raise PreparedPackageError("each source must be a .txt file")
        if not isinstance(self.source_bytes, bytes):
            raise PreparedPackageError("source_bytes must be bytes")
        if not isinstance(self.source_text, str):
            raise PreparedPackageError("source_text must be a string")
        if self.source_bytes != self.source_text.encode("utf-8"):
            raise PreparedPackageError("source bytes do not match strict UTF-8 source text")
        if not isinstance(self.authored, EncodedText):
            raise PreparedPackageError("authored value must be EncodedText")
        _validate_component(self.name, label="item name", extension=".txt")

    @property
    def source_sha256(self) -> str:
        return _sha256(self.source_bytes)

    @property
    def kind(self) -> str:
        return "txt"

    @property
    def payload_sha256(self) -> str:
        return _sha256(self.authored.payload)

    @property
    def aligned_content_bytes(self) -> int:
        return _align4(NATIVE_TEXT_PREFIX_LENGTH + len(self.authored.payload))

    def to_dict(self, order: int, folder_path: str) -> dict[str, Any]:
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
                "encoding": "utf-8",
                "strict": True,
                "utf8_bytes": len(self.source_bytes),
                "characters": len(self.source_text),
            },
            "authoring": {
                "source_encoding": "utf-8",
                "prepared_encoding": "cp932",
                "newline_policy": "crlf",
                "source_characters": len(self.authored.original_text),
                "normalized_characters": len(self.authored.normalized_text),
                "prepared_payload_bytes": len(self.authored.payload),
                "prepared_payload_sha256": self.payload_sha256,
                "unsupported_characters_replaced": False,
                "embedded_nul_rejected": True,
            },
            "native_wrapper": {
                "required": True,
                "length_bytes": NATIVE_TEXT_PREFIX_LENGTH,
                "field_14": "0x00000200",
                "bytes_included": False,
                "source": "existing validated TXT record template required",
            },
        }


@dataclass(frozen=True)
class PreparedTextPackageSet:
    """An ordered, source-bound multi-TXT package with no device bytes."""

    folder_name: str
    items: tuple[PreparedTextSourceItem, ...]

    def __post_init__(self) -> None:
        _validate_component(self.folder_name, label="folder name")
        if not isinstance(self.items, tuple) or len(self.items) < 2:
            raise PreparedPackageError("multiple-TXT package must contain at least two children")
        names = [item.name.casefold() for item in self.items]
        if len(set(names)) != len(names):
            raise PreparedPackageError("prepared item names must be unique case-insensitively")
        source_paths = [item.source_path for item in self.items]
        if len(set(source_paths)) != len(source_paths):
            raise PreparedPackageError("source paths must be unique")
        if any(not isinstance(item, PreparedTextSourceItem) for item in self.items):
            raise PreparedPackageError("items must contain PreparedTextSourceItem values")

    @property
    def target_folder_path(self) -> str:
        return f"root\\{self.folder_name}"

    @property
    def target_item_paths(self) -> tuple[str, ...]:
        return tuple(f"{self.target_folder_path}\\{item.name}" for item in self.items)

    @property
    def minimum_metadata_records(self) -> int:
        # Directory + observed leading parent marker + one record per child.
        # This is a logical lower bound, not a native candidate construction.
        return len(self.items) + 2

    @property
    def aligned_content_bytes(self) -> int:
        return sum(item.aligned_content_bytes for item in self.items)

    @property
    def prepared_payload_bytes(self) -> int:
        return sum(len(item.authored.payload) for item in self.items)

    @property
    def estimated_growth_lower_bound(self) -> int:
        return self.minimum_metadata_records * METADATA_RECORD_SIZE + self.aligned_content_bytes

    def manifest_dict(self) -> dict[str, Any]:
        manifest: dict[str, Any] = {
            "format": PREPARED_MULTI_TEXT_PACKAGE_FORMAT,
            "state": "prepared_offline",
            "device_change": "none",
            "usb_accessed": False,
            "notice": PREPARED_MULTI_TEXT_CONFIRMATION,
            "target": {
                "folder_name": self.folder_name,
                "folder_path": self.target_folder_path,
                "item_paths": list(self.target_item_paths),
                "root_level": True,
                "ordered_children": True,
            },
            "items": [
                item.to_dict(index, self.target_folder_path)
                for index, item in enumerate(self.items)
            ],
            "size": {
                "metadata_record_size": METADATA_RECORD_SIZE,
                "minimum_metadata_records": self.minimum_metadata_records,
                "minimum_metadata_bytes": self.minimum_metadata_records * METADATA_RECORD_SIZE,
                "native_wrapper_bytes_required": len(self.items) * NATIVE_TEXT_PREFIX_LENGTH,
                "prepared_payload_bytes": self.prepared_payload_bytes,
                "aligned_content_bytes": self.aligned_content_bytes,
                "estimated_growth_lower_bound": self.estimated_growth_lower_bound,
                "exact_device_growth_known": False,
                "capacity_result": "not_evaluated_without_verified_backup",
            },
            "compatibility": {
                "preparation": "ready",
                "ordered_multiple_txt": "ready_offline",
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
        manifest["prepared_manifest_sha256"] = _sha256(_canonical_json(manifest))
        return manifest

    @property
    def prepared_manifest_sha256(self) -> str:
        return self.manifest_dict()["prepared_manifest_sha256"]


def _load_source(path: Path, item_name: str) -> PreparedTextSourceItem:
    resolved = Path(path).expanduser().resolve()
    if resolved.suffix.lower() != ".txt":
        raise PreparedPackageError(f"source path must name a .txt file: {resolved}")
    _validate_component(item_name, label="item name", extension=".txt")
    try:
        source_bytes = resolved.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        authored = encode_cp932_text(source_text)
        load_utf8_text_document(resolved)
    except Exception as exc:
        if isinstance(exc, PreparedPackageError):
            raise
        raise PreparedPackageError(
            f"source TXT failed strict UTF-8/CP932 preparation: {resolved}: {exc}"
        ) from exc
    return PreparedTextSourceItem(resolved, item_name, source_bytes, source_text, authored)


def build_prepared_text_package_set(
    sources: Iterable[tuple[Path, str]],
    folder_name: str,
) -> PreparedTextPackageSet:
    """Prepare at least two ordered UTF-8 TXT sources without USB access."""

    if isinstance(sources, (str, bytes)):
        raise PreparedPackageError("sources must be an ordered iterable of (Path, child_name) pairs")
    try:
        source_specs = list(sources)
    except TypeError as exc:
        raise PreparedPackageError("sources must be an ordered iterable") from exc
    if len(source_specs) < 2:
        raise PreparedPackageError("multiple-TXT package must contain at least two sources")
    items: list[PreparedTextSourceItem] = []
    for spec in source_specs:
        if not isinstance(spec, (tuple, list)) or len(spec) != 2:
            raise PreparedPackageError("each source must be a (Path, child_name) pair")
        items.append(_load_source(Path(spec[0]), spec[1]))
    return PreparedTextPackageSet(folder_name, tuple(items))


def export_prepared_text_package_set(
    package: PreparedTextPackageSet,
    destination: Path,
) -> Path:
    """Export source copies and prepared children to a new directory only."""

    if not isinstance(package, PreparedTextPackageSet):
        raise PreparedPackageError("package must be a PreparedTextPackageSet")
    root = Path(destination).expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=False)
        source_root = root / "source"
        prepared_root = root / "prepared" / package.folder_name
        source_root.mkdir()
        prepared_root.mkdir(parents=True)
        for index, item in enumerate(package.items, start=1):
            (source_root / f"{index:04d}_{item.source_path.name}").write_bytes(item.source_bytes)
            (prepared_root / item.name).write_bytes(item.authored.payload)
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
    "PREPARED_MULTI_TEXT_CONFIRMATION",
    "PREPARED_MULTI_TEXT_PACKAGE_FORMAT",
    "PreparedTextPackageSet",
    "PreparedTextSourceItem",
    "build_prepared_text_package_set",
    "export_prepared_text_package_set",
]
