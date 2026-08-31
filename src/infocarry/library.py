"""Non-destructive local Library catalog for supported source files.

The catalog is deliberately independent of USB, device backups, and prepared
device transactions.  It records the relationship between an original local
source file and a future offline preparation result without copying,
modifying, moving, or deleting the source file.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from .prepared_package import PreparedPackageError, _validate_component


LIBRARY_FORMAT = "infocarry-library-v1"
LIBRARY_VERSION = 1
SUPPORTED_TEXT_FORMAT = "utf-8-txt"

STATE_IMPORTED = "imported"
STATE_READY = "ready"
STATE_STALE = "stale"
STATE_BLOCKED = "blocked"
STATE_UNSUPPORTED = "unsupported"
VALID_STATES = frozenset(
    {
        STATE_IMPORTED,
        STATE_READY,
        STATE_STALE,
        STATE_BLOCKED,
        STATE_UNSUPPORTED,
    }
)

PREPARATION_UNPREPARED = "unprepared"
PREPARATION_PREPARED = "prepared"
PREPARATION_STALE = "stale"
PREPARATION_BLOCKED = "blocked"
VALID_PREPARATION_STATES = frozenset(
    {
        PREPARATION_UNPREPARED,
        PREPARATION_PREPARED,
        PREPARATION_STALE,
        PREPARATION_BLOCKED,
    }
)

SOURCE_PRESENT = "present"
SOURCE_CHANGED = "changed"
SOURCE_MISSING = "missing"
VALID_SOURCE_STATUS = frozenset(
    {SOURCE_PRESENT, SOURCE_CHANGED, SOURCE_MISSING}
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LIBRARY_PACKAGE_ITEM_KIND = "prepared_package"
PREPARED_MEDIA_PACKAGE_FORMAT = "infocarry-prepared-typed-media-package-v1"


class LibraryError(ValueError):
    """Base class for safe, user-facing Library errors."""


class LibraryCatalogError(LibraryError):
    """Raised when a catalog is missing, malformed, or unsupported."""


class LibraryImportError(LibraryError):
    """Raised when a source cannot be inspected for import."""


@dataclass(frozen=True)
class LibraryPackageReference:
    """Persistent, hash-bound reference to one imported flat package.

    The package directory remains owned by the caller.  The catalog records a
    non-owning path, the manifest identity, and the manifest's ordered child
    table so queue planning can show the grouping without guessing it.  The
    on-disk package is revalidated before every review.
    """

    format: str
    root_path: str
    manifest_path: str
    manifest_sha256: str
    folder_name: str
    children: tuple[dict[str, Any], ...]

    def __post_init__(self) -> None:
        if self.format != PREPARED_MEDIA_PACKAGE_FORMAT:
            raise LibraryCatalogError("unsupported prepared package contract")
        if not self.root_path or not self.manifest_path or not self.folder_name:
            raise LibraryCatalogError("prepared package reference paths and folder are required")
        try:
            _validate_component(self.folder_name, label="prepared package folder name")
        except PreparedPackageError as exc:
            raise LibraryCatalogError(str(exc)) from exc
        _validate_sha256(self.manifest_sha256, "package manifest_sha256")
        if not isinstance(self.children, tuple) or len(self.children) < 2:
            raise LibraryCatalogError("prepared package reference requires at least two children")
        names: set[str] = set()
        kinds: set[str] = set()
        for index, child in enumerate(self.children):
            if not isinstance(child, dict):
                raise LibraryCatalogError("prepared package children must be objects")
            if isinstance(child.get("order"), bool) or child.get("order") != index:
                raise LibraryCatalogError("prepared package child order is not contiguous")
            kind = child.get("kind")
            if kind not in {"txt", "bmp"}:
                raise LibraryCatalogError("prepared package child kind is unsupported")
            kinds.add(kind)
            name = child.get("name")
            if not isinstance(name, str) or name.casefold() in names:
                raise LibraryCatalogError("prepared package child names must be unique")
            try:
                _validate_component(name, label="prepared package child name", extension=f".{kind}")
            except PreparedPackageError as exc:
                raise LibraryCatalogError(str(exc)) from exc
            names.add(name.casefold())
            if child.get("path") != f"root\\{self.folder_name}\\{name}":
                raise LibraryCatalogError("prepared package child path is inconsistent")
            source = child.get("source")
            if not isinstance(source, dict) or not isinstance(source.get("path"), str):
                raise LibraryCatalogError("prepared package child source metadata is malformed")
            _validate_sha256(source.get("sha256"), "package child source sha256")
            source_size = source.get("bytes", source.get("utf8_bytes"))
            if isinstance(source_size, bool) or not isinstance(source_size, int) or source_size < 0:
                raise LibraryCatalogError("package child source size is malformed")
        if not kinds or kinds - {"txt", "bmp"}:
            raise LibraryCatalogError("prepared package reference contains unsupported children")

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "root_path": self.root_path,
            "manifest_path": self.manifest_path,
            "manifest_sha256": self.manifest_sha256,
            "folder_name": self.folder_name,
            "children": [dict(child) for child in self.children],
        }

    @classmethod
    def from_dict(cls, value: Any) -> "LibraryPackageReference":
        if not isinstance(value, dict):
            raise LibraryCatalogError("package reference must be an object")
        children = value.get("children")
        if not isinstance(children, list):
            raise LibraryCatalogError("package reference children must be a list")
        try:
            return cls(
                format=str(value.get("format")),
                root_path=str(value.get("root_path")),
                manifest_path=str(value.get("manifest_path")),
                manifest_sha256=str(value.get("manifest_sha256")),
                folder_name=str(value.get("folder_name")),
                children=tuple(dict(child) for child in children),
            )
        except (TypeError, ValueError) as exc:
            raise LibraryCatalogError("package reference contains invalid fields") from exc


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _validate_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise LibraryCatalogError(f"{label} must be a lowercase SHA-256 string")
    return value


def default_catalog_path() -> Path:
    """Return the per-user catalog path, outside the source checkout."""

    if sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        root = Path(
            os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
        )
    return root / "SonyInfoCarryModernManager" / "library.json"


def _stable_item_id(source_path: Path) -> str:
    normalized = str(source_path)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"infocarry-library:{normalized}"))


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise LibraryImportError(f"cannot read source file: {path}") from exc
    return digest.hexdigest()


def _source_details(path: Path) -> dict[str, Any]:
    """Read source metadata without changing the source."""

    try:
        stat = path.stat()
    except OSError as exc:
        raise LibraryImportError(f"cannot inspect source file: {path}") from exc
    if not path.is_file():
        raise LibraryImportError(f"source is not a regular file: {path}")

    source_sha256 = _hash_file(path)
    suffix = path.suffix.lower()
    if suffix != ".txt":
        return {
            "sha256": source_sha256,
            "size_bytes": stat.st_size,
            "detected_format": suffix[1:] if suffix else "unknown",
            "supported": False,
            "validation_error": "unsupported source format; only UTF-8 .txt is supported",
        }

    try:
        path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        return {
            "sha256": source_sha256,
            "size_bytes": stat.st_size,
            "detected_format": SUPPORTED_TEXT_FORMAT,
            "supported": True,
            "validation_error": f"source is not valid UTF-8: {exc}",
        }
    return {
        "sha256": source_sha256,
        "size_bytes": stat.st_size,
        "detected_format": SUPPORTED_TEXT_FORMAT,
        "supported": True,
        "validation_error": None,
    }


@dataclass(frozen=True)
class LibraryItem:
    """One original source relationship in the local Library."""

    item_id: str
    source_path: str
    source_filename: str
    source_sha256: str
    import_timestamp_utc: str
    source_size_bytes: int
    detected_format: str
    supported: bool
    state: str
    preparation_state: str = PREPARATION_UNPREPARED
    target_folder_name: Optional[str] = None
    target_child_name: Optional[str] = None
    prepared_manifest_sha256: Optional[str] = None
    prepared_manifest_path: Optional[str] = None
    source_status: str = SOURCE_PRESENT
    observed_source_sha256: Optional[str] = None
    observed_source_size_bytes: Optional[int] = None
    observed_timestamp_utc: Optional[str] = None
    last_validation_error: Optional[str] = None
    source_observations: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    package: Optional[LibraryPackageReference] = None

    def __post_init__(self) -> None:
        if not self.item_id or not self.source_path or not self.source_filename:
            raise LibraryCatalogError("Library item identity and source fields are required")
        _validate_sha256(self.source_sha256, "source_sha256")
        if self.state not in VALID_STATES:
            raise LibraryCatalogError(f"unsupported Library state: {self.state}")
        if self.preparation_state not in VALID_PREPARATION_STATES:
            raise LibraryCatalogError(
                f"unsupported preparation state: {self.preparation_state}"
            )
        if self.source_status not in VALID_SOURCE_STATUS:
            raise LibraryCatalogError(f"unsupported source status: {self.source_status}")
        if self.source_size_bytes < 0:
            raise LibraryCatalogError("source_size_bytes must be non-negative")
        if self.observed_source_sha256 is not None:
            _validate_sha256(self.observed_source_sha256, "observed_source_sha256")
        if self.observed_source_size_bytes is not None and self.observed_source_size_bytes < 0:
            raise LibraryCatalogError("observed_source_size_bytes must be non-negative")
        if self.prepared_manifest_sha256 is not None:
            _validate_sha256(self.prepared_manifest_sha256, "prepared_manifest_sha256")
        if self.package is not None:
            if not self.supported:
                raise LibraryCatalogError("prepared package item must remain supported")
            if self.detected_format != "prepared-flat-package":
                raise LibraryCatalogError("prepared package item has an invalid detected format")
            if self.target_folder_name != self.package.folder_name or self.target_child_name is not None:
                raise LibraryCatalogError("prepared package target does not match its package reference")
            if self.prepared_manifest_sha256 != self.package.manifest_sha256:
                raise LibraryCatalogError("prepared package manifest identity is inconsistent")
            if self.prepared_manifest_path != self.package.manifest_path:
                raise LibraryCatalogError("prepared package manifest path is inconsistent")

    def to_dict(self) -> dict[str, Any]:
        value = {
            "item_id": self.item_id,
            "source_path": self.source_path,
            "source_filename": self.source_filename,
            "source_sha256": self.source_sha256,
            "import_timestamp_utc": self.import_timestamp_utc,
            "source_size_bytes": self.source_size_bytes,
            "detected_format": self.detected_format,
            "supported": self.supported,
            "state": self.state,
            "preparation_state": self.preparation_state,
            "target_folder_name": self.target_folder_name,
            "target_child_name": self.target_child_name,
            "prepared_manifest_sha256": self.prepared_manifest_sha256,
            "prepared_manifest_path": self.prepared_manifest_path,
            "source_status": self.source_status,
            "observed_source_sha256": self.observed_source_sha256,
            "observed_source_size_bytes": self.observed_source_size_bytes,
            "observed_timestamp_utc": self.observed_timestamp_utc,
            "last_validation_error": self.last_validation_error,
            "source_observations": [dict(observation) for observation in self.source_observations],
        }
        # Keep legacy v1 item serialization unchanged.  Package records are
        # an additive optional extension, so old catalogs load without being
        # silently reinterpreted as grouped content.
        if self.package is not None:
            value["item_kind"] = LIBRARY_PACKAGE_ITEM_KIND
            value["package"] = self.package.to_dict()
        return value

    @classmethod
    def from_dict(cls, value: Any) -> "LibraryItem":
        if not isinstance(value, dict):
            raise LibraryCatalogError("each Library item must be an object")
        required = {
            "item_id",
            "source_path",
            "source_filename",
            "source_sha256",
            "import_timestamp_utc",
            "source_size_bytes",
            "detected_format",
            "supported",
            "state",
        }
        missing = sorted(required.difference(value))
        if missing:
            raise LibraryCatalogError(f"Library item is missing fields: {', '.join(missing)}")
        observations = value.get("source_observations", [])
        if not isinstance(observations, list) or any(
            not isinstance(observation, dict) for observation in observations
        ):
            raise LibraryCatalogError("source_observations must be a list of objects")
        package_value = value.get("package")
        package = None if package_value is None else LibraryPackageReference.from_dict(package_value)
        if package is None and value.get("item_kind") not in (None, "source_file"):
            raise LibraryCatalogError("unknown Library item kind")
        if package is not None and value.get("item_kind") != LIBRARY_PACKAGE_ITEM_KIND:
            raise LibraryCatalogError("prepared package item kind is missing")
        try:
            return cls(
                item_id=str(value["item_id"]),
                source_path=str(value["source_path"]),
                source_filename=str(value["source_filename"]),
                source_sha256=str(value["source_sha256"]),
                import_timestamp_utc=str(value["import_timestamp_utc"]),
                source_size_bytes=int(value["source_size_bytes"]),
                detected_format=str(value["detected_format"]),
                supported=bool(value["supported"]),
                state=str(value["state"]),
                preparation_state=str(
                    value.get("preparation_state", PREPARATION_UNPREPARED)
                ),
                target_folder_name=value.get("target_folder_name"),
                target_child_name=value.get("target_child_name"),
                prepared_manifest_sha256=value.get("prepared_manifest_sha256"),
                prepared_manifest_path=value.get("prepared_manifest_path"),
                source_status=str(value.get("source_status", SOURCE_PRESENT)),
                observed_source_sha256=value.get("observed_source_sha256"),
                observed_source_size_bytes=(
                    None
                    if value.get("observed_source_size_bytes") is None
                    else int(value["observed_source_size_bytes"])
                ),
                observed_timestamp_utc=value.get("observed_timestamp_utc"),
                last_validation_error=value.get("last_validation_error"),
                source_observations=tuple(dict(observation) for observation in observations),
                package=package,
            )
        except (TypeError, ValueError) as exc:
            raise LibraryCatalogError("Library item contains invalid field types") from exc


class LibraryCatalog:
    """Versioned, atomically persisted catalog of local source files."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else default_catalog_path()
        self.previous_path = self.path.with_name(f"{self.path.stem}.previous{self.path.suffix}")
        self._items: dict[str, LibraryItem] = {}
        self.load()

    @property
    def items(self) -> tuple[LibraryItem, ...]:
        return tuple(self._items[key] for key in sorted(self._items))

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": LIBRARY_FORMAT,
            "version": LIBRARY_VERSION,
            "items": [item.to_dict() for item in self.items],
        }

    def load(self) -> tuple[LibraryItem, ...]:
        if not self.path.exists():
            self._items = {}
            return self.items
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LibraryCatalogError(f"cannot read Library catalog: {self.path}") from exc
        if not isinstance(raw, dict) or raw.get("format") != LIBRARY_FORMAT:
            raise LibraryCatalogError("unsupported or malformed Library catalog format")
        if raw.get("version") != LIBRARY_VERSION:
            raise LibraryCatalogError("unsupported Library catalog version")
        values = raw.get("items")
        if not isinstance(values, list):
            raise LibraryCatalogError("Library catalog items must be a list")
        parsed = [LibraryItem.from_dict(value) for value in values]
        items = {item.item_id: item for item in parsed}
        if len(items) != len(parsed):
            raise LibraryCatalogError("Library catalog contains duplicate item IDs")
        self._items = items
        return self.items

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        previous_exists = self.path.exists()
        if previous_exists:
            try:
                shutil.copy2(self.path, self.previous_path)
            except OSError as exc:
                raise LibraryCatalogError(
                    f"cannot preserve previous Library catalog: {self.previous_path}"
                ) from exc

        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary_path = Path(stream.name)
                json.dump(self.to_dict(), stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self.path)
            temporary_path = None
            try:
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
            except OSError:
                directory_fd = None
            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        except OSError as exc:
            raise LibraryCatalogError(f"cannot atomically save Library catalog: {self.path}") from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def get(self, item_id: str) -> LibraryItem:
        try:
            return self._items[item_id]
        except KeyError as exc:
            raise LibraryError(f"Library item not found: {item_id}") from exc

    def import_file(self, source: Path, *, now: Optional[str] = None) -> LibraryItem:
        path = Path(source).expanduser().resolve()
        details = _source_details(path)
        timestamp = now or _utc_now()
        item_id = _stable_item_id(path)
        existing = self._items.get(item_id)
        if existing is None:
            item = self._new_item(path, details, timestamp)
            self._items[item.item_id] = item
            self.save()
            return item

        # An explicit re-import of the same present bytes is intentionally a
        # no-op.  This keeps import idempotent and avoids manufacturing
        # observation history merely because the caller supplied a later
        # timestamp.  Missing, changed, or previously observed-invalid
        # sources still pass through _observe so their state can be repaired
        # or kept blocked deliberately.
        if (
            existing.source_status == SOURCE_PRESENT
            and existing.observed_source_sha256 == details["sha256"]
            and existing.observed_source_size_bytes == details["size_bytes"]
        ):
            return existing

        updated = self._observe(existing, details, timestamp)
        if updated != existing:
            self._items[item_id] = updated
            self.save()
        return updated

    def import_prepared_package(
        self,
        package_root: Path,
        *,
        now: Optional[str] = None,
    ) -> LibraryItem:
        """Import one exported flat prepared package without taking ownership.

        The package validator checks the manifest, source copies, prepared
        children, order, paths, and hashes before this catalog is changed.
        Re-importing the same manifest is idempotent.  A changed package keeps
        its original catalog identity and becomes stale; it is never silently
        replaced.
        """

        from .prepared_media_package import (
            PreparedMediaPackageError,
            load_prepared_media_package,
        )

        path = Path(package_root).expanduser().resolve()
        try:
            imported = load_prepared_media_package(path)
        except (OSError, PreparedMediaPackageError) as exc:
            raise LibraryImportError(f"prepared package import blocked: {exc}") from exc
        timestamp = now or _utc_now()
        item_id = _stable_item_id(path)
        existing = self._items.get(item_id)
        if existing is not None and existing.package is None:
            raise LibraryImportError(
                "prepared package path conflicts with an existing non-package Library item"
            )
        reference = LibraryPackageReference(
            format=str(imported.manifest["format"]),
            root_path=str(imported.root),
            manifest_path=str(imported.manifest_path),
            manifest_sha256=imported.manifest_sha256,
            folder_name=imported.package.folder_name,
            children=tuple(dict(child) for child in imported.children),
        )
        manifest_size = imported.manifest_path.stat().st_size
        if existing is None:
            observation = {
                "timestamp_utc": timestamp,
                "status": SOURCE_PRESENT,
                "sha256": imported.manifest_sha256,
                "size_bytes": manifest_size,
            }
            item = LibraryItem(
                item_id=item_id,
                source_path=str(path),
                source_filename=path.name,
                source_sha256=imported.manifest_sha256,
                import_timestamp_utc=timestamp,
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
            )
            self._items[item.item_id] = item
            self.save()
            return item
        if (
            existing.source_status == SOURCE_PRESENT
            and existing.observed_source_sha256 == imported.manifest_sha256
            and existing.observed_source_size_bytes == manifest_size
            and existing.package.manifest_sha256 == imported.manifest_sha256
            and existing.package == reference
        ):
            return existing
        if (
            existing.source_status == SOURCE_PRESENT
            and existing.observed_source_sha256 == imported.manifest_sha256
            and existing.observed_source_size_bytes == manifest_size
            and existing.package.manifest_sha256 == imported.manifest_sha256
            and existing.package != reference
        ):
            raise LibraryImportError(
                "catalog package grouping differs from the verified package manifest"
            )
        updated = self._observe_package(existing, imported.manifest_sha256, manifest_size, timestamp)
        if updated != existing:
            self._items[item_id] = updated
            self.save()
        return updated

    def refresh(self, item_id: str, *, now: Optional[str] = None) -> LibraryItem:
        existing = self.get(item_id)
        timestamp = now or _utc_now()
        path = Path(existing.source_path)
        if existing.package is not None:
            from .prepared_media_package import PreparedMediaPackageError, load_prepared_media_package

            if not path.exists():
                updated = self._observe_missing(existing, timestamp)
            else:
                try:
                    imported = load_prepared_media_package(path)
                except (OSError, PreparedMediaPackageError) as exc:
                    updated = self._observe_package_invalid(existing, path, timestamp, str(exc))
                else:
                    updated = self._observe_package(
                        existing,
                        imported.manifest_sha256,
                        imported.manifest_path.stat().st_size,
                        timestamp,
                    )
        elif not path.exists():
            updated = self._observe_missing(existing, timestamp)
        else:
            details = _source_details(path)
            updated = self._observe(existing, details, timestamp)
        if updated != existing:
            self._items[item_id] = updated
            self.save()
        return updated

    def remove(self, item_id: str) -> bool:
        if item_id not in self._items:
            return False
        del self._items[item_id]
        self.save()
        return True

    def update_preparation(
        self,
        item_id: str,
        *,
        preparation_state: str,
        state: str,
        target_folder_name: Optional[str] = None,
        target_child_name: Optional[str] = None,
        prepared_manifest_sha256: Optional[str] = None,
        prepared_manifest_path: Optional[str] = None,
        last_validation_error: Optional[str] = None,
    ) -> LibraryItem:
        if preparation_state not in VALID_PREPARATION_STATES:
            raise LibraryError(f"unsupported preparation state: {preparation_state}")
        if state not in VALID_STATES:
            raise LibraryError(f"unsupported Library state: {state}")
        item = self.get(item_id)
        if item.package is not None:
            raise LibraryError("prepared package records are updated by package import/revalidation")
        updated = replace(
            item,
            preparation_state=preparation_state,
            state=state,
            target_folder_name=target_folder_name,
            target_child_name=target_child_name,
            prepared_manifest_sha256=prepared_manifest_sha256,
            prepared_manifest_path=prepared_manifest_path,
            last_validation_error=last_validation_error,
        )
        self._items[item_id] = updated
        self.save()
        return updated

    @staticmethod
    def _observe_package(
        existing: LibraryItem,
        manifest_sha256: str,
        manifest_size: int,
        timestamp: str,
    ) -> LibraryItem:
        status = (
            SOURCE_PRESENT
            if manifest_sha256 == existing.source_sha256
            else SOURCE_CHANGED
        )
        observation = {
            "timestamp_utc": timestamp,
            "status": status,
            "sha256": manifest_sha256,
            "size_bytes": manifest_size,
        }
        observations = existing.source_observations
        if not observations or observations[-1] != observation:
            observations = (*observations, observation)
        if status == SOURCE_CHANGED:
            state = STATE_STALE
            preparation_state = PREPARATION_STALE
            error = "prepared package manifest changed since import"
        else:
            state = STATE_READY
            preparation_state = PREPARATION_PREPARED
            error = None
        return replace(
            existing,
            state=state,
            preparation_state=preparation_state,
            source_status=status,
            observed_source_sha256=manifest_sha256,
            observed_source_size_bytes=manifest_size,
            observed_timestamp_utc=timestamp,
            last_validation_error=error,
            source_observations=observations,
        )

    @staticmethod
    def _observe_package_invalid(
        existing: LibraryItem,
        package_root: Path,
        timestamp: str,
        message: str,
    ) -> LibraryItem:
        manifest_path = package_root / "manifest.json"
        observed_hash = existing.observed_source_sha256
        observed_size = existing.observed_source_size_bytes
        if manifest_path.is_file():
            try:
                observed_hash = _hash_file(manifest_path)
                observed_size = manifest_path.stat().st_size
            except OSError:
                pass
        observation = {
            "timestamp_utc": timestamp,
            "status": SOURCE_PRESENT,
            "sha256": observed_hash,
            "size_bytes": observed_size,
        }
        observations = existing.source_observations
        if not observations or observations[-1] != observation:
            observations = (*observations, observation)
        return replace(
            existing,
            state=STATE_BLOCKED,
            preparation_state=PREPARATION_BLOCKED,
            source_status=SOURCE_PRESENT,
            observed_source_sha256=observed_hash,
            observed_source_size_bytes=observed_size,
            observed_timestamp_utc=timestamp,
            last_validation_error=f"prepared package validation failed: {message}",
            source_observations=observations,
        )

    @staticmethod
    def _new_item(path: Path, details: dict[str, Any], timestamp: str) -> LibraryItem:
        if not details["supported"]:
            state = STATE_UNSUPPORTED
        elif details["validation_error"] is not None:
            state = STATE_BLOCKED
        else:
            state = STATE_IMPORTED
        observation = {
            "timestamp_utc": timestamp,
            "status": SOURCE_PRESENT,
            "sha256": details["sha256"],
            "size_bytes": details["size_bytes"],
        }
        return LibraryItem(
            item_id=_stable_item_id(path),
            source_path=str(path),
            source_filename=path.name,
            source_sha256=details["sha256"],
            import_timestamp_utc=timestamp,
            source_size_bytes=details["size_bytes"],
            detected_format=details["detected_format"],
            supported=details["supported"],
            state=state,
            observed_source_sha256=details["sha256"],
            observed_source_size_bytes=details["size_bytes"],
            observed_timestamp_utc=timestamp,
            last_validation_error=details["validation_error"],
            source_observations=(observation,),
        )

    @staticmethod
    def _observe(
        existing: LibraryItem,
        details: dict[str, Any],
        timestamp: str,
    ) -> LibraryItem:
        current_hash = details["sha256"]
        status = (
            SOURCE_PRESENT
            if current_hash == existing.source_sha256
            else SOURCE_CHANGED
        )
        observation = {
            "timestamp_utc": timestamp,
            "status": status,
            "sha256": current_hash,
            "size_bytes": details["size_bytes"],
        }
        observations = existing.source_observations
        if not observations or observations[-1] != observation:
            observations = (*observations, observation)

        if status == SOURCE_CHANGED:
            state = STATE_STALE
            preparation_state = (
                PREPARATION_STALE
                if existing.preparation_state == PREPARATION_PREPARED
                else existing.preparation_state
            )
            error = "source bytes changed since import"
        elif not details["supported"]:
            state = STATE_UNSUPPORTED
            preparation_state = existing.preparation_state
            error = details["validation_error"]
        elif details["validation_error"] is not None:
            state = STATE_BLOCKED
            preparation_state = PREPARATION_BLOCKED
            error = details["validation_error"]
        elif existing.preparation_state == PREPARATION_STALE:
            state = STATE_STALE
            preparation_state = existing.preparation_state
            error = existing.last_validation_error
        elif existing.preparation_state == PREPARATION_PREPARED:
            state = STATE_READY
            preparation_state = existing.preparation_state
            error = None
        else:
            state = STATE_IMPORTED
            preparation_state = existing.preparation_state
            error = None

        return replace(
            existing,
            state=state,
            preparation_state=preparation_state,
            source_status=status,
            observed_source_sha256=current_hash,
            observed_source_size_bytes=details["size_bytes"],
            observed_timestamp_utc=timestamp,
            last_validation_error=error,
            source_observations=observations,
        )

    @staticmethod
    def _observe_missing(existing: LibraryItem, timestamp: str) -> LibraryItem:
        observation = {
            "timestamp_utc": timestamp,
            "status": SOURCE_MISSING,
            "sha256": existing.observed_source_sha256,
            "size_bytes": existing.observed_source_size_bytes,
        }
        observations = existing.source_observations
        if not observations or observations[-1] != observation:
            observations = (*observations, observation)
        return replace(
            existing,
            state=STATE_STALE,
            preparation_state=(
                PREPARATION_STALE
                if existing.preparation_state == PREPARATION_PREPARED
                else existing.preparation_state
            ),
            source_status=SOURCE_MISSING,
            observed_timestamp_utc=timestamp,
            last_validation_error=(
                "prepared package directory is missing"
                if existing.package is not None
                else "source file is missing"
            ),
            source_observations=observations,
        )


__all__ = [
    "LIBRARY_FORMAT",
    "LIBRARY_PACKAGE_ITEM_KIND",
    "LIBRARY_VERSION",
    "PREPARATION_BLOCKED",
    "PREPARATION_PREPARED",
    "PREPARATION_STALE",
    "PREPARATION_UNPREPARED",
    "PREPARED_MEDIA_PACKAGE_FORMAT",
    "STATE_BLOCKED",
    "STATE_IMPORTED",
    "STATE_READY",
    "STATE_STALE",
    "STATE_UNSUPPORTED",
    "LibraryCatalog",
    "LibraryCatalogError",
    "LibraryError",
    "LibraryImportError",
    "LibraryItem",
    "LibraryPackageReference",
    "default_catalog_path",
]
