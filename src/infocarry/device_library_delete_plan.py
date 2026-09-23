"""Host-only generalized delete closure planning; no candidate or execution path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .device_library_semantics import (
    DEVICE_ROOT_PATH,
    DeviceLibrarySnapshot,
    DevicePath,
    ExpectedDeviceDelta,
)


class DeviceLibraryDeletePlanError(ValueError):
    """A deletion selection is stale, unsafe, or semantically unresolved."""


@dataclass(frozen=True)
class DeviceLibrarySelection:
    """A selected device path bound to the node/subtree observed by the user."""

    path: DevicePath
    identity_sha256: str
    snapshot_identity_sha256: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.path, tuple)
            or not self.path
            or any(not isinstance(part, str) or not part for part in self.path)
        ):
            raise DeviceLibraryDeletePlanError("selection path must be a non-empty path tuple")
        for label, value in (
            ("selection identity", self.identity_sha256),
            ("snapshot identity", self.snapshot_identity_sha256),
        ):
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise DeviceLibraryDeletePlanError(f"{label} must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class DeviceLibraryDeletePlan:
    """Normalized closure and independent expected-removal delta."""

    snapshot_identity_sha256: str
    selected_paths: tuple[DevicePath, ...]
    removed_paths: tuple[DevicePath, ...]
    expected_delta: ExpectedDeviceDelta

    def to_dict(self) -> dict[str, object]:
        return {
            "format": "infocarry-device-library-delete-plan-v1",
            "host_only": True,
            "snapshot_identity_sha256": self.snapshot_identity_sha256,
            "selected_paths": [list(path) for path in self.selected_paths],
            "removed_paths": [list(path) for path in self.removed_paths],
            "expected_delta": {
                "added_paths": [],
                "removed_paths": [list(path) for path in self.expected_delta.removed_paths],
            },
            "safety": {
                "candidate_constructed": False,
                "transaction_constructed": False,
                "authorization_created": False,
                "sender_called": False,
                "execution_available": False,
            },
        }


def select_device_path(snapshot: DeviceLibrarySnapshot, path: DevicePath) -> DeviceLibrarySelection:
    """Create a UI selection token from one exact snapshot and subtree."""
    if not isinstance(snapshot, DeviceLibrarySnapshot):
        raise DeviceLibraryDeletePlanError("a typed device library snapshot is required")
    try:
        identity = snapshot.selection_identity(path)
    except ValueError as exc:
        raise DeviceLibraryDeletePlanError(str(exc)) from exc
    return DeviceLibrarySelection(
        path=path,
        identity_sha256=identity,
        snapshot_identity_sha256=snapshot.identity_sha256,
    )


def _is_path_within(path: DevicePath, ancestor: DevicePath) -> bool:
    return len(path) >= len(ancestor) and path[: len(ancestor)] == ancestor


def build_device_library_delete_plan(
    snapshot: DeviceLibrarySnapshot,
    selections: Sequence[DeviceLibrarySelection],
) -> DeviceLibraryDeletePlan:
    """Plan file, multi-file, and disjoint-subtree removals from a snapshot.

    Directory selections expand to their full descendant closure. Duplicate or
    ancestor/descendant selections are rejected instead of silently
    normalizing ambiguous user intent. All auxiliary references must be
    resolved and none may point into the removal closure.
    """
    if not isinstance(snapshot, DeviceLibrarySnapshot):
        raise DeviceLibraryDeletePlanError("a typed device library snapshot is required")
    if not isinstance(selections, (tuple, list)) or not selections:
        raise DeviceLibraryDeletePlanError("select at least one device file or folder")
    if not snapshot.auxiliary_state.resolved:
        raise DeviceLibraryDeletePlanError(
            "auxiliary-state relationships are unresolved; deletion planning is blocked"
        )
    if any(not isinstance(selection, DeviceLibrarySelection) for selection in selections):
        raise DeviceLibraryDeletePlanError("delete selections must be snapshot-bound typed identities")

    selected_paths = tuple(selection.path for selection in selections)
    if len(set(selected_paths)) != len(selected_paths):
        raise DeviceLibraryDeletePlanError("duplicate device selections are ambiguous")
    nodes = snapshot.node_map
    for selection in selections:
        node = nodes.get(selection.path)
        if (
            node is None
            or snapshot.identity_sha256 != selection.snapshot_identity_sha256
            or snapshot.selection_identity(selection.path) != selection.identity_sha256
        ):
            raise DeviceLibraryDeletePlanError(f"stale device selection identity: {selection.path!r}")
        if selection.path == DEVICE_ROOT_PATH:
            raise DeviceLibraryDeletePlanError("device root cannot be deleted")
        if node.system:
            raise DeviceLibraryDeletePlanError(f"system path cannot be deleted: {selection.path!r}")

    for index, path in enumerate(selected_paths):
        if any(
            _is_path_within(other, path) or _is_path_within(path, other)
            for other in selected_paths[index + 1 :]
        ):
            raise DeviceLibraryDeletePlanError("overlapping device selections are ambiguous")

    closure: set[DevicePath] = set()
    for path in selected_paths:
        closure.add(path)
        node = nodes[path]
        if node.kind == "directory":
            closure.update(
                candidate.path
                for candidate in snapshot.nodes
                if _is_path_within(candidate.path, path)
            )
    for path in closure:
        if nodes[path].system:
            raise DeviceLibraryDeletePlanError(f"selection includes a protected system path: {path!r}")

    for value in snapshot.auxiliary_state.values:
        if any(reference in closure for reference in value.referenced_paths):
            raise DeviceLibraryDeletePlanError(
                f"auxiliary state {value.key!r} references a selected deletion path"
            )

    ordered_nodes = snapshot.traversal()
    ordered_removed = tuple(node.path for node in ordered_nodes if node.path in closure)
    selected_in_tree_order = tuple(path for path in (node.path for node in ordered_nodes) if path in set(selected_paths))

    affected_parents = {
        nodes[path].parent_path for path in closure if nodes[path].parent_path is not None
    }
    order_updates: list[tuple[DevicePath, int]] = []
    for parent in sorted(affected_parents):
        survivors = [node for node in snapshot.children(parent) if node.path not in closure]
        for new_order, survivor in enumerate(survivors):
            if survivor.sibling_order != new_order:
                order_updates.append((survivor.path, new_order))

    delta = ExpectedDeviceDelta(
        baseline=snapshot,
        removals=ordered_removed,
        order_updates=tuple(order_updates),
    )
    # Constructing the expected snapshot here makes closure/order errors fail
    # during planning, before any caller can mistake this for an executable op.
    delta.expected_snapshot()
    return DeviceLibraryDeletePlan(
        snapshot_identity_sha256=snapshot.identity_sha256,
        selected_paths=selected_in_tree_order,
        removed_paths=ordered_removed,
        expected_delta=delta,
    )


__all__ = [
    "DeviceLibraryDeletePlan",
    "DeviceLibraryDeletePlanError",
    "DeviceLibrarySelection",
    "build_device_library_delete_plan",
    "select_device_path",
]
