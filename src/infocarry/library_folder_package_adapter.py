"""Transient adapter for exact flat Local Library folders.

This module only translates a folder already admitted by the host-only
logical planner into the existing prepared-package contract. It does not
construct device candidates, authorize operations, or transmit anything.
"""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Optional

from .capability_profile import (
    INITIAL_EXPERIMENTAL_PROFILE_ID,
    VNW_V15_FOUR_LEAF_PROFILE_ID,
)
from .execution_profile import guarded_execution_profile
from .library import (
    NODE_FILE,
    NODE_FOLDER,
    NODE_PREPARED_PACKAGE,
    PREPARATION_PREPARED,
    SOURCE_PRESENT,
    STATE_IMPORTED,
    STATE_READY,
    LibraryCatalog,
    LibraryItem,
    LibraryPackageReference,
)
from .library_device_transfer import LibraryDeviceTransferPlan
from .prepared_content import PreparedContentArtifact
from .prepared_media_package import (
    PreparedMediaPackageError,
    PreparedTextSourceItem,
    build_prepared_media_package,
    export_prepared_media_package,
    load_prepared_media_package,
)
from .transfer_shape import EXACT_VERIFIED_LIVE_PROFILE, assess_transfer_shape


class LibraryFolderPackageAdapterError(ValueError):
    """An otherwise exact folder changed while its transient package was built."""


OPERATION_STAGING_BINDING_FORMAT = "infocarry-p18-037-operation-owned-package-v1"


@dataclass
class LibraryFolderPackageStage:
    """An operation-scoped package view; never saved to the user catalog."""

    catalog: LibraryCatalog
    item: LibraryItem
    artifact: PreparedContentArtifact
    source_folder: Path
    source_bindings: tuple[tuple[Path, str, int], ...]
    _temporary_directory: tempfile.TemporaryDirectory
    operation_owned_root: Optional[Path] = None
    operation_binding_path: Optional[Path] = None

    def verify_source_bindings(self) -> None:
        """Reject original-source drift before entering live preflight."""

        if self.source_folder.is_symlink() or not self.source_folder.is_dir():
            raise LibraryFolderPackageAdapterError(
                "The selected Local Library folder changed after it was planned"
            )
        try:
            entries = tuple(self.source_folder.iterdir())
            payloads = tuple(
                (path, path.read_bytes()) for path, _digest, _size in self.source_bindings
            )
        except OSError as exc:
            raise LibraryFolderPackageAdapterError(
                "A Local Library source could not be rechecked before live preflight"
            ) from exc
        expected_names = {path.name for path, _digest, _size in self.source_bindings}
        if (
            any(path.is_symlink() or not path.is_file() for path in entries)
            or {path.name for path in entries} != expected_names
        ):
            raise LibraryFolderPackageAdapterError(
                "The selected Local Library folder contents changed after planning"
            )
        for (path, expected_digest, expected_size), (observed_path, payload) in zip(
            self.source_bindings, payloads
        ):
            if (
                observed_path != path
                or len(payload) != expected_size
                or _sha256(payload) != expected_digest
            ):
                raise LibraryFolderPackageAdapterError(
                    f"Local Library source changed after planning: {path.name}"
                )

    def cleanup(self) -> None:
        """Remove only the pre-seal workspace.

        Once ``materialize_operation_artifact`` has run, the operation-owned
        copy is deliberately outside this temporary directory.  It is
        evidence required by the sealed operation and is retained for the
        operation's full lifecycle; cleanup must never remove it.
        """

        self._temporary_directory.cleanup()

    def materialize_operation_artifact(self, operation_root: Path) -> LibraryCatalog:
        """Copy the exact package into the operation-owned evidence area.

        The returned catalog is an in-memory overlay only.  The persistent
        Local Library item remains an ordinary folder and the original source
        files remain untouched.  The copy is loaded again after copying so the
        manifest, source copies, prepared payloads, hashes, and canonical
        semantic artifact identity are all checked before live preflight sees
        it.
        """

        if self.operation_owned_root is not None:
            if self.operation_owned_root.parent != Path(operation_root).expanduser().resolve():
                raise LibraryFolderPackageAdapterError(
                    "the operation-owned package was already bound to another operation"
                )
            return self.catalog

        operation_parent = Path(operation_root).expanduser().resolve()
        if operation_parent.is_symlink():
            raise LibraryFolderPackageAdapterError(
                "operation-owned evidence directory must not be a symbolic link"
            )
        operation_parent.mkdir(parents=True, exist_ok=True)
        package_root = operation_parent / "prepared-package"
        if package_root.exists() or package_root.is_symlink():
            raise LibraryFolderPackageAdapterError(
                f"refusing to reuse operation-owned prepared package: {package_root}"
            )

        source_path = Path(self.item.source_path).expanduser()
        if source_path.is_symlink() or not source_path.is_dir():
            raise LibraryFolderPackageAdapterError(
                "the transient prepared package is unavailable before sealing"
            )
        source_root = source_path.resolve()
        try:
            shutil.copytree(source_root, package_root, symlinks=False)
            imported = load_prepared_media_package(package_root)
            stable_artifact = imported.package.to_prepared_content_artifact()
            manifest_size = imported.manifest_path.stat().st_size
        except (OSError, PreparedMediaPackageError, ValueError) as exc:
            shutil.rmtree(package_root, ignore_errors=True)
            raise LibraryFolderPackageAdapterError(
                f"the operation-owned prepared package could not be verified: {exc}"
            ) from exc

        if (
            imported.manifest_sha256 != self.item.prepared_manifest_sha256
            or stable_artifact.artifact_identity != self.artifact.artifact_identity
            or imported.package.folder_name != self.item.source_filename
        ):
            shutil.rmtree(package_root, ignore_errors=True)
            raise LibraryFolderPackageAdapterError(
                "the operation-owned prepared package identity differs before sealing"
            )

        reference = LibraryPackageReference(
            format=str(imported.manifest["format"]),
            root_path=str(imported.root),
            manifest_path=str(imported.manifest_path),
            manifest_sha256=imported.manifest_sha256,
            folder_name=imported.package.folder_name,
            children=tuple(dict(child) for child in imported.children),
        )
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        observation = {
            "timestamp_utc": timestamp,
            "status": SOURCE_PRESENT,
            "sha256": imported.manifest_sha256,
            "size_bytes": manifest_size,
        }
        stable_item = replace(
            self.item,
            source_path=str(imported.root),
            source_filename=imported.package.folder_name,
            source_sha256=imported.manifest_sha256,
            source_size_bytes=manifest_size,
            detected_format="prepared-flat-package",
            supported=True,
            state=STATE_READY,
            preparation_state=PREPARATION_PREPARED,
            target_folder_name=imported.package.folder_name,
            target_child_name=None,
            prepared_manifest_sha256=imported.manifest_sha256,
            prepared_manifest_path=str(imported.manifest_path),
            source_status=SOURCE_PRESENT,
            observed_source_sha256=imported.manifest_sha256,
            observed_source_size_bytes=manifest_size,
            observed_timestamp_utc=timestamp,
            last_validation_error=None,
            source_observations=(observation,),
            package=reference,
            prepared_artifact=stable_artifact.to_dict(),
        )
        stable_catalog = copy(self.catalog)
        descendant_ids = {
            item.item_id
            for item in self.catalog._items.values()
            if item.parent_id == self.item.item_id
        }
        stable_catalog._items = {
            item_id: item
            for item_id, item in self.catalog._items.items()
            if item_id not in descendant_ids and item_id != self.item.item_id
        }
        stable_catalog._items[stable_item.item_id] = stable_item
        catalog_path = operation_parent / "library-catalog.json"
        if catalog_path.exists() or catalog_path.is_symlink():
            shutil.rmtree(package_root, ignore_errors=True)
            raise LibraryFolderPackageAdapterError(
                f"refusing to reuse operation-owned catalog: {catalog_path}"
            )
        stable_catalog.path = catalog_path
        stable_catalog.previous_path = catalog_path.with_name(
            f"{catalog_path.stem}.previous{catalog_path.suffix}"
        )
        try:
            with catalog_path.open("x", encoding="utf-8") as stream:
                json.dump(
                    stable_catalog.to_dict(),
                    stream,
                    ensure_ascii=True,
                    indent=2,
                    sort_keys=True,
                )
                stream.write("\n")
                stream.flush()
        except OSError as exc:
            shutil.rmtree(package_root, ignore_errors=True)
            raise LibraryFolderPackageAdapterError(
                f"the operation-owned catalog could not be persisted: {exc}"
            ) from exc
        self.catalog = stable_catalog
        self.item = stable_item
        self.artifact = stable_artifact
        self.operation_owned_root = package_root
        return stable_catalog

    def bind_operation_identity(
        self,
        *,
        operation_id: str,
        preflight_seal_sha256: str,
    ) -> Path:
        """Persist the seal/operation binding beside the stable package."""

        if self.operation_owned_root is None:
            raise LibraryFolderPackageAdapterError(
                "operation-owned package must be materialized before identity binding"
            )
        if self.operation_binding_path is not None:
            raise LibraryFolderPackageAdapterError(
                "operation-owned package identity is already bound"
            )
        manifest_path = self.operation_owned_root / "manifest.json"
        try:
            manifest_bytes = manifest_path.read_bytes()
        except OSError as exc:
            raise LibraryFolderPackageAdapterError(
                "the operation-owned prepared manifest is unavailable before sealing"
            ) from exc
        binding_path = self.operation_owned_root / "operation-binding.json"
        value = {
            "format": OPERATION_STAGING_BINDING_FORMAT,
            "operation_id": operation_id,
            "preflight_seal_sha256": preflight_seal_sha256,
            "package_root": str(self.operation_owned_root),
            "package_manifest_path": str(manifest_path),
            "package_manifest_file_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "prepared_manifest_sha256": self.item.prepared_manifest_sha256,
            "prepared_artifact_identity": self.artifact.artifact_identity,
        }
        try:
            with binding_path.open("x", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=True, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
        except (FileExistsError, OSError) as exc:
            raise LibraryFolderPackageAdapterError(
                f"the operation-owned identity could not be persisted: {exc}"
            ) from exc
        self.operation_binding_path = binding_path
        return binding_path


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _profile_for_kinds(kinds: tuple[str, ...]) -> Optional[str]:
    if kinds == guarded_execution_profile(INITIAL_EXPERIMENTAL_PROFILE_ID).child_kinds:
        return INITIAL_EXPERIMENTAL_PROFILE_ID
    if kinds == guarded_execution_profile(VNW_V15_FOUR_LEAF_PROFILE_ID).child_kinds:
        return VNW_V15_FOUR_LEAF_PROFILE_ID
    return None


def _folder_plan_matches(
    catalog: LibraryCatalog,
    folder: LibraryItem,
    plan: LibraryDeviceTransferPlan,
    *,
    child_kinds: tuple[str, ...],
    child_names: tuple[str, ...],
) -> Optional[tuple[LibraryItem, ...]]:
    if (
        folder.node_kind != NODE_FOLDER
        or plan.destination_path != ("root",)
        or plan.expected_delta.removed_paths
        or plan.selected_item_ids != (folder.item_id,)
    ):
        return None
    children = catalog.children(folder.item_id)
    if len(children) != len(child_kinds) or len(plan.nodes) != len(children) + 1:
        return None
    root_path = ("root", folder.source_filename)
    root = plan.nodes[0]
    if (
        root.source_item_id != folder.item_id
        or root.source_path != folder.source_path
        or root.kind != "directory"
        or root.destination_path != root_path
    ):
        return None
    expected_paths = {root_path}
    for index, (child, kind, name, node) in enumerate(
        zip(children, child_kinds, child_names, plan.nodes[1:])
    ):
        if (
            child.node_kind != NODE_FILE
            or child.parent_id != folder.item_id
            or child.source_filename != name
            or child.source_status != SOURCE_PRESENT
            or not child.supported
            or child.state not in {STATE_IMPORTED, STATE_READY}
            or Path(child.source_path) != Path(folder.source_path) / child.source_filename
            or Path(child.source_path).is_symlink()
            or node.source_item_id != child.item_id
            or node.source_path != child.source_path
            or node.kind != "file"
            or node.file_type != kind
            or node.destination_path != root_path + (name,)
            or node.sibling_order != index
        ):
            return None
        try:
            payload = Path(child.source_path).read_bytes()
        except OSError as exc:
            raise LibraryFolderPackageAdapterError(
                f"Local Library source changed after planning: {child.source_filename}"
            ) from exc
        digest = _sha256(payload)
        if (
            digest != child.source_sha256
            or len(payload) != child.source_size_bytes
            or node.source_payload_sha256 != digest
            or node.source_payload_bytes != len(payload)
        ):
            raise LibraryFolderPackageAdapterError(
                f"Local Library source changed after planning: {child.source_filename}"
            )
        expected_paths.add(root_path + (name,))
    actual_added = plan.expected_delta.added_paths
    if len(actual_added) != len(expected_paths) or set(actual_added) != expected_paths:
        return None
    return children


def prepare_exact_folder_package(
    catalog: LibraryCatalog,
    folder: LibraryItem,
    plan: LibraryDeviceTransferPlan,
    *,
    staging_parent: Path,
) -> Optional[LibraryFolderPackageStage]:
    """Stage only an exact 3-/4-leaf folder matching an existing profile.

    ``None`` means the host plan is valid but outside the exact live shape.
    Source races and staging failures raise a safe host-side error instead.
    """

    if not isinstance(catalog, LibraryCatalog) or not isinstance(folder, LibraryItem):
        return None
    if not isinstance(plan, LibraryDeviceTransferPlan):
        return None
    children = catalog.children(folder.item_id)
    kinds = tuple(Path(child.source_filename).suffix.lower().lstrip(".") for child in children)
    profile_id = _profile_for_kinds(kinds)
    if profile_id is None:
        return None
    profile = guarded_execution_profile(profile_id)
    children = _folder_plan_matches(
        catalog,
        folder,
        plan,
        child_kinds=profile.child_kinds,
        child_names=profile.child_names,
    )
    if children is None:
        return None

    folder_path = Path(folder.source_path)
    if folder_path.is_symlink() or not folder_path.is_dir():
        raise LibraryFolderPackageAdapterError(
            "Local Library folder changed after transfer planning"
        )
    try:
        entries = tuple(folder_path.iterdir())
    except OSError as exc:
        raise LibraryFolderPackageAdapterError(
            "Local Library folder could not be rechecked before package preparation"
        ) from exc
    if (
        any(entry.is_symlink() or not entry.is_file() for entry in entries)
        or {entry.name for entry in entries}
        != {child.source_filename for child in children}
    ):
        return None

    source_specs = tuple(
        (Path(child.source_path), child.source_filename) for child in children
    )
    try:
        package = build_prepared_media_package(source_specs, folder.source_filename)
    except (OSError, PreparedMediaPackageError, ValueError) as exc:
        raise LibraryFolderPackageAdapterError(
            f"Exact Local Library folder preparation failed: {exc}"
        ) from exc

    planned_hashes = tuple(node.source_payload_sha256 for node in plan.nodes[1:])
    built_hashes = tuple(item.source_sha256 for item in package.items)
    if (
        built_hashes != planned_hashes
        or tuple(item.kind for item in package.items) != profile.child_kinds
        or tuple(item.name for item in package.items) != profile.child_names
    ):
        raise LibraryFolderPackageAdapterError(
            "Local Library sources no longer match the reviewed folder plan"
        )
    if any(
        isinstance(item, PreparedTextSourceItem) and item.authored.substitutions
        for item in package.items
    ):
        raise LibraryFolderPackageAdapterError(
            "This folder contains text that needs CP932 character substitutions. "
            "The Manager will not silently alter it for transfer; use source text "
            "that needs no substitutions. No device checks or changes occurred."
        )

    parent = Path(staging_parent).expanduser()
    if parent.is_symlink():
        raise LibraryFolderPackageAdapterError(
            "transient prepared-content location must not be a symbolic link"
        )
    temporary: Optional[tempfile.TemporaryDirectory] = None
    try:
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(
            prefix="library-transfer-", dir=str(parent.resolve())
        )
        package_root = Path(temporary.name) / "prepared-package"
        export_prepared_media_package(package, package_root)
        imported = load_prepared_media_package(package_root)
        artifact = imported.package.to_prepared_content_artifact()
    except (OSError, PreparedMediaPackageError, ValueError) as exc:
        if temporary is not None:
            temporary.cleanup()
        raise LibraryFolderPackageAdapterError(
            f"Exact Local Library folder could not be staged safely: {exc}"
        ) from exc

    assessment = assess_transfer_shape(artifact)
    if (
        assessment.classification != EXACT_VERIFIED_LIVE_PROFILE
        or artifact.root_name != folder.source_filename
        or tuple(child.kind for child in artifact.children) != profile.child_kinds
        or tuple(child.name for child in artifact.children) != profile.child_names
        or tuple(child.source_sha256 for child in artifact.children) != planned_hashes
    ):
        temporary.cleanup()
        return None

    manifest_size = imported.manifest_path.stat().st_size
    reference = LibraryPackageReference(
        format=str(imported.manifest["format"]),
        root_path=str(imported.root),
        manifest_path=str(imported.manifest_path),
        manifest_sha256=imported.manifest_sha256,
        folder_name=imported.package.folder_name,
        children=tuple(dict(child) for child in imported.children),
    )
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    observation = {
        "timestamp_utc": timestamp,
        "status": SOURCE_PRESENT,
        "sha256": imported.manifest_sha256,
        "size_bytes": manifest_size,
    }
    staged_item = replace(
        folder,
        source_path=str(imported.root),
        source_filename=imported.package.folder_name,
        source_sha256=imported.manifest_sha256,
        source_size_bytes=manifest_size,
        detected_format="prepared-flat-package",
        supported=True,
        state=STATE_READY,
        preparation_state=PREPARATION_PREPARED,
        target_folder_name=imported.package.folder_name,
        target_child_name=None,
        prepared_manifest_sha256=imported.manifest_sha256,
        prepared_manifest_path=str(imported.manifest_path),
        source_status=SOURCE_PRESENT,
        observed_source_sha256=imported.manifest_sha256,
        observed_source_size_bytes=manifest_size,
        observed_timestamp_utc=timestamp,
        last_validation_error=None,
        source_observations=(observation,),
        package=reference,
        prepared_artifact=artifact.to_dict(),
        prepared_metadata={
            "compatibility_adapter": "transient_local_folder_to_prepared_media_package",
            "package_manifest_sha256": imported.manifest_sha256,
        },
        node_kind=NODE_PREPARED_PACKAGE,
    )

    # The existing queue/readiness services require a LibraryCatalog. This
    # shallow in-memory overlay retains all original nodes and is never saved
    # or shown in the Local Library tree.
    transient_catalog = copy(catalog)
    transient_catalog._items = dict(catalog._items)
    transient_catalog._items[staged_item.item_id] = staged_item
    assert temporary is not None
    return LibraryFolderPackageStage(
        catalog=transient_catalog,
        item=staged_item,
        artifact=artifact,
        source_folder=folder_path,
        source_bindings=tuple(
            (Path(child.source_path), child.source_sha256, child.source_size_bytes)
            for child in children
        ),
        _temporary_directory=temporary,
    )


__all__ = [
    "LibraryFolderPackageAdapterError",
    "LibraryFolderPackageStage",
    "OPERATION_STAGING_BINDING_FORMAT",
    "prepare_exact_folder_package",
]
