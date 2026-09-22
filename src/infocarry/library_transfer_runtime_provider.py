"""Lazy production dependencies for the canonical guarded Library route.

This provider constructs no device session and sends no USB request when it
is created. The reviewed P16 template remains an external, hash-verified
application Evidence artifact; it is never copied into the application bundle
or source repository. Device callbacks are invoked only by the existing
read-only preflight or guarded execution coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import time
from typing import Any, Callable, Optional

from .app_paths import ApplicationPaths, application_paths
from .backup import BackupClient, RawBackupArchive
from .capacity_evidence import NativeCapacityResponse
from .device_info import DeviceInfoClient
from .device_model_profile import VNW_V15_PROFILE
from .execution_claim_store import PersistentExecutionClaimStore
from .indeterminate_write_lock import PersistentIndeterminateWriteLock
from .library_transfer_execution import (
    LibraryTransferExecutionFacade,
    LibraryTransferExecutionRuntime,
)
from .prepared_library_package_bridge import (
    P17_003_REVIEWED_TEMPLATE_BLOB_SHA256,
)
from .write_safety_boundary import PersistentWriteSafetyOwner


REVIEWED_LIBRARY_TEMPLATE_FILENAME = "reviewed-vnw-v15-library-template.bin"
LIBRARY_TRANSFER_EVIDENCE_DIRECTORY_NAME = "Library Transfer Operations"


class LibraryTransferRuntimeConfigurationError(RuntimeError):
    """Production runtime is unavailable; the caller must remain read-only."""


def _require_v15_device(device: Any) -> tuple[int, int]:
    identity = (getattr(device, "idVendor", None), getattr(device, "idProduct", None))
    expected = tuple(int(value, 16) for value in VNW_V15_PROFILE.usb_identity or ())
    if identity != expected:
        raise LibraryTransferRuntimeConfigurationError(
            "only the reviewed Sony InfoCarry VNW-V15 USB identity is supported"
        )
    return identity


class _SessionBoundWriteBackend:
    """Open the existing write-capable USB session only at the sender seam."""

    def __init__(self, discover: Callable[[], Any], open_session: Callable[..., Any]):
        self._discover = discover
        self._open_session = open_session
        self._session: Optional[Any] = None
        self._backend: Optional[Any] = None

    def _ensure_session(self) -> Any:
        if self._backend is not None:
            return self._backend
        device = self._discover()
        _require_v15_device(device)
        session = self._open_session(device)
        _require_v15_device(session.device)
        from .transport import PyUsbWriteBackend

        self._session = session
        self._backend = PyUsbWriteBackend(session.device)
        return self._backend

    def control_out(
        self,
        request_type: int,
        request: int,
        value: int,
        index: int,
        data: bytes,
        timeout_ms: int,
    ) -> int:
        return self._ensure_session().control_out(
            request_type, request, value, index, data, timeout_ms
        )

    def control_in(
        self,
        request_type: int,
        request: int,
        value: int,
        index: int,
        length: int,
        timeout_ms: int,
    ) -> bytes:
        return self._ensure_session().control_in(
            request_type, request, value, index, length, timeout_ms
        )

    def bulk_write(self, endpoint: int, data: bytes, timeout_ms: int) -> int:
        return self._ensure_session().bulk_write(endpoint, data, timeout_ms)

    def close(self) -> None:
        session = self._session
        self._session = None
        self._backend = None
        if session is not None:
            session.close()


@dataclass
class ProductionLibraryTransferRuntimeProvider:
    """Build the shared runtime lazily from canonical app and safety paths."""

    paths: ApplicationPaths
    discover_device: Callable[[], Any]
    open_session: Callable[..., Any]
    unix_time: Callable[[], float]

    @classmethod
    def for_current_application(
        cls,
        *,
        paths: Optional[ApplicationPaths] = None,
        discover_device: Optional[Callable[[], Any]] = None,
        open_session: Optional[Callable[..., Any]] = None,
        unix_time: Callable[[], float] = time.time,
    ) -> "ProductionLibraryTransferRuntimeProvider":
        from .transport import InfoCarrySession
        from .usb_access import find_one_device

        return cls(
            paths=paths or application_paths(),
            discover_device=discover_device or find_one_device,
            open_session=open_session or InfoCarrySession.open,
            unix_time=unix_time,
        )

    @property
    def template_path(self) -> Path:
        return self.paths.evidence_root / REVIEWED_LIBRARY_TEMPLATE_FILENAME

    @property
    def evidence_namespace(self) -> Path:
        return self.paths.evidence_root / LIBRARY_TRANSFER_EVIDENCE_DIRECTORY_NAME

    def _load_reviewed_template(self) -> Any:
        from .backup_format import parse_backup_blob

        template_path = self.template_path
        if self.paths.evidence_root.is_symlink() or template_path.is_symlink():
            raise LibraryTransferRuntimeConfigurationError(
                "the reviewed template path must not be a symbolic link"
            )
        try:
            template_bytes = template_path.read_bytes()
        except OSError as exc:
            raise LibraryTransferRuntimeConfigurationError(
                "the reviewed VNW-V15 Library template is missing or unreadable; "
                f"provision {REVIEWED_LIBRARY_TEMPLATE_FILENAME} from preserved evidence "
                f"under {self.paths.evidence_root}: {exc}"
            ) from exc
        actual = hashlib.sha256(template_bytes).hexdigest()
        if actual != P17_003_REVIEWED_TEMPLATE_BLOB_SHA256:
            raise LibraryTransferRuntimeConfigurationError(
                "the external Library template does not match the exact reviewed "
                "P17-003 VNW-V15 template identity"
            )
        try:
            parsed = parse_backup_blob(template_bytes)
        except Exception as exc:
            raise LibraryTransferRuntimeConfigurationError(
                f"the exact reviewed Library template could not be parsed: {exc}"
            ) from exc
        if parsed.data != template_bytes:
            raise LibraryTransferRuntimeConfigurationError(
                "the parsed Library template differs from its preserved source bytes"
            )
        return parsed

    def create_runtime(
        self,
        *,
        write_safety_owner: PersistentWriteSafetyOwner,
    ) -> LibraryTransferExecutionRuntime:
        """Return canonical callbacks without discovering or opening USB."""

        if not isinstance(write_safety_owner, PersistentWriteSafetyOwner):
            raise LibraryTransferRuntimeConfigurationError(
                "the canonical application-wide write-safety owner is unavailable"
            )
        if not isinstance(
            write_safety_owner.execution_claim_store, PersistentExecutionClaimStore
        ) or not isinstance(
            write_safety_owner.indeterminate_write_lock,
            PersistentIndeterminateWriteLock,
        ):
            raise LibraryTransferRuntimeConfigurationError(
                "the shared execution-claim store and global indeterminate lock are required"
            )
        if write_safety_owner.device_model_profile != VNW_V15_PROFILE:
            raise LibraryTransferRuntimeConfigurationError(
                "the shared write-safety owner is not bound to the reviewed VNW-V15 profile"
            )
        expected_claim_path = self.paths.execution_claims_database.expanduser().resolve()
        expected_lock_path = self.paths.indeterminate_write_lock.expanduser().resolve()
        if (
            write_safety_owner.execution_claim_store.path.resolve() != expected_claim_path
            or write_safety_owner.indeterminate_write_lock.path.resolve() != expected_lock_path
        ):
            raise LibraryTransferRuntimeConfigurationError(
                "the shared write-safety owner does not use the canonical application claim and lock paths"
            )

        template = self._load_reviewed_template()

        def detect_device() -> tuple[int, int]:
            device = self.discover_device()
            return _require_v15_device(device)

        def query_capacity() -> NativeCapacityResponse:
            device = self.discover_device()
            identity = _require_v15_device(device)
            with self.open_session(device) as session:
                _require_v15_device(session.device)
                response = DeviceInfoClient(session).read_hardware()
            return NativeCapacityResponse.from_hardware_response(
                response,
                device_identity=identity,
            )

        def capture(
            destination: Path,
            *,
            cancelled: Optional[Callable[[], bool]] = None,
            progress: Optional[Callable[[str, int, int], None]] = None,
        ) -> None:
            device = self.discover_device()
            _require_v15_device(device)
            with self.open_session(device) as session:
                _require_v15_device(session.device)
                archive = RawBackupArchive.create(Path(destination))
                BackupClient(session).backup(
                    archive,
                    cancelled=cancelled,
                    progress=progress,
                )

        return LibraryTransferExecutionRuntime(
            template=template,
            template_path=self.template_path,
            evidence_namespace=self.evidence_namespace,
            detect_device=detect_device,
            query_capacity=query_capacity,
            capture=capture,
            backend=_SessionBoundWriteBackend(
                self.discover_device,
                self.open_session,
            ),
            execution_claim_store=write_safety_owner.execution_claim_store,
            indeterminate_write_lock=write_safety_owner.indeterminate_write_lock,
            new_record_timestamp_be32=lambda: int(self.unix_time()),
        )


def create_production_library_transfer_facade(
    *,
    paths: Optional[ApplicationPaths] = None,
    discover_device: Optional[Callable[[], Any]] = None,
    open_session: Optional[Callable[..., Any]] = None,
    unix_time: Callable[[], float] = time.time,
) -> LibraryTransferExecutionFacade:
    """Shared packaged-app factory; construction is inert and binding-free."""

    provider = ProductionLibraryTransferRuntimeProvider.for_current_application(
        paths=paths,
        discover_device=discover_device,
        open_session=open_session,
        unix_time=unix_time,
    )
    return LibraryTransferExecutionFacade(runtime_provider=provider)


def launch_production_manager() -> None:
    """Launch the common ttk Manager with the inert production provider."""

    from .desktop_ttk import launch_ttk_desktop

    launch_ttk_desktop(
        execution_facade=create_production_library_transfer_facade()
    )


__all__ = [
    "LIBRARY_TRANSFER_EVIDENCE_DIRECTORY_NAME",
    "LibraryTransferRuntimeConfigurationError",
    "ProductionLibraryTransferRuntimeProvider",
    "REVIEWED_LIBRARY_TEMPLATE_FILENAME",
    "create_production_library_transfer_facade",
    "launch_production_manager",
]
