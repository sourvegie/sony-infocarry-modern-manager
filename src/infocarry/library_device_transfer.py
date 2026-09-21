"""Host-only ordered Library-to-device logical planning.

The plan reads existing ``LibraryCatalog`` references, revalidates their
current source trees without changing them, and describes deterministic
logical destination paths.  It does not build candidate bytes, transactions,
authorization, or sender calls and is not a live-capability policy.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Optional, Protocol, Sequence

from .device_library_semantics import (
    DEVICE_ROOT_PATH,
    DeviceLibraryNode,
    DeviceLibrarySnapshot,
    DevicePath,
    ExpectedDeviceDelta,
)
MAX_DEVICE_COMPONENT_CP932_BYTES = 39


class _LibraryItem(Protocol):
    item_id: str
    source_path: str
    source_filename: str
    source_sha256: str
    source_size_bytes: int
    detected_format: str
    supported: bool
    state: str
    preparation_state: str
    source_status: str
    source_observations: tuple[dict[str, object], ...]
    observed_source_sha256: Optional[str]
    observed_source_size_bytes: Optional[int]
    prepared_manifest_sha256: Optional[str]
    last_validation_error: Optional[str]
    node_kind: str
    parent_id: Optional[str]
    package: object


class _LibraryCatalog(Protocol):
    """Structural subset used without importing Tk/USB-bearing modules."""

    def get(self, item_id: str) -> _LibraryItem: ...

    def children(self, parent_id: Optional[str]) -> tuple[_LibraryItem, ...]: ...


_NODE_FILE = "file"
_NODE_FOLDER = "folder"
_NODE_PREPARED_PACKAGE = "prepared_package"
_SOURCE_PRESENT = "present"
_VALID_SOURCE_STATES = frozenset({"imported", "ready"})
_PREPARATION_PREPARED = "prepared"
_SUPPORTED_TEXT_FORMAT = "utf-8-txt"
_SUPPORTED_BITMAP_FORMAT = "validated-237x320-1bit-bmp"


class LibraryDeviceTransferPlanError(ValueError):
    """A source reference or logical destination cannot be planned safely."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _component(value: str, *, label: str, extension: Optional[str] = None) -> bytes:
    if not isinstance(value, str) or not value:
        raise LibraryDeviceTransferPlanError(f"{label} must be a non-empty name")
    if (
        value in {".", ".."}
        or value != value.strip()
        or "\x00" in value
        or "/" in value
        or "\\" in value
        or any(ord(character) < 0x20 for character in value)
    ):
        raise LibraryDeviceTransferPlanError(
            f"{label} must be one trimmed, non-traversal path component"
        )
    if extension is not None and not value.lower().endswith(f".{extension}"):
        raise LibraryDeviceTransferPlanError(f"{label} must have a .{extension} extension")
    try:
        encoded = value.encode("cp932", errors="strict")
    except UnicodeEncodeError as exc:
        raise LibraryDeviceTransferPlanError(f"{label} is not representable in CP932") from exc
    if len(encoded) > MAX_DEVICE_COMPONENT_CP932_BYTES:
        raise LibraryDeviceTransferPlanError(
            f"{label} exceeds the evidenced {MAX_DEVICE_COMPONENT_CP932_BYTES}-byte CP932 component field"
        )
    return encoded


@dataclass(frozen=True)
class CapacityEvidence:
    """Optional host-supplied capacity facts; no physical value is inferred."""

    candidate_growth_bytes: Optional[int] = None
    metadata_overhead_bytes: Optional[int] = None
    candidate_model_size_bytes: Optional[int] = None
    remaining_growth_capacity_bytes: Optional[int] = None

    def __post_init__(self) -> None:
        for label, value in (
            ("candidate growth", self.candidate_growth_bytes),
            ("metadata overhead", self.metadata_overhead_bytes),
            ("candidate model size", self.candidate_model_size_bytes),
            ("remaining growth capacity", self.remaining_growth_capacity_bytes),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise LibraryDeviceTransferPlanError(f"{label} must be a non-negative integer or unknown")

    @property
    def status(self) -> str:
        if self.candidate_growth_bytes is None or self.remaining_growth_capacity_bytes is None:
            return "unknown"
        if self.candidate_growth_bytes > self.remaining_growth_capacity_bytes:
            return "insufficient"
        return "sufficient"


@dataclass(frozen=True)
class PlannedLibraryNode:
    """One source-backed path in the logical plan, never a binary candidate."""

    source_item_id: str
    source_path: str
    destination_path: DevicePath
    kind: str
    sibling_order: int
    file_type: Optional[str] = None
    source_payload_sha256: Optional[str] = None
    source_payload_bytes: int = 0

    def __post_init__(self) -> None:
        if not self.source_item_id or not self.source_path:
            raise LibraryDeviceTransferPlanError("planned node must retain its source reference")
        if self.kind not in {"directory", "file"}:
            raise LibraryDeviceTransferPlanError("planned node kind is invalid")
        if isinstance(self.sibling_order, bool) or not isinstance(self.sibling_order, int) or self.sibling_order < 0:
            raise LibraryDeviceTransferPlanError("planned sibling order is invalid")
        if self.kind == "file":
            if self.file_type not in {"txt", "bmp"}:
                raise LibraryDeviceTransferPlanError("planned file type is unsupported")
            if (
                not isinstance(self.source_payload_sha256, str)
                or len(self.source_payload_sha256) != 64
                or any(character not in "0123456789abcdef" for character in self.source_payload_sha256)
            ):
                raise LibraryDeviceTransferPlanError("planned file hash is missing")
            if (
                isinstance(self.source_payload_bytes, bool)
                or not isinstance(self.source_payload_bytes, int)
                or self.source_payload_bytes < 0
            ):
                raise LibraryDeviceTransferPlanError("planned file size is invalid")
        elif self.file_type is not None or self.source_payload_sha256 is not None or self.source_payload_bytes != 0:
            raise LibraryDeviceTransferPlanError("directory plan nodes cannot carry payload metadata")

    def to_dict(self) -> dict[str, object]:
        return {
            "source_item_id": self.source_item_id,
            "source_path": self.source_path,
            "destination_path": list(self.destination_path),
            "kind": self.kind,
            "sibling_order": self.sibling_order,
            "file_type": self.file_type,
            "source_payload_sha256": self.source_payload_sha256,
            "source_payload_bytes": self.source_payload_bytes,
        }


@dataclass(frozen=True)
class LibraryDeviceTransferPlan:
    """Deterministic logical mapping; deliberately has no execution method."""

    selected_item_ids: tuple[str, ...]
    destination_path: DevicePath
    nodes: tuple[PlannedLibraryNode, ...]
    expected_delta: ExpectedDeviceDelta
    capacity: CapacityEvidence

    @property
    def source_payload_bytes(self) -> int:
        return sum(node.source_payload_bytes for node in self.nodes if node.kind == "file")

    @property
    def candidate_growth_bytes(self) -> Optional[int]:
        return self.capacity.candidate_growth_bytes

    @property
    def capacity_status(self) -> str:
        return self.capacity.status

    def require_capacity_clearance(self) -> None:
        """Reject unknown/insufficient capacity when a caller needs a clearance assertion."""
        if self.capacity_status == "unknown":
            raise LibraryDeviceTransferPlanError(
                "candidate growth or remaining capacity is unknown; no capacity clearance is possible"
            )
        if self.capacity_status == "insufficient":
            raise LibraryDeviceTransferPlanError("known candidate growth exceeds known remaining capacity")

    def to_dict(self) -> dict[str, object]:
        return {
            "format": "infocarry-library-device-logical-plan-v1",
            "host_only": True,
            "selected_item_ids": list(self.selected_item_ids),
            "destination_path": list(self.destination_path),
            "nodes": [node.to_dict() for node in self.nodes],
            "source_payload_bytes": self.source_payload_bytes,
            "capacity": {
                "status": self.capacity_status,
                "candidate_growth_bytes": self.capacity.candidate_growth_bytes,
                "metadata_overhead_bytes": self.capacity.metadata_overhead_bytes,
                "candidate_model_size_bytes": self.capacity.candidate_model_size_bytes,
                "remaining_growth_capacity_bytes": self.capacity.remaining_growth_capacity_bytes,
            },
            "expected_delta": {
                "added_paths": [list(path) for path in self.expected_delta.added_paths],
                "removed_paths": [list(path) for path in self.expected_delta.removed_paths],
            },
            "safety": {
                "candidate_constructed": False,
                "transaction_constructed": False,
                "authorization_created": False,
                "sender_called": False,
                "live_capability_evaluated": False,
            },
        }


def _validate_profile_bmp(payload: bytes) -> None:
    """Validate the established source profile without USB-bearing imports."""
    if len(payload) < 62 or payload[:2] != b"BM":
        raise LibraryDeviceTransferPlanError("BMP is too short or lacks the Windows BM signature")
    declared_size = int.from_bytes(payload[2:6], "little")
    pixel_offset = int.from_bytes(payload[10:14], "little")
    dib_size = int.from_bytes(payload[14:18], "little")
    width = int.from_bytes(payload[18:22], "little", signed=True)
    signed_height = int.from_bytes(payload[22:26], "little", signed=True)
    planes = int.from_bytes(payload[26:28], "little")
    bits_per_pixel = int.from_bytes(payload[28:30], "little")
    compression = int.from_bytes(payload[30:34], "little")
    colors_used = int.from_bytes(payload[46:50], "little")
    if declared_size != len(payload) or dib_size != 40:
        raise LibraryDeviceTransferPlanError("BMP length or BITMAPINFOHEADER is unsupported")
    if width != 237 or abs(signed_height) != 320:
        raise LibraryDeviceTransferPlanError("BMP dimensions are not the validated 237x320 profile")
    if planes != 1 or bits_per_pixel != 1 or compression != 0 or colors_used not in (0, 2):
        raise LibraryDeviceTransferPlanError("BMP is not an uncompressed one-bit two-color image")
    row_stride = ((width + 31) // 32) * 4
    if pixel_offset != 62 or pixel_offset + row_stride * abs(signed_height) != len(payload):
        raise LibraryDeviceTransferPlanError("BMP palette or pixel bounds are malformed")
    from .bitmap import BitmapFormatError, decode_monochrome_bmp

    try:
        preview = decode_monochrome_bmp(payload)
    except BitmapFormatError as exc:
        raise LibraryDeviceTransferPlanError(f"BMP failed monochrome validation: {exc}") from exc
    if (preview.width, preview.height) != (237, 320):
        raise LibraryDeviceTransferPlanError("BMP preview dimensions differ from the validated profile")


def _validate_source_file(item: _LibraryItem) -> tuple[bytes, str]:
    """Read once and validate the catalog-bound original bytes without mutation."""
    path = Path(item.source_path)
    if path.is_symlink() or not path.is_file():
        raise LibraryDeviceTransferPlanError(f"source is missing or no longer a regular file: {path}")
    if path.name != item.source_filename:
        raise LibraryDeviceTransferPlanError(f"source filename changed since import: {path}")
    extension = path.suffix.lower().lstrip(".")
    if extension not in {"txt", "bmp"}:
        raise LibraryDeviceTransferPlanError(f"unsupported source type for transfer planning: {path.name}")
    _component(item.source_filename, label="source filename", extension=extension)
    if item.node_kind != _NODE_FILE or item.package is not None:
        raise LibraryDeviceTransferPlanError(f"unsupported Library source node: {item.source_filename}")
    if (
        not item.supported
        or item.source_status != _SOURCE_PRESENT
        or item.state not in _VALID_SOURCE_STATES
        or item.last_validation_error is not None
    ):
        raise LibraryDeviceTransferPlanError(
            f"source reference is stale, blocked, or unsupported: {item.source_filename}"
        )
    expected_format = _SUPPORTED_TEXT_FORMAT if extension == "txt" else _SUPPORTED_BITMAP_FORMAT
    if item.detected_format != expected_format:
        raise LibraryDeviceTransferPlanError(
            f"source format does not match its {extension.upper()} extension: {item.source_filename}"
        )
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise LibraryDeviceTransferPlanError(f"source could not be re-read: {path}") from exc
    digest = _sha256(payload)
    if digest != item.source_sha256 or len(payload) != item.source_size_bytes:
        raise LibraryDeviceTransferPlanError(f"source bytes changed since import: {path}")
    if extension == "txt":
        try:
            payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise LibraryDeviceTransferPlanError(
                f"TXT source is not valid UTF-8: {item.source_filename}"
            ) from exc
    else:
        try:
            _validate_profile_bmp(payload)
        except LibraryDeviceTransferPlanError as exc:
            raise LibraryDeviceTransferPlanError(
                f"BMP source does not match the validated 237x320 1-bit source format: {item.source_filename}"
            ) from exc
    return payload, extension


def _check_directory_source(item: _LibraryItem) -> Path:
    path = Path(item.source_path)
    if path.is_symlink() or not path.is_dir():
        raise LibraryDeviceTransferPlanError(f"source folder is missing or changed: {path}")
    if (
        item.node_kind != _NODE_FOLDER
        or item.source_status != _SOURCE_PRESENT
        or item.state not in _VALID_SOURCE_STATES
    ):
        raise LibraryDeviceTransferPlanError(f"source folder reference is stale: {path}")
    _component(item.source_filename, label="source folder name")
    return path


def _prepared_package_nodes(
    item: _LibraryItem,
    destination_path: DevicePath,
) -> tuple[PlannedLibraryNode, ...]:
    """Describe one imported package as logical paths after full host revalidation.

    This is still only a product/domain plan.  The package is expanded into
    its declared root folder and ordered direct children; it is never grouped
    with other selected items or converted into device bytes here.
    """

    package_ref = item.package
    if item.node_kind != _NODE_PREPARED_PACKAGE or package_ref is None:
        raise LibraryDeviceTransferPlanError(
            "prepared package reference is missing or inconsistent"
        )
    if (
        not item.supported
        or item.source_status != _SOURCE_PRESENT
        or item.state not in _VALID_SOURCE_STATES
        or item.preparation_state != _PREPARATION_PREPARED
        or item.last_validation_error is not None
    ):
        raise LibraryDeviceTransferPlanError(
            f"prepared package is stale, blocked, or unsupported: {item.source_filename}"
        )

    from .prepared_media_package import (
        PreparedMediaPackageError,
        load_prepared_media_package,
    )

    package_root = Path(package_ref.root_path).expanduser().resolve()
    if (
        str(package_root) != package_ref.root_path
        or package_root != Path(item.source_path).expanduser().resolve()
    ):
        raise LibraryDeviceTransferPlanError(
            "prepared package source path differs from its Library reference"
        )
    try:
        imported = load_prepared_media_package(package_root)
    except (OSError, PreparedMediaPackageError) as exc:
        raise LibraryDeviceTransferPlanError(
            f"prepared package could not be revalidated: {exc}"
        ) from exc

    manifest_size = imported.manifest_path.stat().st_size
    observations = item.source_observations
    latest = observations[-1] if observations else None
    if (
        str(imported.manifest_path) != package_ref.manifest_path
        or imported.manifest_sha256 != package_ref.manifest_sha256
        or imported.manifest_sha256 != item.prepared_manifest_sha256
        or imported.manifest_sha256 != item.source_sha256
        or imported.package.folder_name != package_ref.folder_name
        or imported.package.folder_name != item.source_filename
        or item.source_size_bytes != manifest_size
        or item.observed_source_sha256 != imported.manifest_sha256
        or item.observed_source_size_bytes != manifest_size
        or tuple(dict(child) for child in imported.children) != package_ref.children
        or not isinstance(latest, dict)
        or latest.get("status") != _SOURCE_PRESENT
        or latest.get("sha256") != imported.manifest_sha256
        or latest.get("size_bytes") != manifest_size
    ):
        raise LibraryDeviceTransferPlanError(
            "prepared package could not be fully revalidated: its source, manifest, or ordered grouping differs from the Library reference"
        )

    root_destination = destination_path + (imported.package.folder_name,)
    nodes = [
        PlannedLibraryNode(
            source_item_id=item.item_id,
            source_path=item.source_path,
            destination_path=root_destination,
            kind="directory",
            sibling_order=0,
        )
    ]
    for index, child in enumerate(imported.package.items):
        payload = child.source_bytes
        nodes.append(
            PlannedLibraryNode(
                source_item_id=item.item_id,
                source_path=str(child.source_path),
                destination_path=root_destination + (child.name,),
                kind="file",
                sibling_order=index,
                file_type=child.kind,
                source_payload_sha256=_sha256(payload),
                source_payload_bytes=len(payload),
            )
        )
    return tuple(nodes)


def _folder_entry_names(path: Path) -> tuple[str, ...]:
    try:
        entries = tuple(path.iterdir())
    except OSError as exc:
        raise LibraryDeviceTransferPlanError(f"source folder cannot be enumerated: {path}") from exc
    for entry in entries:
        if entry.is_symlink() or not (entry.is_dir() or entry.is_file()):
            raise LibraryDeviceTransferPlanError(f"unsupported or symbolic-link source entry: {entry}")
    return tuple(sorted((entry.name for entry in entries), key=lambda name: name.encode("utf-8", "surrogatepass")))


def _is_ancestor(catalog: _LibraryCatalog, ancestor_id: str, child_id: str) -> bool:
    cursor = catalog.get(child_id)
    while cursor.parent_id is not None:
        if cursor.parent_id == ancestor_id:
            return True
        cursor = catalog.get(cursor.parent_id)
    return False


def build_library_device_transfer_plan(
    catalog: _LibraryCatalog,
    selected_item_ids: Sequence[str],
    destination_path: DevicePath,
    device_snapshot: DeviceLibrarySnapshot,
    *,
    capacity: Optional[CapacityEvidence] = None,
) -> LibraryDeviceTransferPlan:
    """Build an ordered host-only transfer plan from current catalog references.

    Folder selections retain the selected folder name and all descendant
    structure.  Files are placed directly into the selected destination.
    Selected-item sequence order is preserved; descendants use persisted
    ``LibraryCatalog`` sibling order.  Every target is collision-checked
    case-insensitively against both the snapshot and the rest of the plan.
    """
    if not callable(getattr(catalog, "get", None)) or not callable(getattr(catalog, "children", None)):
        raise LibraryDeviceTransferPlanError("a LibraryCatalog-compatible reference catalog is required")
    if not isinstance(device_snapshot, DeviceLibrarySnapshot):
        raise LibraryDeviceTransferPlanError("a typed device library snapshot is required")
    if capacity is not None and not isinstance(capacity, CapacityEvidence):
        raise LibraryDeviceTransferPlanError("capacity must be typed host evidence or omitted")
    if not isinstance(destination_path, tuple) or not destination_path:
        raise LibraryDeviceTransferPlanError("destination must be a selected device directory path")
    if destination_path[0] != DEVICE_ROOT_PATH[0]:
        raise LibraryDeviceTransferPlanError("destination path must be rooted at device root")
    for part in destination_path[1:]:
        _component(part, label="destination path component")
    device_nodes = device_snapshot.node_map
    destination = device_nodes.get(destination_path)
    if destination is None or destination.kind != "directory":
        raise LibraryDeviceTransferPlanError("selected destination is missing or is not a folder")
    if destination.system and destination_path != DEVICE_ROOT_PATH:
        raise LibraryDeviceTransferPlanError("system folders cannot be selected as transfer destinations")

    ids = tuple(selected_item_ids)
    if not ids or any(not isinstance(item_id, str) or not item_id for item_id in ids):
        raise LibraryDeviceTransferPlanError("select at least one valid Library item")
    if len(ids) != len(set(ids)):
        raise LibraryDeviceTransferPlanError("Library selection contains duplicate items")
    try:
        selected = tuple(catalog.get(item_id) for item_id in ids)
    except (KeyError, ValueError) as exc:
        raise LibraryDeviceTransferPlanError(f"selected Library item is stale or missing: {exc}") from exc
    for index, item in enumerate(selected):
        if any(
            _is_ancestor(catalog, other.item_id, item.item_id)
            or _is_ancestor(catalog, item.item_id, other.item_id)
            for other in selected[index + 1 :]
        ):
            raise LibraryDeviceTransferPlanError("selected Library items overlap by ancestry")

    additions: list[PlannedLibraryNode] = []

    def visit(item: _LibraryItem, destination_for_node: DevicePath) -> None:
        if item.node_kind == _NODE_PREPARED_PACKAGE:
            additions.extend(_prepared_package_nodes(item, destination_for_node))
            return
        if item.node_kind == _NODE_FOLDER:
            source_dir = _check_directory_source(item)
            target_dir = destination_for_node + (item.source_filename,)
            children = catalog.children(item.item_id)
            expected_names = tuple(child.source_filename for child in children)
            actual_names = _folder_entry_names(source_dir)
            if tuple(sorted(expected_names, key=lambda name: name.encode("utf-8", "surrogatepass"))) != actual_names:
                raise LibraryDeviceTransferPlanError(
                    f"source folder contents changed since import: {source_dir}"
                )
            additions.append(
                PlannedLibraryNode(
                    source_item_id=item.item_id,
                    source_path=item.source_path,
                    destination_path=target_dir,
                    kind="directory",
                    sibling_order=0,
                )
            )
            for child in children:
                expected_source_path = source_dir / child.source_filename
                if Path(child.source_path) != expected_source_path:
                    raise LibraryDeviceTransferPlanError(
                        f"Library source path no longer matches its folder reference: {child.source_path}"
                    )
                visit(child, target_dir)
            if _folder_entry_names(source_dir) != actual_names:
                raise LibraryDeviceTransferPlanError(f"source folder changed while planning: {source_dir}")
            return
        if item.node_kind != _NODE_FILE:
            raise LibraryDeviceTransferPlanError(f"unsupported Library node kind: {item.node_kind}")
        payload, extension = _validate_source_file(item)
        target_file = destination_for_node + (item.source_filename,)
        additions.append(
            PlannedLibraryNode(
                source_item_id=item.item_id,
                source_path=item.source_path,
                destination_path=target_file,
                kind="file",
                sibling_order=0,
                file_type=extension,
                source_payload_sha256=_sha256(payload),
                source_payload_bytes=len(payload),
            )
        )

    for item in selected:
        visit(item, destination_path)

    # Assign order using existing destination children followed by the
    # user-selected order and each catalog-persisted subtree order.
    existing_paths_folded = {tuple(part.casefold() for part in path) for path in device_nodes}
    planned_paths_folded: set[tuple[str, ...]] = set()
    next_order: dict[DevicePath, int] = {}
    ordered_additions: list[PlannedLibraryNode] = []
    for planned in additions:
        path = planned.destination_path
        folded = tuple(part.casefold() for part in path)
        if folded in existing_paths_folded or folded in planned_paths_folded:
            raise LibraryDeviceTransferPlanError(
                "destination conflict: an item with the same path already exists"
            )
        parent = path[:-1]
        if parent in next_order:
            order = next_order[parent]
        elif parent in device_nodes:
            order = len(device_snapshot.children(parent))
        else:
            order = 0
        next_order[parent] = order + 1
        planned_paths_folded.add(folded)
        ordered_additions.append(
            PlannedLibraryNode(
                source_item_id=planned.source_item_id,
                source_path=planned.source_path,
                destination_path=path,
                kind=planned.kind,
                sibling_order=order,
                file_type=planned.file_type,
                source_payload_sha256=planned.source_payload_sha256,
                source_payload_bytes=planned.source_payload_bytes,
            )
        )

    logical_additions = tuple(
        DeviceLibraryNode(
            path=item.destination_path,
            kind=item.kind,
            sibling_order=item.sibling_order,
            file_type=item.file_type,
            payload_sha256=item.source_payload_sha256,
            payload_size_bytes=item.source_payload_bytes if item.kind == "file" else None,
        )
        for item in ordered_additions
    )
    # An unresolved auxiliary baseline remains visible in the plan; it is not
    # silently treated as known, and the independent verifier will refuse to
    # claim preservation until its semantic state is resolved.
    delta = ExpectedDeviceDelta(baseline=device_snapshot, additions=logical_additions)
    return LibraryDeviceTransferPlan(
        selected_item_ids=ids,
        destination_path=destination_path,
        nodes=tuple(ordered_additions),
        expected_delta=delta,
        capacity=capacity or CapacityEvidence(),
    )


__all__ = [
    "CapacityEvidence",
    "LibraryDeviceTransferPlan",
    "LibraryDeviceTransferPlanError",
    "MAX_DEVICE_COMPONENT_CP932_BYTES",
    "PlannedLibraryNode",
    "build_library_device_transfer_plan",
]
