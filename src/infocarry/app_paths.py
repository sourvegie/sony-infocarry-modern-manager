"""Central platform-specific paths for the InfoCarry desktop application.

The macOS and Windows application-support directory names predate the Finder
package and already contain user data.  Keep their locations stable.  The
sender-start marker lives in the execution-claims database, so the two safety
files remain at their historical paths while non-safety application data is
organized in distinct subdirectories.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Mapping, Optional


LEGACY_APPLICATION_DIRECTORY_NAME = "SonyInfoCarryModernManager"
PROPOSED_APPLICATION_DIRECTORY_NAME = "InfoCarry"
EXECUTION_CLAIMS_FILENAME = "execution-claims.sqlite3"
INDETERMINATE_LOCK_FILENAME = "indeterminate-write-lock.json"


@dataclass(frozen=True)
class ApplicationPaths:
    """Stable user-data paths, with safety files kept at their legacy names."""

    root: Path
    safety_root: Path
    alternate_safety_roots: tuple[Path, ...]
    execution_claims_database: Path
    indeterminate_write_lock: Path
    library_catalog: Path
    previous_library_catalog: Path
    backup_root: Path
    evidence_root: Path
    prepared_content_root: Path
    source_metadata_root: Path
    preview_cache_root: Path
    latest_backup_record: Path


def _application_support_base(
    *,
    home: Path,
    environ: Mapping[str, str],
    platform: str,
    os_name: str,
    data: bool = False,
) -> Path:
    if platform == "darwin":
        return home / "Library" / "Application Support"
    if os_name == "nt":
        configured = environ.get("APPDATA")
        return Path(configured) if configured else home / "AppData" / "Roaming"
    if data:
        configured = environ.get("XDG_DATA_HOME")
        return Path(configured) if configured else home / ".local" / "share"
    configured = environ.get("XDG_STATE_HOME")
    return Path(configured) if configured else home / ".local" / "state"


def application_paths(
    *,
    home: Optional[Path] = None,
    environ: Optional[Mapping[str, str]] = None,
    platform: Optional[str] = None,
    os_name: Optional[str] = None,
) -> ApplicationPaths:
    """Return application paths without creating directories or files.

    macOS and Windows intentionally retain the exact existing roots used by
    the catalog and persistent write-safety owner.  On other platforms the
    old XDG state/data split is preserved.
    """

    user_home = Path(home) if home is not None else Path.home()
    environment = os.environ if environ is None else environ
    current_platform = sys.platform if platform is None else platform
    current_os_name = os.name if os_name is None else os_name
    support_base = _application_support_base(
        home=user_home,
        environ=environment,
        platform=current_platform,
        os_name=current_os_name,
    )
    data_base = _application_support_base(
        home=user_home,
        environ=environment,
        platform=current_platform,
        os_name=current_os_name,
        data=True,
    )
    safety_root = (support_base / LEGACY_APPLICATION_DIRECTORY_NAME).expanduser().resolve()
    root = (data_base / LEGACY_APPLICATION_DIRECTORY_NAME).expanduser().resolve()
    proposed_root = (
        support_base / PROPOSED_APPLICATION_DIRECTORY_NAME / "Safety"
    ).expanduser().resolve()
    proposed_root_direct = (
        support_base / PROPOSED_APPLICATION_DIRECTORY_NAME
    ).expanduser().resolve()
    backup_root = root / "Backups"
    prepared_root = root / "Prepared Content"
    return ApplicationPaths(
        root=root,
        safety_root=safety_root,
        alternate_safety_roots=(proposed_root, proposed_root_direct),
        execution_claims_database=safety_root / EXECUTION_CLAIMS_FILENAME,
        indeterminate_write_lock=safety_root / INDETERMINATE_LOCK_FILENAME,
        library_catalog=root / "library.json",
        previous_library_catalog=root / "library.previous.json",
        backup_root=backup_root,
        evidence_root=root / "Evidence",
        prepared_content_root=prepared_root,
        source_metadata_root=prepared_root / "Source Metadata",
        preview_cache_root=root / "Cache" / "Previews",
        latest_backup_record=backup_root / "latest-complete.json",
    )


def resource_path(*parts: str, bundle_root: Optional[Path] = None) -> Path:
    """Resolve a bundled resource independently of the process working dir."""

    if any(Path(part).is_absolute() or ".." in Path(part).parts for part in parts):
        raise ValueError("resource path must stay inside the application bundle")
    if bundle_root is not None:
        base = Path(bundle_root)
    elif getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base.joinpath(*parts)


__all__ = [
    "ApplicationPaths",
    "EXECUTION_CLAIMS_FILENAME",
    "INDETERMINATE_LOCK_FILENAME",
    "LEGACY_APPLICATION_DIRECTORY_NAME",
    "PROPOSED_APPLICATION_DIRECTORY_NAME",
    "application_paths",
    "resource_path",
]
