"""Device Library integration of the existing exact guarded Delete operation.

This is a product facade, not a second writer. It admits the reviewed unread
root-TXT and root-BMP envelopes, plus retained exact validation targets;
the exact nested disposable is available only in explicit validation mode.
Ordinary nested files, unsupported BMPs and directories remain unavailable. Every selection
is bound to the library image the user saw and compared with a new complete
backup before approval. All execution authority remains in delete_workflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
import hashlib
import json
from typing import Callable, Sequence

from .desktop import DesktopWorkflowModel, InventoryRow
from .delete_workflow import (
    ExperimentalRootTxtDeleteFacade, RootTxtDeleteBundle,
    ROOT_TXT_DELETE_VALIDATION_FILES, validate_root_txt_delete_name,
    build_root_txt_delete, root_txt_delete_execution_supported,
    ROOT_BMP_DELETE_FIXTURE_PATH, build_experimental_root_bmp_delete, build_root_bmp_delete,
    root_bmp_delete_execution_supported, root_bmp_delete_validation_supported,
    ROOT_BMP_DELETE_VALIDATION_FILES, ROOT_BMP_DELETE_VALIDATION_OFFSETS,
    NESTED_TXT_DELETE_VALIDATION_PATH, NESTED_TXT_DELETE_VALIDATION_BYTES,
    build_nested_txt_validation_delete, _restoration_items,
)
from .library_transfer_execution import OwnerAuthorizedOperationIdentity
from .library_transfer_runtime_provider import PinnedRootTxtRuntime
from .p18_041h_experiment import FIXTURE_FILENAME, FIXTURE_PATH, FIXTURE_SHA256
from .prepared_library_package_live_adapter import PreparedLibraryPackageLiveResult, _backup_identity
from .protocol import TransferCancelledError
from .write_gate import WriteGateError, verify_fresh_backup


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
    general_txt: bool = False
    validation_bmp: bool = False
    general_bmp: bool = False
    nested_validation: bool = False

    @property
    def filename(self) -> str:
        return self.row.display_name.rsplit("\\", 1)[-1]


def select_device_library_delete(
    model: DesktopWorkflowModel, offsets: Sequence[int], *, device_model: str = "VNW-V15",
    allow_general_txt: bool = False, allow_exact_bmp: bool = False, allow_general_bmp: bool = False,
    bmp_validation_target: str | None = None,
    nested_validation_target: str | None = None,
) -> DeviceDeleteSelection:
    """Cheap UI admission; fresh backup/candidate validation happens off Tk."""
    if device_model != "VNW-V15":
        raise DeviceLibraryDeleteError("Delete is unavailable for this device model.")
    if len(offsets) != 1:
        raise DeviceLibraryDeleteError("Select exactly one supported root-level file to delete.")
    rows = model.rows()
    selected = [row for row in rows if row.record_offset == offsets[0]]
    if len(selected) != 1:
        raise DeviceLibraryDeleteError("The selected file is missing or ambiguous. Refresh Device Library.")
    row = selected[0]
    if nested_validation_target == NESTED_TXT_DELETE_VALIDATION_PATH and row.display_name == nested_validation_target:
        if (nested_validation_target != NESTED_TXT_DELETE_VALIDATION_PATH
                or row.kind != "file" or row.extension != "txt" or row.read_state != "unread"
                or row.payload_bytes != len(NESTED_TXT_DELETE_VALIDATION_BYTES)
                or row.payload_sha256 != hashlib.sha256(NESTED_TXT_DELETE_VALIDATION_BYTES).hexdigest()
                or sum(other.display_name.casefold() == row.display_name.casefold() for other in rows) != 1
                or model.state.backup_directory is None or model.state.source_blob_sha256 is None):
            raise DeviceLibraryDeleteError("Only the exact unread nested disposable TXT is eligible.")
        return DeviceDeleteSelection(model.state.backup_directory, model.state.source_blob_sha256,
                                     row, device_model, nested_validation=True)
    if row.kind != "file" or len(row.path.split("\\")) != 2 or row.path.split("\\")[0] != "root":
        raise DeviceLibraryDeleteError("Root, system entries, folders and nested files cannot be deleted.")
    bmp_validation = False
    general_bmp = False
    if row.extension == "bmp":
        if not allow_exact_bmp and not allow_general_bmp:
            raise DeviceLibraryDeleteError("Root-level BMP deletion is unavailable.")
        if row.read_state != "unread":
            raise DeviceLibraryDeleteError("Only supported unread root-level BMP files are eligible.")
        payload = ROOT_BMP_DELETE_VALIDATION_FILES.get(row.display_name)
        exact_bmp = (payload is not None
            and (row.display_name == ROOT_BMP_DELETE_FIXTURE_PATH or row.display_name == bmp_validation_target)
            and row.payload_bytes == len(payload)
            and row.payload_sha256 == hashlib.sha256(payload).hexdigest()
            and row.record_offset == ROOT_BMP_DELETE_VALIDATION_OFFSETS[row.display_name])
        if exact_bmp and allow_exact_bmp:
            bmp_validation = True
        elif allow_general_bmp and bmp_validation_target is None:
            general_bmp = True
        else:
            raise DeviceLibraryDeleteError("The exact disposable root BMP does not match this validation.")
    elif row.extension != "txt":
        raise DeviceLibraryDeleteError("Only supported root-level TXT and BMP files are available.")
    if (sum(other.display_name.casefold() == row.display_name.casefold() for other in rows) != 1
            or sum(other.path.casefold() == row.path.casefold() for other in rows) != 1):
        raise DeviceLibraryDeleteError("The selected path is ambiguous. Delete is unavailable.")
    if bmp_validation or general_bmp:
        exact = False
    else:
        exact = row.display_name == FIXTURE_PATH and row.payload_bytes == 29 and row.payload_sha256 == FIXTURE_SHA256
    if not exact and not bmp_validation and not general_bmp and not allow_general_txt:
        raise DeviceLibraryDeleteError("General root-level TXT deletion still requires hardware validation.")
    if not exact:
        try:
            validate_root_txt_delete_name(row.path.split("\\")[-1])
        except ValueError as exc:
            raise DeviceLibraryDeleteError(str(exc)) from exc
        if (type(row.payload_bytes) is not int or row.payload_bytes < 0
                or not isinstance(row.payload_sha256, str) or len(row.payload_sha256) != 64
                or any(c not in "0123456789abcdef" for c in row.payload_sha256)):
            raise DeviceLibraryDeleteError("Selected file payload identity is incomplete.")
    if model.state.backup_directory is None or model.state.source_blob_sha256 is None:
        raise DeviceLibraryDeleteError("Load a complete backup before selecting Delete.")
    return DeviceDeleteSelection(model.state.backup_directory, model.state.source_blob_sha256,
                                 row, device_model, not exact and not bmp_validation and not general_bmp, bmp_validation, general_bmp)


@dataclass(frozen=True)
class PreparedDeviceDelete:
    selection: DeviceDeleteSelection
    bundle: RootTxtDeleteBundle
    owner_identity: OwnerAuthorizedOperationIdentity

    @property
    def confirmation_message(self) -> str:
        return (
            f"Delete {self.selection.row.display_name if self.selection.nested_validation else self.selection.filename} from Sony InfoCarry VNW-V15?\n\n"
            "Operation: Delete (Experimental)\n"
            "Deletion modifies device storage. A fresh complete backup has been verified. "
            "The Manager will delete once, independently verify the result, and refresh Device Library.\n\n"
            "Backup is not undo. Keep the InfoCarry connected until verification finishes. "
            "A started operation cannot be cancelled or automatically retried."
        )


class DeviceLibraryDeleteService:
    """Own one UI attempt while delegating all safety decisions to P18-041."""

    def __init__(self, runtime_factory: Callable[[], PinnedRootTxtRuntime], *, validation_target: str | None = None,
                 restoration_objects: dict[str, str] | None = None):
        if validation_target is not None and validation_target not in (*ROOT_TXT_DELETE_VALIDATION_FILES, *ROOT_BMP_DELETE_VALIDATION_FILES, NESTED_TXT_DELETE_VALIDATION_PATH):
            raise DeviceLibraryDeleteError("Validation requires one predetermined disposable target.")
        self.restoration_objects = _restoration_items(restoration_objects)
        if self.restoration_objects is not None and validation_target != NESTED_TXT_DELETE_VALIDATION_PATH:
            raise DeviceLibraryDeleteError("Restoration requires the exact nested validation target.")
        self._deletion_task_binding = None
        self.validation_target = validation_target
        self._runtime_factory = runtime_factory
        self._facade = None
        self._prepared = None
        self._preparation_closed = threading.Event()
        self._preparation_lock = threading.RLock()

    def select(self, model, offsets, *, device_model="VNW-V15"):
        return select_device_library_delete(model, offsets, device_model=device_model,
                                            allow_general_txt=True, allow_exact_bmp=True, allow_general_bmp=True,
                                            bmp_validation_target=self.validation_target,
                                            nested_validation_target=self.validation_target)

    def execution_available(self, selection):
        if self.validation_target is not None and selection.row.display_name != self.validation_target:
            return False
        if selection.nested_validation:
            if self.validation_target != NESTED_TXT_DELETE_VALIDATION_PATH:
                return False
            try:
                core = build_nested_txt_validation_delete(selection.backup_directory,
                    selection.row.display_name, target_record_offset=selection.row.record_offset)
                return core.target_record_offset == selection.row.record_offset
            except (OSError, ValueError, RuntimeError, AttributeError, TypeError):
                return False
        if selection.general_bmp:
            try:
                core = build_root_bmp_delete(selection.backup_directory, selection.row.display_name,
                    target_record_offset=selection.row.record_offset)
                # This builder already reconstructs and validates the complete
                # conservative profile. The frozen bundle repeats admission
                # before granting execution authority.
                return core.target_record_offset == selection.row.record_offset
            except (OSError, ValueError, RuntimeError, AttributeError, TypeError):
                return False
        if selection.validation_bmp:
            if (selection.row.display_name != ROOT_BMP_DELETE_FIXTURE_PATH
                    and selection.row.display_name != self.validation_target):
                return False
            try:
                core = build_experimental_root_bmp_delete(selection.backup_directory,
                    target_path=selection.row.display_name)
                return (core.target_record_offset == selection.row.record_offset
                        and (root_bmp_delete_execution_supported(core)
                             or root_bmp_delete_validation_supported(core)))
            except (OSError, ValueError, WriteGateError, AttributeError, TypeError):
                return False
        if selection.row.extension.lower() == "bmp":
            return False
        if self.validation_target is not None:
            payload = ROOT_TXT_DELETE_VALIDATION_FILES.get(self.validation_target)
            from .root_txt_placement import _sha
            if (payload is None or selection.row.payload_bytes != len(payload)
                    or selection.row.payload_sha256 != _sha(payload)):
                return False
        try:
            core = build_root_txt_delete(selection.backup_directory, selection.row.display_name,
                target_record_offset=selection.row.record_offset)
            return root_txt_delete_execution_supported(core)
        except (OSError, ValueError, WriteGateError, AttributeError, TypeError):
            # A cached manifest with malformed JSON structure is unavailable
            # just like a missing/corrupt archive, before any runtime is opened.
            return False

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
        self._deletion_task_binding = None
        if facade is not None:
            facade.discard_prepared_operation()

    def prepare(self, selection: DeviceDeleteSelection, *, cancelled=None, progress=None) -> PreparedDeviceDelete:
        user_cancelled = cancelled
        cancelled = lambda: self._preparation_closed.is_set() or (user_cancelled is not None and user_cancelled())
        if self._facade is not None:
            raise DeviceLibraryDeleteError("An existing Delete review must be discarded first.", stage="approval")
        if self.validation_target is not None and selection.row.display_name != self.validation_target:
            raise DeviceLibraryDeleteError("Validation permits only its named disposable target.", stage="admission")
        if self.validation_target is not None and not self.execution_available(selection):
            raise DeviceLibraryDeleteError("The named disposable validation payload or state is unsupported.", stage="admission")
        if selection.general_bmp and not self.execution_available(selection):
            raise DeviceLibraryDeleteError("The selected BMP structure or protected state is unsupported.", stage="admission")
        # Re-admit the exact selection from its immutable archive before opening
        # any runtime. Caller-created tokens cannot bypass capability admission.
        original = DesktopWorkflowModel()
        original.load_backup(selection.backup_directory)
        admitted = self.select(original, (selection.row.record_offset,), device_model=selection.device_model)
        if admitted != selection:
            raise DeviceLibraryDeleteError("The selected file or library has changed. Refresh Device Library.", stage="approval")
        before = verify_fresh_backup(selection.backup_directory, max_age_seconds=None)
        identity = _backup_identity(before)
        if cancelled is not None and cancelled():
            raise TransferCancelledError("Delete preparation cancelled before execution")
        try:
            self._facade = ExperimentalRootTxtDeleteFacade(self._runtime_factory())
            bundle = self._facade.prepare(target_path=selection.row.display_name,
                device_model=selection.device_model, cancelled=cancelled, progress=progress,
                general_txt=selection.general_txt,
                validation_only=(self.validation_target is not None
                    and selection.general_txt and self.execution_available(selection)),
                validation_bmp_only=selection.validation_bmp, general_bmp=selection.general_bmp,
                nested_validation=selection.nested_validation,
                restoration_objects=dict(self.restoration_objects) if self.restoration_objects is not None else None)
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

    def bind_deletion_task(self, prepared, envelope, *, source_head):
        """Snapshot the reviewed one-write intent; this grants no write authority."""
        if (prepared is not self._prepared or self._facade is None
                or self._facade.owner_approval_accepted):
            raise DeviceLibraryDeleteError("Delete task cannot bind a different preparation.", stage="approval")
        frozen = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
        prepared.bundle.require_deletion_task_binding(json.loads(frozen), source_head=source_head)
        self._deletion_task_binding = (prepared, frozen, source_head)

    def execute_once(self, prepared: PreparedDeviceDelete, *, confirmed: bool, progress=None):
        """One normal Delete/Cancel decision binds the frozen internal identity."""
        try:
            if prepared is not self._prepared or self._facade is None:
                raise DeviceLibraryDeleteError("Delete approval is no longer valid. Review the selection again.", stage="approval")
            if type(confirmed) is not bool:
                raise DeviceLibraryDeleteError("An explicit Delete or Cancel choice is required.", stage="approval")
            if not confirmed:
                return None
            if not self.execution_available(prepared.selection):
                raise DeviceLibraryDeleteError("Delete execution is unavailable for this selection.", stage="admission")
            prepared.bundle.assert_execution_admitted()
            prepared.bundle.verify_seal()
            if OwnerAuthorizedOperationIdentity.from_bundle(prepared.bundle) != prepared.owner_identity:
                raise DeviceLibraryDeleteError("The approved operation changed. Review the selection again.", stage="approval")
            if prepared.bundle.restoration_objects is not None:
                binding = self._deletion_task_binding
                if binding is None or binding[0] is not prepared:
                    raise DeviceLibraryDeleteError("Deletion-only task must be bound before confirmation.", stage="approval")
                prepared.bundle.require_deletion_task_binding(json.loads(binding[1]), source_head=binding[2])
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
    if stage == "admission":
        return "Delete is unsupported for this selection or its protected device state. No device-changing operation was started."
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
