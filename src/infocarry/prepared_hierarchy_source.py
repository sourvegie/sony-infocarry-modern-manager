"""Operation-owned source and payload view for the existing hierarchy artifact.

This is an input adapter for the canonical candidate builder. It does not plan
destinations, authorize a transaction, or access a device. The manifest and
both byte trees live under one durable operation evidence directory.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from .capability_profile import NESTED_HOST_PROFILE_ID
from .library_prepare import PreparedLibraryHierarchy
from .prepared_content import EMPTY_SHA256, PreparedContentArtifact
from .prepared_media_package import validate_bmp_payload
from .text_authoring import encode_cp932_text


class PreparedHierarchySourceError(ValueError):
    """An operation-owned hierarchy is missing, stale, or malformed."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class PreparedHierarchySourceNode:
    kind: str
    name: str
    path: str
    order: int
    source_path: Path
    source_bytes: bytes
    source_sha256: str
    payload: bytes
    payload_sha256: str


@dataclass(frozen=True)
class PreparedHierarchySource:
    """Canonical prepared tree loaded entirely from an operation-owned copy."""

    root: Path
    manifest_path: Path
    prepared_manifest_sha256: str
    artifact: PreparedContentArtifact
    items: tuple[PreparedHierarchySourceNode, ...]

    @property
    def folder_name(self) -> str:
        return self.artifact.root_name

    @property
    def target_folder_path(self) -> str:
        return self.artifact.root_path

    @property
    def source_bytes_total(self) -> int:
        return sum(len(item.source_bytes) for item in self.items)

    @property
    def prepared_payload_bytes_total(self) -> int:
        return sum(len(item.payload) for item in self.items)


def load_prepared_hierarchy_source(package_root: Path) -> PreparedHierarchySource:
    """Strictly reload every bound source and prepared byte after staging."""

    root = Path(package_root).expanduser().resolve()
    manifest_path = root / "manifest.json"
    source_root = root / "source"
    payload_root = root / "prepared"
    if any(path.is_symlink() for path in (package_root, root, manifest_path, source_root, payload_root)):
        raise PreparedHierarchySourceError("operation-owned hierarchy contains a symbolic link")
    if not root.is_dir() or not source_root.is_dir() or not payload_root.is_dir():
        raise PreparedHierarchySourceError("operation-owned hierarchy is incomplete")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hierarchy = PreparedLibraryHierarchy(manifest)
    except (OSError, ValueError, TypeError) as exc:
        raise PreparedHierarchySourceError(f"operation-owned hierarchy manifest is invalid: {exc}") from exc
    if hierarchy.manifest["profile_id"] != NESTED_HOST_PROFILE_ID:
        raise PreparedHierarchySourceError("operation-owned hierarchy has the wrong host profile")
    artifact = hierarchy.artifact
    expected_source: set[Path] = {source_root}
    expected_payload: set[Path] = {payload_root}
    values: list[PreparedHierarchySourceNode] = []
    for child in artifact.children:
        parts = child.path.split("\\")[2:]
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise PreparedHierarchySourceError("operation-owned hierarchy path is malformed")
        source_path = source_root.joinpath(*parts)
        payload_path = payload_root.joinpath(*parts)
        if source_path.is_symlink() or payload_path.is_symlink():
            raise PreparedHierarchySourceError("operation-owned hierarchy contains a symbolic link")
        for parent in source_path.parents:
            if parent == source_root:
                break
            expected_source.add(parent)
        if child.kind == "folder":
            if not source_path.is_dir() or not payload_path.is_dir():
                raise PreparedHierarchySourceError("operation-owned folder differs from the manifest")
            expected_source.add(source_path)
            expected_payload.add(payload_path)
            source = payload = b""
        else:
            if not source_path.is_file() or not payload_path.is_file():
                raise PreparedHierarchySourceError("operation-owned leaf is missing")
            try:
                source = source_path.read_bytes()
                payload = payload_path.read_bytes()
            except OSError as exc:
                raise PreparedHierarchySourceError("operation-owned leaf cannot be read") from exc
            if len(source) != child.source_bytes or _sha256(source) != child.source_sha256:
                raise PreparedHierarchySourceError("operation-owned source bytes differ")
            if len(payload) != child.payload_bytes or _sha256(payload) != child.payload_sha256:
                raise PreparedHierarchySourceError("operation-owned prepared bytes differ")
            if child.kind == "txt":
                try:
                    authored = encode_cp932_text(source.decode("utf-8", errors="strict"))
                except (UnicodeDecodeError, ValueError) as exc:
                    raise PreparedHierarchySourceError("operation-owned TXT is invalid") from exc
                if authored.substitutions or authored.payload != payload:
                    raise PreparedHierarchySourceError("operation-owned TXT preparation differs")
            elif child.kind == "bmp":
                try:
                    validate_bmp_payload(source)
                except ValueError as exc:
                    raise PreparedHierarchySourceError("operation-owned BMP is invalid") from exc
                if payload != source:
                    raise PreparedHierarchySourceError("operation-owned BMP preparation differs")
            else:
                raise PreparedHierarchySourceError("operation-owned leaf type is unsupported")
            expected_source.add(source_path)
            expected_payload.add(payload_path)
            for parent in payload_path.parents:
                if parent == payload_root:
                    break
                expected_payload.add(parent)
        values.append(
            PreparedHierarchySourceNode(
                child.kind, child.name, child.path, child.order,
                source_path, source, child.source_sha256 if child.kind != "folder" else EMPTY_SHA256,
                payload, child.payload_sha256,
            )
        )
    actual_source = set(source_root.rglob("*")) | {source_root}
    actual_payload = set(payload_root.rglob("*")) | {payload_root}
    if actual_source != expected_source or actual_payload != expected_payload:
        raise PreparedHierarchySourceError("operation-owned hierarchy contains missing or unexpected paths")
    if any(path.is_symlink() for path in actual_source | actual_payload):
        raise PreparedHierarchySourceError("operation-owned hierarchy contains a symbolic link")
    return PreparedHierarchySource(
        root, manifest_path, hierarchy.prepared_manifest_sha256,
        artifact, tuple(values),
    )


__all__ = [
    "PreparedHierarchySource",
    "PreparedHierarchySourceError",
    "PreparedHierarchySourceNode",
    "load_prepared_hierarchy_source",
]
