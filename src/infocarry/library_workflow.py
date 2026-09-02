"""Framework-independent Select -> Arrange -> Prepare -> Preview workflow.

This host-only service binds the persistent ordered Library tree to the P18-002
capability/facade model.  It imports no GUI, USB, candidate builder, live
adapter, authorization, or sender code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional

from .capability_profile import hierarchical_offline_capability_profile
from .device_model_profile import VNW_V15_PROFILE
from .library import LibraryCatalog, LibraryError, LibraryItem
from .library_prepare import PreparedLibraryHierarchy, prepare_library_hierarchy
from .transfer_foundation import PreparedItem, TransferFoundation


EXTERNAL_FILE_DROP_STATUS = "unavailable_without_optional_tkdnd_adapter"


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
class LibraryWorkflowPreview:
    prepared: PreparedLibraryHierarchy
    foundation: TransferFoundation
    device_tree: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "device_tree", _freeze(self.device_tree))

    def to_dict(self) -> dict[str, Any]:
        return {
            "prepared_manifest": self.prepared.to_dict(),
            "foundation": self.foundation.to_dict(),
            "device_tree_preview": _thaw(self.device_tree),
            "drag_and_drop": {
                "status": EXTERNAL_FILE_DROP_STATUS,
                "chooser_import_available": True,
            },
        }


class LibraryWorkflowService:
    """Small application service shared by chooser/GUI/test adapters."""

    def __init__(self, catalog: LibraryCatalog) -> None:
        if not isinstance(catalog, LibraryCatalog):
            raise TypeError("catalog must be a LibraryCatalog")
        self.catalog = catalog

    def import_files(self, paths: Iterable[Path]) -> tuple[LibraryItem, ...]:
        return self.catalog.import_files(paths)

    def import_folder(self, path: Path) -> LibraryItem:
        return self.catalog.import_folder(path)

    def remove(self, item_id: str) -> bool:
        return self.catalog.remove(item_id)

    def can_move_up(self, item_id: str) -> bool:
        item = self.catalog.get(item_id)
        siblings = self.catalog.children(item.parent_id)
        return bool(siblings and siblings[0].item_id != item_id)

    def can_move_down(self, item_id: str) -> bool:
        item = self.catalog.get(item_id)
        siblings = self.catalog.children(item.parent_id)
        return bool(siblings and siblings[-1].item_id != item_id)

    def move_up(self, item_id: str) -> LibraryItem:
        return self.catalog.move_up(item_id)

    def move_down(self, item_id: str) -> LibraryItem:
        return self.catalog.move_down(item_id)

    def prepare_preview(
        self,
        item_id: str,
        *,
        existing_paths: Optional[Iterable[str]] = None,
    ) -> LibraryWorkflowPreview:
        prepared = prepare_library_hierarchy(self.catalog, item_id)
        item = PreparedItem.from_hierarchy_manifest(prepared.to_dict())
        foundation = TransferFoundation.from_prepared_items(
            (item,),
            profile=hierarchical_offline_capability_profile(),
            device_model_profile=VNW_V15_PROFILE,
        )
        preview = foundation.plan.preview(
            existing_paths=(None if existing_paths is None else tuple(existing_paths))
        )
        return LibraryWorkflowPreview(prepared, foundation, preview)


__all__ = [
    "EXTERNAL_FILE_DROP_STATUS",
    "LibraryWorkflowPreview",
    "LibraryWorkflowService",
]
