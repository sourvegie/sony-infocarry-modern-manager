"""R3 host-only bridge from one Library package to the reviewed package path.

This module is deliberately not imported by the normal CLI or ttk application.
It accepts exactly one revalidated P17-002 package item, enriches the existing
P16 multi-child candidate with a hash-only Library binding, and reuses the
existing fake-only guarded workflow.  It does not detect USB, capture a real
backup, authorize a live operation, or send a transaction.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional

from .backup_format import ParsedBackupBlob
from .capacity_evidence import NativeCapacityResponse
from .library import (
    LIBRARY_FORMAT,
    LIBRARY_VERSION,
    PREPARATION_PREPARED,
    SOURCE_PRESENT,
    STATE_READY,
    LibraryCatalog,
    LibraryItem,
)
from .prepared_media_package import (
    PREPARED_MEDIA_PACKAGE_FORMAT,
    PreparedMediaPackageError,
    PreparedMediaPackageImport,
    load_prepared_media_package,
)
from .prepared_multi_package_gate import (
    PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_EXPLICIT,
    PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_FIXED,
    PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE,
    PreparedMultiPackageAuthorization,
    PreparedMultiPackageGateError,
    authorize_prepared_multi_package,
)
from .prepared_multi_package_workflow import (
    CancelledCallback,
    CaptureCallback,
    DetectDeviceCallback,
    GuardedPreparedMultiPackageWorkflow,
    PreparedMultiFakeTransport,
    PreparedMultiPackageWorkflowResult,
    ProgressCallback,
)
from .prepared_package_multi_candidate import (
    PreparedMultiCandidateError,
    PreparedMultiPackageCandidate,
    REVIEWED_TEMPLATE_SUBSET_POLICY_SHA256,
    build_prepared_multi_package_candidate,
)
from .write_gate import DEFAULT_MAX_AGE_SECONDS, VerifiedBackup


P17_003_BRIDGE_FORMAT = "infocarry-p17-003-library-package-bridge-v1"
P17_003_PROFILE = "one_root_folder_ordered_txt_bmp_txt"
P17_003_CONFIRMATION_PHRASE = PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE
P17_003_TEMPLATE_FOLDER_PATH = ("root", "IC_P16_MIXED_20260830_01")
P17_003_TEMPLATE_ITEM_PATHS = {
    "txt": (*P17_003_TEMPLATE_FOLDER_PATH, "01-introduction"),
    "bmp": (*P17_003_TEMPLATE_FOLDER_PATH, "02-page-01"),
}
# The complete P16-001 post-operation dynamic blob is the reviewed native
# mixed-package template.  The core candidate builder deliberately accepts a
# caller-supplied template for reuse by generic offline tests; this bridge is
# narrower and therefore rejects any other template bytes before construction.
P17_003_REVIEWED_TEMPLATE_BLOB_SHA256 = (
    REVIEWED_TEMPLATE_SUBSET_POLICY_SHA256
)
P17_003_TIMESTAMP_POLICY = "one_explicit_frozen_value_for_new_records_only"
P17_003_RUNNER_FORMAT = "infocarry-p17-003-library-package-preflight-v1"


class PreparedLibraryPackageBridgeError(ValueError):
    """Raised when the selected Library package cannot be bridged safely."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.lower() != value
    ):
        raise PreparedLibraryPackageBridgeError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise PreparedLibraryPackageBridgeError(
            f"{label} must be a lowercase SHA-256 digest"
        ) from exc
    return value


def _freeze_report(value: Any) -> Any:
    """Recursively freeze a hash-bound report before exposing it."""

    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_report(child) for key, child in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_report(child) for child in value)
    return value


def _thaw_report(value: Any) -> Any:
    """Return a JSON-friendly detached view of a frozen report."""

    if isinstance(value, Mapping):
        return {key: _thaw_report(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw_report(child) for child in value]
    return value


def _audit_without_seal(audit: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical report content covered by the preflight seal."""

    value = _thaw_report(audit)
    if not isinstance(value, dict):
        raise PreparedLibraryPackageBridgeError("preflight audit is not an object")
    value.pop("preflight_seal_sha256", None)
    return value


def _source_size(child: Mapping[str, Any]) -> int:
    source = child.get("source")
    if not isinstance(source, Mapping):
        raise PreparedLibraryPackageBridgeError("package child source metadata is malformed")
    value = source.get("utf8_bytes", source.get("bytes"))
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PreparedLibraryPackageBridgeError("package child source size is malformed")
    return value


def _child_binding(child: Mapping[str, Any], package_root: Path) -> dict[str, Any]:
    kind = child.get("kind")
    if kind not in {"txt", "bmp"}:
        raise PreparedLibraryPackageBridgeError("package child kind is unsupported")
    source = child.get("source")
    if not isinstance(source, Mapping):
        raise PreparedLibraryPackageBridgeError("package child source metadata is malformed")
    package_path = child.get("package_path")
    prepared_path = child.get("prepared_path")
    source_path = source.get("path")
    if not all(isinstance(value, str) and value for value in (package_path, prepared_path, source_path)):
        raise PreparedLibraryPackageBridgeError("package child path binding is malformed")
    payload_hash = (
        child.get("authoring", {}).get("prepared_payload_sha256")
        if kind == "txt" and isinstance(child.get("authoring"), Mapping)
        else child.get("bmp", {}).get("payload_sha256")
        if kind == "bmp" and isinstance(child.get("bmp"), Mapping)
        else None
    )
    _digest(source.get("sha256"), "package child source hash")
    _digest(payload_hash, "package child prepared payload hash")
    if kind == "txt":
        authoring = child.get("authoring")
        prepared_size = (
            authoring.get("prepared_payload_bytes")
            if isinstance(authoring, Mapping)
            else None
        )
    else:
        # The validated prepared BMP is an exact copy of the source BMP.
        prepared_size = _source_size(child)
    if isinstance(prepared_size, bool) or not isinstance(prepared_size, int) or prepared_size < 0:
        raise PreparedLibraryPackageBridgeError("package child prepared size is malformed")
    return {
        "order": child.get("order"),
        "kind": kind,
        "name": child.get("name"),
        "target_path": child.get("path"),
        "source_path": source_path,
        "source_archive_path": package_path,
        "prepared_archive_path": prepared_path,
        "source_sha256": source.get("sha256"),
        "source_bytes": _source_size(child),
        "prepared_payload_sha256": payload_hash,
        "prepared_payload_bytes": prepared_size,
        "package_root": str(package_root),
    }


def _library_binding(
    catalog: LibraryCatalog,
    item: LibraryItem,
    imported: PreparedMediaPackageImport,
) -> dict[str, Any]:
    item_dict = item.to_dict()
    children = tuple(_child_binding(child, imported.root) for child in imported.children)
    return {
        "format": P17_003_BRIDGE_FORMAT,
        "library_format": LIBRARY_FORMAT,
        "library_version": LIBRARY_VERSION,
        "catalog_path": str(catalog.path.expanduser().resolve()),
        "catalog_sha256": _sha256(_canonical_json(catalog.to_dict())),
        "catalog_item_id": item.item_id,
        "catalog_item_sha256": _sha256(_canonical_json(item_dict)),
        "package_contract": PREPARED_MEDIA_PACKAGE_FORMAT,
        "package_root": str(imported.root),
        "manifest_path": str(imported.manifest_path),
        "manifest_sha256": imported.manifest_sha256,
        "folder_name": imported.package.folder_name,
        "profile": P17_003_PROFILE,
        "ordered_children": list(children),
        "grouping_policy": "explicit_manifest_one_library_item_no_inference",
        "ownership_policy": "non_owning_original_files_unchanged",
    }


def _validate_selected_package(
    catalog: LibraryCatalog,
    selected_item_id: str,
) -> tuple[LibraryItem, PreparedMediaPackageImport, dict[str, Any]]:
    if not isinstance(catalog, LibraryCatalog):
        raise PreparedLibraryPackageBridgeError("a LibraryCatalog is required")
    if not isinstance(selected_item_id, str) or not selected_item_id:
        raise PreparedLibraryPackageBridgeError("exactly one Library item ID is required")
    try:
        item = catalog.get(selected_item_id)
    except Exception as exc:
        raise PreparedLibraryPackageBridgeError(str(exc)) from exc
    if item.package is None:
        raise PreparedLibraryPackageBridgeError(
            "selected Library item is not an explicitly imported prepared package"
        )
    if (
        item.state != STATE_READY
        or item.preparation_state != PREPARATION_PREPARED
        or item.source_status != SOURCE_PRESENT
        or not item.supported
    ):
        raise PreparedLibraryPackageBridgeError(
            "selected Library package is stale, missing, unsupported, or not prepared"
        )
    package_root = Path(item.package.root_path).expanduser().resolve()
    if str(package_root) != item.package.root_path:
        raise PreparedLibraryPackageBridgeError("Library package root is not canonical")
    try:
        imported = load_prepared_media_package(package_root)
    except (OSError, PreparedMediaPackageError) as exc:
        raise PreparedLibraryPackageBridgeError(
            f"selected Library package failed manifest revalidation: {exc}"
        ) from exc
    if str(imported.manifest_path) != item.package.manifest_path:
        raise PreparedLibraryPackageBridgeError("Library manifest path binding differs")
    if imported.manifest_sha256 != item.package.manifest_sha256:
        raise PreparedLibraryPackageBridgeError("Library manifest hash binding differs")
    if imported.manifest_sha256 != item.prepared_manifest_sha256:
        raise PreparedLibraryPackageBridgeError("Library prepared hash binding differs")
    manifest_size = imported.manifest_path.stat().st_size
    if (
        item.source_path != str(imported.root)
        or item.source_filename != imported.root.name
        or item.source_sha256 != imported.manifest_sha256
        or item.source_size_bytes != manifest_size
        or item.observed_source_sha256 != imported.manifest_sha256
        or item.observed_source_size_bytes != manifest_size
    ):
        raise PreparedLibraryPackageBridgeError(
            "Library source/manifest binding differs from the verified package"
        )
    if not item.source_observations:
        raise PreparedLibraryPackageBridgeError(
            "Library package has no source observation for the verified manifest"
        )
    latest_observation = item.source_observations[-1]
    if (
        latest_observation.get("status") != SOURCE_PRESENT
        or latest_observation.get("sha256") != imported.manifest_sha256
        or latest_observation.get("size_bytes") != manifest_size
    ):
        raise PreparedLibraryPackageBridgeError(
            "Library source observation differs from the verified manifest"
        )
    if tuple(dict(child) for child in imported.children) != item.package.children:
        raise PreparedLibraryPackageBridgeError(
            "authoritative package child grouping differs from the Library record"
        )
    items = tuple(imported.package.items)
    expected_names = (
        "01-introduction.txt",
        "02-page-01.bmp",
        "03-ending.txt",
    )
    if len(items) != 3 or tuple(item.name for item in items) != expected_names:
        raise PreparedLibraryPackageBridgeError(
            "selected package must be exactly introduction TXT, BMP page, ending TXT"
        )
    if tuple(item.kind for item in items) != ("txt", "bmp", "txt"):
        raise PreparedLibraryPackageBridgeError(
            "selected package must have ordered TXT/BMP/TXT children"
        )
    if imported.package.folder_name != item.package.folder_name:
        raise PreparedLibraryPackageBridgeError("Library package folder binding differs")
    binding = _library_binding(catalog, item, imported)
    return item, imported, binding


def _attach_library_binding(
    candidate: PreparedMultiPackageCandidate,
    binding: Mapping[str, Any],
) -> PreparedMultiPackageCandidate:
    audit = dict(candidate.audit_dict())
    audit["library_binding"] = json.loads(json.dumps(binding, ensure_ascii=True))
    audit["bridge"] = {
        "format": P17_003_BRIDGE_FORMAT,
        "profile": P17_003_PROFILE,
        "state": "offline_host_readiness_only",
        "candidate_bytes_exposed": False,
        "hardware_accessed": False,
    }
    return replace(candidate, audit=audit)


@dataclass(frozen=True)
class PreparedLibraryPackageCandidate:
    """Existing native candidate plus one exact Library binding."""

    core: PreparedMultiPackageCandidate
    library_binding: Mapping[str, Any]

    @property
    def package(self):
        return self.core.package

    @property
    def candidate_blob(self) -> bytes:
        return self.core.candidate_blob

    @property
    def candidate_blob_sha256(self) -> str:
        return self.core.candidate_blob_sha256

    @property
    def transaction(self):
        return self.core.transaction

    @property
    def transaction_sha256(self) -> str:
        return self.core.transaction_sha256

    def audit_dict(self) -> dict[str, Any]:
        return self.core.audit_dict()


@dataclass(frozen=True)
class PreparedLibraryPackageAuthorization:
    """Core authorization plus immutable-in-practice Library identity binding."""

    core: PreparedMultiPackageAuthorization
    library_binding: Mapping[str, Any]
    library_binding_sha256: str

    def __post_init__(self) -> None:
        actual = _sha256(_canonical_json(self.library_binding))
        if actual != self.library_binding_sha256:
            raise PreparedLibraryPackageBridgeError(
                "Library authorization binding hash does not match its contents"
            )

    def require_same_candidate(self, candidate: PreparedLibraryPackageCandidate) -> None:
        if not isinstance(candidate, PreparedLibraryPackageCandidate):
            raise PreparedLibraryPackageBridgeError("Library candidate binding is invalid")
        self.core.require_same_candidate(candidate.core)
        if candidate.library_binding != self.library_binding:
            raise PreparedLibraryPackageBridgeError(
                "Library candidate top-level binding differs from authorization"
            )
        if _sha256(_canonical_json(candidate.library_binding)) != self.library_binding_sha256:
            raise PreparedLibraryPackageBridgeError(
                "Library candidate top-level binding hash differs from authorization"
            )
        candidate_binding = candidate.core.audit.get("library_binding")
        if candidate_binding != self.library_binding:
            raise PreparedLibraryPackageBridgeError(
                "Library catalog/package binding differs from authorization"
            )
        if _sha256(_canonical_json(candidate_binding)) != self.library_binding_sha256:
            raise PreparedLibraryPackageBridgeError(
                "Library candidate binding hash differs from authorization"
            )

    def to_dict(self) -> dict[str, Any]:
        value = self.core.to_dict()
        value["bridge"] = {
            "format": P17_003_BRIDGE_FORMAT,
            "library_binding_sha256": self.library_binding_sha256,
            "library_binding": json.loads(
                json.dumps(self.library_binding, ensure_ascii=True)
            ),
        }
        return value


def authorize_prepared_library_package(
    candidate: PreparedLibraryPackageCandidate,
    *,
    confirmation: str,
    confirmation_policy: str = PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_FIXED,
) -> PreparedLibraryPackageAuthorization:
    if not isinstance(candidate, PreparedLibraryPackageCandidate):
        raise PreparedLibraryPackageBridgeError("Library candidate is invalid")
    if (
        confirmation_policy == PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_FIXED
        and confirmation != P17_003_CONFIRMATION_PHRASE
    ):
        raise PreparedLibraryPackageBridgeError(
            "wrong prepared-package confirmation phrase"
        )
    binding = candidate.library_binding
    nested_binding = candidate.core.audit.get("library_binding")
    if not isinstance(binding, Mapping) or binding != nested_binding:
        raise PreparedLibraryPackageBridgeError(
            "candidate Library bindings are inconsistent"
        )
    try:
        core = authorize_prepared_multi_package(
            candidate.core,
            confirmation=confirmation,
            confirmation_policy=confirmation_policy,
        )
    except PreparedMultiPackageGateError as exc:
        raise PreparedLibraryPackageBridgeError(str(exc)) from exc
    binding_copy = json.loads(json.dumps(binding, ensure_ascii=True))
    return PreparedLibraryPackageAuthorization(
        core=core,
        library_binding=binding_copy,
        library_binding_sha256=_sha256(_canonical_json(binding_copy)),
    )


def build_prepared_library_package_candidate(
    catalog: LibraryCatalog,
    selected_item_id: str,
    backup: VerifiedBackup,
    template: ParsedBackupBlob,
    *,
    new_record_timestamp_be32: int,
    native_capacity_response: NativeCapacityResponse,
    template_folder_path: tuple[str, ...] = P17_003_TEMPLATE_FOLDER_PATH,
    template_item_paths: Optional[Mapping[str, tuple[str, ...]]] = None,
) -> PreparedLibraryPackageCandidate:
    """Revalidate one imported package and enrich the existing native builder."""

    if not isinstance(backup, VerifiedBackup):
        raise PreparedLibraryPackageBridgeError("a verified offline backup is required")
    if not isinstance(native_capacity_response, NativeCapacityResponse):
        raise PreparedLibraryPackageBridgeError(
            "parsed native 0x0019 capacity evidence is required"
        )
    _item, imported, binding = _validate_selected_package(catalog, selected_item_id)
    paths = dict(template_item_paths or P17_003_TEMPLATE_ITEM_PATHS)
    if tuple(template_folder_path) != P17_003_TEMPLATE_FOLDER_PATH:
        raise PreparedLibraryPackageBridgeError(
            "only the reviewed native mixed-package template is supported"
        )
    if paths != P17_003_TEMPLATE_ITEM_PATHS:
        raise PreparedLibraryPackageBridgeError(
            "template paths do not match the reviewed native TXT/BMP records"
        )
    if _sha256(template.data) != P17_003_REVIEWED_TEMPLATE_BLOB_SHA256:
        raise PreparedLibraryPackageBridgeError(
            "template bytes do not match the reviewed native mixed-package template"
        )
    try:
        core = build_prepared_multi_package_candidate(
            imported.package,
            backup,
            template,
            new_record_timestamp_be32=new_record_timestamp_be32,
            native_capacity_response=native_capacity_response,
            template_folder_path=tuple(template_folder_path),
            template_item_paths=paths,
            template_subset_policy_sha256=P17_003_REVIEWED_TEMPLATE_BLOB_SHA256,
            allow_verified_bookmarks=True,
        )
    except (PreparedMultiCandidateError, OSError) as exc:
        raise PreparedLibraryPackageBridgeError(
            f"selected Library package candidate construction failed: {exc}"
        ) from exc
    enriched = _attach_library_binding(core, binding)
    return PreparedLibraryPackageCandidate(enriched, binding)


def _sealed_backup_dict(backup: VerifiedBackup) -> dict[str, Any]:
    value = backup.to_dict()
    value.pop("verified_at_utc", None)
    return value


def _seal_payload(
    *,
    candidate: PreparedLibraryPackageCandidate,
    authorization: PreparedLibraryPackageAuthorization,
    backup: VerifiedBackup,
    capacity_response: NativeCapacityResponse,
    template: ParsedBackupBlob,
    template_folder_path: tuple[str, ...],
    template_item_paths: Mapping[str, tuple[str, ...]],
    new_record_timestamp_be32: int,
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "format": P17_003_RUNNER_FORMAT,
        "candidate": candidate.audit_dict(),
        "authorization": authorization.to_dict(),
        "before_backup": _sealed_backup_dict(backup),
        "capacity_response": capacity_response.to_dict(),
        "template_sha256": _sha256(template.data),
        "template_folder_path": list(template_folder_path),
        "template_item_paths": {
            key: list(value) for key, value in sorted(template_item_paths.items())
        },
        "new_record_timestamp_be32": f"0x{new_record_timestamp_be32:08x}",
        "confirmation_phrase": P17_003_CONFIRMATION_PHRASE,
        "automatic_retry_allowed": False,
        "read_only_hardware_accessed": bool(
            audit.get("read_only_hardware_accessed", False)
        ),
        "hardware_write_performed": bool(
            audit.get("hardware_write_performed", False)
        ),
        "audit": _audit_without_seal(audit),
    }


def _seal_sha256(**kwargs: Any) -> str:
    return _sha256(_canonical_json(_seal_payload(**kwargs)))


@dataclass(frozen=True)
class PreparedLibraryPackagePreflight:
    """Hash-bound offline readiness record; it is not live authorization."""

    candidate: PreparedLibraryPackageCandidate
    authorization: PreparedLibraryPackageAuthorization
    before_backup: VerifiedBackup
    capacity_response: NativeCapacityResponse
    template: ParsedBackupBlob
    template_folder_path: tuple[str, ...]
    template_item_paths: tuple[tuple[str, tuple[str, ...]], ...]
    new_record_timestamp_be32: int
    seal_sha256: str
    audit: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "audit", _freeze_report(self.audit))

    def _paths(self) -> dict[str, tuple[str, ...]]:
        return dict(self.template_item_paths)

    def verify_seal(self) -> None:
        report = self.to_dict()
        if report.get("preflight_seal_sha256") != self.seal_sha256:
            raise PreparedLibraryPackageBridgeError(
                "prepared Library package preflight report seal is missing or modified"
            )
        actual = _seal_sha256(
            candidate=self.candidate,
            authorization=self.authorization,
            backup=self.before_backup,
            capacity_response=self.capacity_response,
            template=self.template,
            template_folder_path=self.template_folder_path,
            template_item_paths=self._paths(),
            new_record_timestamp_be32=self.new_record_timestamp_be32,
            audit=self.audit,
        )
        if actual != self.seal_sha256:
            raise PreparedLibraryPackageBridgeError(
                "prepared Library package preflight seal was modified"
            )
        self.authorization.require_same_candidate(self.candidate)

    def to_dict(self) -> dict[str, Any]:
        return _thaw_report(self.audit)


def prepare_prepared_library_package_preflight(
    catalog: LibraryCatalog,
    selected_item_id: str,
    backup: VerifiedBackup,
    template: ParsedBackupBlob,
    *,
    new_record_timestamp_be32: int,
    native_capacity_response: NativeCapacityResponse,
    template_folder_path: tuple[str, ...] = P17_003_TEMPLATE_FOLDER_PATH,
    template_item_paths: Optional[Mapping[str, tuple[str, ...]]] = None,
    confirmation_phrase: str = P17_003_CONFIRMATION_PHRASE,
    confirmation_policy: str = PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_FIXED,
) -> PreparedLibraryPackagePreflight:
    """Prepare one exact future operation without device access or USB."""

    candidate = build_prepared_library_package_candidate(
        catalog,
        selected_item_id,
        backup,
        template,
        new_record_timestamp_be32=new_record_timestamp_be32,
        native_capacity_response=native_capacity_response,
        template_folder_path=template_folder_path,
        template_item_paths=template_item_paths,
    )
    authorization = authorize_prepared_library_package(
        candidate,
        confirmation=confirmation_phrase,
        confirmation_policy=confirmation_policy,
    )
    audit = {
        "format": P17_003_RUNNER_FORMAT,
        "state": "ready_for_hardware_test_host_only",
        "read_only_hardware_accessed": False,
        "hardware_write_performed": False,
        "hardware_transaction_performed": False,
        "device_changing_operation_performed": False,
        "send_count": 0,
        "candidate_bytes_exposed": False,
        "library_binding": candidate.library_binding,
        "candidate": candidate.audit_dict(),
        "authorization": authorization.to_dict(),
        "before_backup": _sealed_backup_dict(backup),
        "capacity_response": native_capacity_response.to_dict(),
        "template_sha256": _sha256(template.data),
        "template_folder_path": list(template_folder_path),
        "template_item_paths": {
            key: list(value)
            for key, value in sorted(
                dict(template_item_paths or P17_003_TEMPLATE_ITEM_PATHS).items()
            )
        },
        "timestamp_policy": {
            "name": P17_003_TIMESTAMP_POLICY,
            "existing_records": "preserve_exactly",
            "new_records": "one_explicit_frozen_value",
            "legacy_global_rewrite_reproduced": False,
        },
        "confirmation_phrase": confirmation_phrase,
        "confirmation_policy": confirmation_policy,
        "automatic_retry_allowed": False,
        "normal_gui_cli_transfer_exposed": False,
    }
    seal = _seal_sha256(
        candidate=candidate,
        authorization=authorization,
        backup=backup,
        capacity_response=native_capacity_response,
        template=template,
        template_folder_path=tuple(template_folder_path),
        template_item_paths=dict(
            template_item_paths or P17_003_TEMPLATE_ITEM_PATHS
        ),
        new_record_timestamp_be32=new_record_timestamp_be32,
        audit=audit,
    )
    audit["preflight_seal_sha256"] = seal
    return PreparedLibraryPackagePreflight(
        candidate=candidate,
        authorization=authorization,
        before_backup=backup,
        capacity_response=native_capacity_response,
        template=template,
        template_folder_path=tuple(template_folder_path),
        template_item_paths=tuple(
            sorted(
                dict(template_item_paths or P17_003_TEMPLATE_ITEM_PATHS).items()
            )
        ),
        new_record_timestamp_be32=new_record_timestamp_be32,
        seal_sha256=seal,
        audit=audit,
    )


@dataclass(frozen=True)
class PreparedLibraryPackageWorkflowResult:
    """Fake-host result retaining the Library-enriched candidate binding."""

    preflight: PreparedLibraryPackagePreflight
    candidate: PreparedLibraryPackageCandidate
    authorization: PreparedLibraryPackageAuthorization
    before_backup: VerifiedBackup
    after_backup: VerifiedBackup
    completion: int
    verification: Any
    audit: Mapping[str, Any]


def run_prepared_library_package_fake_workflow(
    preflight: PreparedLibraryPackagePreflight,
    *,
    catalog: LibraryCatalog,
    selected_item_id: str,
    backup_destination: Path,
    post_operation_destination: Path,
    capture: CaptureCallback,
    transport: PreparedMultiFakeTransport,
    detect_device: DetectDeviceCallback,
    query_capacity: Callable[[], NativeCapacityResponse],
    cancelled: Optional[CancelledCallback] = None,
    progress: Optional[ProgressCallback] = None,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
    timeout_seconds: float = 60.0,
    clock: Callable[[], float] = time.monotonic,
) -> PreparedLibraryPackageWorkflowResult:
    """Exercise the guarded fake workflow after revalidating Library state.

    The injected transport is the only accepted transport boundary.  This
    helper is for host tests and does not provide a live sender.
    """

    preflight.verify_seal()
    current = build_prepared_library_package_candidate(
        catalog,
        selected_item_id,
        preflight.before_backup,
        preflight.template,
        new_record_timestamp_be32=preflight.new_record_timestamp_be32,
        native_capacity_response=preflight.capacity_response,
        template_folder_path=preflight.template_folder_path,
        template_item_paths=preflight._paths(),
    )
    if current.audit_dict() != preflight.candidate.audit_dict():
        raise PreparedLibraryPackageBridgeError(
            "Library package candidate differs from the sealed preflight"
        )
    if not isinstance(transport, PreparedMultiFakeTransport):
        raise PreparedLibraryPackageBridgeError(
            "P17-003 fake workflow requires PreparedMultiFakeTransport"
        )

    def enrich(candidate: PreparedMultiPackageCandidate) -> PreparedMultiPackageCandidate:
        return _attach_library_binding(candidate, current.library_binding)

    workflow = GuardedPreparedMultiPackageWorkflow(
        capture,
        transport,
        preflight.template,
        detect_device=detect_device,
        query_capacity=query_capacity,
        template_folder_path=preflight.template_folder_path,
        template_item_paths=preflight._paths(),
        candidate_enricher=enrich,
    )
    result: PreparedMultiPackageWorkflowResult = workflow.run(
        backup_destination=backup_destination,
        post_operation_destination=post_operation_destination,
        package=current.package,
        preview=current.core,
        new_record_timestamp_be32=preflight.new_record_timestamp_be32,
        confirmation=preflight.authorization.core.confirmation_phrase,
        fake_transport=True,
        cancelled=cancelled,
        progress=progress,
        now=now,
        max_age_seconds=max_age_seconds,
        timeout_seconds=timeout_seconds,
        clock=clock,
    )
    candidate = PreparedLibraryPackageCandidate(
        result.candidate,
        current.library_binding,
    )
    authorization = PreparedLibraryPackageAuthorization(
        result.authorization,
        current.library_binding,
        _sha256(_canonical_json(current.library_binding)),
    )
    authorization.require_same_candidate(candidate)
    audit = dict(result.audit)
    audit["bridge"] = {
        "format": P17_003_BRIDGE_FORMAT,
        "library_binding_sha256": authorization.library_binding_sha256,
        "hardware_accessed": False,
        "hardware_transaction_performed": False,
    }
    audit["authorization"] = authorization.to_dict()
    return PreparedLibraryPackageWorkflowResult(
        preflight=preflight,
        candidate=candidate,
        authorization=authorization,
        before_backup=result.before_backup,
        after_backup=result.after_backup,
        completion=result.completion,
        verification=replace(result.verification, candidate=result.candidate),
        audit=audit,
    )


__all__ = [
    "P17_003_BRIDGE_FORMAT",
    "P17_003_CONFIRMATION_PHRASE",
    "P17_003_PROFILE",
    "P17_003_REVIEWED_TEMPLATE_BLOB_SHA256",
    "P17_003_RUNNER_FORMAT",
    "P17_003_TEMPLATE_FOLDER_PATH",
    "P17_003_TEMPLATE_ITEM_PATHS",
    "P17_003_TIMESTAMP_POLICY",
    "PreparedLibraryPackageAuthorization",
    "PreparedLibraryPackageBridgeError",
    "PreparedLibraryPackageCandidate",
    "PreparedLibraryPackagePreflight",
    "PreparedLibraryPackageWorkflowResult",
    "authorize_prepared_library_package",
    "build_prepared_library_package_candidate",
    "prepare_prepared_library_package_preflight",
    "run_prepared_library_package_fake_workflow",
]
