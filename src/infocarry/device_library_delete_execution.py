"""Device Library integration of the existing exact guarded Delete operation.

This is a product facade, not a second writer. General root TXT, BMP, nested
files and directories remain unavailable for execution. Every selection is
bound to the library image the user saw and compared with a new complete
backup before approval. All execution authority remains in delete_workflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Callable, Sequence

from .desktop import DesktopWorkflowModel, InventoryRow
from .delete_workflow import ExperimentalRootTxtDeleteFacade, RootTxtDeleteBundle
from .library_transfer_execution import OwnerAuthorizedOperationIdentity
from .library_transfer_runtime_provider import PinnedRootTxtRuntime
from .p18_041h_experiment import FIXTURE_FILENAME, FIXTURE_PATH, FIXTURE_SHA256
from .prepared_library_package_live_adapter import PreparedLibraryPackageLiveResult, _backup_identity
from .protocol import TransferCancelledError
from .write_gate import verify_fresh_backup


class DeviceLibraryDeleteError(ValueError):
    def __init__(self, message: str, *, stage: str = "selection"):
        self.stage = stage
        super().__init__(message)


@dataclass(frozen=True)
class DeviceDeleteSelection:
    backup_directory: Path
    baseline_blob_sha256: str
    row: InventoryRow
    device_model: str = "VNW-V15"

    @property
    def filename(self) -> str:
        return self.row.display_name.rsplit("\\", 1)[-1]


def select_device_library_delete(
    model: DesktopWorkflowModel, offsets: Sequence[int], *, device_model: str = "VNW-V15"
) -> DeviceDeleteSelection:
    """Cheap UI admission; fresh backup/candidate validation happens off Tk."""
    if device_model != "VNW-V15":
        raise DeviceLibraryDeleteError("Delete is unavailable for this device model.")
    if len(offsets) != 1:
        raise DeviceLibraryDeleteError("Select exactly one root-level TXT file to delete.")
    rows = model.rows()
    selected = [row for row in rows if row.record_offset == offsets[0]]
    if len(selected) != 1:
        raise DeviceLibraryDeleteError("The selected file is missing or ambiguous. Refresh Device Library.")
    row = selected[0]
    if row.kind != "file" or len(row.path.split("\\")) != 2 or row.path.split("\\")[0] != "root":
        raise DeviceLibraryDeleteError("Root, system entries, folders and nested files cannot be deleted.")
    if row.extension != "txt":
        raise DeviceLibraryDeleteError("Only the demonstrated root-level TXT operation is available.")
    if sum(other.display_name == row.display_name for other in rows) != 1:
        raise DeviceLibraryDeleteError("The selected path is ambiguous. Delete is unavailable.")
    if (row.display_name != FIXTURE_PATH or row.payload_bytes != 29
            or row.payload_sha256 != FIXTURE_SHA256):
        raise DeviceLibraryDeleteError("General root-level TXT deletion still requires hardware validation.")
    if model.state.backup_directory is None or model.state.source_blob_sha256 is None:
        raise DeviceLibraryDeleteError("Load a complete backup before selecting Delete.")
    return DeviceDeleteSelection(model.state.backup_directory, model.state.source_blob_sha256, row, device_model)


@dataclass(frozen=True)
class PreparedDeviceDelete:
    selection: DeviceDeleteSelection
    bundle: RootTxtDeleteBundle
    owner_identity: OwnerAuthorizedOperationIdentity

    @property
    def confirmation_message(self) -> str:
        return (
            f"Delete {self.selection.filename} from Sony InfoCarry VNW-V15?\n\n"
            "Operation: Delete (Experimental)\n"
            "Deletion modifies device storage. A fresh complete backup has been verified. "
            "The Manager will delete once, independently verify the result, and refresh Device Library.\n\n"
            "Backup is not undo. Keep the InfoCarry connected until verification finishes. "
            "A started operation cannot be cancelled or automatically retried."
        )


class DeviceLibraryDeleteService:
    """Own one UI attempt while delegating all safety decisions to P18-041."""

    def __init__(self, runtime_factory: Callable[[], PinnedRootTxtRuntime]):
        self._runtime_factory = runtime_factory
        self._facade = None
        self._prepared = None
        self._preparation_closed = threading.Event()
        self._preparation_lock = threading.RLock()

    def close_preparation(self) -> None:
        """Teardown cancels reads; a completed, undelivered review is released."""
        self._preparation_closed.set()
        with self._preparation_lock:
            if self._prepared is not None:
                self.discard()

    def discard(self) -> None:
        facade = self._facade
        self._facade = None
        self._prepared = None
        if facade is not None:
            facade.discard_prepared_operation()

    def prepare(self, selection: DeviceDeleteSelection, *, cancelled=None, progress=None) -> PreparedDeviceDelete:
        user_cancelled = cancelled
        cancelled = lambda: self._preparation_closed.is_set() or (user_cancelled is not None and user_cancelled())
        if self._facade is not None:
            raise DeviceLibraryDeleteError("An existing Delete review must be discarded first.", stage="approval")
        # Re-admit the exact selection from its immutable archive before opening
        # any runtime. Caller-created tokens cannot bypass capability admission.
        original = DesktopWorkflowModel()
        original.load_backup(selection.backup_directory)
        admitted = select_device_library_delete(original, (selection.row.record_offset,), device_model=selection.device_model)
        if admitted != selection:
            raise DeviceLibraryDeleteError("The selected file or library has changed. Refresh Device Library.", stage="approval")
        before = verify_fresh_backup(selection.backup_directory, max_age_seconds=None)
        identity = _backup_identity(before)
        if cancelled is not None and cancelled():
            raise TransferCancelledError("Delete preparation cancelled before execution")
        try:
            self._facade = ExperimentalRootTxtDeleteFacade(self._runtime_factory())
            bundle = self._facade.prepare(target_path=selection.row.display_name,
                device_model=selection.device_model, cancelled=cancelled, progress=progress)
            if (_backup_identity(bundle.before_backup) != identity
                    or bundle.candidate.core.target_record_offset != selection.row.record_offset):
                raise DeviceLibraryDeleteError("Device contents changed since the displayed backup. Refresh Device Library.", stage="approval")
            owner = OwnerAuthorizedOperationIdentity.from_bundle(bundle)
            with self._preparation_lock:
                if cancelled():
                    raise TransferCancelledError("Delete preparation cancelled before review")
                self._prepared = PreparedDeviceDelete(selection, bundle, owner)
                return self._prepared
        except BaseException:
            self.discard()
            raise

    def execute_once(self, prepared: PreparedDeviceDelete, *, confirmed: bool, progress=None):
        """One normal Delete/Cancel decision binds the frozen internal identity."""
        try:
            if prepared is not self._prepared or self._facade is None:
                raise DeviceLibraryDeleteError("Delete approval is no longer valid. Review the selection again.", stage="approval")
            if type(confirmed) is not bool:
                raise DeviceLibraryDeleteError("An explicit Delete or Cancel choice is required.", stage="approval")
            if not confirmed:
                return None
            prepared.bundle.verify_seal()
            if OwnerAuthorizedOperationIdentity.from_bundle(prepared.bundle) != prepared.owner_identity:
                raise DeviceLibraryDeleteError("The approved operation changed. Review the selection again.", stage="approval")
            self._facade.authorize_prepared_operation(prepared.owner_identity.approval_phrase)
            review = prepared.bundle.review_dict()
            def confirmation(current):
                if current != review:
                    raise DeviceLibraryDeleteError("Delete review changed after confirmation.", stage="approval")
                return prepared.bundle.authorization.core.confirmation_phrase
            return self._facade.execute_once(confirmation_interaction=confirmation, progress=progress)
        finally:
            self.discard()


def load_verified_delete_result(model: DesktopWorkflowModel, result):
    """Refresh from verified post-write evidence, never from guessed removals."""
    if (type(result) is not PreparedLibraryPackageLiveResult
            or type(result.preflight) is not RootTxtDeleteBundle
            or result.audit.get("state") != "readback_verified"
            or result.audit.get("completion") != "0x0000"
            or result.audit.get("execution_claim", {}).get("sender_marker", {}).get("resolved") is not True):
        raise DeviceLibraryDeleteError("Verified complete post-delete evidence is unavailable.", stage="verification")
    try:
        result.preflight.reconcile_result(result)
        from .backup_history import summarize_complete_backup
        summary = summarize_complete_backup(result.after_backup.directory)
        model.load_backup(result.after_backup.directory)
        return summary
    except Exception as exc:
        raise DeviceLibraryDeleteError("Complete post-delete evidence could not be verified.", stage="verification") from exc


def delete_failure_message(error: BaseException) -> str:
    """Stable product guidance; detailed exception/audit stays in Technical Details."""
    state, stage = getattr(error, "state", None), getattr(error, "stage", None)
    if state == "indeterminate_after_transaction_start":
        return "Delete outcome is uncertain. Writes are locked. Preserve the evidence and use read-only diagnosis; do not retry."
    if stage in {"post_write_backup", "post_write_verification", "post_operation_readback", "post_delete_readback", "verification", "result_reconciliation"}:
        return "Delete verification failed. Preserve the backups and use read-only diagnosis; do not retry."
    if stage in {"write", "write_completion", "send", "transfer"}:
        return "Delete transfer failed. No automatic retry was attempted. Review the preserved result before another operation."
    if stage in {"approval", "owner_authorization", "preflight_revalidation", "operation_bundle", "confirmation"}:
        return "Delete approval was invalidated by changed device contents or operation details. Refresh Device Library and review again."
    if stage in {"write_guard", "claim_configuration"}:
        return "Delete is blocked by existing write-safety state. Use read-only diagnosis and preserve the safety files."
    if isinstance(error, DeviceLibraryDeleteError):
        return str(error)
    from .usb_access import DeviceAccessError
    if isinstance(error, DeviceAccessError):
        return "InfoCarry is disconnected or inaccessible. Reconnect and refresh Device Library."
    return "Delete preparation or backup failed. No new operation will be retried automatically. Check the connection and preserved evidence."
