"""Product-neutral device-tree snapshots and independent semantic deltas.

This module models logical paths, sibling order, file payload fingerprints,
and opaque auxiliary-state fingerprints.  It intentionally knows nothing
about candidate bytes, device protocols, authorization, or execution.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import re
from typing import Optional


DevicePath = tuple[str, ...]
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DEVICE_ROOT_PATH: DevicePath = ("root",)


class DeviceLibrarySemanticError(ValueError):
    """A logical device snapshot or expected delta is malformed."""


def _require_path(value: object, label: str) -> DevicePath:
    if not isinstance(value, tuple) or not value or any(
        not isinstance(part, str) or not part or "\x00" in part for part in value
    ):
        raise DeviceLibrarySemanticError(f"{label} must be a non-empty tuple of path components")
    return value


def _require_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise DeviceLibrarySemanticError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _path_key(path: DevicePath) -> tuple[str, ...]:
    return tuple(part.casefold() for part in path)


def _canonical_digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class DeviceLibraryNode:
    """One logical device path; file payloads are represented only by hashes."""

    path: DevicePath
    kind: str
    sibling_order: int
    file_type: Optional[str] = None
    payload_sha256: Optional[str] = None
    payload_size_bytes: Optional[int] = None
    system: bool = False

    def __post_init__(self) -> None:
        _require_path(self.path, "node path")
        if self.kind not in {"directory", "file"}:
            raise DeviceLibrarySemanticError("node kind must be directory or file")
        if isinstance(self.sibling_order, bool) or not isinstance(self.sibling_order, int) or self.sibling_order < 0:
            raise DeviceLibrarySemanticError("sibling order must be a non-negative integer")
        if not isinstance(self.system, bool):
            raise DeviceLibrarySemanticError("system marker must be boolean")
        if self.kind == "directory":
            if any(value is not None for value in (self.file_type, self.payload_sha256, self.payload_size_bytes)):
                raise DeviceLibrarySemanticError("directory nodes cannot contain file payload metadata")
        else:
            if not isinstance(self.file_type, str) or not self.file_type:
                raise DeviceLibrarySemanticError("file type is required")
            _require_digest(self.payload_sha256, "payload_sha256")
            if (
                isinstance(self.payload_size_bytes, bool)
                or not isinstance(self.payload_size_bytes, int)
                or self.payload_size_bytes < 0
            ):
                raise DeviceLibrarySemanticError("file payload size must be a non-negative integer")

    @property
    def parent_path(self) -> Optional[DevicePath]:
        return None if self.path == DEVICE_ROOT_PATH else self.path[:-1]

    def to_dict(self) -> dict[str, object]:
        return {
            "path": list(self.path),
            "kind": self.kind,
            "sibling_order": self.sibling_order,
            "file_type": self.file_type,
            "payload_sha256": self.payload_sha256,
            "payload_size_bytes": self.payload_size_bytes,
            "system": self.system,
        }


@dataclass(frozen=True)
class AuxiliaryStateValue:
    """Opaque auxiliary-state identity with optional resolved path references."""

    key: str
    fingerprint_sha256: str
    referenced_paths: tuple[DevicePath, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key:
            raise DeviceLibrarySemanticError("auxiliary-state key is required")
        _require_digest(self.fingerprint_sha256, "auxiliary fingerprint")
        if not isinstance(self.referenced_paths, tuple):
            raise DeviceLibrarySemanticError("auxiliary referenced_paths must be a tuple")
        for path in self.referenced_paths:
            _require_path(path, "auxiliary referenced path")

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "fingerprint_sha256": self.fingerprint_sha256,
            "referenced_paths": [list(path) for path in self.referenced_paths],
        }


@dataclass(frozen=True)
class AuxiliaryStateSnapshot:
    """A captured auxiliary-state view; unresolved means mutation must fail closed."""

    resolved: bool = False
    values: tuple[AuxiliaryStateValue, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.resolved, bool):
            raise DeviceLibrarySemanticError("auxiliary-state resolved marker must be boolean")
        if not isinstance(self.values, tuple) or any(
            not isinstance(value, AuxiliaryStateValue) for value in self.values
        ):
            raise DeviceLibrarySemanticError("auxiliary-state values must be typed records")
        keys = [value.key for value in self.values]
        if len(keys) != len(set(keys)):
            raise DeviceLibrarySemanticError("auxiliary-state keys must be unique")

    def to_dict(self) -> dict[str, object]:
        return {"resolved": self.resolved, "values": [value.to_dict() for value in self.values]}


@dataclass(frozen=True)
class DeviceLibrarySnapshot:
    """Immutable logical tree with explicit sibling order and auxiliary state."""

    nodes: tuple[DeviceLibraryNode, ...]
    auxiliary_state: AuxiliaryStateSnapshot = AuxiliaryStateSnapshot()

    def __post_init__(self) -> None:
        if not isinstance(self.nodes, tuple) or any(
            not isinstance(node, DeviceLibraryNode) for node in self.nodes
        ):
            raise DeviceLibrarySemanticError("snapshot nodes must be a tuple of typed nodes")
        if not isinstance(self.auxiliary_state, AuxiliaryStateSnapshot):
            raise DeviceLibrarySemanticError("snapshot auxiliary state must be typed")
        paths = [node.path for node in self.nodes]
        if len(paths) != len(set(paths)):
            raise DeviceLibrarySemanticError("snapshot contains duplicate paths")
        if len({_path_key(path) for path in paths}) != len(paths):
            raise DeviceLibrarySemanticError("snapshot contains case-insensitive path collisions")
        by_path = {node.path: node for node in self.nodes}
        root = by_path.get(DEVICE_ROOT_PATH)
        if root is None or root.kind != "directory":
            raise DeviceLibrarySemanticError("snapshot must contain a directory at root")
        if root.sibling_order != 0:
            raise DeviceLibrarySemanticError("root sibling order must be zero")
        siblings: dict[Optional[DevicePath], list[DeviceLibraryNode]] = {}
        for node in self.nodes:
            parent = node.parent_path
            if parent is not None:
                parent_node = by_path.get(parent)
                if parent_node is None or parent_node.kind != "directory":
                    raise DeviceLibrarySemanticError(f"node has no directory parent: {node.path!r}")
            siblings.setdefault(parent, []).append(node)
        for parent, children in siblings.items():
            if parent is None:
                continue
            orders = sorted(child.sibling_order for child in children)
            if orders != list(range(len(children))):
                raise DeviceLibrarySemanticError(f"sibling order is not contiguous below {parent!r}")
            names = [child.path[-1].casefold() for child in children]
            if len(names) != len(set(names)):
                raise DeviceLibrarySemanticError(f"duplicate sibling names below {parent!r}")
        for value in self.auxiliary_state.values:
            for path in value.referenced_paths:
                if path not in by_path:
                    raise DeviceLibrarySemanticError(
                        f"auxiliary reference points to a missing path: {path!r}"
                    )

    @property
    def node_map(self) -> dict[DevicePath, DeviceLibraryNode]:
        return {node.path: node for node in self.nodes}

    def children(self, parent_path: DevicePath) -> tuple[DeviceLibraryNode, ...]:
        return tuple(
            sorted(
                (node for node in self.nodes if node.parent_path == parent_path),
                key=lambda node: node.sibling_order,
            )
        )

    def traversal(self) -> tuple[DeviceLibraryNode, ...]:
        result: list[DeviceLibraryNode] = []

        def visit(parent: DevicePath) -> None:
            for child in self.children(parent):
                result.append(child)
                if child.kind == "directory":
                    visit(child.path)

        root = self.node_map[DEVICE_ROOT_PATH]
        result.append(root)
        visit(root.path)
        return tuple(result)

    def selection_identity(self, path: DevicePath) -> str:
        """Hash one node and its ordered subtree for stale-selection checks."""
        if path not in self.node_map:
            raise DeviceLibrarySemanticError(f"selected path does not exist: {path!r}")
        selected = [
            node.to_dict()
            for node in self.traversal()
            if node.path == path or node.path[: len(path)] == path
        ]
        return _canonical_digest(selected)

    @property
    def identity_sha256(self) -> str:
        return _canonical_digest(
            {
                "nodes": [node.to_dict() for node in self.traversal()],
                "auxiliary_state": self.auxiliary_state.to_dict(),
            }
        )


@dataclass(frozen=True)
class ExpectedDeviceDelta:
    """Expected logical additions/removals and order adjustments, independent of candidates."""

    baseline: DeviceLibrarySnapshot
    additions: tuple[DeviceLibraryNode, ...] = ()
    removals: tuple[DevicePath, ...] = ()
    order_updates: tuple[tuple[DevicePath, int], ...] = ()
    auxiliary_after: Optional[AuxiliaryStateSnapshot] = None

    def __post_init__(self) -> None:
        if not isinstance(self.baseline, DeviceLibrarySnapshot):
            raise DeviceLibrarySemanticError("expected delta baseline must be a device snapshot")
        if not isinstance(self.additions, tuple) or any(
            not isinstance(node, DeviceLibraryNode) for node in self.additions
        ):
            raise DeviceLibrarySemanticError("expected additions must be typed nodes")
        if not isinstance(self.removals, tuple):
            raise DeviceLibrarySemanticError("expected removals must be a tuple")
        for path in self.removals:
            _require_path(path, "expected removal path")
        if len(set(self.removals)) != len(self.removals):
            raise DeviceLibrarySemanticError("expected removals contain duplicates")
        if not isinstance(self.order_updates, tuple):
            raise DeviceLibrarySemanticError("order updates must be a tuple")
        for update in self.order_updates:
            if not isinstance(update, tuple) or len(update) != 2:
                raise DeviceLibrarySemanticError("each order update must be a (path, order) pair")
            _require_path(update[0], "order update path")
        if self.auxiliary_after is not None and not isinstance(
            self.auxiliary_after, AuxiliaryStateSnapshot
        ):
            raise DeviceLibrarySemanticError("expected auxiliary state must be typed")
        self.expected_snapshot()

    @property
    def added_paths(self) -> tuple[DevicePath, ...]:
        return tuple(node.path for node in self.additions)

    @property
    def removed_paths(self) -> tuple[DevicePath, ...]:
        return self.removals

    def expected_snapshot(self) -> DeviceLibrarySnapshot:
        before = self.baseline.node_map
        removed = set(self.removals)
        if DEVICE_ROOT_PATH in removed:
            raise DeviceLibrarySemanticError("the device root cannot be removed")
        for path in removed:
            node = before.get(path)
            if node is None:
                raise DeviceLibrarySemanticError(f"cannot remove a missing baseline path: {path!r}")
            if node.system:
                raise DeviceLibrarySemanticError(f"cannot remove a system path: {path!r}")
        for parent in removed:
            if any(path[: len(parent)] == parent and path != parent for path in before if path not in removed):
                raise DeviceLibrarySemanticError("removal set is not a complete subtree closure")

        nodes = {path: node for path, node in before.items() if path not in removed}
        updates: dict[DevicePath, int] = {}
        for path, order in self.order_updates:
            if path in updates or path not in nodes:
                raise DeviceLibrarySemanticError("order update is duplicate or targets a removed/missing path")
            if isinstance(order, bool) or not isinstance(order, int) or order < 0:
                raise DeviceLibrarySemanticError("updated sibling order must be non-negative")
            updates[path] = order
        for path, order in updates.items():
            nodes[path] = replace(nodes[path], sibling_order=order)

        folded_paths = {_path_key(path) for path in nodes}
        for addition in self.additions:
            if addition.path in nodes or _path_key(addition.path) in folded_paths:
                raise DeviceLibrarySemanticError("expected addition collides with a baseline path")
            if addition.path in removed:
                raise DeviceLibrarySemanticError("an expected delta cannot replace a removed path")
            nodes[addition.path] = addition
            folded_paths.add(_path_key(addition.path))

        auxiliary = self.auxiliary_after or self.baseline.auxiliary_state
        ordered = tuple(
            [nodes[DEVICE_ROOT_PATH]]
            + sorted(
                (node for path, node in nodes.items() if path != DEVICE_ROOT_PATH),
                key=lambda node: (len(node.path), tuple(part.casefold() for part in node.path)),
            )
        )
        return DeviceLibrarySnapshot(ordered, auxiliary)


@dataclass(frozen=True)
class SemanticVerificationReport:
    """Successful comparison details for an independent logical read-back."""

    expected_added_paths: tuple[DevicePath, ...]
    expected_removed_paths: tuple[DevicePath, ...]
    verified_path_count: int
    expected_snapshot_sha256: str
    actual_snapshot_sha256: str


class DeviceSemanticVerificationError(RuntimeError):
    """The actual tree differs from its independently specified semantic delta."""


def verify_device_library_delta(
    expected: ExpectedDeviceDelta,
    actual: DeviceLibrarySnapshot,
) -> SemanticVerificationReport:
    """Compare an actual snapshot to explicit expected deltas and preserved state.

    The expected state is reconstructed only from the baseline and the typed
    logical delta.  No candidate builder or candidate output is accepted.
    """
    if not isinstance(expected, ExpectedDeviceDelta):
        raise DeviceSemanticVerificationError("expected semantic delta is invalid")
    if not isinstance(actual, DeviceLibrarySnapshot):
        raise DeviceSemanticVerificationError("actual device snapshot is invalid")
    wanted = expected.expected_snapshot()
    wanted_nodes = wanted.node_map
    actual_nodes = actual.node_map
    expected_paths, actual_paths = set(wanted_nodes), set(actual_nodes)
    missing = sorted(expected_paths - actual_paths)
    unexpected = sorted(actual_paths - expected_paths)
    problems: list[str] = []
    if missing:
        problems.append(f"missing expected paths: {missing!r}")
    if unexpected:
        problems.append(f"unexpected paths: {unexpected!r}")
    for path in sorted(expected_paths & actual_paths):
        if wanted_nodes[path] != actual_nodes[path]:
            if path in expected.baseline.node_map and path not in set(expected.removals):
                problems.append(f"unaffected path modified (hierarchy/order/type/payload): {path!r}")
            else:
                problems.append(f"expected hierarchy/order/type/payload differs at {path!r}")
    if wanted.auxiliary_state != actual.auxiliary_state:
        problems.append("auxiliary-state fingerprints or references differ from expectation")
    if not wanted.auxiliary_state.resolved:
        problems.append("auxiliary state is unresolved; semantic preservation cannot be verified")
    if problems:
        raise DeviceSemanticVerificationError("; ".join(problems))
    before_paths = set(expected.baseline.node_map)
    return SemanticVerificationReport(
        expected_added_paths=tuple(sorted(expected_paths - before_paths)),
        expected_removed_paths=tuple(sorted(before_paths - expected_paths)),
        verified_path_count=len(wanted_nodes),
        expected_snapshot_sha256=wanted.identity_sha256,
        actual_snapshot_sha256=actual.identity_sha256,
    )


__all__ = [
    "AuxiliaryStateSnapshot",
    "AuxiliaryStateValue",
    "DEVICE_ROOT_PATH",
    "DeviceLibraryNode",
    "DeviceLibrarySemanticError",
    "DeviceLibrarySnapshot",
    "DevicePath",
    "DeviceSemanticVerificationError",
    "ExpectedDeviceDelta",
    "SemanticVerificationReport",
    "verify_device_library_delta",
]
