"""Offline Prepare workflow for one supported local Library TXT item.

This module binds the Library catalog to the existing PreparedTextPackage
authoring boundary. It deliberately stops at an offline package and audit:
there is no USB callback, device candidate, authorization, or transfer path.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Optional

from .capability_profile import (
    HIERARCHICAL_OFFLINE_PROFILE_ID,
    hierarchical_offline_capability_profile,
)

from .library import (
    PREPARATION_BLOCKED,
    PREPARATION_PREPARED,
    STATE_BLOCKED,
    STATE_IMPORTED,
    STATE_READY,
    LibraryCatalog,
    LibraryError,
    LibraryItem,
    NODE_FILE,
    NODE_FOLDER,
)
from .prepared_package import (
    PREPARED_PACKAGE_CONFIRMATION,
    PreparedPackageError,
    PreparedTextPackage,
    build_prepared_text_package,
)
from .prepared_media_package import PreparedMediaPackageError, validate_bmp_payload
from .text_authoring import TextAuthoringError, encode_cp932_text


HIERARCHICAL_PREPARED_MANIFEST_FORMAT = "infocarry-prepared-library-hierarchy-v1"
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class LibraryPreparationError(LibraryError):
    """Raised when a Library item cannot be prepared safely offline."""


@dataclass(frozen=True)
class LibraryPreparationResult:
    """Prepared package and user-visible audit for one Library item."""

    item: LibraryItem
    package: PreparedTextPackage
    audit: Mapping[str, Any]


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(child) for child in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw(child) for child in value]
    return value


@dataclass(frozen=True)
class PreparedLibraryHierarchy:
    """Deterministic strict TXT/BMP hierarchy prepared for offline preview."""

    manifest: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, Mapping):
            raise LibraryPreparationError("prepared hierarchy manifest must be an object")
        value = _thaw(self.manifest)
        required = {
            "format",
            "version",
            "profile_id",
            "profile_sha256",
            "status",
            "root_item_id",
            "nodes",
            "totals",
            "capacity",
            "safety",
            "prepared_manifest_sha256",
        }
        if set(value) != required:
            raise LibraryPreparationError("prepared hierarchy manifest schema differs")
        profile = hierarchical_offline_capability_profile()
        if value["format"] != HIERARCHICAL_PREPARED_MANIFEST_FORMAT:
            raise LibraryPreparationError("prepared hierarchy manifest format is unsupported")
        if value["version"] != 1 or value["profile_id"] != HIERARCHICAL_OFFLINE_PROFILE_ID:
            raise LibraryPreparationError("prepared hierarchy manifest profile/version is unsupported")
        if value["profile_sha256"] != profile.sha256:
            raise LibraryPreparationError("prepared hierarchy profile hash differs")
        if value["status"] != "prepared_offline":
            raise LibraryPreparationError("prepared hierarchy manifest is not prepared offline")
        nodes = value["nodes"]
        if not isinstance(nodes, list) or not nodes:
            raise LibraryPreparationError("prepared hierarchy ordered nodes are missing")
        try:
            validated = profile.validate_hierarchy(nodes)
        except Exception as exc:
            raise LibraryPreparationError(str(exc)) from exc
        if value["root_item_id"] != nodes[0].get("node_id"):
            raise LibraryPreparationError("prepared hierarchy root identity differs")
        expected_totals = {
            "logical_nodes": len(validated),
            "leaf_items": sum(node["kind"] != "folder" for node in validated),
            "directory_nodes": sum(node["kind"] == "folder" for node in validated),
            "source_bytes": sum(node["source_bytes"] for node in validated),
            "prepared_payload_bytes": sum(node["prepared_payload_bytes"] for node in validated),
        }
        if value["totals"] != expected_totals:
            raise LibraryPreparationError("prepared hierarchy totals differ from ordered nodes")
        expected_capacity = {
            "total_model_limit_bytes": "not_evaluated",
            "fresh_baseline_model_length_bytes": "not_evaluated",
            "candidate_growth_bytes": "not_evaluated",
            "remaining_after_transfer_bytes": "not_evaluated",
        }
        if value["capacity"] != expected_capacity:
            raise LibraryPreparationError("prepared hierarchy capacity must remain not evaluated")
        if value["safety"] != {
            "usb_accessed": False,
            "device_change": "none",
            "candidate_constructed": False,
            "live_enabled": False,
        }:
            raise LibraryPreparationError("prepared hierarchy safety envelope is invalid")
        expected = value.get("prepared_manifest_sha256")
        unsigned = dict(value)
        unsigned.pop("prepared_manifest_sha256", None)
        actual = hashlib.sha256(_canonical_json(unsigned)).hexdigest()
        if expected != actual:
            raise LibraryPreparationError("prepared hierarchy manifest hash is inconsistent")
        object.__setattr__(self, "manifest", _freeze(value))

    @property
    def prepared_manifest_sha256(self) -> str:
        return str(self.manifest["prepared_manifest_sha256"])

    @property
    def nodes(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.manifest["nodes"])

    def to_dict(self) -> dict[str, Any]:
        return _thaw(self.manifest)


def prepare_library_hierarchy(
    catalog: LibraryCatalog,
    item_id: str,
) -> PreparedLibraryHierarchy:
    """Prepare exactly one selected Library root and its descendants offline."""

    root = catalog.get(item_id)
    profile = hierarchical_offline_capability_profile()
    prepared_nodes: list[dict[str, Any]] = []
    total_source = 0
    total_prepared = 0

    def prepare_node(
        item: LibraryItem,
        parent_id: Optional[str],
        order: int,
        parent_path: str,
    ) -> None:
        nonlocal total_source, total_prepared
        destination = f"{parent_path}\\{item.source_filename}"
        if item.node_kind == NODE_FOLDER:
            source_path = Path(item.source_path)
            if not source_path.is_dir() or source_path.is_symlink():
                raise LibraryPreparationError(
                    f"folder source is missing, changed, or symbolic: {source_path}"
                )
            children = catalog.children(item.item_id)
            try:
                actual_names = sorted(
                    (entry.name for entry in source_path.iterdir()),
                    key=lambda name: name.encode("utf-8", "surrogatepass"),
                )
            except OSError as exc:
                raise LibraryPreparationError(f"cannot inspect folder source: {source_path}") from exc
            recorded_names = sorted(
                (child.source_filename for child in children),
                key=lambda name: name.encode("utf-8", "surrogatepass"),
            )
            if actual_names != recorded_names:
                raise LibraryPreparationError(
                    f"folder contents changed since import: {source_path}"
                )
            prepared_nodes.append(
                {
                    "node_id": item.item_id,
                    "parent_id": parent_id,
                    "order": order,
                    "kind": "folder",
                    "name": item.source_filename,
                    "path": destination,
                    "source_sha256": _EMPTY_SHA256,
                    "prepared_payload_sha256": _EMPTY_SHA256,
                    "source_bytes": 0,
                    "prepared_payload_bytes": 0,
                    "validation": "passed",
                }
            )
            for child_order, child in enumerate(children):
                prepare_node(child, item.item_id, child_order, destination)
            return
        if item.node_kind != NODE_FILE:
            raise LibraryPreparationError(
                "legacy prepared-package entries use the preserved flat review path"
            )
        if not item.supported or item.last_validation_error:
            raise LibraryPreparationError(
                f"unsupported or invalid source {item.source_filename}: "
                f"{item.last_validation_error or item.detected_format}"
            )
        source_path = Path(item.source_path)
        if source_path.is_symlink() or not source_path.is_file():
            raise LibraryPreparationError(
                f"source is missing, non-regular, or symbolic: {source_path}"
            )
        try:
            source_bytes = source_path.read_bytes()
        except OSError as exc:
            raise LibraryPreparationError(f"cannot read source file: {source_path}") from exc
        source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        if source_sha256 != item.source_sha256:
            raise LibraryPreparationError(
                f"source changed since import: {item.source_filename}"
            )
        suffix = source_path.suffix.lower()
        try:
            if suffix == ".txt":
                source_text = source_bytes.decode("utf-8", errors="strict")
                prepared_bytes = encode_cp932_text(source_text).payload
                kind = "txt"
            elif suffix == ".bmp":
                validate_bmp_payload(source_bytes)
                prepared_bytes = source_bytes
                kind = "bmp"
            else:
                raise LibraryPreparationError(
                    f"unsupported source type: {item.source_filename}"
                )
        except (UnicodeDecodeError, TextAuthoringError, PreparedMediaPackageError) as exc:
            raise LibraryPreparationError(
                f"strict preparation failed for {item.source_filename}: {exc}"
            ) from exc
        total_source += len(source_bytes)
        total_prepared += len(prepared_bytes)
        prepared_nodes.append(
            {
                "node_id": item.item_id,
                "parent_id": parent_id,
                "order": order,
                "kind": kind,
                "name": item.source_filename,
                "path": destination,
                "source_sha256": source_sha256,
                "prepared_payload_sha256": hashlib.sha256(prepared_bytes).hexdigest(),
                "source_bytes": len(source_bytes),
                "prepared_payload_bytes": len(prepared_bytes),
                "validation": "passed",
            }
        )

    prepare_node(root, None, 0, "root")
    try:
        validated = profile.validate_hierarchy(prepared_nodes)
    except Exception as exc:
        raise LibraryPreparationError(str(exc)) from exc
    manifest: dict[str, Any] = {
        "format": HIERARCHICAL_PREPARED_MANIFEST_FORMAT,
        "version": 1,
        "profile_id": profile.profile_id,
        "profile_sha256": profile.sha256,
        "status": "prepared_offline",
        "root_item_id": root.item_id,
        "nodes": [dict(node) for node in validated],
        "totals": {
            "logical_nodes": len(validated),
            "leaf_items": sum(node["kind"] != "folder" for node in validated),
            "directory_nodes": sum(node["kind"] == "folder" for node in validated),
            "source_bytes": total_source,
            "prepared_payload_bytes": total_prepared,
        },
        "capacity": {
            "total_model_limit_bytes": "not_evaluated",
            "fresh_baseline_model_length_bytes": "not_evaluated",
            "candidate_growth_bytes": "not_evaluated",
            "remaining_after_transfer_bytes": "not_evaluated",
        },
        "safety": {
            "usb_accessed": False,
            "device_change": "none",
            "candidate_constructed": False,
            "live_enabled": False,
        },
    }
    manifest["prepared_manifest_sha256"] = hashlib.sha256(
        _canonical_json(manifest)
    ).hexdigest()
    return PreparedLibraryHierarchy(manifest)


def _blocked_item(
    catalog: LibraryCatalog,
    item: LibraryItem,
    message: str,
    *,
    folder_name: Optional[str],
    child_name: Optional[str],
) -> None:
    catalog.update_preparation(
        item.item_id,
        preparation_state=PREPARATION_BLOCKED,
        state=STATE_BLOCKED,
        target_folder_name=folder_name,
        target_child_name=child_name,
        prepared_manifest_sha256=None,
        prepared_manifest_path=None,
        last_validation_error=message,
    )


def prepare_library_item(
    catalog: LibraryCatalog,
    item_id: str,
    folder_name: str,
    child_name: str,
    *,
    now: Optional[str] = None,
) -> LibraryPreparationResult:
    """Prepare one current Library TXT source without any device operation."""

    item = catalog.get(item_id)
    try:
        item = catalog.refresh(item_id, now=now)
    except LibraryError as exc:
        raise LibraryPreparationError(str(exc)) from exc

    if not item.supported or item.detected_format != "utf-8-txt":
        message = "Library item is unsupported; only UTF-8 .txt preparation is supported"
        _blocked_item(
            catalog,
            item,
            message,
            folder_name=folder_name,
            child_name=child_name,
        )
        raise LibraryPreparationError(message)
    if item.state not in {STATE_IMPORTED, STATE_READY, STATE_BLOCKED} or item.source_status != "present":
        message = item.last_validation_error or "Library source is not current and ready for preparation"
        _blocked_item(
            catalog,
            item,
            message,
            folder_name=folder_name,
            child_name=child_name,
        )
        raise LibraryPreparationError(message)

    try:
        package = build_prepared_text_package(
            Path(item.source_path),
            folder_name,
            child_name,
        )
    except PreparedPackageError as exc:
        message = str(exc)
        _blocked_item(
            catalog,
            item,
            message,
            folder_name=folder_name,
            child_name=child_name,
        )
        raise LibraryPreparationError(message) from exc

    if package.source_sha256 != item.source_sha256:
        message = "source changed during offline preparation; no package was accepted"
        _blocked_item(
            catalog,
            item,
            message,
            folder_name=folder_name,
            child_name=child_name,
        )
        raise LibraryPreparationError(message)

    updated = catalog.update_preparation(
        item.item_id,
        preparation_state=PREPARATION_PREPARED,
        state=STATE_READY,
        target_folder_name=package.folder_name,
        target_child_name=package.item.name,
        prepared_manifest_sha256=package.prepared_manifest_sha256,
        prepared_manifest_path=None,
        last_validation_error=None,
    )
    manifest = package.manifest_dict()
    audit = {
        "operation": "offline_library_prepare",
        "device_operation": "none",
        "usb_accessed": False,
        "notice": PREPARED_PACKAGE_CONFIRMATION,
        "item_id": updated.item_id,
        "source": {
            "path": updated.source_path,
            "filename": updated.source_filename,
            "sha256": updated.source_sha256,
            "utf8_bytes": len(package.source_bytes),
            "source_characters": len(package.source_text),
        },
        "prepared": {
            "manifest_sha256": package.prepared_manifest_sha256,
            "folder_path": package.target_folder_path,
            "child_path": package.target_item_path,
            "encoded_payload_bytes": package.prepared_payload_bytes,
            "aligned_content_bytes": package.aligned_content_bytes,
            "estimated_growth_lower_bound": package.estimated_growth_lower_bound,
            "compatibility": manifest["compatibility"],
        },
    }
    return LibraryPreparationResult(item=updated, package=package, audit=audit)


__all__ = [
    "HIERARCHICAL_PREPARED_MANIFEST_FORMAT",
    "LibraryPreparationError",
    "LibraryPreparationResult",
    "PreparedLibraryHierarchy",
    "prepare_library_item",
    "prepare_library_hierarchy",
]
