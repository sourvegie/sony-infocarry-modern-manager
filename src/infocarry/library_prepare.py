"""Offline Prepare workflow for one supported local Library TXT item.

This module binds the Library catalog to the existing PreparedTextPackage
authoring boundary. It deliberately stops at an offline package and audit:
there is no USB callback, device candidate, authorization, or transfer path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from .library import (
    PREPARATION_BLOCKED,
    PREPARATION_PREPARED,
    STATE_BLOCKED,
    STATE_IMPORTED,
    STATE_READY,
    LibraryCatalog,
    LibraryError,
    LibraryItem,
)
from .prepared_package import (
    PREPARED_PACKAGE_CONFIRMATION,
    PreparedPackageError,
    PreparedTextPackage,
    build_prepared_text_package,
)


class LibraryPreparationError(LibraryError):
    """Raised when a Library item cannot be prepared safely offline."""


@dataclass(frozen=True)
class LibraryPreparationResult:
    """Prepared package and user-visible audit for one Library item."""

    item: LibraryItem
    package: PreparedTextPackage
    audit: Mapping[str, Any]


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
    "LibraryPreparationError",
    "LibraryPreparationResult",
    "prepare_library_item",
]
