"""Framework-independent Select -> Arrange -> Prepare -> Preview workflow.

This host-only service binds the persistent ordered Library tree to the P18-002
capability/facade model.  It imports no GUI, USB, candidate builder, live
adapter, authorization, or sender code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
import threading
from typing import Any, Callable, Iterable, Mapping, Optional

from .capability_profile import hierarchical_offline_capability_profile
from .device_model_profile import VNW_V15_PROFILE
from .content_workspace import (
    ContentWorkspace,
    ContentWorkspaceCancelled,
    ContentWorkspaceError,
    ContentWorkspaceResult,
    ContentWorkspaceSettings,
    PreparedContentResult,
)
from .library import (
    PREPARATION_BLOCKED,
    PREPARATION_PREPARED,
    STATE_BLOCKED,
    STATE_READY,
    LibraryCatalog,
    LibraryError,
    LibraryItem,
    NODE_FOLDER,
    SUPPORTED_EPUB_FORMAT,
)
from .library_prepare import (
    LibraryPreparationError,
    PreparedLibraryHierarchy,
    prepare_library_hierarchy,
)
from .prepared_content import PreparedContentArtifact
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
    prepared: Any
    foundation: Any
    device_tree: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "device_tree", _freeze(self.device_tree))

    @property
    def artifact(self) -> PreparedContentArtifact:
        artifact = getattr(self.prepared, "artifact", None)
        if not isinstance(artifact, PreparedContentArtifact):
            raise ValueError("workflow preview does not carry a canonical artifact")
        return artifact

    def to_dict(self) -> dict[str, Any]:
        return {
            "prepared_manifest": self.prepared.to_dict(),
            "prepared_content_artifact": self.artifact.to_dict(),
            "foundation": self.foundation.to_dict(),
            "device_tree_preview": _thaw(self.device_tree),
            "drag_and_drop": {
                "status": EXTERNAL_FILE_DROP_STATUS,
                "chooser_import_available": True,
            },
        }


@dataclass(frozen=True)
class HostOnlyTransferPreview:
    """EPUB preview record without candidate or authorization attachment APIs."""

    plan: Any
    _report: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return _thaw(self._report)


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
        settings: Optional[ContentWorkspaceSettings] = None,
        cancel_event: Optional[threading.Event] = None,
        progress: Optional[Callable[[str, Optional[int], Optional[int]], None]] = None,
    ) -> LibraryWorkflowPreview:
        if cancel_event is not None and cancel_event.is_set():
            raise ContentWorkspaceCancelled("content preparation was cancelled")
        if progress is not None:
            progress("Refreshing source")
        try:
            current = self.catalog.refresh(item_id)
        except LibraryError as exc:
            raise LibraryPreparationError(str(exc)) from exc
        if current.source_status != "present":
            raise LibraryPreparationError(
                current.last_validation_error or "Library source is not current and present"
            )

        is_epub = False
        if current.node_kind == NODE_FOLDER:
            if progress is not None:
                progress("Preparing folder hierarchy")
            prepared: Any = prepare_library_hierarchy(self.catalog, item_id)
            artifact = prepared.artifact
            preparation_manifest = prepared.prepared_manifest_sha256
            target_child_name = None
        else:
            is_epub = current.detected_format == SUPPORTED_EPUB_FORMAT
            workspace = ContentWorkspace()
            workspace_settings = settings or ContentWorkspaceSettings(
                root_name=current.target_folder_name or None
            )
            try:
                if (
                    settings is None
                    and current.package is None
                    and current.prepared_artifact is not None
                    and not is_epub
                ):
                    prepared = workspace.preview_existing_artifact(
                        Path(current.source_path),
                        PreparedContentArtifact.from_dict(current.prepared_artifact),
                        metadata=current.prepared_metadata,
                    )
                    if progress is not None:
                        progress("Loaded current prepared content")
                else:
                    prepared = workspace.prepare(
                        Path(current.source_path),
                        settings=workspace_settings,
                        cancel_event=cancel_event,
                        progress=progress,
                    )
            except (ContentWorkspaceError, ValueError) as exc:
                if (
                    not isinstance(exc, ContentWorkspaceCancelled)
                    and current.package is None
                    and current.supported
                ):
                    self.catalog.update_preparation(
                        current.item_id,
                        preparation_state=PREPARATION_BLOCKED,
                        state=STATE_BLOCKED,
                        target_folder_name=current.target_folder_name,
                        target_child_name=current.target_child_name,
                        prepared_manifest_sha256=None,
                        prepared_manifest_path=None,
                        last_validation_error=str(exc),
                    )
                raise LibraryPreparationError(str(exc)) from exc
            artifact = prepared.artifact
            preparation_manifest = (
                current.prepared_manifest_sha256
                if current.package is not None and current.prepared_manifest_sha256 is not None
                else artifact.artifact_identity
            )
            target_child_name = artifact.children[0].name if len(artifact.children) == 1 else None

        if cancel_event is not None and cancel_event.is_set():
            raise ContentWorkspaceCancelled("content preparation was cancelled")

        if current.package is None:
            updated = self.catalog.update_preparation(
                current.item_id,
                preparation_state=PREPARATION_PREPARED,
                state=STATE_READY,
                target_folder_name=artifact.root_name,
                target_child_name=target_child_name,
                prepared_manifest_sha256=preparation_manifest,
                prepared_manifest_path=None,
                last_validation_error=None,
                prepared_artifact=artifact.to_dict(),
                prepared_metadata=(
                    {
                        **dict(prepared.preparation_metadata),
                        "canonical_artifact_identity": artifact.artifact_identity,
                    }
                    if isinstance(prepared, (ContentWorkspaceResult, PreparedContentResult))
                    and hasattr(prepared, "preparation_metadata")
                    else {
                        "compatibility_adapter": (
                            "ContentWorkspace EPUB preparation"
                            if isinstance(prepared, PreparedContentResult)
                            else "LibraryCatalog + prepare_library_hierarchy"
                        ),
                        "hierarchy_profile": (
                            None
                            if isinstance(prepared, PreparedContentResult)
                            else "host-offline-hierarchical-library-txt-bmp-v1"
                        ),
                        **(
                            dict(prepared.report())
                            if isinstance(prepared, PreparedContentResult)
                            else {}
                        ),
                        "canonical_artifact_identity": artifact.artifact_identity,
                    }
                ),
            )
            current = updated

        grouping_contract = (
            "explicit_prepared_package"
            if current.package is not None or current.detected_format == SUPPORTED_EPUB_FORMAT
            else "explicit_prepared_hierarchy"
        )
        item = PreparedItem.from_prepared_content(
            artifact,
            library_item_id=(
                prepared.manifest["root_item_id"]
                if isinstance(prepared, PreparedLibraryHierarchy)
                else current.item_id
            ),
            package_manifest_sha256=preparation_manifest,
            grouping_contract=grouping_contract,
        )
        foundation = TransferFoundation.from_prepared_items(
            (item,),
            profile=(
                hierarchical_offline_capability_profile()
                if grouping_contract == "explicit_prepared_hierarchy"
                else None
            ),
            device_model_profile=VNW_V15_PROFILE,
        )
        if is_epub:
            foundation = HostOnlyTransferPreview(
                plan=foundation.plan,
                _report={
                    **foundation.to_dict(),
                    "host_only": True,
                    "candidate_attachment": "unavailable",
                    "authorization_attachment": "unavailable",
                },
            )
        preview = foundation.plan.preview(
            existing_paths=(None if existing_paths is None else tuple(existing_paths))
        )
        return LibraryWorkflowPreview(prepared, foundation, preview)


__all__ = [
    "EXTERNAL_FILE_DROP_STATUS",
    "HostOnlyTransferPreview",
    "LibraryWorkflowPreview",
    "LibraryWorkflowService",
]
