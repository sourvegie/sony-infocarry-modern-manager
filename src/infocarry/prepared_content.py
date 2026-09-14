"""Canonical, device-neutral prepared-content contract.

The Library and conversion layers produce one semantic artifact.  Older
hierarchy and typed-package manifests remain supported as import/export views,
but they do not own a second copy of the prepared-content identity.

This module deliberately knows nothing about USB, candidate construction,
authorization, claims, locks, or sender operations.  Live-transfer policy is
applied by the separate readiness gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Iterable, Mapping, Optional


PREPARED_CONTENT_ARTIFACT_FORMAT = "infocarry-prepared-content-v1"
PREPARED_CONTENT_ARTIFACT_VERSION = 1
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_DIGEST_LENGTH = 64
_VALID_KINDS = frozenset({"folder", "txt", "bmp"})


class PreparedContentError(ValueError):
    """Raised when a prepared-content artifact is malformed or ambiguous."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _is_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _DIGEST_LENGTH
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _digest(value: Any, label: str) -> str:
    if not _is_digest(value):
        raise PreparedContentError(f"{label} must be a lowercase SHA-256 digest")
    return str(value)


def _component(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PreparedContentError(f"{label} must be a non-empty string")
    if (
        value in {".", ".."}
        or "\x00" in value
        or "\\" in value
        or "/" in value
        or value != value.strip()
        or any(ord(character) < 0x20 for character in value)
    ):
        raise PreparedContentError(
            f"{label} must be one trimmed non-traversal path component without NUL"
        )
    try:
        value.encode("cp932", errors="strict")
    except UnicodeEncodeError as exc:
        raise PreparedContentError(f"{label} is not representable in CP932") from exc
    return value


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PreparedContentError(f"{label} must be a non-negative integer")
    return value


def _copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _copy(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy(child) for child in value]
    return value


@dataclass(frozen=True)
class PreparedContentChild:
    """One ordered logical child of a prepared Library root.

    ``path`` is the owner-visible destination path.  ``payload_path`` is an
    optional archive/local payload location and is intentionally not part of
    the semantic fingerprint; the immutable payload digest is the identity.
    ``node_id`` and source metadata are compatibility/provenance fields and do
    not make the artifact dependent on a local catalog implementation.
    """

    order: int
    kind: str
    name: str
    path: str
    payload_sha256: str
    payload_bytes: int
    payload_path: Optional[str] = None
    source_sha256: str = EMPTY_SHA256
    source_bytes: int = 0
    node_id: Optional[str] = None
    parent_id: Optional[str] = None

    def __post_init__(self) -> None:
        if isinstance(self.order, bool) or not isinstance(self.order, int) or self.order < 0:
            raise PreparedContentError("prepared child order must be a non-negative integer")
        if self.kind not in _VALID_KINDS:
            raise PreparedContentError(f"unsupported prepared child kind: {self.kind}")
        _component(self.name, "prepared child name")
        if not isinstance(self.path, str) or not self.path:
            raise PreparedContentError("prepared child path is required")
        if "\x00" in self.path or "/" in self.path or self.path.startswith("\\"):
            raise PreparedContentError("prepared child path is malformed")
        _digest(self.payload_sha256, "prepared payload sha256")
        _nonnegative_int(self.payload_bytes, "prepared payload bytes")
        _digest(self.source_sha256, "source sha256")
        _nonnegative_int(self.source_bytes, "source bytes")
        if self.kind == "folder":
            if self.payload_path is not None:
                raise PreparedContentError("folder children cannot have a payload path")
            if self.payload_sha256 != EMPTY_SHA256 or self.payload_bytes != 0:
                raise PreparedContentError("folder children cannot claim payload bytes")
        elif self.payload_path is not None and (
            not isinstance(self.payload_path, str) or not self.payload_path
        ):
            raise PreparedContentError("prepared payload path is malformed")
        if self.node_id is not None and (not isinstance(self.node_id, str) or not self.node_id):
            raise PreparedContentError("prepared child node identity is malformed")
        if self.parent_id is not None and (
            not isinstance(self.parent_id, str) or not self.parent_id
        ):
            raise PreparedContentError("prepared child parent identity is malformed")

    @property
    def prepared_payload_sha256(self) -> str:
        """Compatibility spelling used by the hierarchy manifest."""

        return self.payload_sha256

    @property
    def prepared_payload_bytes(self) -> int:
        """Compatibility spelling used by the hierarchy manifest."""

        return self.payload_bytes

    def semantic_dict(self) -> dict[str, Any]:
        """Return only fields that describe prepared content semantics."""

        return {
            "order": self.order,
            "kind": self.kind,
            "name": self.name,
            "path": self.path,
            "payload_sha256": self.payload_sha256,
            "payload_bytes": self.payload_bytes,
            "source_sha256": self.source_sha256,
            "source_bytes": self.source_bytes,
        }

    def to_dict(self) -> dict[str, Any]:
        value = self.semantic_dict()
        value.update(
            {
                "payload_path": self.payload_path,
                "node_id": self.node_id,
                "parent_id": self.parent_id,
            }
        )
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], *, index: Optional[int] = None) -> "PreparedContentChild":
        if not isinstance(value, Mapping):
            raise PreparedContentError("prepared content child must be an object")
        required = {
            "order",
            "kind",
            "name",
            "path",
            "payload_sha256",
            "payload_bytes",
            "payload_path",
            "source_sha256",
            "source_bytes",
            "node_id",
            "parent_id",
        }
        if set(value) != required:
            raise PreparedContentError("prepared content child schema differs")
        if index is not None and value.get("order") != index:
            raise PreparedContentError("prepared content child order is not contiguous")
        return cls(
            order=value["order"],
            kind=value["kind"],
            name=value["name"],
            path=value["path"],
            payload_sha256=value["payload_sha256"],
            payload_bytes=value["payload_bytes"],
            payload_path=value["payload_path"],
            source_sha256=value["source_sha256"],
            source_bytes=value["source_bytes"],
            node_id=value["node_id"],
            parent_id=value["parent_id"],
        )


@dataclass(frozen=True)
class PreparedContentArtifact:
    """The single canonical semantic contract for prepared Library content."""

    root_name: str
    children: tuple[PreparedContentChild, ...]
    profile_id: Optional[str] = None
    profile_sha256: Optional[str] = None
    artifact_identity: str = field(init=False)

    def __post_init__(self) -> None:
        _component(self.root_name, "prepared Library root name")
        if not isinstance(self.children, tuple) or not self.children:
            raise PreparedContentError("prepared content requires at least one child")
        if any(not isinstance(child, PreparedContentChild) for child in self.children):
            raise PreparedContentError("prepared content children must be typed")
        if tuple(child.order for child in self.children) != tuple(range(len(self.children))):
            raise PreparedContentError("prepared content child order is not contiguous")
        if self.profile_id is not None and (
            not isinstance(self.profile_id, str) or not self.profile_id
        ):
            raise PreparedContentError("prepared content profile identity is malformed")
        if self.profile_sha256 is not None:
            _digest(self.profile_sha256, "prepared content profile sha256")

        root_path = f"root\\{self.root_name}"
        folder_paths = {root_path}
        names_by_parent: dict[str, set[str]] = {}
        for child in self.children:
            if not child.path.startswith(root_path + "\\"):
                raise PreparedContentError("prepared child path is outside the logical root")
            parts = child.path.split("\\")
            if parts[:2] != ["root", self.root_name] or len(parts) < 3:
                raise PreparedContentError("prepared child path is not rooted at the Library root")
            if parts[-1] != child.name or any(not part for part in parts):
                raise PreparedContentError("prepared child path and name differ")
            parent_path = "\\".join(parts[:-1])
            if parent_path not in folder_paths:
                raise PreparedContentError(
                    f"prepared child parent is missing or appears after its child: {child.path}"
                )
            folded = child.name.casefold()
            siblings = names_by_parent.setdefault(parent_path, set())
            if folded in siblings:
                raise PreparedContentError(
                    f"duplicate owner-visible sibling name in prepared content: {child.name}"
                )
            siblings.add(folded)
            if child.kind == "folder":
                folder_paths.add(child.path)

        aggregate_size = sum(child.payload_bytes for child in self.children)
        object.__setattr__(self, "children", tuple(self.children))
        object.__setattr__(self, "artifact_identity", hashlib.sha256(_canonical_json(self._identity_dict())).hexdigest())
        object.__setattr__(self, "_aggregate_size", aggregate_size)

    @property
    def aggregate_size(self) -> int:
        return int(getattr(self, "_aggregate_size"))

    @property
    def root_path(self) -> str:
        return f"root\\{self.root_name}"

    @property
    def valid_preparation(self) -> bool:
        """True when the artifact passed content validation, independent of transfer."""

        return True

    @property
    def fingerprint(self) -> str:
        """Alias used by product-facing callers that avoid hash jargon."""

        return self.artifact_identity

    def _identity_dict(self) -> dict[str, Any]:
        return {
            "format": PREPARED_CONTENT_ARTIFACT_FORMAT,
            "version": PREPARED_CONTENT_ARTIFACT_VERSION,
            "root_name": self.root_name,
            "profile_id": self.profile_id,
            "profile_sha256": self.profile_sha256,
            "children": [child.semantic_dict() for child in self.children],
        }

    def to_dict(self) -> dict[str, Any]:
        value = {
            **self._identity_dict(),
            "children": [child.to_dict() for child in self.children],
            "aggregate_size": self.aggregate_size,
            "artifact_identity": self.artifact_identity,
        }
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PreparedContentArtifact":
        if not isinstance(value, Mapping):
            raise PreparedContentError("prepared content artifact must be an object")
        required = {
            "format",
            "version",
            "root_name",
            "profile_id",
            "profile_sha256",
            "children",
            "aggregate_size",
            "artifact_identity",
        }
        if set(value) != required:
            raise PreparedContentError("prepared content artifact schema differs")
        if value.get("format") != PREPARED_CONTENT_ARTIFACT_FORMAT or value.get("version") != PREPARED_CONTENT_ARTIFACT_VERSION:
            raise PreparedContentError("prepared content artifact format is unsupported")
        raw_children = value.get("children")
        if not isinstance(raw_children, list):
            raise PreparedContentError("prepared content children must be a list")
        artifact = cls(
            root_name=value.get("root_name"),
            children=tuple(
                PreparedContentChild.from_dict(child, index=index)
                for index, child in enumerate(raw_children)
            ),
            profile_id=value.get("profile_id"),
            profile_sha256=value.get("profile_sha256"),
        )
        if value.get("aggregate_size") != artifact.aggregate_size:
            raise PreparedContentError("prepared content aggregate size differs")
        if value.get("artifact_identity") != artifact.artifact_identity:
            raise PreparedContentError("prepared content artifact identity differs")
        return artifact

    @classmethod
    def from_hierarchy_manifest(cls, manifest: Mapping[str, Any]) -> "PreparedContentArtifact":
        if not isinstance(manifest, Mapping):
            raise PreparedContentError("prepared hierarchy manifest must be an object")
        nodes = manifest.get("nodes")
        if not isinstance(nodes, list) or not nodes or not isinstance(nodes[0], Mapping):
            raise PreparedContentError("prepared hierarchy ordered nodes are missing")
        root = nodes[0]
        if root.get("kind") != "folder":
            raise PreparedContentError("prepared hierarchy root must be a folder")
        root_name = root.get("name")
        children: list[PreparedContentChild] = []
        for index, raw in enumerate(nodes[1:]):
            if not isinstance(raw, Mapping):
                raise PreparedContentError("prepared hierarchy child is malformed")
            children.append(
                PreparedContentChild(
                    order=index,
                    kind=raw.get("kind"),
                    name=raw.get("name"),
                    path=raw.get("path"),
                    payload_sha256=raw.get("prepared_payload_sha256", EMPTY_SHA256),
                    payload_bytes=raw.get("prepared_payload_bytes", 0),
                    payload_path=raw.get("path") if raw.get("kind") != "folder" else None,
                    source_sha256=raw.get("source_sha256", EMPTY_SHA256),
                    source_bytes=raw.get("source_bytes", 0),
                    node_id=raw.get("node_id"),
                    parent_id=raw.get("parent_id"),
                )
            )
        return cls(
            root_name=root_name,
            children=tuple(children),
            profile_id=manifest.get("profile_id"),
            profile_sha256=manifest.get("profile_sha256"),
        )

    @classmethod
    def from_text_package(cls, package: Any) -> "PreparedContentArtifact":
        """Adapt the legacy single-TXT package without copying its semantics."""

        try:
            item = package.item
            payload = item.authored.payload
            source_bytes = package.source_bytes
            source_sha256 = package.source_sha256
            child = PreparedContentChild(
                order=0,
                kind="txt",
                name=item.name,
                path=package.target_item_path,
                payload_sha256=hashlib.sha256(payload).hexdigest(),
                payload_bytes=len(payload),
                payload_path=f"prepared/{package.folder_name}/{item.name}",
                source_sha256=source_sha256,
                source_bytes=len(source_bytes),
            )
            return cls(
                root_name=package.folder_name,
                children=(child,),
                profile_id="prepared-text-package-v1",
            )
        except (AttributeError, TypeError) as exc:
            raise PreparedContentError("legacy text package cannot be adapted") from exc

    @classmethod
    def from_media_package(cls, package: Any) -> "PreparedContentArtifact":
        """Adapt an in-memory typed TXT/BMP package to the canonical contract."""

        try:
            items = package.items
            children: list[PreparedContentChild] = []
            for index, item in enumerate(items):
                payload = item.authored.payload if item.kind == "txt" else item.source_bytes
                children.append(
                    PreparedContentChild(
                        order=index,
                        kind=item.kind,
                        name=item.name,
                        path=f"root\\{package.folder_name}\\{item.name}",
                        payload_sha256=hashlib.sha256(payload).hexdigest(),
                        payload_bytes=len(payload),
                        payload_path=f"prepared/{package.folder_name}/{item.name}",
                        source_sha256=item.source_sha256,
                        source_bytes=len(item.source_bytes),
                    )
                )
            return cls(
                root_name=package.folder_name,
                children=tuple(children),
                profile_id="prepared-typed-media-package-v1",
            )
        except (AttributeError, TypeError) as exc:
            raise PreparedContentError("legacy typed package cannot be adapted") from exc

    @classmethod
    def from_legacy_children(
        cls,
        *,
        root_name: str,
        children: Iterable[Mapping[str, Any]],
        profile_id: Optional[str] = "prepared-typed-media-package-v1",
        profile_sha256: Optional[str] = None,
    ) -> "PreparedContentArtifact":
        normalized: list[PreparedContentChild] = []
        for index, raw in enumerate(children):
            if not isinstance(raw, Mapping):
                raise PreparedContentError("legacy prepared child is malformed")
            kind = raw.get("kind")
            authoring = raw.get("authoring") if isinstance(raw.get("authoring"), Mapping) else {}
            bmp = raw.get("bmp") if isinstance(raw.get("bmp"), Mapping) else {}
            source = raw.get("source") if isinstance(raw.get("source"), Mapping) else {}
            payload_sha = raw.get("prepared_payload_sha256")
            if payload_sha is None:
                payload_sha = authoring.get("prepared_payload_sha256", bmp.get("payload_sha256"))
            payload_bytes = raw.get("prepared_payload_bytes")
            if payload_bytes is None:
                payload_bytes = authoring.get("prepared_payload_bytes", source.get("bytes", 0))
            source_sha256 = source.get("sha256", raw.get("source_sha256", EMPTY_SHA256))
            source_bytes = raw.get(
                "source_bytes",
                source.get("bytes", source.get("utf8_bytes", 0)),
            )
            normalized.append(
                PreparedContentChild(
                    order=index,
                    kind=kind,
                    name=raw.get("name"),
                    path=raw.get("path", f"root\\{root_name}\\{raw.get('name', '')}"),
                    payload_sha256=payload_sha or EMPTY_SHA256,
                    payload_bytes=payload_bytes,
                    payload_path=raw.get("prepared_path"),
                    source_sha256=source_sha256,
                    source_bytes=source_bytes,
                )
            )
        return cls(
            root_name=root_name,
            children=tuple(normalized),
            profile_id=profile_id,
            profile_sha256=profile_sha256,
        )

    def to_legacy_children(self) -> list[dict[str, Any]]:
        """Project to the stable queue/readiness child view."""

        return [
            {
                "order": child.order,
                "kind": child.kind,
                "name": child.name,
                "path": child.path,
                "source_sha256": child.source_sha256,
                "source_bytes": child.source_bytes,
                "prepared_payload_sha256": child.payload_sha256,
                "prepared_payload_bytes": child.payload_bytes,
            }
            for child in self.children
        ]

    def to_hierarchy_nodes(self, root_item_id: str) -> list[dict[str, Any]]:
        """Project a hierarchy artifact to the historical depth-first view."""

        if not isinstance(root_item_id, str) or not root_item_id:
            raise PreparedContentError("hierarchy root item identity is required")
        root_node = {
            "node_id": root_item_id,
            "parent_id": None,
            "order": 0,
            "kind": "folder",
            "name": self.root_name,
            "path": self.root_path,
            "source_sha256": EMPTY_SHA256,
            "prepared_payload_sha256": EMPTY_SHA256,
            "source_bytes": 0,
            "prepared_payload_bytes": 0,
            "validation": "passed",
        }
        node_ids = {self.root_path: root_item_id}
        sibling_orders: dict[str, int] = {self.root_path: 0}
        nodes = [root_node]
        for index, child in enumerate(self.children):
            parent_path = child.path.rsplit("\\", 1)[0]
            parent_id = node_ids.get(parent_path)
            if parent_id is None:
                raise PreparedContentError(f"prepared hierarchy parent is missing: {child.path}")
            order = sibling_orders.get(parent_path, 0)
            sibling_orders[parent_path] = order + 1
            node_id = child.node_id or f"{root_item_id}:child:{index}"
            node_ids[child.path] = node_id
            if child.kind == "folder":
                sibling_orders[child.path] = 0
            nodes.append(
                {
                    "node_id": node_id,
                    "parent_id": child.parent_id or parent_id,
                    "order": order,
                    "kind": child.kind,
                    "name": child.name,
                    "path": child.path,
                    "source_sha256": child.source_sha256,
                    "prepared_payload_sha256": child.payload_sha256,
                    "source_bytes": child.source_bytes,
                    "prepared_payload_bytes": child.payload_bytes,
                    "validation": "passed",
                }
            )
        return nodes


__all__ = [
    "EMPTY_SHA256",
    "PREPARED_CONTENT_ARTIFACT_FORMAT",
    "PREPARED_CONTENT_ARTIFACT_VERSION",
    "PreparedContentArtifact",
    "PreparedContentChild",
    "PreparedContentError",
]
