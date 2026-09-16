"""Normal-manager host preparation workspace.

This is the single adapter boundary between user-selected source content and
the canonical :class:`PreparedContentArtifact`.  It composes the existing
strict TXT authoring, BMP validation, prepared-package import, and Library
hierarchy preparation utilities; it does not define a second prepared-content
model and has no device, sender, or authorization dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping, Optional

from .capability_profile import HIERARCHICAL_OFFLINE_PROFILE_ID, hierarchical_offline_capability_profile
from .library import LibraryCatalog
from .library_prepare import PreparedLibraryHierarchy, prepare_library_hierarchy
from .offline_conversion import PageLayout, load_utf8_text_document
from .prepared_content import PreparedContentArtifact, PreparedContentChild, PreparedContentError
from .prepared_media_package import (
    PreparedMediaPackageError,
    load_prepared_media_package,
    validate_bmp_payload,
)
from .prepared_package import PreparedPackageError, build_prepared_text_package
from .text_authoring import CP932_NORMALIZATION_POLICY


class ContentWorkspaceError(ValueError):
    """Base class for typed, user-facing host preparation failures."""


class UnsupportedContentError(ContentWorkspaceError):
    """Raised when a source format has no complete conversion path yet."""


class ContentWorkspaceCancelled(ContentWorkspaceError):
    """Raised when cooperative host preparation was cancelled."""


class ContentSourceKind(str, Enum):
    TXT = "txt"
    BMP = "bmp"
    PREPARED_FOLDER = "prepared_folder"
    PREPARED_PACKAGE = "prepared_package"


@dataclass(frozen=True)
class ContentWorkspaceSettings:
    """Deterministic settings that participate in a workspace result.

    The layout remains the existing 240 x 320 logical rendering canvas.  It is
    included in the workspace profile identity so changing preparation settings
    cannot leave an old preview/readiness result looking current.
    """

    root_name: Optional[str] = None
    page_layout: PageLayout = PageLayout()

    def __post_init__(self) -> None:
        if self.root_name is not None and (
            not isinstance(self.root_name, str) or not self.root_name.strip()
        ):
            raise ContentWorkspaceError("workspace root name must be a non-empty string or None")
        if not isinstance(self.page_layout, PageLayout):
            raise ContentWorkspaceError("workspace page layout is malformed")

    @property
    def profile_suffix(self) -> str:
        layout = self.page_layout
        return (
            f"canvas-{layout.width_px}x{layout.height_px};"
            f"columns-{layout.columns};lines-{layout.lines_per_page};"
            f"normalization-{CP932_NORMALIZATION_POLICY}"
        )


@dataclass(frozen=True)
class ContentWorkspacePreview:
    """Owner-readable preview bound to one exact canonical artifact object."""

    artifact: PreparedContentArtifact
    source_path: Path
    source_kind: ContentSourceKind
    title: str
    text_excerpt: Optional[str] = None
    rendered_details: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    normalization_substitutions: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.artifact, PreparedContentArtifact):
            raise ContentWorkspaceError("workspace preview must carry a canonical artifact")
        if not isinstance(self.source_path, Path):
            raise ContentWorkspaceError("workspace preview source path is malformed")
        if not isinstance(self.source_kind, ContentSourceKind):
            raise ContentWorkspaceError("workspace preview source kind is malformed")
        if not isinstance(self.title, str) or not self.title:
            raise ContentWorkspaceError("workspace preview title is required")

    @property
    def artifact_identity(self) -> str:
        return self.artifact.artifact_identity

    @property
    def prepared_size(self) -> int:
        return self.artifact.aggregate_size

    @property
    def child_count(self) -> int:
        return len(self.artifact.children)

    @property
    def preparation_valid(self) -> bool:
        return self.artifact.valid_preparation

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete preview for diagnostics and tests.

        Technical hashes are intentionally kept in this machine-facing view;
        the normal ttk formatter chooses the owner-facing subset.
        """

        return {
            "format": "infocarry-content-workspace-preview-v1",
            "source_path": str(self.source_path),
            "source_kind": self.source_kind.value,
            "title": self.title,
            "artifact": self.artifact.to_dict(),
            "artifact_identity": self.artifact_identity,
            "prepared_size": self.prepared_size,
            "child_count": self.child_count,
            "ordered_children": [
                {
                    "order": child.order,
                    "name": child.name,
                    "kind": child.kind,
                    "path": child.path,
                    "payload_bytes": child.payload_bytes,
                }
                for child in self.artifact.children
            ],
            "text_excerpt": self.text_excerpt,
            "rendered_details": list(self.rendered_details),
            "warnings": list(self.warnings),
            "normalization_substitutions": [
                {"from": source, "to": replacement}
                for source, replacement in self.normalization_substitutions
            ],
            "preparation_valid": self.preparation_valid,
            "device_accessed": False,
            "device_change": "none",
        }


@dataclass(frozen=True)
class ContentWorkspaceResult:
    """The canonical preparation result returned by Add Content / Prepare."""

    artifact: PreparedContentArtifact
    preview: ContentWorkspacePreview
    source_path: Path
    source_kind: ContentSourceKind
    preparation_metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.preview.artifact is not self.artifact:
            raise ContentWorkspaceError(
                "workspace preview must consume the exact prepared artifact instance"
            )
        if self.preview.artifact_identity != self.artifact.artifact_identity:
            raise ContentWorkspaceError("workspace preview artifact identity differs")
        if not isinstance(self.preparation_metadata, Mapping):
            raise ContentWorkspaceError("workspace preparation metadata is malformed")

    @property
    def artifact_identity(self) -> str:
        return self.artifact.artifact_identity

    @property
    def valid_preparation(self) -> bool:
        return self.artifact.valid_preparation

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "infocarry-content-workspace-result-v1",
            "source_path": str(self.source_path),
            "source_kind": self.source_kind.value,
            "artifact": self.artifact.to_dict(),
            "artifact_identity": self.artifact_identity,
            "preview": self.preview.to_dict(),
            "preparation_metadata": dict(self.preparation_metadata),
            "valid_preparation": self.valid_preparation,
            "device_accessed": False,
            "device_change": "none",
        }


Progress = Callable[[str, Optional[int], Optional[int]], None]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_cancel(cancel_event: Any, label: str) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise ContentWorkspaceCancelled(f"{label} was cancelled")


def _progress(progress: Optional[Progress], label: str, completed: Optional[int] = None, total: Optional[int] = None) -> None:
    if progress is not None:
        progress(label, completed, total)


def _workspace_artifact_profile(
    artifact: PreparedContentArtifact,
    *,
    source_kind: ContentSourceKind,
    settings: ContentWorkspaceSettings,
) -> PreparedContentArtifact:
    """Bind direct-file results to the settings used to prepare them."""

    return PreparedContentArtifact(
        artifact.root_name,
        artifact.children,
        profile_id=f"infocarry-content-workspace-{source_kind.value}-v1:{settings.profile_suffix}",
        profile_sha256=None,
    )


def _bmp_artifact(path: Path, root_name: str, payload: bytes) -> PreparedContentArtifact:
    validate_bmp_payload(payload)
    name = path.name
    child = PreparedContentChild(
        order=0,
        kind="bmp",
        name=name,
        path=f"root\\{root_name}\\{name}",
        payload_sha256=_sha256(payload),
        payload_bytes=len(payload),
        payload_path=f"source/{name}",
        source_sha256=_sha256(payload),
        source_bytes=len(payload),
    )
    return PreparedContentArtifact(root_name, (child,))


class ContentWorkspace:
    """Prepare supported sources using existing utilities and one result type."""

    EPUB_NOT_READY_MESSAGE = "This format is not ready for conversion yet."

    def detect_source_kind(self, source: Path) -> ContentSourceKind | None:
        path = Path(source).expanduser()
        if path.is_dir():
            return (
                ContentSourceKind.PREPARED_PACKAGE
                if (path / "manifest.json").is_file()
                else ContentSourceKind.PREPARED_FOLDER
            )
        suffix = path.suffix.casefold()
        if suffix == ".txt":
            return ContentSourceKind.TXT
        if suffix == ".bmp":
            return ContentSourceKind.BMP
        return None

    def prepare(
        self,
        source: Path,
        *,
        settings: ContentWorkspaceSettings | None = None,
        cancel_event: Any = None,
        progress: Optional[Progress] = None,
    ) -> ContentWorkspaceResult:
        """Prepare one TXT, BMP, existing package, or source folder offline."""

        selected = Path(source).expanduser()
        if selected.is_symlink():
            raise ContentWorkspaceError("symbolic-link sources are not supported")
        path = selected.resolve()
        settings = settings or ContentWorkspaceSettings()
        kind = self.detect_source_kind(path)
        if kind is None:
            raise UnsupportedContentError(self.EPUB_NOT_READY_MESSAGE)
        _check_cancel(cancel_event, "content preparation")
        _progress(progress, "Reading source")

        if kind is ContentSourceKind.TXT:
            return self._prepare_txt(path, settings, cancel_event, progress)
        if kind is ContentSourceKind.BMP:
            return self._prepare_bmp(path, settings, cancel_event, progress)
        if kind is ContentSourceKind.PREPARED_PACKAGE:
            return self._prepare_package(path, cancel_event, progress)
        return self._prepare_folder(path, cancel_event, progress)

    def preview_existing_artifact(
        self,
        source: Path,
        artifact: PreparedContentArtifact,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> ContentWorkspaceResult:
        """Build a preview view around an already persisted canonical artifact.

        This path intentionally does not re-run conversion or create another
        prepared representation.  It only reads owner-visible source text for
        the readable excerpt and binds the preview to the supplied artifact.
        """

        if not isinstance(artifact, PreparedContentArtifact):
            raise ContentWorkspaceError("existing prepared artifact is malformed")
        selected = Path(source).expanduser()
        if selected.is_symlink():
            raise ContentWorkspaceError("symbolic-link sources are not supported")
        path = selected.resolve()
        kind = self.detect_source_kind(path)
        if kind is None:
            raise UnsupportedContentError(self.EPUB_NOT_READY_MESSAGE)
        details = dict(metadata or {})
        raw_substitutions = details.get("normalization_substitutions", [])
        substitutions: list[tuple[str, str]] = []
        if isinstance(raw_substitutions, list):
            for value in raw_substitutions:
                if isinstance(value, Mapping):
                    source_value = value.get("from")
                    replacement = value.get("to")
                    if isinstance(source_value, str) and isinstance(replacement, str):
                        substitutions.append((source_value, replacement))
        warnings = (
            (
                "Some characters were normalized for CP932 compatibility; "
                "review the substitutions before sending.",
            )
            if substitutions
            else ()
        )
        text_excerpt: Optional[str] = None
        if kind is ContentSourceKind.TXT:
            try:
                text_excerpt = path.read_text(encoding="utf-8")[:4000]
            except (OSError, UnicodeDecodeError) as exc:
                raise ContentWorkspaceError(f"cannot read preview text: {exc}") from exc
        rendered_details: list[str] = []
        if kind is ContentSourceKind.BMP and artifact.children:
            child = artifact.children[0]
            rendered_details.append(
                f"{child.name}: transferable 237 × 320 1-bit BMP payload"
            )
        elif kind is ContentSourceKind.TXT:
            page_count = details.get("page_count")
            canvas = details.get("rendering_canvas")
            if isinstance(page_count, int) and isinstance(canvas, Mapping):
                rendered_details.append(
                    f"{page_count} logical page(s) on the {canvas.get('width_px')} × "
                    f"{canvas.get('height_px')} rendering canvas"
                )
        preview = ContentWorkspacePreview(
            artifact=artifact,
            source_path=path,
            source_kind=kind,
            title=artifact.root_name,
            text_excerpt=text_excerpt,
            rendered_details=tuple(rendered_details),
            warnings=warnings,
            normalization_substitutions=tuple(substitutions),
        )
        return ContentWorkspaceResult(
            artifact=artifact,
            preview=preview,
            source_path=path,
            source_kind=kind,
            preparation_metadata=details,
        )

    def _prepare_txt(
        self,
        path: Path,
        settings: ContentWorkspaceSettings,
        cancel_event: Any,
        progress: Optional[Progress],
    ) -> ContentWorkspaceResult:
        root_name = settings.root_name or path.stem
        _check_cancel(cancel_event, "text normalization")
        _progress(progress, "Normalizing text")
        try:
            package = build_prepared_text_package(path, root_name, path.name)
            document = load_utf8_text_document(path, layout=settings.page_layout)
        except (OSError, PreparedPackageError) as exc:
            raise ContentWorkspaceError(str(exc)) from exc
        _check_cancel(cancel_event, "text preparation")
        artifact = _workspace_artifact_profile(
            package.to_prepared_content_artifact(),
            source_kind=ContentSourceKind.TXT,
            settings=settings,
        )
        substitutions = tuple(document.authored.substitutions)
        warnings = (
            (
                "Some characters were normalized for CP932 compatibility; "
                "review the substitutions before sending.",
            )
            if substitutions
            else ()
        )
        preview = ContentWorkspacePreview(
            artifact=artifact,
            source_path=path,
            source_kind=ContentSourceKind.TXT,
            title=artifact.root_name,
            text_excerpt=document.original_text[:4000],
            rendered_details=(
                f"{document.page_count} logical page(s) on the "
                f"{settings.page_layout.width_px} × {settings.page_layout.height_px} rendering canvas",
            ),
            warnings=warnings,
            normalization_substitutions=substitutions,
        )
        metadata = {
            "source_sha256": _sha256(path.read_bytes()),
            "source_bytes": path.stat().st_size,
            "encoding": "cp932",
            "newline_policy": "crlf",
            "normalization_policy": CP932_NORMALIZATION_POLICY,
            "normalization_substitutions": [
                {"from": source, "to": replacement}
                for source, replacement in substitutions
            ],
            "page_count": document.page_count,
            "rendering_canvas": {
                "width_px": settings.page_layout.width_px,
                "height_px": settings.page_layout.height_px,
            },
        }
        _progress(progress, "Content prepared")
        return ContentWorkspaceResult(artifact, preview, path, ContentSourceKind.TXT, metadata)

    def _prepare_bmp(
        self,
        path: Path,
        settings: ContentWorkspaceSettings,
        cancel_event: Any,
        progress: Optional[Progress],
    ) -> ContentWorkspaceResult:
        _check_cancel(cancel_event, "bitmap preparation")
        _progress(progress, "Validating bitmap")
        try:
            payload = path.read_bytes()
            details = validate_bmp_payload(payload)
            root_name = settings.root_name or path.stem
            artifact = _workspace_artifact_profile(
                _bmp_artifact(path, root_name, payload),
                source_kind=ContentSourceKind.BMP,
                settings=settings,
            )
        except (OSError, PreparedMediaPackageError, PreparedContentError) as exc:
            raise ContentWorkspaceError(str(exc)) from exc
        preview = ContentWorkspacePreview(
            artifact=artifact,
            source_path=path,
            source_kind=ContentSourceKind.BMP,
            title=artifact.root_name,
            rendered_details=(
                f"{details['width']} × {details['height']} pixels; "
                f"{details['bits_per_pixel']}-bit uncompressed BMP",
            ),
        )
        metadata = {
            "source_sha256": _sha256(payload),
            "source_bytes": len(payload),
            "transferable_payload_viewport": {
                "width_px": details["width"],
                "height_px": details["height"],
                "bits_per_pixel": details["bits_per_pixel"],
            },
            "rendering_canvas": {
                "width_px": settings.page_layout.width_px,
                "height_px": settings.page_layout.height_px,
            },
        }
        _progress(progress, "Content prepared")
        return ContentWorkspaceResult(artifact, preview, path, ContentSourceKind.BMP, metadata)

    def _prepare_package(
        self,
        path: Path,
        cancel_event: Any,
        progress: Optional[Progress],
    ) -> ContentWorkspaceResult:
        _check_cancel(cancel_event, "prepared-package import")
        _progress(progress, "Validating prepared package")
        try:
            imported = load_prepared_media_package(path)
            artifact = imported.package.to_prepared_content_artifact()
        except (OSError, PreparedMediaPackageError, PreparedContentError) as exc:
            raise ContentWorkspaceError(str(exc)) from exc
        preview = ContentWorkspacePreview(
            artifact=artifact,
            source_path=path,
            source_kind=ContentSourceKind.PREPARED_PACKAGE,
            title=artifact.root_name,
            rendered_details=tuple(
                "237 × 320 1-bit BMP page" if child.kind == "bmp" else "CP932 text child"
                for child in artifact.children
            ),
        )
        metadata = {
            "package_manifest_sha256": imported.manifest_sha256,
            "package_format": imported.manifest.get("format"),
            "package_children": len(artifact.children),
            "compatibility_adapter": "PreparedMediaPackage.to_prepared_content_artifact",
        }
        _progress(progress, "Content prepared")
        return ContentWorkspaceResult(artifact, preview, path, ContentSourceKind.PREPARED_PACKAGE, metadata)

    def _prepare_folder(
        self,
        path: Path,
        cancel_event: Any,
        progress: Optional[Progress],
    ) -> ContentWorkspaceResult:
        """Use the existing hierarchy preparer through a temporary catalog adapter."""

        _check_cancel(cancel_event, "prepared-folder import")
        _progress(progress, "Inspecting prepared folder")
        try:
            with tempfile.TemporaryDirectory(prefix="infocarry-content-workspace-") as temporary:
                catalog = LibraryCatalog(Path(temporary) / "library.json")
                root = catalog.import_folder(path)
                _check_cancel(cancel_event, "prepared-folder preparation")
                hierarchy: PreparedLibraryHierarchy = prepare_library_hierarchy(
                    catalog, root.item_id
                )
                artifact = hierarchy.artifact
        except (OSError, ValueError) as exc:
            if isinstance(exc, ContentWorkspaceCancelled):
                raise
            raise ContentWorkspaceError(str(exc)) from exc
        preview = ContentWorkspacePreview(
            artifact=artifact,
            source_path=path,
            source_kind=ContentSourceKind.PREPARED_FOLDER,
            title=artifact.root_name,
            rendered_details=(
                f"{sum(child.kind == 'bmp' for child in artifact.children)} rendered/image item(s); "
                f"{sum(child.kind == 'txt' for child in artifact.children)} text item(s)",
            ),
        )
        metadata = {
            "compatibility_adapter": "LibraryCatalog + prepare_library_hierarchy",
            "hierarchy_profile": HIERARCHICAL_OFFLINE_PROFILE_ID,
            "hierarchy_profile_sha256": hierarchical_offline_capability_profile().sha256,
            "logical_nodes": len(artifact.children) + 1,
        }
        _progress(progress, "Content prepared")
        return ContentWorkspaceResult(artifact, preview, path, ContentSourceKind.PREPARED_FOLDER, metadata)


__all__ = [
    "ContentSourceKind",
    "ContentWorkspace",
    "ContentWorkspaceCancelled",
    "ContentWorkspaceError",
    "ContentWorkspacePreview",
    "ContentWorkspaceResult",
    "ContentWorkspaceSettings",
    "UnsupportedContentError",
]
