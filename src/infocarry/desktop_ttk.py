"""ttk-based read-only Device Manager view."""

from __future__ import annotations

from datetime import datetime
import errno
import json
import os
import queue
from pathlib import Path
import stat
import subprocess
import sys
import threading
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .bitmap import BitmapFormatError, decode_monochrome_bmp
from .backup import BackupClient, RawBackupArchive
from .backup_format import BackupFormatError
from .backup_history import (
    BackupHistoryError,
    BackupSnapshotSummary,
    latest_complete_backup,
    remember_complete_backup,
    summarize_complete_backup,
)
from .capture import CaptureError
from .desktop import DesktopWorkflowError, DesktopWorkflowModel
from .app_paths import ApplicationPaths, application_paths
from .device_home import (
    DeviceHomeService,
    DeviceHomeSnapshot,
    format_capacity_summary,
)
from .guarded_workflow import (
    ExistingTextReplacementResult,
    ExistingTextReplacementWorkflow,
    GuardedWorkflowError,
)
from .offline_conversion import (
    OfflineConversionError,
    OfflineTextDocument,
    export_text_document,
    load_utf8_text_document,
)
from .library import (
    NODE_FILE,
    NODE_FOLDER,
    NODE_PREPARED_PACKAGE,
    LibraryCatalog,
    LibraryCatalogError,
    LibraryError,
)
from .library_folder_package_adapter import (
    LibraryFolderPackageAdapterError,
    LibraryFolderPackageStage,
    prepare_exact_folder_package,
)
from .device_library_semantics import (
    AuxiliaryStateSnapshot,
    DeviceLibraryNode,
    DeviceLibrarySemanticError,
    DeviceLibrarySnapshot,
)
from .library_device_transfer import (
    CapacityEvidence,
    LibraryDeviceTransferPlan,
    LibraryDeviceTransferPlanError,
    build_library_device_transfer_plan,
)
from .content_workspace import ContentWorkspaceSettings
from .library_prepare import LibraryPreparationError
from .library_workflow import LibraryWorkflowService
from .prepared_content import PreparedContentArtifact, PreparedContentError
from .capability_profile import (
    INITIAL_EXPERIMENTAL_PROFILE_ID,
    VNW_V15_FOUR_LEAF_PROFILE_ID,
)
from .execution_profile import guarded_execution_profile
from .transfer_shape import (
    EXACT_VERIFIED_LIVE_PROFILE,
    FOUR_LEAF_VERIFIED_CHILD_KINDS,
    CURRENT_VERIFIED_CHILD_KINDS,
    assess_transfer_shape,
)
from .library_transfer_plan import (
    LibraryTransferPlanError,
    SELECTION_ALL_READY,
    SELECTION_SELECTED,
    build_library_transfer_queue_plan,
)
from .library_transfer_readiness import (
    LibraryTransferReadinessError,
    LibraryTransferReadiness,
    ReadinessAction,
    ReadinessState,
    build_library_transfer_readiness,
    readiness_state_from_error,
)
from .library_transfer_execution import (
    LibraryTransferExecutionError,
    LibraryTransferExecutionFacade,
    PreparedLibraryTransferOperation,
)
from .execution_claim_store import ExecutionClaimStoreError, PersistentExecutionClaimStore
from .indeterminate_write_lock import PersistentIndeterminateWriteLock
from .operation_controller import (
    OperationBusyError,
    OperationController,
    OperationOutcome,
    OperationProgress,
    OperationStatus,
)
from .runtime import DesktopRuntimeError, check_desktop_runtime
from .write_gate import verify_fresh_backup
from .write_safety_boundary import (
    PersistentWriteSafetyOwner,
    WriteSafetyBoundaryError,
    create_default_application_write_safety_owner,
)


# The Library review is designed for an ordinary non-maximized macOS window.
# Keep this geometry explicit so visual checks and future layout changes share
# one documented boundary.
LIBRARY_MINIMUM_GEOMETRY = (1080, 680)
LIBRARY_DEFAULT_GEOMETRY = (1320, 800)
LIBRARY_LIST_MIN_WIDTH = 360
LIBRARY_DETAIL_MIN_WIDTH = 440


def _library_package_shape(package: Any) -> str:
    """Return a concise child-kind shape for the Library list.

    ``LibraryPackageReference`` deliberately persists its children as plain
    dictionaries.  Keep the display boundary compatible with that canonical
    representation while also accepting the small object-shaped fixtures used
    by older in-memory callers.
    """

    kinds: list[str] = []
    for child in getattr(package, "children", ()):
        if isinstance(child, dict):
            kind = child.get("kind")
        else:
            kind = getattr(child, "kind", None)
        kinds.append(str(kind).upper() if kind else "?")
    return "/".join(kinds) or "PACKAGE"


def _exact_live_package_artifact(
    item: Any,
    plan: LibraryDeviceTransferPlan,
) -> Optional[PreparedContentArtifact]:
    """Return the artifact only for one exact, root-level guarded mapping.

    The generic device plan remains host-only. This adapter proves that its
    explicit package expansion agrees with an existing guarded profile;
    readiness, authorization, preflight, execution, and read-back remain
    owned by ``LibraryTransferExecutionFacade``.
    """

    if (
        not isinstance(plan, LibraryDeviceTransferPlan)
        or plan.destination_path != ("root",)
        or plan.expected_delta.removed_paths
        or plan.selected_item_ids != (getattr(item, "item_id", None),)
        or getattr(item, "node_kind", None) != NODE_PREPARED_PACKAGE
        or getattr(item, "package", None) is None
        or not isinstance(getattr(item, "prepared_artifact", None), dict)
    ):
        return None
    try:
        artifact = PreparedContentArtifact.from_dict(item.prepared_artifact)
        assessment = assess_transfer_shape(artifact)
    except (PreparedContentError, TypeError, ValueError):
        return None
    if assessment.classification != EXACT_VERIFIED_LIVE_PROFILE:
        return None

    if assessment.ordered_kinds == CURRENT_VERIFIED_CHILD_KINDS:
        profile_id = INITIAL_EXPERIMENTAL_PROFILE_ID
    elif assessment.ordered_kinds == FOUR_LEAF_VERIFIED_CHILD_KINDS:
        profile_id = VNW_V15_FOUR_LEAF_PROFILE_ID
    else:
        return None
    try:
        profile = guarded_execution_profile(profile_id)
    except ValueError:
        return None
    if (
        artifact.root_name != getattr(item.package, "folder_name", None)
        or tuple(child.kind for child in artifact.children) != profile.child_kinds
        or tuple(child.name for child in artifact.children) != profile.child_names
    ):
        return None

    expected_root = ("root", artifact.root_name)
    nodes = plan.nodes
    if (
        len(nodes) != len(artifact.children) + 1
        or nodes[0].source_item_id != item.item_id
        or nodes[0].source_path != item.source_path
        or nodes[0].kind != "directory"
        or nodes[0].destination_path != expected_root
    ):
        return None
    for index, (child, node) in enumerate(zip(artifact.children, nodes[1:])):
        if (
            node.source_item_id != item.item_id
            or node.kind != "file"
            or node.file_type != child.kind
            or node.destination_path != expected_root + (child.name,)
            or node.source_payload_sha256 != child.source_sha256
            or node.source_payload_bytes != child.source_bytes
            or node.sibling_order != index
        ):
            return None
    return artifact


def _library_display_type(item: Any) -> str:
    if getattr(item, "package", None) is not None or getattr(item, "prepared_artifact", None) is not None:
        return "Prepared content"
    if getattr(item, "node_kind", None) == NODE_FOLDER:
        return "Folder"
    detected = str(getattr(item, "detected_format", "content"))
    if detected == "utf-8-txt":
        return "Text"
    if detected == "validated-237x320-1bit-bmp":
        return "Bitmap"
    if detected == "epub":
        return "EPUB"
    return "Content"


def _library_display_state(item: Any) -> str:
    if getattr(item, "source_status", None) != "present":
        return "Needs attention"
    if getattr(item, "state", None) == "unsupported":
        return "Unsupported"
    if getattr(item, "preparation_state", None) == "prepared":
        return "Prepared"
    if getattr(item, "state", None) == "blocked":
        return "Needs attention"
    return "Needs preparation"


def _device_library_snapshot_from_inventory(
    inventory: Mapping[str, Any],
) -> DeviceLibrarySnapshot:
    """Adapt an ordered backup inventory to the host-only logical tree model.

    The inventory's depth-first record order is derived from stored device
    child tables.  Auxiliary references are intentionally unresolved here;
    this snapshot supports conflict planning, not a claim that a later live
    operation would preserve all unknown device state.
    """

    records = inventory.get("records")
    if not isinstance(records, (tuple, list)) or not records:
        raise DeviceLibrarySemanticError("a complete device-library inventory is required")
    nodes: list[DeviceLibraryNode] = []
    next_sibling: dict[Tuple[str, ...], int] = {}
    for record in records:
        if not isinstance(record, Mapping):
            raise DeviceLibrarySemanticError("device inventory contains a malformed record")
        raw_path = record.get("path")
        kind = record.get("kind")
        if not isinstance(raw_path, str) or not raw_path:
            raise DeviceLibrarySemanticError("device inventory path is missing")
        path = tuple(raw_path.split("\\"))
        if not path or path[0] != "root" or any(not part for part in path):
            raise DeviceLibrarySemanticError("device inventory path is not rooted at InfoCarry root")
        if kind not in {"directory", "file"}:
            raise DeviceLibrarySemanticError(
                "device inventory contains an unresolved item; transfer planning is blocked"
            )
        if kind == "file":
            extension = record.get("extension")
            if isinstance(extension, str) and extension:
                path = path[:-1] + (f"{path[-1]}.{extension.lower()}",)
            file_type = extension.lower() if isinstance(extension, str) and extension else "unknown"
            payload_sha256 = record.get("payload_sha256")
            payload_size_bytes = record.get("payload_bytes")
        else:
            file_type = None
            payload_sha256 = None
            payload_size_bytes = None
        if path == ("root",):
            if kind != "directory":
                raise DeviceLibrarySemanticError("device root must be a directory")
            sibling_order = 0
        else:
            parent = path[:-1]
            sibling_order = next_sibling.get(parent, 0)
            next_sibling[parent] = sibling_order + 1
        nodes.append(
            DeviceLibraryNode(
                path=path,
                kind=kind,
                sibling_order=sibling_order,
                file_type=file_type,
                payload_sha256=payload_sha256,
                payload_size_bytes=payload_size_bytes,
                system=(path == ("root",)),
            )
        )
    return DeviceLibrarySnapshot(
        tuple(nodes),
        AuxiliaryStateSnapshot(resolved=False),
    )


def _device_path_label(path: Tuple[str, ...]) -> str:
    """Render a logical device path without exposing internal path tokens."""

    if path and path[0] == "root":
        parts = path[1:]
    else:
        parts = path
    return "/" + "/".join(parts)


def _backup_destination(parent: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = parent.expanduser().resolve() / f"InfoCarry-backup-{stamp}"
    suffix = 2
    while candidate.exists():
        candidate = parent.expanduser().resolve() / f"InfoCarry-backup-{stamp}-{suffix}"
        suffix += 1
    return candidate


def _export_destination(parent: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = parent.expanduser().resolve() / f"InfoCarry-export-{stamp}"
    suffix = 2
    while candidate.exists():
        candidate = parent.expanduser().resolve() / f"InfoCarry-export-{stamp}-{suffix}"
        suffix += 1
    return candidate


def _replacement_backup_destination(parent: Path, label: str) -> Path:
    """Choose a new, descriptive backup path for one guarded replacement."""

    if label not in {"before", "after"}:
        raise ValueError("replacement backup label must be before or after")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = parent.expanduser().resolve() / f"InfoCarry-write-{label}-{stamp}"
    candidate = base
    suffix = 2
    while candidate.exists():
        candidate = parent.expanduser().resolve() / f"InfoCarry-write-{label}-{stamp}-{suffix}"
        suffix += 1
    return candidate


def _backup_review_filesystem_revision(directory: Optional[Path]) -> tuple[Any, ...]:
    """Capture a cheap disk-state token so an edited backup stales its review.

    The complete backup is cryptographically verified by the review worker and
    again by the guarded execution path. This lightweight token only lets the
    UI notice ordinary file replacement or edits without hashing a large
    backup on Tk's event thread.
    """

    if directory is None:
        return ()
    root = Path(directory).expanduser()
    try:
        resolved = root.resolve()
        entries = []
        for entry in sorted(resolved.iterdir(), key=lambda value: value.name):
            info = entry.lstat()
            entries.append(
                (
                    entry.name,
                    info.st_mode,
                    info.st_dev,
                    info.st_ino,
                    info.st_size,
                    info.st_mtime_ns,
                )
            )
        return str(resolved), tuple(entries)
    except OSError as exc:
        return str(root), "unavailable", type(exc).__name__, exc.errno


def _source_review_filesystem_revision(source: Optional[Path]) -> tuple[Any, ...]:
    """Capture cheap file metadata so an open review stales after source edits."""

    if source is None:
        return ()
    path = Path(source).expanduser()

    def signature(info: os.stat_result) -> tuple[int, ...]:
        return (
            info.st_mode,
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )

    try:
        link_info = path.lstat()
        link_signature = signature(link_info)
        if stat.S_ISLNK(link_info.st_mode):
            try:
                target_info = path.stat()
            except OSError as exc:
                return str(path), "symlink", link_signature, "target-unavailable", type(exc).__name__, exc.errno
            return str(path), "symlink", link_signature, signature(target_info)
        return str(path), signature(link_info)
    except OSError as exc:
        return str(path), "unavailable", type(exc).__name__, exc.errno


def _conversion_destination(parent: Path, source: Path) -> Path:
    """Choose a new destination for one offline conversion package."""

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = source.stem or "document"
    base = parent.expanduser().resolve() / f"{stem}-InfoCarry-offline-{stamp}"
    candidate = base
    suffix = 2
    while candidate.exists():
        candidate = parent.expanduser().resolve() / f"{stem}-InfoCarry-offline-{stamp}-{suffix}"
        suffix += 1
    return candidate


def friendly_error_message(error: BaseException) -> str:
    """Translate common failures into recovery guidance for the UI."""

    if isinstance(error, DesktopRuntimeError):
        return str(error)
    if isinstance(error, GuardedWorkflowError):
        if error.state == "indeterminate_after_transaction_start":
            return (
                "The existing-text replacement may have started, but its final outcome "
                "could not be independently established. ESCALATION_REQUIRED: do not "
                "retry or start another replacement. Preserve the backups, keep the "
                "application-wide write lock active, and perform read-only diagnosis.\n\n"
                f"Stage: {error.stage}\nDetails: {error}"
            )
        if error.write_started:
            return (
                "The guarded replacement stopped after the device operation began. "
                "Do not retry automatically; preserve the backups and inspect the "
                "read-back evidence before doing anything else.\n\n"
                f"Stage: {error.stage}\nDetails: {error}"
            )
        return f"The guarded replacement stopped before any device write.\n\nStage: {error.stage}\nDetails: {error}"
    if getattr(error, "state", None) == "indeterminate_after_transaction_start":
        return (
            "The guarded Library transfer may have started, but its final outcome "
            "could not be independently established. ESCALATION_REQUIRED: do not "
            "retry or click Transfer once again. Preserve the evidence and perform "
            "read-only diagnosis.\n\n"
            f"Stage: {getattr(error, 'stage', 'execution')}\nDetails: {error}"
        )
    if isinstance(error, OSError) and error.errno == errno.ENOSPC:
        return "There is not enough free disk space. Choose another destination and retry."
    if isinstance(error, CaptureError):
        return f"The operation could not preserve its output safely: {error}"
    if isinstance(error, BackupFormatError):
        return (
            "The backup is incomplete or malformed. Keep the original backup, "
            "do not overwrite it, and create a fresh read-only backup.\n\n"
            f"Details: {error}"
        )
    text = str(error)
    lowered = text.lower()
    if any(word in lowered for word in ("disconnect", "timeout", "usb", "not found")):
        return (
            "The InfoCarry connection was interrupted or unavailable. Reconnect "
            "the device, close the legacy manager, and retry the read-only operation.\n\n"
            f"Details: {text}"
        )
    if isinstance(error, PermissionError):
        return f"The selected folder is not writable. Choose another destination.\n\nDetails: {error}"
    return text or error.__class__.__name__


def _set_readonly_text(widget: Any, value: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", value)
    widget.configure(state="disabled")


def format_text_replacement_preview(report: Dict[str, Any]) -> str:
    """Render a concise, explicit no-write summary for the ttk detail pane."""

    authoring = report["authoring"]
    target = report["target"]
    workflow = report.get("workflow", {})
    capacity = report["capacity"]
    if capacity["limit_applied"]:
        capacity_line = (
            f"Capacity check: {authoring['encoded_payload_bytes']} / "
            f"{capacity['limit_bytes']} bytes "
            f"({'within limit' if capacity['encoded_payload_within_limit'] else 'OVER LIMIT'})"
        )
    else:
        capacity_line = "Capacity check: no device capacity claimed (offline preview)"
    prefix = target["native_prefix"]
    return "\n".join(
        (
            "OFFLINE REPLACEMENT PREVIEW — no device change occurred",
            "",
            f"Target: {workflow.get('target_path') or target.get('path') or 'unknown'}",
            f"Record offset: {workflow.get('target_record_offset') or target['record_offset_hex']}",
            f"Source file: {workflow.get('input_path', 'unknown')}",
            f"Source characters: {authoring['input_characters']}",
            f"Source UTF-8 bytes: {authoring['input_utf8_bytes']}",
            f"Normalized characters (CRLF): {authoring['normalized_characters']}",
            f"Encoded payload (strict CP932): {authoring['encoded_payload_bytes']} bytes",
            capacity_line,
            f"Native prefix: {prefix['length_bytes']} bytes; preserved exactly: "
            f"{'yes' if prefix['preserved_exactly'] else 'no'}",
            "Candidate bytes included: no",
            "USB operation performed: no",
        )
    )


def format_post_write_verification(result: Dict[str, Any]) -> str:
    """Render the complete read-back result without implying a retry path."""

    if not isinstance(result, dict):
        raise ValueError("post-write verification result must be a mapping")
    before = result.get("before_backup", {})
    after = result.get("after_backup", {})
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("post-write verification backups are malformed")
    fixed = result.get("fixed_state_matches") is True
    dynamic = result.get("dynamic_blob_matches") is True
    unrelated = result.get("unrelated_objects_unchanged") is True
    outcome = "VERIFIED" if fixed and dynamic and unrelated else "FAILED — do not retry automatically"
    return "\n".join(
        (
            f"POST-WRITE READ-BACK VERIFICATION — {outcome}",
            "",
            f"Before backup: {before.get('directory', 'unknown')}",
            f"After backup: {after.get('directory', 'unknown')}",
            f"Fixed state matches candidate: {'yes' if fixed else 'no'}",
            f"Dynamic content matches candidate: {'yes' if dynamic else 'no'}",
            f"Unrelated backup objects unchanged: {'yes' if unrelated else 'no'}",
            "Automatic retry: no",
        )
    )


def format_offline_conversion_report(document: OfflineTextDocument) -> str:
    """Render the dependency-free conversion report for the ttk tabs."""

    report = document.report()
    layout = report["page_layout"]
    return "\n".join(
        (
            "OFFLINE TEXT CONVERSION — no device access",
            "",
            f"Source: {report['source_path']}",
            f"Source SHA-256: {report['source_sha256']}",
            f"Encoding: {report['encoding']} / {report['newline_policy'].upper()}",
            f"Source characters: {report['source_characters']}",
            f"Source UTF-8 bytes: {report['source_utf8_bytes']}",
            f"Encoded CP932 bytes: {report['encoded_payload_bytes']}",
            f"Pages: {report['page_count']}",
            (
                f"Logical profile: {layout['columns']} columns × "
                f"{layout['lines_per_page']} lines; "
                f"target canvas {layout['width_px']} × {layout['height_px']} px"
            ),
            "Device accessed: no",
            "Candidate device bytes included: no",
        )
    )


def format_offline_page_preview(document: OfflineTextDocument, page_number: int) -> str:
    """Render one deterministic page plan for the ebook renderer tab."""

    if not 1 <= page_number <= document.page_count:
        raise OfflineConversionError(
            f"page must be between 1 and {document.page_count}"
        )
    page = document.pages[page_number - 1]
    return f"Page {page.number} / {document.page_count}\n\n{page.text}"


def format_library_preparation_audit(report: Dict[str, Any]) -> str:
    """Render a compatibility diagnostic; normal ttk uses the product summary."""

    if not isinstance(report, dict):
        raise ValueError("Library preparation audit must be a mapping")
    return "OFFLINE LIBRARY PREPARE — no device change occurred\n\n" + json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _capacity_preview_value(value: Any) -> str:
    if value is None or value == "not_evaluated":
        return "Not evaluated"
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("device-tree capacity value is malformed")
    return f"{value:,} bytes"


def format_library_device_tree_preview(report: Dict[str, Any]) -> str:
    """Render a compatibility diagnostic; normal ttk uses the product preview."""

    if not isinstance(report, dict):
        raise ValueError("Library device-tree preview must be a mapping")
    nodes = report.get("ordered_nodes")
    validation = report.get("validation")
    capacity = report.get("capacity")
    execution = report.get("execution")
    if (
        not isinstance(nodes, list)
        or not isinstance(validation, dict)
        or not isinstance(capacity, dict)
        or not isinstance(execution, dict)
    ):
        raise ValueError("Library device-tree preview is malformed")

    lines = [
        "PREPARED DEVICE-TREE PREVIEW — host/offline only; no device change occurred",
        "",
        f"Profile: {report.get('profile_id', 'unknown')}",
        f"Profile status: {report.get('profile_status', 'unknown')}",
        f"Plan SHA-256: {report.get('plan_sha256', 'unknown')}",
        "",
        "Exact ordered destinations",
    ]
    depths: dict[str, int] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("device-tree node is malformed")
        node_id = node.get("node_id")
        parent_id = node.get("parent_id")
        if not isinstance(node_id, str) or not node_id or node_id in depths:
            raise ValueError("device-tree node identity is missing or duplicated")
        if parent_id is None:
            depth = 0
        elif not isinstance(parent_id, str) or parent_id not in depths:
            raise ValueError("device-tree node parent is missing or out of order")
        else:
            depth = depths[parent_id] + 1
        depths[node_id] = depth
        indent = "  " * depth
        lines.append(
            f"{indent}order={node.get('order', '?')} "
            f"type={str(node.get('kind', '?')).upper()} "
            f"name={node.get('name', '?')}"
        )
        lines.extend(
            (
                f"{indent}  Destination: {node.get('path', 'unknown')}",
                f"{indent}  Prepared size: {node.get('prepared_payload_bytes', '?')} bytes",
                f"{indent}  Validation: {node.get('validation', 'unknown')}",
                f"{indent}  Conflict: {node.get('conflict', 'unknown')}",
            )
        )

    conflicts = validation.get("conflicts", [])
    if not isinstance(conflicts, list):
        raise ValueError("device-tree conflicts must be a list")
    lines.extend(
        (
            "",
            "Validation and conflicts",
            f"  Prepared manifest: {validation.get('prepared_manifest', 'unknown')}",
            f"  Paths and sibling order: {validation.get('internal_paths_and_order', 'unknown')}",
            f"  Existing device paths: {validation.get('existing_device_paths', 'unknown')}",
            f"  Capability match: {validation.get('capability_match', 'unknown')}",
            f"  Conflicts: {', '.join(str(value) for value in conflicts) if conflicts else 'none'}",
            "",
            "Capacity",
            f"  Total model limit: {_capacity_preview_value(capacity.get('total_model_limit_bytes'))}",
            f"  Fresh baseline length: {_capacity_preview_value(capacity.get('fresh_baseline_model_length_bytes'))}",
            f"  Candidate growth: {_capacity_preview_value(capacity.get('candidate_growth_bytes'))}",
            f"  Remaining after transfer: {_capacity_preview_value(capacity.get('remaining_after_transfer_bytes'))}",
            "",
            "Safety",
            f"  Execution enabled: {'yes' if execution.get('enabled') else 'no'}",
            f"  Candidate constructed: {'yes' if execution.get('candidate_constructed') else 'no'}",
            f"  USB accessed: {'yes' if execution.get('usb_accessed') else 'no'}",
            f"  Device change: {execution.get('device_change', 'none')}",
        )
    )
    return "\n".join(lines)


def format_library_transfer_plan(report: Dict[str, Any]) -> str:
    """Render a compatibility diagnostic; normal ttk uses the product review."""

    if not isinstance(report, dict):
        raise ValueError("Library transfer plan must be a mapping")
    selection = report.get("selection", {})
    baseline = report.get("baseline", {})
    grouping = report.get("grouping", {})
    capacity = report.get("capacity", {})
    eligibility = report.get("eligibility", {})
    totals = report.get("totals", {})
    lines = [
        "OFFLINE LIBRARY TRANSFER REVIEW — no device access or device change occurred",
        "",
        f"Selection: {selection.get('mode', 'unknown')} "
        f"({len(selection.get('selected_item_ids', []))} selected; "
        f"{len(selection.get('excluded_items', []))} excluded)",
        f"Baseline: {'verified offline backup' if baseline.get('available') else 'not supplied'}",
        f"Grouping: {grouping.get('policy', 'unknown')}",
        "",
        "Queue entries:",
    ]
    for index, item in enumerate(report.get("items", []), start=1):
        source = item.get("source", {})
        prepared = item.get("prepared_artifact", {})
        destination = item.get("destination", {})
        conflicts = item.get("conflicts", [])
        reasons = item.get("reasons", [])
        lines.extend(
            (
                f"  {index}. {source.get('filename', 'unknown')} — "
                f"{item.get('operation_type', 'unknown')}",
                f"     Compatibility: {item.get('compatibility_state', 'unknown')}",
                f"     Destination: {', '.join(destination.get('paths', [])) or 'unknown'}",
                f"     Order: {', '.join(prepared.get('child_order', [])) or 'unknown'}",
                f"     Ordered contents: {', '.join(str(child.get('kind')) + ':' + str(child.get('name')) for child in prepared.get('ordered_children', [])) or 'unknown'}",
                f"     Source SHA-256: {source.get('sha256', 'unknown')}",
                f"     Prepared manifest SHA-256: "
                f"{prepared.get('manifest_sha256', 'unknown')}",
                f"     Source/prepared bytes: {source.get('size_bytes', '?')} / "
                f"{prepared.get('prepared_payload_bytes', '?')}",
                f"     Conflict: {'yes' if conflicts else 'no'}",
                f"     Queue ready: {'yes' if item.get('queue_ready') else 'no'}",
            )
        )
        if reasons:
            lines.append(f"     Reasons: {'; '.join(str(reason) for reason in reasons)}")
    lines.extend(
        (
            "",
            f"Totals: {totals.get('selected_items', 0)} selected; "
            f"{totals.get('source_bytes', 0)} source bytes; "
            f"{totals.get('prepared_payload_bytes', 0)} prepared payload bytes; "
            f"lower-bound growth {totals.get('estimated_growth_lower_bound', 0)} bytes",
            f"Capacity: {capacity.get('status', 'unknown')} "
            f"(available {capacity.get('available_bytes', 'unknown')}; "
            f"lower bound {capacity.get('lower_bound_bytes', 'unknown')})",
            f"Queue review: {'ready' if eligibility.get('queue_ready') else 'blocked'}",
            "Device execution: disabled",
            "Candidate/auth/transaction/sender: none",
            "USB operation performed: no",
        )
    )
    return "\n".join(lines)


def format_experimental_library_transfer_review(report: Dict[str, Any]) -> str:
    """Render a compatibility diagnostic; normal ttk uses typed readiness."""

    if not isinstance(report, dict):
        raise ValueError("Experimental Library transfer review must be a mapping")
    package = report.get("package", {})
    destination = report.get("destination", {})
    capacity = report.get("capacity", {})
    candidate = report.get("candidate", {})
    identity = report.get("operation_identity", {})
    eligibility = report.get("eligibility", {})
    verification = report.get("verification", {})
    children = package.get("ordered_children", [])
    lines = [
        "EXPERIMENTAL LIBRARY TRANSFER REVIEW — no device access or device change occurred",
        "",
        "Status",
        f"  Eligibility: {eligibility.get('experimental_status', 'preview_only')}",
        f"  Profile: {report.get('profile', 'unknown')}",
        f"  Logical selection: {report.get('selection', {}).get('logical_item_id', 'none')} (one grouped package)",
        "",
        "Package contents (authoritative order)",
    ]
    for child in children:
        lines.append(
            f"  {child.get('order', '?')}. {child.get('kind', '?')} "
            f"{child.get('name', '?')} — {child.get('path', '?')} — "
            f"{child.get('prepared_payload_bytes', '?')} B prepared"
        )
    lines.extend(
        (
            "",
            "Destination and conflicts",
            f"  Paths: {', '.join(destination.get('paths', [])) or 'unknown'}",
            f"  Conflicts: {'yes' if destination.get('conflicts') else 'no'}",
            "",
            "Capacity and backup state",
            f"  Validation: {capacity.get('status', 'unknown')}",
            f"  Total model capacity: {capacity.get('total_model_capacity_bytes', 'not sealed')} bytes",
            f"  Verified baseline/used model length: {capacity.get('baseline_model_bytes', 'not sealed')} bytes",
            f"  Candidate model length: {capacity.get('candidate_model_bytes', 'not sealed')} bytes",
            f"  Candidate growth: {capacity.get('candidate_growth_bytes', 'not sealed')} bytes",
            f"  Remaining growth capacity: {capacity.get('remaining_growth_bytes', 'not sealed')} bytes",
            f"  Remaining after transfer: {capacity.get('remaining_after_transfer_bytes', 'not sealed')} bytes",
            f"  Fresh complete backup: required; destination {report.get('fresh_backup', {}).get('destination', 'not specified')}",
            "",
            "Safety rules",
            "  Physical semantics: one logical selection transfers a complete candidate library image",
            "  One logical transaction maximum; exact confirmation; explicit 0x0000 only",
            "  automatic retry: no; post-operation complete backup + independent read-back required",
            f"  Verification: {verification.get('wrapper_reconciliation', 'reviewed reconciliation')}",
            "",
            "Technical details",
            f"  Prepared manifest SHA-256: {package.get('prepared_manifest_sha256', 'not sealed')}",
            f"  Candidate SHA-256: {candidate.get('candidate_blob_sha256', 'not sealed')}",
            f"  Operation bundle SHA-256: {identity.get('bundle_sha256', 'not sealed')}",
            f"  Transaction SHA-256: {identity.get('transaction_sha256', 'not sealed')}",
            f"  Preflight seal SHA-256: {identity.get('preflight_seal_sha256', 'not sealed')}",
            f"  Audit location: {verification.get('audit_location') or 'allocated under bounded external evidence namespace'}",
            f"  Execution action exposed: {'yes' if eligibility.get('execution_action_exposed') else 'no'} (no send action in this review surface)",
        )
    )
    reasons = eligibility.get("reasons", [])
    lines.extend(
        (
            "",
            "Why not hardware-ready / why transfer is unavailable",
            f"  {'; '.join(str(reason) for reason in reasons) if reasons else 'Execution is intentionally unavailable in this review-only surface'}",
            "Normal GUI/CLI transfer: no send control; review only",
        )
    )
    return "\n".join(lines)


def format_library_transfer_execution_result(report: Dict[str, Any]) -> str:
    """Render the product terminal result after independent verification."""

    if not isinstance(report, dict):
        raise ValueError("Library transfer execution result must be a mapping")
    verification = report.get("verification", {})
    lines = [
        "TRANSFERRED AND VERIFIED",
        "",
        "  The content transfer completed and passed its independent verification.",
        f"  Post-transfer backup verified: {'yes' if report.get('post_backup_verified') else 'no'}",
        f"  Independent read-back verified: {'yes' if report.get('independent_readback_verified') else 'no'}",
        f"  Verified content paths: {verification.get('shared_path_count', 'unknown')}",
        "  Automatic retry: no",
        "",
        "The result is terminal; do not retry automatically after an uncertain outcome.",
    ]
    return "\n".join(lines)


def format_library_host_only_terminal_state() -> str:
    """Render a truthful test/fake terminal state without claiming a transfer."""

    return "\n".join(
        (
            "TRANSFERRED AND VERIFIED — host-only simulation",
            "",
            "The simulated result passed terminal verification checks.",
            "No device operation was performed during this host-only task.",
        )
    )


def _readiness_action_label(action: ReadinessAction) -> str:
    return {
        ReadinessAction.NONE: "No further action",
        ReadinessAction.PREPARE: "Prepare",
        ReadinessAction.REPREPARE: "Prepare again",
        ReadinessAction.RECONNECT: "Reconnect device",
        ReadinessAction.REVIEW: "Review transfer",
        ReadinessAction.DIAGNOSE: "Open Technical Details and diagnose",
    }[action]


def _readiness_for_display(value: Any) -> tuple[ReadinessState, dict[str, Any]]:
    if isinstance(value, LibraryTransferReadiness):
        return value.ui_state, value.to_dict()
    if isinstance(value, ReadinessState):
        return value, {}
    if isinstance(value, dict):
        report = value
        eligibility = report.get("eligibility", {})
        reasons = eligibility.get("reasons", []) if isinstance(eligibility, dict) else []
        fresh = (
            eligibility.get("fresh_evidence_reasons", [])
            if isinstance(eligibility, dict)
            else []
        )
        state = ReadinessState(
            state="blocked" if eligibility.get("blocked") is True else "needs_review",
            message=(
                "Content is prepared. Review current device readiness before sending."
                if eligibility.get("blocked") is not True
                else "The content is not ready for transfer. Review the details and prepare again."
            ),
            action_allowed=False,
            next_action=ReadinessAction.REVIEW,
            reasons=(),
            artifact_identity=None,
            transfer_enabled=False,
        )
        try:
            readiness = build_library_transfer_readiness(report)
        except (LibraryTransferReadinessError, ValueError):
            return state, report
        return readiness.ui_state, report
    raise ValueError("readiness display value must be typed readiness or a mapping")


def format_library_readiness_summary(value: Any) -> str:
    """Render the product-facing readiness view without technical identities."""

    state, report = _readiness_for_display(value)
    package = report.get("package", {})
    destination = report.get("destination", {})
    capacity = report.get("capacity", {})
    if not isinstance(package, dict) or not isinstance(destination, dict):
        raise ValueError("readiness package and destination are malformed")
    if not isinstance(capacity, dict):
        raise ValueError("readiness capacity is malformed")
    children = package.get("ordered_children", [])
    if not isinstance(children, list):
        raise ValueError("readiness children are malformed")
    paths = destination.get("paths", [])
    if not isinstance(paths, list):
        raise ValueError("readiness destination paths are malformed")

    eligibility = report.get("eligibility", {})
    shape_eligible = (
        isinstance(eligibility, dict)
        and eligibility.get("host_profile_eligible") is True
    )
    heading = (
        "MATCHES A REVIEWED TRANSFER SHAPE"
        if shape_eligible
        else "NOT CURRENTLY READY FOR TRANSFER"
    )
    owner_status = (
        "Ready for guarded transfer after fresh device checks"
        if shape_eligible
        else state.message
    )
    lines = [
        heading,
        "",
        "Status",
        f"  {owner_status}",
        f"  Next step: {_readiness_action_label(state.next_action)}",
        "  Viewing this review does not authorize or start a transfer",
        "",
        "Prepared content",
        f"  Destination: {package.get('folder_path') or 'not prepared'}",
        f"  Items: {len(children)}",
        f"  Prepared size: {package.get('prepared_payload_bytes', 'not evaluated')} bytes",
        "  Order:",
    ]
    for child in children:
        if not isinstance(child, dict):
            raise ValueError("readiness child is malformed")
        kind = str(child.get("kind", "content")).upper()
        lines.append(
            f"    {child.get('order', '?') + 1 if isinstance(child.get('order'), int) else '?'}. "
            f"{kind} {child.get('name', 'unnamed')} — {child.get('prepared_payload_bytes', '?')} bytes"
        )
    conflict = destination.get("conflicts")
    lines.extend(
        (
            "",
            "Transfer review",
            f"  Target paths: {', '.join(str(path) for path in paths) or 'not available'}",
            f"  Destination check: {'blocked — destination already exists' if conflict else 'not reported as conflicting'}",
            f"  Current capacity check: {capacity.get('status', 'not evaluated')}",
            "  Device-changing operations during this review: 0",
            "  Review complete; no device change occurred.",
            "  Technical details: available on request",
        )
    )
    if state.reasons:
        lines.extend(("", "Action needed"))
        for reason in state.reasons:
            lines.append(f"  • {reason.message}")
    return "\n".join(lines)


def format_library_preparation_summary(result: Any) -> str:
    """Render Prepare as a concise user-facing, host-only result."""

    artifact = getattr(result, "artifact", None)
    if artifact is None:
        prepared = getattr(result, "prepared", None)
        artifact = getattr(prepared, "artifact", None)
    if artifact is None:
        raise ValueError("prepared content artifact is missing")
    eligibility = format_early_transfer_eligibility_summary(artifact)
    children = getattr(artifact, "children", ())
    prepared = getattr(result, "prepared", None)
    preview = getattr(prepared, "preview", None)
    source_path = getattr(prepared, "source_path", None) or getattr(preview, "source_path", None)
    source_name = getattr(source_path, "name", None) or "Imported content"
    source_kind = getattr(getattr(preview, "source_kind", None), "value", None)
    if source_kind is None:
        source_kind = getattr(prepared, "source_format", None)
    source_kind_label = {
        "txt": "TXT text",
        "bmp": "BMP image",
        "epub": "EPUB book",
        "prepared_package": "Prepared package",
        "prepared_folder": "Prepared folder",
    }.get(source_kind, str(source_kind or "content").upper())
    metadata = getattr(prepared, "preparation_metadata", {})
    page_count = metadata.get("page_count") if isinstance(metadata, Mapping) else None
    lines = [
        "PREPARED SUCCESSFULLY — ready to preview",
        "",
        f"From: {source_name} ({source_kind_label})",
        f"Title: {artifact.root_name}",
        f"Destination: {artifact.root_path}",
        f"Prepared items: {len(children)}" + (f"; text pages: {page_count}" if isinstance(page_count, int) else ""),
        f"Total prepared size: {artifact.aggregate_size:,} bytes",
        "Order:",
    ]
    for child in children:
        lines.append(
            f"  {child.order + 1}. {child.kind.upper()} {child.name} — {child.payload_bytes} bytes"
        )
    if preview is not None:
        lines.extend(_normalization_notice_lines(preview))
        for warning in getattr(preview, "warnings", ()):
            lines.extend(("", f"Note: {warning}"))
    lines.extend(_prepared_epub_normalization_lines(prepared))
    unsupported_features = getattr(prepared, "unsupported_features", ())
    if unsupported_features:
        lines.extend(("", f"EPUB conversion notes: {len(unsupported_features)} item(s) were not converted."))
    lines.extend(
        (
            "",
            eligibility,
            "Preparation is separate from transfer eligibility; nothing was sent.",
        )
    )
    return "\n".join(lines)


def format_early_transfer_eligibility_summary(
    artifact: Optional[PreparedContentArtifact] = None,
) -> str:
    """Explain exact verified VNW-V15 shapes before or after preparation."""

    if artifact is None:
        return (
            "Transfer patterns: VNW-V15 TXT → BMP → TXT and TXT → BMP → TXT → TXT "
            "are currently supported shapes. Prepare first to check the exact order; "
            "other valid content can still be prepared and previewed."
        )
    assessment = assess_transfer_shape(artifact)
    if assessment.classification == EXACT_VERIFIED_LIVE_PROFILE:
        if assessment.ordered_kinds == CURRENT_VERIFIED_CHILD_KINDS:
            shape = "TXT → BMP → TXT"
        elif assessment.ordered_kinds == FOUR_LEAF_VERIFIED_CHILD_KINDS:
            shape = "TXT → BMP → TXT → TXT"
        else:
            raise ValueError("verified transfer shape has an unknown ordered child sequence")
        return (
            f"Transfer pattern: {shape} is transferable for the reviewed VNW-V15 "
            "shape. Fresh device checks and separate operation authorization "
            "are still required before any future transfer."
        )
    return (
        "Prepared successfully — this arrangement is not yet supported for transfer. "
        "Preparation and preview remain available."
    )


def _normalization_notice_lines(preview: Any, *, limit: int = 12) -> list[str]:
    substitutions = tuple(getattr(preview, "normalization_substitutions", ()) or ())
    details = tuple(getattr(preview, "normalization_details", ()) or ())
    if not substitutions and not details:
        return []
    occurrences = tuple(getattr(preview, "normalization_occurrences", ()) or ())
    total = len(occurrences) + len(details)
    lines = [
        "",
        f"Text changes: {total or len(substitutions)} character(s) used deterministic safe substitutions.",
    ]
    for line, column, source, replacement in occurrences[:limit]:
        lines.append(f"  Line {line}, column {column}: {source!r} → {replacement!r}")
    remaining = max(0, limit - len(occurrences))
    for child, source_reference, line, column, source, replacement in details[:remaining]:
        lines.append(
            f"  {child} (source {source_reference}), line {line}, column {column}: "
            f"{source!r} → {replacement!r}"
        )
    if total > limit:
        lines.append(
            f"  {total - limit} more location(s) are available in Technical Details."
        )
    lines.append("Characters without a clean CP932 representation stop preparation; they are never replaced automatically.")
    return lines


def _prepared_epub_normalization_lines(prepared: Any, *, limit: int = 12) -> list[str]:
    preview_children = getattr(prepared, "preview_children", None)
    if not callable(preview_children):
        return []
    try:
        children = preview_children(max_text_characters=1200)
    except (TypeError, ValueError):
        return []
    details = [
        (child.get("name", "Text item"), item)
        for child in children
        if child.get("kind") == "txt"
        for item in child.get("normalization_occurrences", ())
    ]
    if not details:
        return []
    lines = [
        "",
        f"Text changes: {len(details)} character(s) used deterministic safe substitutions.",
        "Locations refer to extracted chapter text before CP932 normalization.",
    ]
    for child_name, detail in details[:limit]:
        lines.append(
            f"  {child_name} (EPUB {detail.get('source', 'chapter')}), "
            f"line {detail.get('line')}, column {detail.get('column')}: "
            f"{detail.get('from')!r} → {detail.get('to')!r}"
        )
    if len(details) > limit:
        lines.append(
            f"  {len(details) - limit} more location(s) are available in Technical Details."
        )
    return lines


def format_library_preview_summary(preview: Any) -> str:
    """Render the current canonical artifact as an owner-readable preview."""

    artifact = getattr(preview, "artifact", None)
    if artifact is None:
        prepared = getattr(preview, "prepared", None)
        artifact = getattr(prepared, "artifact", None)
    if artifact is None:
        raise ValueError("preview does not carry a canonical prepared artifact")
    eligibility = format_early_transfer_eligibility_summary(artifact)
    title = getattr(artifact, "root_name", None)
    if not isinstance(title, str) or not title:
        title = str(getattr(artifact, "root_path", "content")).rsplit("\\", 1)[-1]
    source_path = getattr(getattr(preview, "prepared", None), "source_path", None)
    source_name = getattr(source_path, "name", None) or "Imported content"
    workspace_preview = getattr(getattr(preview, "prepared", None), "preview", None)
    source_kind = getattr(getattr(workspace_preview, "source_kind", None), "value", None)
    prepared = getattr(preview, "prepared", None)
    if source_kind is None:
        source_kind = getattr(prepared, "source_format", None)
    source_kind_label = {
        "txt": "TXT text",
        "bmp": "BMP image",
        "epub": "EPUB conversion",
        "prepared_package": "Prepared package",
        "prepared_folder": "Prepared folder",
    }.get(source_kind, str(source_kind or "content").upper())
    lines = [
        "PREVIEW — prepared output",
        "",
        f"From: {source_name} ({source_kind_label})",
        f"Title: {title}",
        f"Destination: {artifact.root_path}",
        f"Items: {len(artifact.children)}",
        f"Total prepared size: {artifact.aggregate_size:,} bytes",
        "Ordered contents:",
    ]
    for child in artifact.children:
        lines.append(
            f"  {child.order + 1}. {child.kind.upper()} {child.path} — {child.payload_bytes} bytes"
        )
    if workspace_preview is not None:
        prepared_text = getattr(workspace_preview, "prepared_text_excerpt", None)
        if prepared_text:
            lines.extend(
                (
                    "",
                    "Prepared text preview (CP932 / CRLF)",
                    prepared_text,
                    "InfoCarry's device-native text rendering may differ from this preview.",
                )
            )
        elif getattr(workspace_preview, "text_excerpt", None):
            lines.extend(("", "Text preview", workspace_preview.text_excerpt))
        if getattr(workspace_preview, "rendered_details", ()):
            lines.extend(("", "Content details", *workspace_preview.rendered_details))
        lines.extend(_normalization_notice_lines(workspace_preview))
    preview_children = getattr(prepared, "preview_children", None)
    if callable(preview_children):
        converted = preview_children(max_text_characters=1200)
        if converted:
            lines.extend(("", "Converted EPUB output"))
            for child in converted[:2]:
                if child.get("kind") == "txt":
                    lines.extend((f"{child.get('name', 'Text item')}", str(child.get("text", ""))))
                    if child.get("truncated"):
                        lines.append("Preview shortened; the prepared item contains more text.")
                elif child.get("kind") == "bmp":
                    lines.append(f"{child.get('name', 'Image')}: validated 237 × 320, 1-bit BMP")
            if len(converted) > 2:
                lines.append(f"{len(converted) - 2} additional prepared item(s) are listed above.")
            lines.extend(_prepared_epub_normalization_lines(prepared))
        if getattr(prepared, "normalization_events", 0):
            lines.append(
                f"\nCP932 safe normalization occurred in {prepared.normalization_events} converted text item(s)."
            )
        unsupported = getattr(prepared, "unsupported_features", ())
        if unsupported:
            lines.append(
                f"\nEPUB conversion note: {len(unsupported)} source feature(s) were not converted."
            )
    lines.extend(
        (
            "",
            "This preview and Prepare use the same current prepared content.",
            eligibility,
            "Previewing does not authorize or start a transfer.",
        )
    )
    return "\n".join(lines)


def format_library_selection_summary(item: Any) -> str:
    """Render concise Local Library details without exposing catalog internals."""

    if item is None:
        return "Select content to continue."
    return "\n".join(
        (
            "LOCAL LIBRARY ITEM",
            "",
            f"Name: {item.source_filename}",
            f"Type: {_library_display_type(item)}",
            f"Size: {item.source_size_bytes:,} bytes",
            f"Status: {_library_display_state(item)}",
            "Original source remains in its current location.",
            "Transfer planning checks current source files, destination and conflicts.",
        )
    )


def format_library_transfer_review_summary(
    report: Dict[str, Any],
    *,
    artifacts: Optional[Mapping[str, PreparedContentArtifact]] = None,
    device_snapshot: Optional[DeviceHomeSnapshot] = None,
    backup_created_at: Optional[str] = None,
    readiness: Optional[LibraryTransferReadiness] = None,
) -> str:
    """Render one owner-facing review without implying authorization."""

    if not isinstance(report, dict):
        raise ValueError("Library transfer review must be a mapping")
    items = report.get("items", [])
    if not isinstance(items, list):
        raise ValueError("Library transfer review items are malformed")
    lines = [
        "REVIEW TRANSFER",
        "",
        "This review describes the current prepared content. It does not authorize or start a transfer.",
        "",
        "Device",
        (
            f"  Last checked: {device_snapshot.heading}"
            if device_snapshot is not None
            else "  Connection has not been checked yet; refresh Device for the latest status."
        ),
        "",
        "Backup",
        (
            f"  Complete backup from {backup_created_at or 'an earlier time'} was integrity-checked for this review."
            if report.get("baseline", {}).get("available") is True
            else "  No complete backup was verified for this review."
        ),
        "  A fresh complete backup and current device checks are still required before any guarded transfer.",
        "",
        "Content and order",
    ]
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError("Library transfer review item is malformed")
        prepared = item.get("prepared_artifact", {})
        destination = item.get("destination", {})
        children = prepared.get("ordered_children", []) if isinstance(prepared, dict) else []
        lines.append(f"  {index}. {item.get('source', {}).get('filename', 'content')}")
        lines.append(
            f"     Target: {', '.join(destination.get('paths', [])) or 'not available'}"
        )
        lines.append(
            "     Order: "
            + ", ".join(
                f"{str(child.get('kind', '?')).upper()} {child.get('name', '?')}"
                for child in children
                if isinstance(child, dict)
            )
        )
        lines.append(
            f"     Prepared size: {prepared.get('prepared_payload_bytes', 'not evaluated')} bytes"
        )
        artifact = (artifacts or {}).get(str(item.get("item_id", "")))
        if artifact is None and isinstance(prepared.get("canonical"), dict):
            try:
                artifact = PreparedContentArtifact.from_dict(prepared["canonical"])
            except PreparedContentError:
                artifact = None
        if artifact is not None:
            lines.append(
                "     "
                + format_early_transfer_eligibility_summary(artifact)
            )
        elif item.get("reasons"):
            lines.append(
                "     Transfer pattern: not currently supported for transfer; "
                "preparation and preview remain available."
            )
        if prepared.get("kind") == "epub_prepared_content":
            lines.append(
                "     EPUB conversion can succeed even when its prepared arrangement is not supported for transfer."
            )
        for warning in item.get("warnings", ()) if isinstance(item.get("warnings", ()), list) else ():
            if isinstance(warning, str):
                lines.append(f"     Note: {warning}")
    totals = report.get("totals", {})
    if not isinstance(totals, dict):
        totals = {}
    capacity = report.get("capacity", {})
    if not isinstance(capacity, dict):
        capacity = {}
    device_capacity = (
        device_snapshot.capacity_bytes
        if device_snapshot is not None and device_snapshot.state == "connected"
        else None
    )
    prepared_total = totals.get("prepared_payload_bytes")
    capacity_line = (
        f"  Latest reported VNW-V15 total capacity: {device_capacity:,} bytes."
        if isinstance(device_capacity, int)
        else "  Capacity has not been checked for the current device session."
    )
    content_size_line = (
        f"  Prepared payload total: {prepared_total:,} bytes; exact device model growth is not known from this review."
        if isinstance(prepared_total, int)
        else "  Prepared payload total is not available."
    )
    lines.extend(
        (
            "",
            "Review outcome",
            f"  Destination: {'one or more targets conflict with the reviewed backup' if any(item.get('conflicts') for item in items if isinstance(item, dict)) else 'no conflict was reported in the reviewed backup'}",
            content_size_line,
            capacity_line,
            f"  Capacity comparison: {capacity.get('status', 'not evaluated')}; metadata growth is not included.",
            (
                "  Transfer status: Ready for guarded transfer after fresh device checks."
                if readiness is not None and readiness.host_profile_eligible
                else (
                    "  Transfer status: this arrangement is not currently supported for transfer."
                    if readiness is not None
                    else "  Transfer status: see the shape assessment for each prepared item."
                )
            ),
            "  No authorization was created and no device change occurred.",
            "  Technical details are available on request.",
        )
    )
    if report.get("eligibility", {}).get("queue_ready") is not True:
        lines.extend(("", "Still needed"))
        if report.get("baseline", {}).get("available") is not True:
            lines.append("  Verify a complete backup before any future guarded transfer.")
        if capacity.get("status") in {"unknown", "not_evaluated_without_verified_backup"}:
            lines.append("  Check capacity with the current VNW-V15 device session.")
        if any(item.get("conflicts") for item in items if isinstance(item, dict)):
            lines.append("  Choose a destination that does not already exist on the device.")
    return "\n".join(lines)


def format_library_operation_failure(error: BaseException, *, artifact_identity: Optional[str] = None) -> str:
    """Render a typed, actionable worker failure for the normal UI."""

    state = readiness_state_from_error(error, artifact_identity=artifact_identity)
    detail = str(error)
    if (
        isinstance(error, LibraryFolderPackageAdapterError)
        and "needs CP932 character substitutions" in detail
    ):
        return "\n".join(
            (
                "TRANSFER PREPARATION STOPPED — source text needs review",
                "",
                "This folder contains text that cannot be transferred without substitutions. The source was not changed.",
                "Use source text that needs no CP932 substitutions, then try Transfer again.",
                "",
                "No device checks or changes occurred.",
            )
        )
    marker = "text contains characters unsupported by CP932:"
    if marker in detail:
        diagnostic = detail.split(marker, 1)[1].strip().rstrip(")")
        return "\n".join(
            (
                "PREPARATION STOPPED — some text cannot be represented safely",
                "",
                "These characters were not replaced. Edit the source and prepare it again.",
                diagnostic,
                "",
                "No device change occurred.",
            )
        )
    return "\n".join(
        (
            "ACTION NEEDED — the operation did not complete",
            "",
            state.message,
            f"Next step: {_readiness_action_label(state.next_action)}",
            "",
            "No automatic retry was offered.",
            "Technical details are available for diagnosis.",
        )
    )


def format_library_technical_details(value: Any) -> str:
    """Render diagnostic evidence only after the user explicitly requests it."""

    if isinstance(value, LibraryTransferReadiness):
        report: Any = value.to_dict()
    elif isinstance(value, ReadinessState):
        report = value.to_dict(include_technical=True)
    elif hasattr(value, "to_dict"):
        report = value.to_dict()
    else:
        report = value
    return "TECHNICAL DETAILS\n\n" + json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=str,
    )


def format_library_transfer_readiness(report: Dict[str, Any]) -> str:
    """Render a compatibility diagnostic for the pre-P18-027 readiness view.

    Normal ttk uses :func:`format_library_readiness_summary`; technical
    identities remain available only through the explicit Technical Details
    action.
    """

    if not isinstance(report, dict):
        raise ValueError("Library transfer readiness must be a mapping")
    profile = report.get("profile", {})
    selection = report.get("selection", {})
    package = report.get("package", {})
    destination = report.get("destination", {})
    capacity = report.get("capacity", {})
    evidence = report.get("evidence", {})
    boundary = report.get("transfer_boundary", {})
    eligibility = report.get("eligibility", {})
    device = report.get("device_model", {})
    if not all(
        isinstance(value, dict)
        for value in (
            profile,
            selection,
            package,
            destination,
            capacity,
            evidence,
            boundary,
            eligibility,
            device,
        )
    ):
        raise ValueError("Library transfer readiness is malformed")

    host_eligible = eligibility.get("host_profile_eligible") is True
    status = eligibility.get("status_text")
    if not isinstance(status, str) or not status:
        status = (
            "Reviewed shape eligible — guarded live transfer requires fresh evidence"
            if host_eligible
            else "Blocked — selected package is outside a reviewed shape"
        )
    conflicts = destination.get("conflicts", [])
    if not isinstance(conflicts, list):
        raise ValueError("Library transfer readiness conflicts are malformed")
    children = package.get("ordered_children", [])
    if not isinstance(children, list):
        raise ValueError("Library transfer readiness children are malformed")

    lines = [
        "TRANSFER READINESS — host review only; no device change occurred",
        "",
        "Status",
        f"  {status}",
        f"  Device boundary: {device.get('model_name', 'Sony InfoCarry VNW-V15')} only",
        "  Model status: " + str(device.get("capability_status", "unknown")),
        f"  Selected packages: {selection.get('count', 0)} (one explicit package required)",
        "",
        "Package contents (authoritative order)",
        f"  Root destination: {package.get('folder_path') or 'not available'}",
    ]
    for child in children:
        if not isinstance(child, dict):
            raise ValueError("Library transfer readiness child is malformed")
        lines.extend(
            (
                f"  {child.get('order', '?') + 1 if isinstance(child.get('order'), int) else '?'}.",
                f"     {str(child.get('kind', '?')).upper()} {child.get('name', '?')}",
                f"     Destination: {child.get('path', 'unknown')}",
                f"     Source: {child.get('source_bytes', '?')} bytes; SHA-256: {child.get('source_sha256', 'unknown')}",
                f"     Prepared: {child.get('prepared_payload_bytes', '?')} bytes; SHA-256: {child.get('prepared_payload_sha256', 'unknown')}",
            )
        )
    lines.extend(
        (
            "",
            "Destination and conflicts",
            f"  Paths: {', '.join(str(path) for path in destination.get('paths', [])) or 'not available'}",
            f"  Verified baseline: {'available' if evidence.get('verified_baseline_available') else 'not supplied'}",
            f"  Conflict: {'BLOCKED — existing destination path' if conflicts else 'none reported'}",
            f"  Baseline check: {destination.get('baseline_status', 'not evaluated')}",
            "",
            "Prepared sizes and capacity evidence",
            f"  Source total: {package.get('source_bytes', 'not evaluated')} bytes",
            f"  Prepared payload total: {package.get('prepared_payload_bytes', 'not evaluated')} bytes",
            f"  Prepared lower-bound growth: {capacity.get('lower_bound_bytes', 'not evaluated')} bytes",
            f"  Baseline model length: {capacity.get('baseline_model_bytes', 'not evaluated')}",
            f"  Offline capacity status: {capacity.get('status', 'not evaluated')}",
            "  Exact candidate growth and remaining-after-transfer margin: not evaluated",
            "",
            "What a future live review would still require",
            "  Fresh complete verified device backup and destination recheck",
            "  Fresh native 0x0019 capacity evidence and exact candidate sizing",
            "  Separate operation identity, review, and transaction-specific confirmation",
            "  One transaction maximum, explicit 0x0000 completion, complete post-write backup, and independent read-back",
            "  No automatic retry after an indeterminate result",
            "",
            "Safety boundary",
            f"  Candidate constructed: {'yes' if boundary.get('candidate_constructed') else 'no'}",
            f"  Authorization exposed: {'yes' if boundary.get('authorization_exposed') else 'no'}",
            f"  Transfer enabled: {'yes' if boundary.get('transfer_enabled') else 'no'}",
            f"  Device-changing operations: {boundary.get('device_changing_operations', 0)}",
            "  Final action: Transfer once — disabled; a separately reviewed live boundary is required",
        )
    )
    reasons = eligibility.get("reasons", [])
    fresh_reasons = eligibility.get("fresh_evidence_reasons", [])
    if not isinstance(reasons, list) or not isinstance(fresh_reasons, list):
        raise ValueError("Library transfer readiness reasons are malformed")
    lines.extend(
        (
            "",
            "Why this is eligible or blocked",
            f"  {'; '.join(str(reason) for reason in reasons) if reasons else 'Exact host profile shape and canonical preparation checks passed'}",
            f"  {'; '.join(str(reason) for reason in fresh_reasons) if fresh_reasons else 'No additional evidence note'}",
            "  Normal UI does not authorize, construct, or send a live transaction",
            "",
            "Technical details",
            f"  Profile: {profile.get('id', 'unknown')} ({profile.get('status', 'unknown')})",
            f"  Prepared manifest SHA-256: {package.get('prepared_manifest_sha256', 'unknown')}",
            f"  Review SHA-256: {report.get('review_sha256', 'unknown')}",
            "  Historical operation identity reused: no",
            "  USB operation performed: no",
        )
    )
    return "\n".join(lines)


def format_prepared_package_readiness_preview(report: Dict[str, Any]) -> str:
    """Render an ordered package readiness report without enabling transfer."""

    if not isinstance(report, dict):
        raise ValueError("package readiness report must be a mapping")
    package = report.get("package", {})
    items = package.get("ordered_items", [])
    capacity = report.get("capacity", {})
    candidate = report.get("candidate", {})
    conflicts = report.get("conflicts", [])
    reasons = report.get("eligibility", {}).get("reasons", [])
    lines = [
        "OFFLINE PACKAGE READINESS PREVIEW — no device change occurred",
        "",
        f"Folder: {package.get('folder_path', 'unknown')}",
        f"Prepared manifest SHA-256: {package.get('prepared_manifest_sha256', 'unknown')}",
        "",
        "Ordered contents:",
    ]
    for item in items:
        lines.append(
            f"  {item.get('order', '?')}: {item.get('kind', '?').upper()} "
            f"{item.get('path', 'unknown')} — "
            f"source {item.get('source_bytes', '?')} B, "
            f"encoded/payload {item.get('encoded_or_payload_bytes', '?')} B, "
            f"aligned {item.get('aligned_content_bytes', '?')} B"
        )
    lines.extend(
        (
            "",
            f"Capacity: {capacity.get('status', 'unknown')} "
            f"(baseline {capacity.get('baseline_model_bytes', 'unknown')}, "
            f"candidate {capacity.get('candidate_model_bytes', 'unknown')}, "
            f"growth {capacity.get('growth_bytes', 'unknown')}, "
            f"limit {capacity.get('capacity_limit_bytes', 'unknown')})",
            f"Native 0x0019 response SHA-256: {capacity.get('native_capacity_response_sha256', 'none')}",
            f"Candidate SHA-256: {candidate.get('candidate_blob_sha256', 'not constructed')}",
            f"Transaction SHA-256: {candidate.get('transaction_sha256', 'not constructed')}",
            f"Conflicts: {', '.join(conflicts) if conflicts else 'none'}",
            f"Eligibility: {'offline preview ready' if report.get('eligibility', {}).get('offline_preview_ready') else 'blocked'}",
            f"Reasons: {'; '.join(reasons) if reasons else 'none'}",
            "USB operation performed: no",
            "Package transfer control: disabled",
        )
    )
    return "\n".join(lines)


def _try_create_application_write_safety_owner(
    paths: ApplicationPaths,
) -> tuple[Optional[PersistentWriteSafetyOwner], Optional[str]]:
    """Keep the UI read-only when historical persistent safety state is invalid."""

    try:
        return create_default_application_write_safety_owner(paths=paths), None
    except (
        WriteSafetyBoundaryError,
        ExecutionClaimStoreError,
        OSError,
        ValueError,
    ) as exc:
        return None, str(exc)


def _application_write_safety_status(
    owner: Optional[PersistentWriteSafetyOwner],
) -> tuple[bool, Optional[str]]:
    """Report whether the shared persistent state permits a guarded action."""

    if owner is None:
        return False, None
    try:
        owner.assert_execution_boundary_available()
    except Exception as exc:
        return False, str(exc)
    return True, None


def _application_safety_notice(
    owner: Optional[PersistentWriteSafetyOwner],
    configuration_error: Optional[str],
) -> Optional[str]:
    if configuration_error:
        return configuration_error
    if owner is None:
        return None
    try:
        owner.inspect_execution_boundary()
    except Exception as exc:
        return str(exc)
    return None


def _persistent_safety_unavailable_message(detail: str) -> str:
    return (
        "Read-only Device Home remains available. Device-changing actions are disabled "
        "because existing write-safety state could not be verified. Do not remove or "
        "recreate the safety files. Review the state with project support.\n\n"
        f"Details: {detail}"
    )


def _initial_device_home_status() -> tuple[str, str]:
    return (
        "Device status not checked",
        "Refresh Device Home to check for a connected Sony InfoCarry VNW-V15.",
    )


def launch_ttk_desktop(
    execution_facade: Optional[LibraryTransferExecutionFacade] = None,
) -> None:
    """Launch the ttk manager with the guarded Library facade."""

    runtime = check_desktop_runtime()
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, simpledialog, ttk
    except ImportError as exc:  # pragma: no cover - guarded by runtime check
        raise DesktopRuntimeError("Tkinter is not available in this Python installation") from exc

    root = tk.Tk()
    root.title("InfoCarry Manager")
    root.geometry(f"{LIBRARY_DEFAULT_GEOMETRY[0]}x{LIBRARY_DEFAULT_GEOMETRY[1]}")
    root.minsize(*LIBRARY_MINIMUM_GEOMETRY)
    model = DesktopWorkflowModel()
    application_data_paths = application_paths()
    device_home_service = DeviceHomeService()
    latest_backup_summary: Optional[BackupSnapshotSummary] = None
    loaded_backup_summary: Optional[BackupSnapshotSummary] = None
    latest_backup_error: Optional[str] = None
    try:
        latest_backup_summary = latest_complete_backup(application_data_paths)
        if latest_backup_summary is not None:
            model.load_backup(latest_backup_summary.directory)
            loaded_backup_summary = latest_backup_summary
    except (BackupHistoryError, DesktopWorkflowError) as exc:
        latest_backup_error = str(exc)
        latest_backup_summary = None
        loaded_backup_summary = None
    library_execution_facade = execution_facade or LibraryTransferExecutionFacade()
    replacement_safety_owner: Optional[PersistentWriteSafetyOwner]
    configured_runtime = library_execution_facade.runtime
    if configured_runtime is None:
        (
            replacement_safety_owner,
            replacement_safety_configuration_error,
        ) = _try_create_application_write_safety_owner(application_data_paths)
    elif (
        isinstance(configured_runtime.execution_claim_store, PersistentExecutionClaimStore)
        and isinstance(
            configured_runtime.indeterminate_write_lock,
            PersistentIndeterminateWriteLock,
        )
    ):
        replacement_safety_owner = PersistentWriteSafetyOwner(
            execution_claim_store=configured_runtime.execution_claim_store,
            indeterminate_write_lock=configured_runtime.indeterminate_write_lock,
        )
        replacement_safety_configuration_error = None
    else:
        # Never silently create a second installation-wide store when a
        # configured Library runtime has incomplete safety state.
        replacement_safety_owner = None
        replacement_safety_configuration_error = (
            "the configured Library runtime does not provide the shared persistent "
            "claim store and indeterminate-write lock"
        )
    if configured_runtime is None and library_execution_facade.runtime_provider is not None:
        library_execution_facade.attach_write_safety_owner(
            replacement_safety_owner,
            replacement_safety_configuration_error,
        )
    events: "queue.Queue[Tuple[str, Any]]" = queue.Queue()
    cancel_event = threading.Event()
    worker: Optional[threading.Thread] = None
    library_callbacks: "queue.Queue[Any]" = queue.Queue()
    library_operation_controller: OperationController[Any] = OperationController(
        library_callbacks.put
    )
    try:
        library_catalog: Optional[LibraryCatalog] = LibraryCatalog()
        library_workflow: Optional[LibraryWorkflowService] = LibraryWorkflowService(
            library_catalog
        )
        library_catalog_error: Optional[str] = None
    except LibraryCatalogError as exc:
        library_catalog = None
        library_workflow = None
        library_catalog_error = str(exc)

    try:
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except tk.TclError:
        pass

    status_var = tk.StringVar(value=f"Ready — {runtime.description}; device writes disabled")
    backup_var = tk.StringVar(value="No backup loaded")
    initial_device_home_heading, initial_device_home_message = _initial_device_home_status()
    device_home_heading_var = tk.StringVar(value=initial_device_home_heading)
    device_home_message_var = tk.StringVar(value=initial_device_home_message)
    initial_safety_detail = _application_safety_notice(
        replacement_safety_owner,
        replacement_safety_configuration_error,
    )
    safety_state_var = tk.StringVar(
        value=(
            _persistent_safety_unavailable_message(initial_safety_detail)
            if initial_safety_detail
            else ""
        )
    )
    device_capacity_var = tk.StringVar(
        value=format_capacity_summary(
            total_model_bytes=None,
            baseline_model_bytes=(
                loaded_backup_summary.model_bytes if loaded_backup_summary else None
            ),
            backup_timestamp=(
                loaded_backup_summary.created_at_utc if loaded_backup_summary else None
            ),
        )
    )
    device_snapshot_var = tk.StringVar(
        value=(
            f"Latest complete backup: {latest_backup_summary.created_at_utc} — "
            f"{latest_backup_summary.directory}"
            if latest_backup_summary is not None
            else (
                f"Latest complete backup could not be verified: {latest_backup_error}"
                if latest_backup_error
                else "No complete backup has been saved here yet."
            )
        )
    )
    device_home_snapshot: Optional[DeviceHomeSnapshot] = None
    device_technical_details = ""
    details_var = tk.StringVar(value="Select a file or folder")
    tree_items: Dict[str, int] = {}

    def replacement_write_safety_available() -> bool:
        """Keep the replacement affordance closed when shared state is unsafe."""

        available, detail = _application_write_safety_status(replacement_safety_owner)
        if detail:
            safety_state_var.set(_persistent_safety_unavailable_message(detail))
        elif available and replacement_safety_configuration_error is None:
            safety_state_var.set("")
        return available

    workspace = ttk.Panedwindow(root, orient="horizontal")
    workspace.pack(fill="both", expand=True, padx=8, pady=(8, 0))
    library_tab = ttk.Frame(workspace, padding=10)
    device_tab = ttk.Frame(workspace, padding=8)
    workspace.add(library_tab, weight=1)
    workspace.add(device_tab, weight=1)
    # Retain the utility implementations as internal code, but do not expose
    # their old workflows as primary Manager navigation.
    text_converter_tab = ttk.Frame(root, padding=12)
    ebook_renderer_tab = ttk.Frame(root, padding=12)
    settings_tab = ttk.Frame(root, padding=12)

    library_status_var = tk.StringVar(
        value=(
            f"Library unavailable: {library_catalog_error}"
            if library_catalog_error
            else "Add files or folders, choose a Device Library destination, then select Transfer."
        )
    )
    library_detail_var = tk.StringVar(value="Select a Library item")
    library_tree_items: Dict[str, str] = {}
    library_drag_state: dict[str, Any] = {
        "source": None,
        "start_y": 0,
        "moved": False,
    }
    library_current_plan_report: Optional[Dict[str, Any]] = None
    library_current_readiness: Any = None
    library_prepared_operation: Optional[PreparedLibraryTransferOperation] = None
    library_current_preview: Any = None
    library_current_revision: Any = None
    library_technical_details_open = False
    library_operation_token: Any = None
    library_device_change_in_progress = False
    ttk.Label(
        library_tab,
        text="LOCAL LIBRARY",
        font=("TkDefaultFont", 14, "bold"),
    ).pack(anchor="w", pady=(0, 4))
    library_transfer_eligibility_label = ttk.Label(
        library_tab,
        text=format_early_transfer_eligibility_summary(),
        justify="left",
        wraplength=900,
    )
    library_transfer_eligibility_label.pack(anchor="w", fill="x", pady=(0, 8))
    library_toolbar = ttk.Frame(library_tab)
    library_toolbar.pack(fill="x", pady=(0, 8))
    library_toolbar.columnconfigure(1, weight=1)
    library_import_group = ttk.LabelFrame(library_toolbar, text="Add Content")
    library_import_group.grid(row=0, column=0, sticky="w")
    library_review_group = ttk.LabelFrame(library_toolbar, text="Prepare and Preview")
    library_review_group.grid(row=1, column=0, sticky="w", pady=(4, 0))
    library_arrange_group = ttk.LabelFrame(library_toolbar, text="Arrange")
    library_arrange_group.grid(row=2, column=0, sticky="w", pady=(4, 0))
    library_transfer_review_group = ttk.LabelFrame(library_toolbar, text="Review Transfer")
    library_transfer_review_group.grid(row=3, column=0, sticky="w", pady=(4, 0))
    library_experimental_group = ttk.LabelFrame(
        library_toolbar, text="Guarded transfer"
    )
    library_experimental_group.grid(
        row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0)
    )
    library_experimental_group.columnconfigure(3, weight=1)
    library_import_button = ttk.Button(library_import_group, text="Add content…")
    library_folder_import_button = ttk.Button(
        library_import_group, text="Add folder…"
    )
    library_move_up_button = ttk.Button(
        library_arrange_group, text="Move up", state="disabled"
    )
    library_move_down_button = ttk.Button(
        library_arrange_group, text="Move down", state="disabled"
    )
    library_rename_button = ttk.Button(
        library_arrange_group, text="Change destination…", state="disabled"
    )
    library_package_import_button = ttk.Button(
        library_import_group, text="Add prepared package…"
    )
    library_remove_button = ttk.Button(
        library_import_group, text="Remove from Library", state="disabled"
    )
    library_prepare_button = ttk.Button(
        library_review_group, text="Prepare", state="disabled"
    )
    library_preview_button = ttk.Button(
        library_review_group, text="Preview", state="disabled"
    )
    library_selected_queue_button = ttk.Button(
        library_transfer_review_group, text="Review transfer…", state="disabled"
    )
    library_all_queue_button = ttk.Button(
        library_transfer_review_group, text="Review all prepared…", state="disabled"
    )
    library_live_preflight_button = ttk.Button(
        library_experimental_group,
        text="Refresh device checks…",
        state="disabled",
        takefocus=False,
    )
    library_transfer_once_button = ttk.Button(
        library_experimental_group,
        text="Send to InfoCarry",
        state="disabled",
        takefocus=False,
    )
    # Compatibility note for the pre-P18-027 label: text="Transfer once".
    library_cancel_button = ttk.Button(
        library_transfer_review_group, text="Cancel", state="disabled", takefocus=False
    )
    for button in (
        library_import_button,
        library_folder_import_button,
        library_package_import_button,
        library_remove_button,
    ):
        button.pack(side="left", padx=3, pady=3)
    for button in (library_prepare_button, library_preview_button):
        button.pack(side="left", padx=3, pady=3)
    for button in (library_move_up_button, library_move_down_button, library_rename_button):
        button.pack(side="left", padx=3, pady=3)
    for button in (
        library_selected_queue_button,
        library_all_queue_button,
        library_cancel_button,
    ):
        button.pack(side="left", padx=3, pady=3)
    library_live_preflight_button.grid(row=0, column=0, sticky="w", padx=3, pady=3)
    library_transfer_once_button.grid(row=0, column=1, sticky="w", padx=3, pady=3)
    ttk.Label(
        library_experimental_group,
        text="A review does not authorize or send. Fresh backup, device checks, and separate approval are required.",
        foreground="#6b4f00",
        anchor="w",
    ).grid(row=0, column=3, sticky="ew", padx=(8, 8), pady=3)
    library_safety_notice = ttk.Label(
        library_toolbar,
        text=(
            "Add TXT, BMP/image, EPUB, or prepared content. Arrange the order, then "
            "prepare and preview the output. Valid content can remain unavailable "
            "for transfer when its shape is not supported."
        ),
        foreground="#6b4f00",
        anchor="w",
        justify="left",
        wraplength=900,
    )
    library_safety_notice.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(5, 0))

    library_primary_toolbar = ttk.Frame(library_tab)
    library_primary_toolbar.pack(fill="x", pady=(0, 8), before=library_toolbar)
    library_add_button = ttk.Menubutton(library_primary_toolbar, text="+ Add")
    library_add_menu = tk.Menu(library_add_button, tearoff=False)
    library_add_menu.add_command(
        label="Add Files…", command=lambda: library_import_action()
    )
    library_add_menu.add_command(
        label="Add Folder…", command=lambda: library_folder_import_action()
    )
    library_add_button.configure(menu=library_add_menu)
    library_add_button.pack(side="left", padx=(0, 6))
    library_search_var = tk.StringVar(value="")
    ttk.Label(library_primary_toolbar, text="Search").pack(side="left")
    library_search_entry = ttk.Entry(
        library_primary_toolbar, textvariable=library_search_var, width=18
    )
    library_search_entry.pack(side="left", fill="x", expand=True, padx=(4, 8))
    library_remove_selection_button = ttk.Button(
        library_primary_toolbar, text="Remove", state="disabled"
    )
    library_remove_selection_button.pack(side="left", padx=2)
    library_reorder_up_button = ttk.Button(
        library_primary_toolbar, text="▲", width=3, state="disabled"
    )
    library_reorder_down_button = ttk.Button(
        library_primary_toolbar, text="▼", width=3, state="disabled"
    )
    library_reorder_up_button.pack(side="left", padx=(6, 1))
    library_reorder_down_button.pack(side="left", padx=(1, 2))
    library_details_visible = False
    library_details_toggle_button = ttk.Button(
        library_primary_toolbar, text="Details", state="disabled"
    )
    library_details_toggle_button.pack(side="left", padx=(6, 2))
    library_technical_details_action_button = ttk.Button(
        library_primary_toolbar, text="Technical", state="disabled"
    )
    library_technical_details_action_button.pack(side="left", padx=2)
    library_transfer_eligibility_label.pack_forget()
    library_toolbar.pack_forget()

    library_status_frame = ttk.Frame(library_tab)
    library_status_frame.pack(side="bottom", fill="x", pady=(8, 0))
    library_status_label = ttk.Label(
        library_status_frame,
        textvariable=library_status_var,
        anchor="w",
        justify="left",
        wraplength=900,
    )
    library_status_label.pack(anchor="w", fill="x")
    library_operation_progress = ttk.Progressbar(
        library_status_frame, mode="indeterminate", length=180
    )
    library_operation_progress.pack(side="left", padx=(0, 8), pady=(5, 0))
    library_operation_activity_var = tk.StringVar(value="")
    ttk.Label(
        library_status_frame,
        textvariable=library_operation_activity_var,
        anchor="w",
    ).pack(side="left", fill="x", expand=True, pady=(5, 0))

    library_selection_summary_var = tk.StringVar(value="0 items selected")
    library_destination_summary_var = tk.StringVar(value="Destination: root")
    transfer_footer = ttk.Frame(root, padding=(10, 6))
    transfer_footer.pack(side="bottom", fill="x", padx=8, pady=(0, 6))
    ttk.Label(
        transfer_footer, textvariable=library_selection_summary_var, anchor="w"
    ).pack(side="left", padx=(0, 16))
    ttk.Label(
        transfer_footer, textvariable=library_destination_summary_var, anchor="w"
    ).pack(side="left", fill="x", expand=True)
    library_transfer_button = ttk.Button(
        transfer_footer, text="Transfer →", state="disabled"
    )
    library_transfer_button.pack(side="right", padx=(12, 0))

    library_content = ttk.Panedwindow(library_tab, orient="horizontal")
    library_content.pack(fill="both", expand=True)
    # ttk::panedwindow has weighted panes but no portable minsize option.
    # Explicit child widths provide useful requested minima without relying on
    # the classic tk::panedwindow API.
    library_list_frame = ttk.Frame(
        library_content, width=LIBRARY_LIST_MIN_WIDTH, padding=(0, 0, 8, 0)
    )
    library_detail_frame = ttk.Frame(
        library_content, width=LIBRARY_DETAIL_MIN_WIDTH, padding=(8, 0, 0, 0)
    )
    library_content.add(library_list_frame, weight=3)
    library_content.add(library_detail_frame, weight=2)
    library_list_frame.columnconfigure(0, weight=1)
    library_list_frame.rowconfigure(0, weight=1)
    library_tree = ttk.Treeview(
        library_list_frame,
        columns=("type", "state", "size", "source"),
        show="tree headings",
        selectmode="extended",
    )
    library_tree.heading("#0", text="Item")
    library_tree.heading("type", text="Type")
    library_tree.heading("state", text="State")
    library_tree.heading("size", text="Size")
    library_tree.heading("source", text="Source")
    library_tree.column("#0", minwidth=150, width=190, stretch=True)
    library_tree.column("type", minwidth=70, width=88, stretch=False)
    library_tree.column("state", minwidth=78, width=88, stretch=False)
    library_tree.column("size", minwidth=75, width=86, stretch=False, anchor="e")
    library_tree.column("source", minwidth=180, width=240, stretch=True)
    library_tree_scroll = ttk.Scrollbar(
        library_list_frame, orient="vertical", command=library_tree.yview
    )
    library_tree_horizontal_scroll = ttk.Scrollbar(
        library_list_frame, orient="horizontal", command=library_tree.xview
    )
    library_tree.configure(
        yscrollcommand=library_tree_scroll.set,
        xscrollcommand=library_tree_horizontal_scroll.set,
        displaycolumns=("type", "size"),
    )
    library_tree.grid(row=0, column=0, sticky="nsew")
    library_tree_scroll.grid(row=0, column=1, sticky="ns")
    library_tree_horizontal_scroll.grid(row=1, column=0, sticky="ew")
    library_detail_frame.columnconfigure(0, weight=1)
    library_detail_frame.rowconfigure(2, weight=0)
    library_detail_frame.rowconfigure(3, weight=1)
    library_detail_heading = ttk.Label(library_detail_frame, text="Content selection")
    library_detail_heading.grid(row=0, column=0, sticky="w")
    library_technical_details_button = ttk.Button(
        library_detail_frame,
        text="Technical Details",
        state="disabled",
        takefocus=False,
    )
    library_technical_details_button.grid(row=0, column=0, sticky="e")
    library_detail_label = ttk.Label(
        library_detail_frame,
        textvariable=library_detail_var,
        wraplength=420,
        justify="left",
    )
    library_detail_label.grid(row=1, column=0, sticky="ew", pady=(2, 10))
    library_report_frame = ttk.Frame(library_detail_frame)
    library_report_frame.grid(row=3, column=0, sticky="nsew")
    library_report_frame.columnconfigure(0, weight=1)
    library_report_frame.rowconfigure(1, weight=1)
    library_bitmap_preview_label = ttk.Label(
        library_detail_frame, anchor="center", justify="center"
    )
    library_preview_image: Optional[Any] = None
    library_report = tk.Text(
        library_report_frame, height=20, width=48, wrap="word", undo=False
    )
    library_report_vertical_scroll = ttk.Scrollbar(
        library_report_frame, orient="vertical", command=library_report.yview
    )
    library_report_horizontal_scroll = ttk.Scrollbar(
        library_report_frame, orient="horizontal", command=library_report.xview
    )
    library_report.configure(
        yscrollcommand=library_report_vertical_scroll.set,
        xscrollcommand=library_report_horizontal_scroll.set,
    )
    library_report.grid(row=1, column=0, sticky="nsew")
    library_report_vertical_scroll.grid(row=1, column=1, sticky="ns")
    library_report_horizontal_scroll.grid(row=2, column=0, sticky="ew")
    library_report.configure(state="disabled")
    library_content.forget(library_detail_frame)

    def update_library_responsive_labels(_event: Any = None) -> None:
        """Keep safety and status text readable as the window is resized."""

        available_width = max(320, library_tab.winfo_width() - 24)
        library_safety_notice.configure(wraplength=available_width)
        library_status_label.configure(wraplength=available_width)
        detail_width = max(260, library_detail_frame.winfo_width() - 20)
        library_detail_label.configure(wraplength=detail_width)

    def keep_library_sash_in_bounds(_event: Any = None) -> None:
        """Keep both Library panes useful while retaining a draggable sash."""

        try:
            total_width = library_content.winfo_width()
            current_position = library_content.sashpos(0)
        except tk.TclError:
            return
        minimum_position = LIBRARY_LIST_MIN_WIDTH
        maximum_position = total_width - LIBRARY_DETAIL_MIN_WIDTH
        if maximum_position < minimum_position:
            return
        bounded_position = max(
            minimum_position, min(current_position, maximum_position)
        )
        if bounded_position != current_position:
            library_content.sashpos(0, bounded_position)

    library_tab.bind("<Configure>", update_library_responsive_labels)
    library_content.bind("<Configure>", keep_library_sash_in_bounds)
    library_content.bind("<ButtonRelease-1>", keep_library_sash_in_bounds)

    def show_library_inspector(show: Optional[bool] = None) -> None:
        nonlocal library_details_visible
        desired = not library_details_visible if show is None else bool(show)
        if desired == library_details_visible:
            return
        if desired:
            library_content.add(library_detail_frame, weight=2)
            library_details_toggle_button.configure(text="Hide Details")
        else:
            library_content.forget(library_detail_frame)
            library_details_toggle_button.configure(text="Details")
        library_details_visible = desired

    device_home_frame = ttk.LabelFrame(device_tab, text="Device Home", padding=10)
    device_home_frame.pack(fill="x", padx=10, pady=(10, 6))
    device_home_frame.columnconfigure(0, weight=1)
    device_home_heading = ttk.Label(
        device_home_frame,
        textvariable=device_home_heading_var,
        font=("TkDefaultFont", 13, "bold"),
    )
    device_home_heading.grid(row=0, column=0, sticky="w")
    device_home_message = ttk.Label(
        device_home_frame,
        textvariable=device_home_message_var,
        wraplength=850,
        justify="left",
    )
    device_home_message.grid(row=1, column=0, sticky="ew", pady=(2, 6))
    device_capacity_label = ttk.Label(
        device_home_frame,
        textvariable=device_capacity_var,
        wraplength=850,
        justify="left",
    )
    device_capacity_label.grid(row=2, column=0, sticky="ew", pady=(0, 6))
    device_snapshot_label = ttk.Label(
        device_home_frame,
        textvariable=device_snapshot_var,
        wraplength=850,
        justify="left",
    )
    device_snapshot_label.grid(row=3, column=0, sticky="ew")
    backup_semantics_label = ttk.Label(
        device_home_frame,
        text="Backup ≠ Restore: backups are read-only snapshots; Restore is unavailable.",
        foreground="#555555",
        wraplength=850,
        justify="left",
    )
    backup_semantics_label.grid(row=4, column=0, sticky="ew", pady=(6, 0))
    safety_state_label = ttk.Label(
        device_home_frame,
        textvariable=safety_state_var,
        wraplength=850,
        justify="left",
    )
    safety_state_label.grid(row=5, column=0, sticky="ew", pady=(6, 0))
    device_home_actions = ttk.Frame(device_home_frame)
    device_home_actions.grid(row=0, column=1, rowspan=6, sticky="ne", padx=(12, 0))
    technical_details_button = ttk.Button(device_home_actions, text="Technical Details…")
    technical_details_button.pack(anchor="e", pady=(0, 4))
    show_backup_button = ttk.Button(
        device_home_actions,
        text="Show in Finder" if sys.platform == "darwin" else "Show backup location",
        state="disabled",
    )
    show_backup_button.pack(anchor="e")

    def update_device_home_responsive_labels(_event: Any = None) -> None:
        available_width = max(
            320,
            device_home_frame.winfo_width()
            - device_home_actions.winfo_width()
            - 48,
        )
        for label in (
            device_home_message,
            device_capacity_label,
            device_snapshot_label,
            backup_semantics_label,
            safety_state_label,
        ):
            label.configure(wraplength=available_width)

    device_home_frame.bind("<Configure>", update_device_home_responsive_labels)
    device_home_frame.pack_forget()

    def update_device_home_display(
        snapshot: Optional[DeviceHomeSnapshot] = None,
    ) -> None:
        nonlocal device_home_snapshot, device_technical_details
        if snapshot is not None:
            device_home_snapshot = snapshot
            device_home_heading_var.set(snapshot.heading)
            device_home_message_var.set(snapshot.message)
            device_technical_details = snapshot.technical_details
            invalidate_library_transfer_review_if_stale()
        baseline = loaded_backup_summary
        device_capacity_var.set(
            format_capacity_summary(
                total_model_bytes=(
                    device_home_snapshot.capacity_bytes
                    if device_home_snapshot is not None
                    and device_home_snapshot.state == "connected"
                    else None
                ),
                baseline_model_bytes=(baseline.model_bytes if baseline else None),
                backup_timestamp=(baseline.created_at_utc if baseline else None),
            )
        )
        if latest_backup_summary is not None:
            device_snapshot_var.set(
                f"Latest complete backup: {latest_backup_summary.created_at_utc} — "
                f"{latest_backup_summary.directory}"
            )
        elif latest_backup_error:
            device_snapshot_var.set(
                f"Latest complete backup could not be verified: {latest_backup_error}"
            )
        elif loaded_backup_summary is not None:
            device_snapshot_var.set(
                "Loaded complete backup (outside app-managed history): "
                f"{loaded_backup_summary.created_at_utc} — {loaded_backup_summary.directory}"
            )
        else:
            device_snapshot_var.set("No complete backup has been saved here yet.")
        selected_backup = latest_backup_summary or loaded_backup_summary
        show_backup_button.configure(
            state="normal" if selected_backup is not None else "disabled"
        )
        backup_var.set(
            f"Backup: {loaded_backup_summary.directory.name}"
            if loaded_backup_summary is not None
            else "No backup loaded"
        )
        invalidate_library_transfer_review_if_stale()

    def show_technical_details_action() -> None:
        details = device_technical_details or "No USB session details are available yet."
        messagebox.showinfo("Technical Details", details, parent=root)

    def show_backup_location_action() -> None:
        summary = latest_backup_summary or loaded_backup_summary
        if summary is None:
            return
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["/usr/bin/open", "-R", str(summary.directory)])
            elif os.name == "nt":
                os.startfile(str(summary.directory.parent))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(summary.directory.parent)])
        except OSError as exc:
            messagebox.showerror(
                "Show backup location",
                f"The backup is saved at:\n{summary.directory}\n\n{exc}",
                parent=root,
            )

    toolbar = ttk.Frame(device_tab, padding=(2, 2, 2, 6))
    toolbar.pack(fill="x")
    ttk.Label(toolbar, text="DEVICE LIBRARY", font=("TkDefaultFont", 13, "bold")).pack(
        side="left", padx=(0, 8)
    )
    check_button = ttk.Button(toolbar, text="Refresh")
    backup_button = ttk.Button(toolbar, text="Back Up")
    open_button = ttk.Button(toolbar, text="Open backup…")
    export_button = ttk.Button(toolbar, text="Export selected…", state="disabled")
    replacement_button = ttk.Button(
        toolbar, text="Preview replacement…", state="disabled"
    )
    write_button = ttk.Button(
        toolbar, text="Replace selected text…", state="disabled"
    )
    for button in (check_button, backup_button):
        button.pack(side="left", padx=3)
    device_more_button = ttk.Menubutton(toolbar, text="More")
    device_more_menu = tk.Menu(device_more_button, tearoff=False)
    device_more_menu.add_command(
        label="Open Backup…", command=lambda: open_button.invoke()
    )
    device_more_menu.add_command(
        label="Export Selected…", command=lambda: export_button.invoke()
    )
    device_more_menu.add_separator()
    device_more_menu.add_command(
        label="View Backup Location…", command=lambda: show_backup_location_action()
    )
    device_more_menu.add_command(
        label="Technical Details…", command=lambda: show_technical_details_action()
    )
    device_more_button.configure(menu=device_more_menu)
    device_more_button.pack(side="left", padx=3)
    device_details_visible = False
    device_details_button = ttk.Button(toolbar, text="Details")
    device_details_button.pack(side="left", padx=3)
    device_delete_button = ttk.Button(toolbar, text="Delete", state="disabled")
    device_delete_button.pack(side="left", padx=3)
    ttk.Label(toolbar, textvariable=backup_var, anchor="e").pack(
        side="right", fill="x", expand=True, padx=(12, 0)
    )

    device_overview = ttk.Frame(device_tab, padding=(2, 0, 2, 5))
    device_overview.pack(fill="x")
    ttk.Label(
        device_overview, textvariable=device_home_heading_var, anchor="w"
    ).pack(side="left", fill="x", expand=True)
    ttk.Label(
        device_overview,
        textvariable=device_capacity_var,
        anchor="e",
        justify="right",
    ).pack(side="right", padx=(8, 0))
    device_delete_status_var = tk.StringVar(
        value="Delete is not enabled for this selection."
    )
    ttk.Label(
        device_tab, textvariable=device_delete_status_var, anchor="w"
    ).pack(fill="x", padx=4, pady=(0, 4))

    device_search_bar = ttk.Frame(device_tab, padding=(2, 0, 2, 5))
    device_search_bar.pack(fill="x")
    ttk.Label(device_search_bar, text="Search").pack(side="left")
    device_search_var = tk.StringVar(value="")
    device_search_entry = ttk.Entry(
        device_search_bar, textvariable=device_search_var, width=22
    )
    device_search_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))

    content = ttk.Panedwindow(device_tab, orient="horizontal")
    content.pack(fill="both", expand=True, padx=10, pady=(0, 8))
    browser_frame = ttk.Frame(content, padding=6)
    detail_frame = ttk.Frame(content, padding=10)
    content.add(browser_frame, weight=3)
    content.add(detail_frame, weight=2)

    ttk.Label(browser_frame, text="Name / Type / Size").pack(anchor="w", pady=(0, 5))
    tree_container = ttk.Frame(browser_frame)
    tree_container.pack(fill="both", expand=True)
    tree = ttk.Treeview(
        tree_container,
        columns=("kind", "size", "state"),
        show="tree headings",
        selectmode="extended",
    )
    tree.heading("#0", text="Name")
    tree.heading("kind", text="Type")
    tree.heading("size", text="Size")
    tree.heading("state", text="State")
    tree.column("#0", minwidth=220, width=360, stretch=True)
    tree.column("kind", minwidth=80, width=90, stretch=False)
    tree.column("size", minwidth=80, width=100, stretch=False, anchor="e")
    tree.column("state", minwidth=80, width=90, stretch=False)
    tree_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=tree.yview)
    tree_horizontal_scroll = ttk.Scrollbar(
        tree_container, orient="horizontal", command=tree.xview
    )
    tree.configure(
        yscrollcommand=tree_scroll.set,
        xscrollcommand=tree_horizontal_scroll.set,
        displaycolumns=("kind", "size"),
    )
    tree_container.columnconfigure(0, weight=1)
    tree_container.rowconfigure(0, weight=1)
    tree.grid(row=0, column=0, sticky="nsew")
    tree_scroll.grid(row=0, column=1, sticky="ns")
    tree_horizontal_scroll.grid(row=1, column=0, sticky="ew")

    ttk.Label(detail_frame, text="Selection").pack(anchor="w")
    ttk.Label(detail_frame, textvariable=details_var, wraplength=360).pack(
        anchor="w", fill="x", pady=(2, 10)
    )
    preview = tk.Text(detail_frame, height=18, width=42, wrap="word")
    preview.pack(fill="both", expand=True)
    preview.configure(state="disabled")
    image_preview = ttk.Label(detail_frame, anchor="center")
    image_preview.pack_forget()
    preview_image: Optional[Any] = None
    ttk.Label(detail_frame, text="Read-only preview").pack(anchor="w", pady=(8, 0))
    content.forget(detail_frame)

    def toggle_device_inspector() -> None:
        nonlocal device_details_visible
        if device_details_visible:
            content.forget(detail_frame)
            device_details_visible = False
            device_details_button.configure(text="Details")
        else:
            content.add(detail_frame, weight=1)
            device_details_visible = True
            device_details_button.configure(text="Hide Details")

    bottom = ttk.Frame(device_tab, padding=(10, 0, 10, 10))
    bottom.pack(fill="x")
    progress = ttk.Progressbar(bottom, mode="determinate", maximum=8)
    progress.pack(side="left", fill="x", expand=True, padx=(0, 10))
    ttk.Label(bottom, textvariable=status_var, anchor="w").pack(side="left", fill="x", expand=True)

    conversion_document: Optional[OfflineTextDocument] = None
    renderer_document: Optional[OfflineTextDocument] = None
    converter_source_var = tk.StringVar()
    converter_status_var = tk.StringVar(value="Choose a UTF-8 TXT file for an offline conversion preview.")
    converter_report = tk.Text(text_converter_tab, height=22, wrap="word")
    converter_report.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=(12, 8))
    converter_report.configure(state="disabled")
    text_converter_tab.columnconfigure(0, weight=1)
    text_converter_tab.rowconfigure(2, weight=1)
    ttk.Label(
        text_converter_tab,
        text=(
            "Offline Text Converter — strict UTF-8 input, CP932/CRLF output, "
            "and deterministic logical pages. No USB operation is available here."
        ),
        wraplength=760,
    ).grid(row=0, column=0, columnspan=4, sticky="w")
    ttk.Entry(text_converter_tab, textvariable=converter_source_var).grid(
        row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0)
    )
    converter_browse_button = ttk.Button(text_converter_tab, text="Browse…")
    converter_browse_button.grid(row=1, column=2, padx=(6, 0), pady=(10, 0))
    converter_preview_button = ttk.Button(text_converter_tab, text="Preview conversion")
    converter_preview_button.grid(row=1, column=3, padx=(6, 0), pady=(10, 0))
    converter_export_button = ttk.Button(
        text_converter_tab, text="Export offline package…", state="disabled"
    )
    converter_export_button.grid(row=3, column=0, sticky="w")
    ttk.Label(text_converter_tab, textvariable=converter_status_var, wraplength=760).grid(
        row=3, column=1, columnspan=3, sticky="w", padx=(10, 0)
    )

    renderer_source_var = tk.StringVar()
    renderer_page_var = tk.StringVar(value="1")
    renderer_status_var = tk.StringVar(
        value="The renderer currently previews logical pages; font rasterization is not yet enabled."
    )
    renderer_preview = tk.Text(ebook_renderer_tab, height=22, width=80, wrap="none")
    renderer_preview.grid(row=2, column=0, columnspan=5, sticky="nsew", pady=(12, 8))
    renderer_preview.configure(state="disabled")
    ebook_renderer_tab.columnconfigure(0, weight=1)
    ebook_renderer_tab.rowconfigure(2, weight=1)
    ttk.Label(
        ebook_renderer_tab,
        text=(
            "Ebook Renderer — deterministic 240 × 320 / 1-bit page profile. "
            "This first slice displays the page plan without claiming font or EPUB/MOBI compatibility."
        ),
        wraplength=760,
    ).grid(row=0, column=0, columnspan=5, sticky="w")
    ttk.Entry(ebook_renderer_tab, textvariable=renderer_source_var).grid(
        row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0)
    )
    renderer_browse_button = ttk.Button(ebook_renderer_tab, text="Browse…")
    renderer_browse_button.grid(row=1, column=2, padx=(6, 0), pady=(10, 0))
    renderer_load_button = ttk.Button(ebook_renderer_tab, text="Load pages")
    renderer_load_button.grid(row=1, column=3, padx=(6, 0), pady=(10, 0))
    renderer_page_spin = ttk.Spinbox(
        ebook_renderer_tab, from_=1, to=1, width=6, textvariable=renderer_page_var
    )
    renderer_page_spin.grid(row=1, column=4, padx=(6, 0), pady=(10, 0))
    ttk.Label(ebook_renderer_tab, textvariable=renderer_status_var, wraplength=760).grid(
        row=3, column=0, columnspan=5, sticky="w"
    )

    settings_text = tk.Text(settings_tab, height=20, width=80, wrap="word")
    settings_text.pack(fill="both", expand=True)
    _set_readonly_text(
        settings_text,
        "Sony InfoCarry settings and recovery help\n\n"
        f"Runtime: {runtime.description}\n"
        "Supported device: Sony InfoCarry VNW-V15 (VID 054c, PID 001e)\n"
        "Device Manager writes are limited to the guarded existing-TXT workflow.\n"
        "The exact reviewed VNW-V15 TXT/BMP/TXT and TXT/BMP/TXT/TXT shapes can enter a guarded transfer flow only after fresh device checks and separate operation approval. Other arrangements remain unavailable for transfer.\n"
        "Unsupported package shapes remain unavailable; recovery is unresolved and automatic write retry is never used.\n"
        "Text Converter and Ebook Renderer are offline-only in the current product scope.\n\n"
        "Recovery: preserve any before/after backup, do not retry a started write, "
        "and use only read-only detection or backup checks after a disconnect.\n"
        "The separate InfoCarry-Toolkit project remains read-only and is not imported.\n",
    )

    def choose_source(target: Any, title: str) -> None:
        selected = filedialog.askopenfilename(
            title=title,
            filetypes=(("UTF-8 text files", "*.txt"), ("All files", "*")),
            parent=root,
        )
        if selected:
            target.set(selected)

    def library_item_revision(item: Any) -> tuple[Any, ...]:
        """Capture the content/target inputs that own a Library result."""

        if library_catalog is None:
            return ()
        values: list[Any] = []

        def visit(value: Any) -> None:
            values.extend(
                (
                    value.item_id,
                    value.source_path,
                    _source_review_filesystem_revision(value.source_path),
                    value.source_filename,
                    value.source_sha256,
                    value.source_status,
                    value.state,
                    value.preparation_state,
                    value.parent_id,
                    value.sibling_order,
                    value.target_folder_name,
                    value.target_child_name,
                    value.prepared_manifest_sha256,
                    (
                        value.prepared_artifact.get("artifact_identity")
                        if isinstance(getattr(value, "prepared_artifact", None), dict)
                        else None
                    ),
                )
            )
            package = getattr(value, "package", None)
            if package is not None:
                package_root = Path(value.source_path).expanduser()
                package_paths = [getattr(package, "manifest_path", None)]
                for child in getattr(package, "children", ()):
                    if not isinstance(child, Mapping):
                        continue
                    package_paths.extend(
                        (child.get("package_path"), child.get("prepared_path"))
                    )
                for relative_path in package_paths:
                    if not isinstance(relative_path, str):
                        continue
                    relative = Path(relative_path)
                    if not relative.is_absolute() and ".." in relative.parts:
                        continue
                    candidate = relative if relative.is_absolute() else package_root / relative
                    try:
                        candidate.resolve().relative_to(package_root.resolve())
                    except (OSError, ValueError):
                        continue
                    values.append(_source_review_filesystem_revision(candidate))
            for child in library_catalog.children(value.item_id):
                visit(child)

        visit(item)
        return tuple(values)

    def selected_library_revision() -> Optional[tuple[Any, ...]]:
        item = selected_library_item()
        return None if item is None else library_item_revision(item)

    def selected_library_selection_revision() -> tuple[tuple[Any, ...], ...]:
        return tuple(library_item_revision(item) for item in selected_library_items())

    def all_library_revision() -> tuple[Any, ...]:
        """Capture every catalog item used by an all-ready review."""

        if library_catalog is None:
            return ("all_ready", ())
        return (
            "all_ready",
            tuple(library_item_revision(item) for item in library_catalog.items),
        )

    def library_review_context_revision() -> tuple[Any, ...]:
        snapshot = device_home_snapshot
        backup_summaries = tuple(
            (
                str(summary.directory),
                summary.created_at_utc,
                summary.model_bytes,
                summary.blob_sha256,
            )
            if summary is not None
            else None
            for summary in (latest_backup_summary, loaded_backup_summary)
        )
        return (
            (
                snapshot.state,
                snapshot.heading,
                snapshot.capacity_bytes,
                snapshot.technical_details,
            )
            if snapshot is not None
            else None,
            str(model.state.backup_directory or ""),
            selected_device_destination_path(),
            backup_summaries,
            _backup_review_filesystem_revision(model.state.backup_directory),
            latest_backup_error,
        )

    def library_transfer_review_revision(
        selection_revision: tuple[Any, ...],
    ) -> tuple[Any, ...]:
        return (
            "transfer-review",
            selection_revision,
            library_review_context_revision(),
        )

    def library_selection_matches(revision: Any) -> bool:
        if (
            isinstance(revision, tuple)
            and len(revision) == 3
            and revision[0] == "transfer-review"
        ):
            return (
                library_selection_matches(revision[1])
                and library_review_context_revision() == revision[2]
            )
        if (
            isinstance(revision, tuple)
            and len(revision) == 2
            and revision[0] == "all_ready"
        ):
            return library_catalog is not None and all_library_revision() == revision
        current = selected_library_revision()
        if (
            isinstance(revision, tuple)
            and revision
            and isinstance(revision[0], tuple)
        ):
            return selected_library_selection_revision() == revision
        if revision == ():
            return not selected_library_items()
        return revision is not None and (
            current == revision or current == (revision,)
        )

    def invalidate_library_transfer_review_if_stale() -> None:
        nonlocal library_current_plan_report, library_current_readiness
        nonlocal library_prepared_operation, library_current_revision
        nonlocal library_technical_details_open
        revision = library_current_revision
        if (
            isinstance(revision, tuple)
            and len(revision) == 3
            and revision[0] == "transfer-review"
            and not library_selection_matches(revision)
        ):
            invalidated = library_operation_controller.invalidate()
            library_current_plan_report = None
            library_current_readiness = None
            library_prepared_operation = None
            library_current_revision = None
            library_technical_details_open = False
            library_technical_details_button.configure(
                text="Technical Details", state="disabled"
            )
            if invalidated:
                restore_device_manager_controls()
            selected = selected_library_item()
            if selected is not None:
                _set_readonly_text(
                    library_report,
                    format_library_selection_summary(selected)
                    + "\n\nThe previous review is no longer current. If a source file changed, "
                    "prepare the content again before reviewing transfer.",
                )
            library_status_var.set(
                "Content, Device Home, or backup details changed; review transfer again for current information"
            )

    def process_library_review_freshness() -> None:
        """Invalidate a displayed review when its source or context changes."""

        if not root.winfo_exists():
            return
        if not library_operation_controller.busy:
            invalidate_library_transfer_review_if_stale()
        if root.winfo_exists():
            root.after(1000, process_library_review_freshness)

    def set_library_add_controls_available(available: bool) -> None:
        """Bind host import affordances only to Local Library health."""

        state = "normal" if available else "disabled"
        library_add_button.configure(state=state)
        for index in range(2):
            library_add_menu.entryconfigure(index, state=state)
        for button in (
            library_import_button,
            library_folder_import_button,
            library_package_import_button,
        ):
            button.configure(state=state)

    def restore_device_manager_controls() -> None:
        """Restore Device Manager controls after a Library operation ends."""

        if worker is None or not worker.is_alive():
            for button in (check_button, backup_button, open_button):
                button.configure(state="normal")
            show_selection()

    def set_library_operation_busy(busy: bool, *, label: str = "") -> None:
        """Keep Library actions stable while a background operation owns them."""

        if busy:
            library_operation_activity_var.set(label or "Working…")
            library_operation_progress.start(12)
            for button in (
                check_button,
                backup_button,
                open_button,
                export_button,
                replacement_button,
                write_button,
            ):
                button.configure(state="disabled")
            for button in (
                library_search_entry,
                library_remove_selection_button,
                library_reorder_up_button,
                library_reorder_down_button,
                library_details_toggle_button,
                library_technical_details_action_button,
                library_transfer_button,
                library_move_up_button,
                library_move_down_button,
                library_rename_button,
                library_remove_button,
                library_prepare_button,
                library_preview_button,
                library_selected_queue_button,
                library_all_queue_button,
                library_live_preflight_button,
                library_transfer_once_button,
                library_cancel_button,
            ):
                button.configure(state="disabled")
            library_cancel_button.configure(state="normal")
            library_technical_details_button.configure(state="disabled")
        else:
            library_operation_progress.stop()
            library_operation_activity_var.set("")
            library_cancel_button.configure(state="disabled")
            restore_device_manager_controls()
            show_library_selection()

    def library_cancel_action() -> None:
        if library_operation_controller.cancel():
            library_status_var.set(
                "Stopping the host-only operation… no device-changing action was started"
            )
            library_operation_activity_var.set("Stopping…")

    def library_technical_details_action() -> None:
        nonlocal library_technical_details_open
        value = (
            library_current_readiness
            or library_current_preview
            or selected_library_item()
        )
        if value is None:
            return
        if library_technical_details_open:
            library_technical_details_open = False
            library_technical_details_button.configure(text="Technical Details")
            library_technical_details_action_button.configure(text="Technical")
            show_library_selection()
            return
        library_technical_details_open = True
        library_technical_details_button.configure(text="Hide Technical Details")
        library_technical_details_action_button.configure(text="Hide Technical")
        show_library_inspector()
        _set_readonly_text(library_report, format_library_technical_details(value))

    def start_library_operation(
        name: str,
        revision: tuple[Any, ...],
        work: Any,
        on_success: Any,
        *,
        validate_revision: bool = True,
        on_terminal: Any = None,
    ) -> None:
        """Start a Library operation and apply only current main-thread results."""

        nonlocal library_operation_token
        if worker is not None and worker.is_alive():
            library_status_var.set(
                "A Device Manager operation is in progress; Library work will remain disabled"
            )
            if on_terminal is not None:
                on_terminal()
            return
        set_library_operation_busy(True, label=f"{name}…")

        def on_progress(update: OperationProgress) -> None:
            library_operation_activity_var.set(update.label)

        def finish_terminal() -> None:
            if on_terminal is not None:
                on_terminal()

        def on_complete(outcome: OperationOutcome[Any]) -> None:
            nonlocal library_operation_token, library_current_readiness
            library_operation_token = None
            if validate_revision and not library_selection_matches(revision):
                set_library_operation_busy(False)
                library_current_readiness = readiness_state_from_error(
                    RuntimeError("content or target changed while the operation was running")
                )
                _set_readonly_text(
                    library_report,
                    format_library_operation_failure(
                        RuntimeError("content or target changed while the operation was running")
                    ),
                )
                library_status_var.set(
                    "The result was discarded because the selected content or target changed; prepare or review again"
                )
                finish_terminal()
                return
            set_library_operation_busy(False)
            if outcome.status is OperationStatus.SUCCEEDED:
                try:
                    on_success(outcome.value)
                except BaseException as error:
                    state = readiness_state_from_error(error)
                    library_current_readiness = state
                    _set_readonly_text(
                        library_report, format_library_operation_failure(error)
                    )
                    library_status_var.set(state.message)
                finish_terminal()
                return
            if outcome.cancelled:
                library_status_var.set(
                    "Host-only operation cancelled safely; no device-changing action was started"
                )
                finish_terminal()
                return
            error = outcome.error or RuntimeError("the host-only operation failed")
            state = readiness_state_from_error(error)
            # The typed state is retained for an explicitly requested
            # Technical Details view; the normal report remains product-safe.
            library_current_readiness = state
            _set_readonly_text(library_report, format_library_operation_failure(error))
            library_status_var.set(state.message)
            finish_terminal()

        try:
            library_operation_token = library_operation_controller.start(
                name,
                work,
                on_complete=on_complete,
                on_progress=on_progress,
            )
        except OperationBusyError:
            set_library_operation_busy(False)
            library_status_var.set("Another Library operation is already in progress")
            if on_terminal is not None:
                on_terminal()

    def clear_library_review_for_input_change() -> None:
        nonlocal library_current_plan_report, library_current_readiness
        nonlocal library_prepared_operation, library_current_preview
        nonlocal library_current_revision, library_technical_details_open
        clear_library_bitmap_preview()
        invalidated = library_operation_controller.invalidate()
        library_current_plan_report = None
        library_current_readiness = None
        library_prepared_operation = None
        library_current_preview = None
        library_current_revision = None
        library_technical_details_open = False
        library_technical_details_button.configure(
            text="Technical Details", state="disabled"
        )
        library_technical_details_action_button.configure(
            text="Technical", state="disabled"
        )
        library_operation_progress.stop()
        library_operation_activity_var.set("")
        library_cancel_button.configure(state="disabled")
        if invalidated:
            restore_device_manager_controls()

    def visible_library_tree_items(parent: str = "") -> list[str]:
        result: list[str] = []
        for tree_item in library_tree.get_children(parent):
            result.append(tree_item)
            result.extend(visible_library_tree_items(tree_item))
        return result

    def refresh_library_view(*, selected_item_id: Optional[str] = None) -> None:
        nonlocal library_current_plan_report, library_current_readiness, library_prepared_operation
        had_tree_items = bool(library_tree_items)
        selected_ids = {
            library_tree_items[tree_item]
            for tree_item in library_tree.selection()
            if tree_item in library_tree_items
        }
        if selected_item_id is not None:
            selected_ids = {selected_item_id}
        search_text = library_search_var.get().strip().casefold()
        open_ids = {
            item_id
            for tree_item, item_id in library_tree_items.items()
            if library_tree.item(tree_item, "open")
        }
        library_tree.delete(*library_tree.get_children())
        library_tree_items.clear()
        if library_catalog is None or library_workflow is None:
            set_library_add_controls_available(False)
            library_search_entry.configure(state="disabled")
            library_transfer_button.configure(state="disabled")
            library_remove_selection_button.configure(state="disabled")
            library_reorder_up_button.configure(state="disabled")
            library_reorder_down_button.configure(state="disabled")
            library_details_toggle_button.configure(state="disabled")
            library_technical_details_action_button.configure(state="disabled")
            library_import_button.configure(state="disabled")
            library_folder_import_button.configure(state="disabled")
            library_package_import_button.configure(state="disabled")
            library_move_up_button.configure(state="disabled")
            library_move_down_button.configure(state="disabled")
            library_rename_button.configure(state="disabled")
            library_remove_button.configure(state="disabled")
            library_prepare_button.configure(state="disabled")
            library_preview_button.configure(state="disabled")
            library_selected_queue_button.configure(state="disabled")
            library_all_queue_button.configure(state="disabled")
            library_live_preflight_button.configure(state="disabled")
            library_transfer_once_button.configure(state="disabled")
            library_selection_summary_var.set("Local Library unavailable")
            return
        set_library_add_controls_available(True)
        library_search_entry.configure(state="normal")
        library_live_preflight_button.configure(state="disabled")
        library_transfer_once_button.configure(state="disabled")

        ordered_items = library_catalog.items
        visible_ids: set[str] = set()
        if search_text:
            for item in ordered_items:
                if (
                    search_text in item.source_filename.casefold()
                    or search_text in item.source_path.casefold()
                ):
                    cursor: Optional[Any] = item
                    while cursor is not None and cursor.item_id not in visible_ids:
                        visible_ids.add(cursor.item_id)
                        cursor = (
                            None
                            if cursor.parent_id is None
                            else library_catalog.get(cursor.parent_id)
                        )
        else:
            visible_ids = {item.item_id for item in ordered_items}
        node_tree_items: dict[str, str] = {}

        def insert_nodes(parent_id: Optional[str], parent_tree_item: str) -> None:
            for item in library_catalog.children(parent_id):
                if item.item_id not in visible_ids:
                    continue
                node_type = item.node_kind
                if item.package is not None and item.target_folder_name:
                    node_type = "Prepared content"
                else:
                    node_type = _library_display_type(item)
                size = "" if item.node_kind == NODE_FOLDER else f"{item.source_size_bytes:,} B"
                tree_item = library_tree.insert(
                    parent_tree_item,
                    "end",
                    text=item.source_filename,
                    values=(node_type, _library_display_state(item), size, item.source_path),
                    open=(
                        item.item_id in open_ids
                        or bool(search_text)
                        or (not had_tree_items and item.node_kind == NODE_FOLDER)
                    ),
                )
                library_tree_items[tree_item] = item.item_id
                node_tree_items[item.item_id] = tree_item
                insert_nodes(item.item_id, tree_item)

        insert_nodes(None, "")
        restored = [node_tree_items[item_id] for item_id in selected_ids if item_id in node_tree_items]
        if restored:
            library_tree.selection_set(restored)
            library_tree.focus(restored[0])
            library_tree.see(restored[0])
        show_library_selection()

    def selected_library_item() -> Optional[Any]:
        if library_catalog is None:
            return None
        selected = library_tree.selection()
        if len(selected) != 1:
            return None
        item_id = library_tree_items.get(selected[0])
        if item_id is None:
            return None
        try:
            return library_catalog.get(item_id)
        except LibraryError:
            return None

    def selected_library_items() -> list[Any]:
        """Return selected items in the visible Library order."""

        if library_catalog is None:
            return []
        selected_tree_items = set(library_tree.selection())
        items = []
        for tree_item in visible_library_tree_items():
            if tree_item not in selected_tree_items:
                continue
            item_id = library_tree_items.get(tree_item)
            if item_id is None:
                continue
            try:
                items.append(library_catalog.get(item_id))
            except LibraryError:
                continue
        return items

    def canonical_artifacts_for(
        items: Sequence[Any],
        *,
        current_item_id: Optional[str] = None,
    ) -> dict[str, PreparedContentArtifact]:
        """Bind queue/review to the currently displayed canonical artifact."""

        result: dict[str, PreparedContentArtifact] = {}
        current_preview = library_current_preview
        current_artifact = getattr(current_preview, "artifact", None)
        for item in items:
            if (
                current_item_id is not None
                and item.item_id == current_item_id
                and isinstance(current_artifact, PreparedContentArtifact)
            ):
                result[item.item_id] = current_artifact
                continue
            value = getattr(item, "prepared_artifact", None)
            if isinstance(value, dict):
                try:
                    result[item.item_id] = PreparedContentArtifact.from_dict(value)
                except PreparedContentError:
                    continue
            elif getattr(item, "package", None) is not None:
                try:
                    result[item.item_id] = PreparedContentArtifact.from_legacy_children(
                        root_name=item.package.folder_name,
                        children=item.package.children,
                    )
                except (AttributeError, PreparedContentError):
                    continue
        return result

    def clear_library_bitmap_preview() -> None:
        nonlocal library_preview_image
        library_preview_image = None
        library_bitmap_preview_label.configure(image="", text="")
        library_bitmap_preview_label.grid_remove()

    def show_library_bitmap_preview(result: Any) -> None:
        """Show an exact prepared BMP payload using the existing safe decoder."""

        nonlocal library_preview_image
        prepared = getattr(result, "prepared", None)
        workspace_preview = getattr(prepared, "preview", None)
        payload = getattr(workspace_preview, "prepared_bitmap_payload", None)
        if payload is None:
            payload = next(
                (
                    child.payload
                    for child in getattr(prepared, "payloads", ())
                    if getattr(child, "kind", None) == "bmp"
                ),
                None,
            )
        if not isinstance(payload, bytes):
            clear_library_bitmap_preview()
            return
        try:
            bitmap = decode_monochrome_bmp(payload)
            photo = tk.PhotoImage(width=bitmap.width, height=bitmap.height)
            for row_index, row_data in enumerate(bitmap.photo_rows):
                photo.put(row_data, to=(0, row_index))
        except (BitmapFormatError, tk.TclError):
            clear_library_bitmap_preview()
            return
        library_preview_image = photo
        library_bitmap_preview_label.configure(
            image=photo,
            text=f"Prepared bitmap preview — {bitmap.width} × {bitmap.height}, 1-bit",
            compound="top",
        )
        library_bitmap_preview_label.grid(row=2, column=0, sticky="n", pady=(0, 8))

    def show_library_selection(_event: Any = None) -> None:
        nonlocal library_current_plan_report, library_current_readiness, library_prepared_operation
        nonlocal library_current_preview, library_current_revision, library_technical_details_open
        item = selected_library_item()
        enabled = item is not None and library_catalog is not None
        has_selection = bool(library_tree.selection()) and library_catalog is not None
        hierarchy_enabled = enabled
        selected_items = selected_library_items()
        prepared_selection = bool(selected_items) and all(
            selected.package is not None or selected.prepared_artifact is not None
            for selected in selected_items
        )
        prepared_items_available = bool(
            library_catalog is not None
            and any(
                value.package is not None or value.prepared_artifact is not None
                for value in library_catalog.items
            )
        )
        library_remove_selection_button.configure(
            state="normal" if selected_items else "disabled"
        )
        library_details_toggle_button.configure(
            state="normal" if enabled else "disabled"
        )
        library_technical_details_action_button.configure(
            state="normal" if has_selection else "disabled"
        )
        library_transfer_button.configure(
            state=(
                "normal"
                if selected_items and not library_operation_controller.busy
                else "disabled"
            )
        )
        selected_file_ids: set[str] = set()

        def collect_source_files(value: Any) -> None:
            if value.node_kind == NODE_FOLDER:
                for child in library_catalog.children(value.item_id):
                    collect_source_files(child)
            else:
                selected_file_ids.add(value.item_id)

        for selected_item in selected_items:
            collect_source_files(selected_item)
        selected_source_bytes = sum(
            library_catalog.get(item_id).source_size_bytes
            for item_id in selected_file_ids
        )
        library_selection_summary_var.set(
            f"{len(selected_items)} item(s) selected · "
            f"{selected_source_bytes:,} B source"
        )
        library_remove_button.configure(state="normal" if enabled else "disabled")
        library_move_up_button.configure(
            state=(
                "normal"
                if enabled and library_workflow is not None and library_workflow.can_move_up(item.item_id)
                else "disabled"
            )
        )
        library_move_down_button.configure(
            state=(
                "normal"
                if enabled and library_workflow is not None and library_workflow.can_move_down(item.item_id)
                else "disabled"
            )
        )
        if item is None or library_catalog is None:
            library_reorder_up_button.configure(state="disabled")
            library_reorder_down_button.configure(state="disabled")
        else:
            siblings = library_catalog.children(item.parent_id)
            sibling_index = next(
                index for index, sibling in enumerate(siblings)
                if sibling.item_id == item.item_id
            )
            library_reorder_up_button.configure(
                state="normal" if sibling_index > 0 else "disabled"
            )
            library_reorder_down_button.configure(
                state=(
                    "normal"
                    if sibling_index + 1 < len(siblings)
                    else "disabled"
                )
            )
        library_rename_button.configure(
            state=(
                "normal"
                if enabled
                and item.node_kind == NODE_FILE
                and item.package is None
                and item.supported
                else "disabled"
            )
        )
        library_prepare_button.configure(state="normal" if hierarchy_enabled else "disabled")
        library_preview_button.configure(state="normal" if hierarchy_enabled else "disabled")
        library_selected_queue_button.configure(
            state="normal" if has_selection and prepared_selection else "disabled"
        )
        library_all_queue_button.configure(
            state="normal" if prepared_items_available else "disabled"
        )
        current_item_id = item.item_id if item is not None else None
        prepared_item_id = (
            library_prepared_operation.readiness.report.get("selection", {}).get(
                "logical_item_id"
            )
            if library_prepared_operation is not None
            else None
        )
        if prepared_item_id != current_item_id:
            library_current_plan_report = None
            library_current_readiness = None
            library_prepared_operation = None
        current_revision = None if item is None else library_item_revision(item)
        if (
            library_current_revision is not None
            and not library_selection_matches(library_current_revision)
        ):
            invalidated = library_operation_controller.invalidate()
            library_current_plan_report = None
            library_current_readiness = None
            library_prepared_operation = None
            library_current_preview = None
            library_current_revision = None
            library_technical_details_open = False
            clear_library_bitmap_preview()
            library_operation_progress.stop()
            library_operation_activity_var.set("")
            library_cancel_button.configure(state="disabled")
            if invalidated:
                restore_device_manager_controls()
        if not enabled:
            library_current_revision = None
        if library_operation_controller.busy:
            for button in (
                library_move_up_button,
                library_move_down_button,
                library_rename_button,
                library_remove_button,
                library_prepare_button,
                library_preview_button,
                library_selected_queue_button,
                library_all_queue_button,
                library_live_preflight_button,
                library_transfer_once_button,
            ):
                button.configure(state="disabled")
            library_cancel_button.configure(state="normal")
        live_review_ready = bool(
            library_current_readiness is not None
            and getattr(library_current_readiness, "host_profile_eligible", False)
            and library_execution_facade.can_prepare_live
        )
        library_live_preflight_button.configure(
            state="normal" if enabled and live_review_ready else "disabled"
        )
        library_transfer_once_button.configure(
            state=(
                "normal"
                if enabled
                and library_prepared_operation is not None
                and library_execution_facade.transfer_actionable
                else "disabled"
            )
        )
        if library_operation_controller.busy:
            library_live_preflight_button.configure(state="disabled")
            library_transfer_once_button.configure(state="disabled")
            library_technical_details_button.configure(state="disabled")
        if item is None:
            clear_library_bitmap_preview()
            if selected_items:
                library_detail_var.set(
                    f"{len(selected_items)} items selected\n"
                    f"{selected_source_bytes:,} bytes of source files"
                )
                _set_readonly_text(
                    library_report,
                    "Selected items keep their Library order. Transfer planning "
                    "will check source freshness, destination conflicts, and the "
                    "currently available device-transfer shape.",
                )
            else:
                library_detail_var.set("Select files or folders")
                _set_readonly_text(library_report, "")
            library_technical_details_button.configure(
                text="Technical Details", state="disabled"
            )
            return
        library_path_parts = [item.source_filename]
        parent_id = item.parent_id
        while parent_id is not None:
            parent = library_catalog.get(parent_id)
            library_path_parts.append(parent.source_filename)
            parent_id = parent.parent_id
        library_path = "/".join(reversed(library_path_parts))
        library_detail_var.set(
            f"{item.source_filename}\n\n"
            f"Type: {_library_display_type(item)}\n"
            f"Size: {item.source_size_bytes:,} bytes\n"
            f"Library path: {library_path}\n"
            f"Order: {item.sibling_order + 1}\n"
            "Original source remains in its current location."
        )
        if library_technical_details_open:
            _set_readonly_text(library_report, format_library_technical_details(item))
            library_technical_details_button.configure(text="Hide Technical Details")
        else:
            library_technical_details_button.configure(
                text="Technical Details", state="normal"
            )
            _set_readonly_text(
                library_report,
                format_library_selection_summary(item),
            )

    def library_import_can_start() -> bool:
        if not library_operation_controller.busy:
            return True
        message = (
            "The current Manager operation is still in progress. This import was not started; "
            "wait for the current operation to finish and then try again. Your source files "
            "were not changed."
        )
        library_status_var.set(message)
        messagebox.showinfo("Local Library", message, parent=root)
        return False

    def library_import_action() -> None:
        if library_workflow is None:
            messagebox.showerror("Library", library_catalog_error or "Library is unavailable", parent=root)
            return
        selected = filedialog.askopenfilenames(
            title="Add content to Library",
            filetypes=(
                ("Supported source files", ("*.txt", "*.bmp", "*.epub")),
                ("UTF-8 text files", "*.txt"),
                ("237x320 1-bit bitmap files", "*.bmp"),
                ("EPUB files", "*.epub"),
                ("All files", "*"),
            ),
            parent=root,
        )
        if not selected:
            return
        if not library_import_can_start():
            return
        try:
            clear_library_review_for_input_change()
            items = library_workflow.import_files(Path(value) for value in selected)
            refresh_library_view(selected_item_id=items[0].item_id)
            library_status_var.set(
                f"Added {len(items)} file(s) to Local Library; originals unchanged"
            )
            _set_readonly_text(library_report, format_library_selection_summary(items[0]))
        except (LibraryError, OSError) as exc:
            library_status_var.set(f"Library import blocked: {exc}")
            messagebox.showerror("Library import", str(exc), parent=root)

    def library_folder_import_action() -> None:
        if library_workflow is None:
            messagebox.showerror("Library", library_catalog_error or "Library is unavailable", parent=root)
            return
        selected = filedialog.askdirectory(
            title="Recursively import folder hierarchy into Library",
            parent=root,
        )
        if not selected:
            return
        if not library_import_can_start():
            return
        try:
            clear_library_review_for_input_change()
            item = library_workflow.import_folder(Path(selected))
            refresh_library_view(selected_item_id=item.item_id)
            library_status_var.set(
                f"Added {item.source_filename} and its contents to Local Library; originals unchanged"
            )
        except (LibraryError, OSError) as exc:
            library_status_var.set(f"Folder import blocked: {exc}")
            messagebox.showerror("Library folder import", str(exc), parent=root)

    def library_package_import_action() -> None:
        if library_catalog is None:
            messagebox.showerror("Library", library_catalog_error or "Library is unavailable", parent=root)
            return
        selected = filedialog.askdirectory(
            title="Import prepared flat TXT/BMP package",
            parent=root,
        )
        if not selected:
            return
        if not library_import_can_start():
            return
        try:
            clear_library_review_for_input_change()
            item = library_catalog.import_prepared_package(Path(selected))
            refresh_library_view(selected_item_id=item.item_id)
            library_status_var.set(
                f"Imported grouped package {item.source_filename}; original files unchanged; no device access"
            )
            _set_readonly_text(library_report, format_library_selection_summary(item))
        except (LibraryError, OSError) as exc:
            library_status_var.set(f"Prepared package import blocked: {exc}")
            messagebox.showerror("Prepared package import", str(exc), parent=root)

    def library_remove_action() -> None:
        if library_catalog is None or library_workflow is None:
            return
        selected = selected_library_items()
        if not selected:
            return
        removed_ids: set[str] = set()
        for item in selected:
            pending = [item.item_id]
            while pending:
                current = pending.pop()
                if current in removed_ids:
                    continue
                removed_ids.add(current)
                pending.extend(
                    child.item_id for child in library_catalog.children(current)
                )
        display_names = ", ".join(item.source_filename for item in selected[:3])
        if len(selected) > 3:
            display_names += f", and {len(selected) - 3} more"
        if not messagebox.askyesno(
            "Remove from Library",
            (
                f"Remove {display_names} ({len(removed_ids)} Library entries) "
                "from the local Library?\n\nThe original source files will not be "
                "moved or deleted. The device will not be touched."
            ),
            parent=root,
        ):
            return
        clear_library_review_for_input_change()
        library_catalog.remove_many(item.item_id for item in selected)
        refresh_library_view()
        library_status_var.set(
            f"Removed {len(removed_ids)} local Library node(s) only; originals and device unchanged"
        )

    def library_move_action(direction: str) -> None:
        if library_workflow is None:
            return
        item = selected_library_item()
        if item is None:
            return
        try:
            clear_library_review_for_input_change()
            if direction == "up":
                library_workflow.move_up(item.item_id)
            elif direction == "down":
                library_workflow.move_down(item.item_id)
            else:
                raise ValueError("Library move direction is invalid")
            refresh_library_view(selected_item_id=item.item_id)
            library_status_var.set(
                f"Order updated for {item.source_filename}; source files unchanged"
            )
        except (LibraryError, ValueError) as exc:
            library_status_var.set(f"Move blocked: {exc}")

    def library_drag_press(event: Any) -> None:
        row = library_tree.identify_row(event.y)
        selection = tuple(library_tree.selection())
        library_drag_state.update(
            {
                "source": row if row and (row in selection or len(selection) <= 1) else None,
                "start_y": event.y,
                "moved": False,
            }
        )

    def library_drag_motion(event: Any) -> None:
        source = library_drag_state.get("source")
        if source and abs(int(event.y) - int(library_drag_state.get("start_y", 0))) >= 5:
            library_drag_state["moved"] = True

    def library_drag_release(event: Any) -> None:
        source_tree_item = library_drag_state.get("source")
        moved = bool(library_drag_state.get("moved"))
        library_drag_state.update({"source": None, "moved": False})
        if not moved or not source_tree_item or library_catalog is None:
            return
        target_tree_item = library_tree.identify_row(event.y)
        source_id = library_tree_items.get(source_tree_item)
        target_id = library_tree_items.get(target_tree_item)
        if not source_id or not target_id or source_id == target_id:
            return
        try:
            source = library_catalog.get(source_id)
            target = library_catalog.get(target_id)
            if source.parent_id != target.parent_id:
                library_status_var.set("Items can only be reordered within the same folder")
                return
            siblings = list(library_catalog.children(source.parent_id))
            source_index = next(
                index for index, item in enumerate(siblings)
                if item.item_id == source_id
            )
            target_index = next(
                index for index, item in enumerate(siblings)
                if item.item_id == target_id
            )
            bounds = library_tree.bbox(target_tree_item)
            after_target = bool(bounds and event.y > bounds[1] + bounds[3] / 2)
            final_index = target_index + (1 if after_target else 0)
            if source_index < final_index:
                final_index -= 1
            final_index = max(0, min(final_index, len(siblings) - 1))
            clear_library_review_for_input_change()
            library_catalog.move_to(source_id, final_index)
            refresh_library_view(selected_item_id=source_id)
            library_status_var.set(
                f"Order updated for {source.source_filename}; source files unchanged"
            )
        except (LibraryError, ValueError, StopIteration) as exc:
            library_status_var.set(f"Reorder blocked: {exc}")

    def library_rename_destination_action() -> None:
        if library_catalog is None or library_workflow is None:
            return
        item = selected_library_item()
        if (
            item is None
            or item.node_kind != "file"
            or item.package is not None
            or not item.supported
        ):
            library_status_var.set(
                "Change destination is available for supported TXT, BMP, and EPUB files."
            )
            return
        current_name = item.target_folder_name or Path(item.source_filename).stem
        chosen = simpledialog.askstring(
            "Change destination",
            "Destination folder name on the InfoCarry:",
            initialvalue=current_name,
            parent=root,
        )
        if chosen is None:
            return
        chosen = chosen.strip()
        if not chosen:
            messagebox.showerror(
                "Change destination", "Enter a destination folder name.", parent=root
            )
            return
        try:
            settings = ContentWorkspaceSettings(root_name=chosen)
        except ValueError as exc:
            messagebox.showerror("Change destination", str(exc), parent=root)
            return
        revision = library_item_revision(item)
        clear_library_review_for_input_change()
        library_current_revision = revision

        def work(cancelled: threading.Event, progress_callback: Any) -> Any:
            if cancelled.is_set():
                raise LibraryPreparationError(
                    "content preparation was cancelled before it started"
                )
            progress_callback("Preparing the updated destination")
            return library_workflow.prepare_preview(
                item.item_id,
                settings=settings,
                cancel_event=cancelled,
                progress=progress_callback,
            )

        def success(result: Any) -> None:
            nonlocal library_current_preview, library_current_revision
            library_current_preview = result
            library_current_revision = library_item_revision(
                library_catalog.get(item.item_id)
            )
            _set_readonly_text(library_report, format_library_preparation_summary(result))
            library_status_var.set(
                "Destination changed and content prepared again; review the new preview before transfer review"
            )

        start_library_operation(
            "Arrange destination", revision, work, success, validate_revision=False
        )

    def library_prepare_action() -> None:
        nonlocal library_current_preview, library_current_revision
        if library_workflow is None:
            return
        item = selected_library_item()
        if item is None:
            messagebox.showinfo("Prepare", "Select exactly one Library file or folder.", parent=root)
            return
        revision = library_item_revision(item)
        clear_library_review_for_input_change()
        library_current_revision = revision

        def work(cancelled: threading.Event, progress_callback: Any) -> Any:
            if cancelled.is_set():
                raise LibraryPreparationError("preparation was cancelled before it started")
            progress_callback("Preparing content")
            result = library_workflow.prepare_preview(
                item.item_id,
                cancel_event=cancelled,
                progress=progress_callback,
            )
            progress_callback("Preparation complete")
            return result

        def success(result: Any) -> None:
            nonlocal library_current_preview, library_current_revision
            library_current_preview = result
            library_current_revision = library_item_revision(
                library_catalog.get(item.item_id)
            )
            # Detailed compatibility renderer remains available only from
            # Technical Details: format_library_preparation_audit.
            _set_readonly_text(library_report, format_library_preparation_summary(result))
            library_status_var.set(
                f"Prepared {item.source_filename}; review its preview, then review transfer"
            )

        start_library_operation("Prepare", revision, work, success, validate_revision=False)

    def library_preview_action() -> None:
        nonlocal library_current_preview, library_current_revision
        if library_workflow is None:
            return
        item = selected_library_item()
        if item is None:
            messagebox.showinfo("Preview", "Select exactly one Library file or folder.", parent=root)
            return
        revision = library_item_revision(item)
        clear_library_review_for_input_change()
        library_current_revision = revision

        def work(cancelled: threading.Event, progress_callback: Any) -> Any:
            if cancelled.is_set():
                raise LibraryPreparationError("preview was cancelled before it started")
            progress_callback("Preparing current preview")
            result = library_workflow.prepare_preview(
                item.item_id,
                cancel_event=cancelled,
                progress=progress_callback,
            )
            progress_callback("Preview ready")
            return result

        def success(result: Any) -> None:
            nonlocal library_current_preview, library_current_revision
            library_current_preview = result
            library_current_revision = library_item_revision(
                library_catalog.get(item.item_id)
            )
            # The older detailed renderer is diagnostic-only:
            # format_library_device_tree_preview.
            _set_readonly_text(library_report, format_library_preview_summary(result))
            show_library_bitmap_preview(result)
            library_status_var.set("Preview ready; it uses the same current prepared content as Prepare")

        start_library_operation(
            "Preview", revision, work, success, validate_revision=False
        )

    def library_transfer_review_action(selection_mode: str) -> None:
        """Render an offline queue review; this handler has no USB path."""

        nonlocal library_current_plan_report, library_current_revision
        if library_catalog is None:
            return
        selected_item_ids = None
        if selection_mode == SELECTION_SELECTED:
            selected_items = selected_library_items()
            if not selected_items:
                library_status_var.set("Select one or more Library items; no device access")
                return
            selected_item_ids = [item.item_id for item in selected_items]
        else:
            selected_items = []
        selected_for_plan = (
            tuple(library_catalog.items)
            if selection_mode == SELECTION_ALL_READY
            else tuple(selected_items)
        )
        current_selected_item_id = (
            selected_items[0].item_id
            if len(selected_items) == 1
            else None
        )
        selection_revision = (
            all_library_revision()
            if selection_mode == SELECTION_ALL_READY
            else selected_library_selection_revision()
        )
        revision = library_transfer_review_revision(selection_revision)
        review_artifacts = canonical_artifacts_for(
            selected_for_plan,
            current_item_id=current_selected_item_id,
        )
        clear_library_review_for_input_change()
        library_current_revision = revision

        def work(cancelled: threading.Event, progress_callback: Any) -> Any:
            progress_callback("Reviewing prepared content")
            backup = None
            backup_directory = model.state.backup_directory
            if backup_directory is not None and not cancelled.is_set():
                try:
                    backup = verify_fresh_backup(
                        backup_directory,
                        now=None,
                        max_age_seconds=None,
                    )
                except Exception:
                    # Missing/stale evidence is a typed review outcome, not a
                    # worker crash.  The planner will explain what is needed.
                    backup = None
            if cancelled.is_set():
                raise LibraryTransferPlanError("transfer review was cancelled")
            plan = build_library_transfer_queue_plan(
                library_catalog,
                selected_item_ids=selected_item_ids,
                selection_mode=selection_mode,
                backup=backup,
                canonical_artifacts=review_artifacts,
            )
            progress_callback("Transfer review ready")
            return plan, None if backup is None else backup.created_at_utc

        def success(value: Any) -> None:
            nonlocal library_current_plan_report, library_current_revision
            plan, backup_created_at = value
            library_current_plan_report = plan.to_dict()
            library_current_revision = revision
            _set_readonly_text(
                library_report,
                format_library_transfer_review_summary(
                    library_current_plan_report,
                    artifacts=review_artifacts,
                    device_snapshot=device_home_snapshot,
                    backup_created_at=backup_created_at,
                ),
            )
            library_status_var.set(
                "Transfer review complete; no authorization or device change occurred"
            )

        start_library_operation("Review transfer", revision, work, success)

    def library_single_transfer_review_action(
        *,
        continue_to_preflight: bool = False,
        catalog_override: Optional[LibraryCatalog] = None,
        artifact_override: Optional[PreparedContentArtifact] = None,
        transfer_stage: Optional[LibraryFolderPackageStage] = None,
    ) -> None:
        """Show one prepared item's supported shape and review requirements."""

        nonlocal library_current_plan_report, library_current_readiness
        nonlocal library_prepared_operation, library_current_revision

        if library_catalog is None:
            if transfer_stage is not None:
                transfer_stage.cleanup()
            return
        selected_items = selected_library_items()
        if len(selected_items) != 1:
            library_status_var.set("Review one prepared item at a time, or review all prepared items.")
            if transfer_stage is not None:
                transfer_stage.cleanup()
            return
        item = selected_items[0]
        review_catalog = catalog_override or library_catalog
        if review_catalog is None:
            if transfer_stage is not None:
                transfer_stage.cleanup()
            return
        try:
            review_item = review_catalog.get(item.item_id)
        except LibraryError:
            library_status_var.set(
                "The selected content changed before exact transfer review; no device action occurred"
            )
            if transfer_stage is not None:
                transfer_stage.cleanup()
            return
        revision = library_transfer_review_revision(library_item_revision(item))
        review_artifacts = (
            {item.item_id: artifact_override}
            if artifact_override is not None
            else canonical_artifacts_for((review_item,), current_item_id=item.item_id)
        )
        clear_library_review_for_input_change()
        library_current_revision = revision
        transfer_stage_handed_off = {"value": False}

        def work(cancelled: threading.Event, progress_callback: Any) -> Any:
            progress_callback("Reviewing transfer readiness")
            backup = None
            backup_directory = model.state.backup_directory
            if backup_directory is not None and not cancelled.is_set():
                try:
                    backup = verify_fresh_backup(
                        backup_directory,
                        now=None,
                        max_age_seconds=None,
                    )
                except Exception:
                    backup = None
            if cancelled.is_set():
                raise LibraryTransferReadinessError("transfer readiness review was cancelled")
            plan = build_library_transfer_queue_plan(
                review_catalog,
                selected_item_ids=[item.item_id],
                selection_mode=SELECTION_SELECTED,
                backup=backup,
                canonical_artifacts=review_artifacts,
            )
            plan_report = plan.to_dict()
            review = library_execution_facade.review_readiness(plan_report)
            progress_callback("Transfer readiness ready")
            return plan_report, review, None if backup is None else backup.created_at_utc

        def success(value: Any) -> None:
            nonlocal library_current_plan_report, library_current_readiness
            nonlocal library_prepared_operation, library_current_revision
            plan_report, review, backup_created_at = value
            library_current_plan_report = plan_report
            library_current_readiness = review
            library_prepared_operation = None
            library_current_revision = revision
            _set_readonly_text(
                library_report,
                format_library_transfer_review_summary(
                    plan_report,
                    artifacts=review_artifacts,
                    device_snapshot=device_home_snapshot,
                    backup_created_at=backup_created_at,
                    readiness=review,
                ),
            )
            library_status_var.set(
                "Transfer review complete; no authorization or device change occurred"
            )
            library_live_preflight_button.configure(
                state=(
                    "normal"
                    if review.host_profile_eligible
                    and library_execution_facade.can_prepare_live
                    else "disabled"
                )
            )
            if continue_to_preflight:
                if not review.host_profile_eligible:
                    library_status_var.set(
                        "This selection is not ready for the existing guarded device-transfer flow; see the review details"
                    )
                    if transfer_stage is not None:
                        transfer_stage.cleanup()
                    return
                if not library_execution_facade.can_prepare_live:
                    library_status_var.set(
                        "This exact package shape is reviewable, but the guarded live runtime is unavailable; no device checks or transfer occurred"
                    )
                    messagebox.showinfo(
                        "Transfer unavailable",
                        "This exact package shape can be reviewed, but the guarded VNW-V15 runtime is unavailable. No device checks or device change occurred.",
                        parent=root,
                    )
                    if transfer_stage is not None:
                        transfer_stage.cleanup()
                    return
                transfer_stage_handed_off["value"] = transfer_stage is not None
                library_live_preflight_action(
                    continue_to_confirmation=True,
                    catalog_override=review_catalog,
                    transfer_stage=transfer_stage,
                )
            elif transfer_stage is not None:
                transfer_stage.cleanup()

        start_library_operation(
            "Review transfer",
            revision,
            work,
            success,
            on_terminal=(
                None
                if transfer_stage is None
                else lambda: (
                    None
                    if transfer_stage_handed_off["value"]
                    else transfer_stage.cleanup()
                )
            ),
        )

    def library_primary_transfer_review_action() -> None:
        selected = selected_library_items()
        if len(selected) == 1:
            library_single_transfer_review_action()
        elif selected:
            library_transfer_review_action(SELECTION_SELECTED)

    def library_live_preflight_action(
        *,
        continue_to_confirmation: bool = False,
        catalog_override: Optional[LibraryCatalog] = None,
        transfer_stage: Optional[LibraryFolderPackageStage] = None,
    ) -> None:
        """Refresh read-only evidence through the product facade only."""

        nonlocal library_current_plan_report, library_current_readiness, library_prepared_operation
        nonlocal library_current_revision
        preflight_catalog = catalog_override or library_catalog
        if (
            preflight_catalog is None
            or library_current_plan_report is None
            or not library_execution_facade.can_prepare_live
        ):
            library_status_var.set(
                "Live preflight is blocked until the exact supported selection and guarded runtime are ready"
            )
            if transfer_stage is not None:
                transfer_stage.cleanup()
            return
        item = selected_library_item()
        if item is None:
            if transfer_stage is not None:
                transfer_stage.cleanup()
            return
        plan_report = library_current_plan_report
        revision = library_transfer_review_revision(library_item_revision(item))
        clear_library_review_for_input_change()
        library_current_revision = revision
        operation_root = (
            library_execution_facade.evidence_namespace.expanduser().resolve()
            / f"ui-preflight-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
        )

        def work(cancelled: threading.Event, progress_callback: Any) -> Any:
            if cancelled.is_set():
                raise LibraryTransferExecutionError(
                    "read-only preflight was cancelled before it started",
                    stage="preflight",
                )
            progress_callback("Checking current device readiness")
            if transfer_stage is not None:
                transfer_stage.verify_source_bindings()
            prepared = library_execution_facade.refresh_live_preflight(
                plan_report or {},
                catalog=preflight_catalog,
                preflight_report_path=operation_root / "sealed-preflight.json",
                bundle_path=operation_root / "operation-bundle.json",
                audit_location=str(library_execution_facade.evidence_namespace),
                cancelled=cancelled.is_set,
                progress=lambda label, _completed, _total: progress_callback(label),
                store=False,
                operation_stage=transfer_stage,
            )
            progress_callback("Device readiness checked")
            return prepared

        def success(prepared: PreparedLibraryTransferOperation) -> None:
            nonlocal library_prepared_operation, library_current_plan_report
            nonlocal library_current_readiness, library_current_revision
            library_execution_facade.adopt_prepared_operation(prepared)
            library_prepared_operation = prepared
            library_current_plan_report = dict(prepared.plan_report)
            library_current_readiness = prepared.readiness
            library_current_revision = revision
            _set_readonly_text(library_report, format_library_readiness_summary(prepared.readiness))
            library_transfer_once_button.configure(
                state="normal" if library_execution_facade.transfer_actionable else "disabled"
            )
            library_status_var.set(
                "Current device readiness checked; Send to InfoCarry remains guarded for this exact operation"
            )
            if continue_to_confirmation:
                library_transfer_once_action()

        start_library_operation(
            "Check device readiness",
            revision,
            work,
            success,
            on_terminal=(
                None if transfer_stage is None else transfer_stage.cleanup
            ),
        )

    def library_transfer_action() -> None:
        """Plan one selection, then hand exact packages to the guarded facade."""

        if library_catalog is None:
            library_status_var.set("Local Library is unavailable; no device action was started")
            return
        selected = selected_library_items()
        if not selected:
            library_status_var.set("Select files or folders in Local Library first")
            return
        if not isinstance(model.state.inventory, Mapping):
            library_status_var.set(
                "Open a complete Device Library backup before checking destination conflicts"
            )
            messagebox.showinfo(
                "Device Library needed",
                "A complete Device Library snapshot is needed to check the selected destination and conflicts.\n\n"
                "Open or create a complete backup, then try Transfer again. No device change occurred.",
                parent=root,
            )
            return

        selected_ids = tuple(item.item_id for item in selected)
        selected_names = tuple(item.source_filename for item in selected)
        destination = selected_device_destination_path()
        if not destination:
            library_status_var.set(
                "Select one Device Library folder as the transfer destination"
            )
            messagebox.showinfo(
                "Choose a destination",
                "Select exactly one destination folder in Device Library, or clear the selection to use the device root.",
                parent=root,
            )
            return
        selection_revision = selected_library_selection_revision()
        baseline_digest = model.state.source_blob_sha256

        def work(cancelled: threading.Event, progress_callback: Any) -> LibraryDeviceTransferPlan:
            if cancelled.is_set():
                raise LibraryDeviceTransferPlanError("transfer planning was cancelled")
            progress_callback("Checking source files and destination")
            snapshot = _device_library_snapshot_from_inventory(
                model.state.inventory or {}
            )
            plan = build_library_device_transfer_plan(
                library_catalog,
                selected_ids,
                destination,
                snapshot,
                capacity=CapacityEvidence(),
            )
            if cancelled.is_set():
                raise LibraryDeviceTransferPlanError("transfer planning was cancelled")
            return plan

        def planned(plan: LibraryDeviceTransferPlan) -> None:
            current_ids = tuple(
                item.item_id for item in selected_library_items()
            )
            if (
                current_ids != selected_ids
                or selected_device_destination_path() != destination
                or model.state.source_blob_sha256 != baseline_digest
            ):
                library_status_var.set(
                    "Transfer plan discarded because the selection, destination, or Device Library changed"
                )
                return
            shown_names = ", ".join(selected_names[:4])
            if len(selected_names) > 4:
                shown_names += f", and {len(selected_names) - 4} more"
            file_count = sum(node.kind == "file" for node in plan.nodes)
            folder_count = sum(node.kind == "directory" for node in plan.nodes)
            destination_label = _device_path_label(plan.destination_path)
            backup_label = (
                loaded_backup_summary.created_at_utc
                if loaded_backup_summary is not None
                else "no complete backup loaded"
            )
            details = (
                f"Destination: {destination_label}\n"
                f"Selected: {len(selected_ids)} item(s) — {shown_names}\n"
                f"Contents: {file_count} file(s), {folder_count} folder(s)\n"
                f"Selected payload: {plan.source_payload_bytes:,} bytes\n"
                "Conflicts: none in the loaded Device Library snapshot\n"
                "Candidate growth and capacity: unknown; no candidate was built\n"
                f"Backup: {backup_label}; this is not a fresh pre-operation backup\n"
                "Readiness: not evaluated by this offline plan\n"
                "Physical transfer: not attempted; this plan does not authorize a device operation\n"
                "Device auxiliary state: unresolved; this plan does not claim live verification"
            )
            preview_paths = plan.expected_delta.added_paths
            preview_lines = []
            for path in preview_paths[:12]:
                relative_parts = path[len(plan.destination_path) :]
                depth = max(0, len(relative_parts) - 1)
                preview_lines.append(f"  {'  ' * depth}{relative_parts[-1]}")
            if len(preview_paths) > len(preview_lines):
                preview_lines.append(
                    f"  … {len(preview_paths) - len(preview_lines)} more item(s)"
                )
            details += "\n\nExpected additions:\n" + (
                "\n".join(preview_lines) if preview_lines else "  None"
            )
            folder_stage: Optional[LibraryFolderPackageStage] = None
            catalog_override: Optional[LibraryCatalog] = None
            artifact_override: Optional[PreparedContentArtifact] = None
            live_artifact: Optional[PreparedContentArtifact] = None
            if len(selected) == 1:
                if selected[0].node_kind == NODE_FOLDER:
                    folder_stage = prepare_exact_folder_package(
                        library_catalog,
                        selected[0],
                        plan,
                        staging_parent=application_paths().prepared_content_root,
                    )
                    if folder_stage is not None:
                        catalog_override = folder_stage.catalog
                        artifact_override = folder_stage.artifact
                        live_artifact = folder_stage.artifact
                else:
                    live_artifact = _exact_live_package_artifact(selected[0], plan)
            if live_artifact is None:
                details += (
                    "\n\n"
                    f"{file_count} item(s) are ready in the Local Library, but this transfer structure has not yet been enabled for device transfer.\n"
                    "This is a host-only plan; no device checks, candidate, authorization, or transfer occurred."
                )
                library_status_var.set(
                    "Offline transfer plan ready; this selection is not enabled for device transfer"
                )
                messagebox.showinfo("Offline transfer plan", details, parent=root)
                return

            details += (
                "\n\n"
                "This selection matches an existing exact guarded transfer shape. "
                "Continuing through its current readiness and safety checks; this plan itself "
                "does not authorize or perform a device change."
            )
            library_status_var.set(
                "Exact transfer mapping found; continuing through existing guarded readiness checks"
            )
            messagebox.showinfo("Transfer plan", details, parent=root)
            library_single_transfer_review_action(
                continue_to_preflight=True,
                catalog_override=catalog_override,
                artifact_override=artifact_override,
                transfer_stage=folder_stage,
            )

        start_library_operation(
            "Checking transfer plan",
            selection_revision,
            work,
            planned,
            validate_revision=False,
        )

    def library_transfer_once_action() -> None:
        """Confirm simply, then run one guarded transfer away from Tk's main thread."""

        nonlocal library_prepared_operation, library_current_readiness
        nonlocal library_device_change_in_progress

        if library_operation_controller.busy or (worker is not None and worker.is_alive()):
            library_status_var.set(
                "Another manager operation is in progress; Send to InfoCarry remains disabled"
            )
            return
        if (
            library_prepared_operation is None
            or not library_execution_facade.transfer_actionable
        ):
            library_status_var.set(
                "Send to InfoCarry is blocked until the exact reviewed operation is ready"
            )
            library_transfer_once_button.configure(state="disabled")
            return
        binding = library_execution_facade.operation_binding
        intent = library_prepared_operation.operation_intent
        confirmation_phrase = (
            intent.confirmation_phrase
            if intent is not None
            else binding.confirmation_phrase
            if binding is not None
            else None
        )
        target_name = (
            intent.target_folder_name
            if intent is not None
            else binding.target_folder_name
            if binding is not None
            else None
        )
        if confirmation_phrase is None or target_name is None:
            library_status_var.set(
                "Send to InfoCarry is blocked because the exact operation confirmation is unavailable"
            )
            library_transfer_once_button.configure(state="disabled")
            return

        report = library_prepared_operation.readiness.report
        package = report.get("package", {}) if isinstance(report, Mapping) else {}
        children = (
            package.get("ordered_children", [])
            if isinstance(package, Mapping)
            else []
        )
        item_count = len(children) if isinstance(children, list) else 0
        item_label = f"{item_count} item(s)" if item_count else "the selected content"
        confirmed = messagebox.askokcancel(
            "Confirm Transfer",
            (
                f"Transfer {item_label} to /{target_name} on the connected Sony VNW-V15?\n\n"
                "The Manager will perform final safety checks, create a fresh backup, "
                "transfer once, and verify the result on the device.\n\n"
                "After the device-changing transfer begins, it cannot be cancelled or "
                "automatically retried. Keep the InfoCarry connected until verification finishes."
            ),
            parent=root,
        )
        if not confirmed:
            library_status_var.set("Transfer cancelled; no device-changing transaction attempted")
            return
        if library_operation_controller.busy or (worker is not None and worker.is_alive()):
            library_status_var.set(
                "Another manager operation started while confirmation was open; Send to InfoCarry remains disabled"
            )
            return

        execution_plan_report = dict(library_current_plan_report or {})

        def work(
            _cancelled: threading.Event,
            progress_callback: Any,
        ) -> Any:
            sender_progress_seen = False
            progress_callback("Final safety checks — keep the InfoCarry connected")

            def live_progress(
                label: str,
                completed: Optional[int],
                total: Optional[int],
            ) -> None:
                nonlocal sender_progress_seen
                lowered = str(label).casefold()
                if any(
                    marker in lowered
                    for marker in (
                        "write authorized",
                        "header sent",
                        "sending payload",
                        "write complete",
                    )
                ):
                    sender_progress_seen = True
                    owner_label = "Transferring to InfoCarry — do not disconnect"
                elif sender_progress_seen:
                    owner_label = "Verifying transfer — do not disconnect"
                else:
                    owner_label = "Final safety checks — keep the InfoCarry connected"
                progress_callback(owner_label, completed, total)

            return library_execution_facade.execute_once(
                execution_plan_report,
                confirmation_interaction=lambda _review: confirmation_phrase,
                # The confirmation dialog is the cancellation boundary for a
                # device-changing operation. Once this worker starts, no UI
                # cancellation request is forwarded into the sender lifecycle.
                cancelled=lambda: False,
                progress=live_progress,
            )

        def success(result: Any) -> None:
            nonlocal library_prepared_operation, library_current_readiness
            library_prepared_operation = None
            library_current_readiness = None
            _set_readonly_text(
                library_report,
                format_library_transfer_execution_result(result.to_dict()),
            )
            library_transfer_once_button.configure(state="disabled")
            library_status_var.set(
                "Transfer complete — content verified on the InfoCarry"
            )

        def terminal() -> None:
            nonlocal library_device_change_in_progress
            library_device_change_in_progress = False

        library_status_var.set(
            "Transfer confirmed; final safety checks are running"
        )
        library_device_change_in_progress = True
        start_library_operation(
            "Transfer to InfoCarry",
            (),
            work,
            success,
            # The operation is sealed before this point. A harmless UI
            # selection change must not discard a terminal device result.
            validate_revision=False,
            on_terminal=terminal,
        )
        # The user already had an explicit Cancel choice in the confirmation
        # dialog. Once execution starts, disabling cancellation avoids an
        # ambiguous after-sender-start outcome while the Tk event loop remains
        # fully responsive.
        library_cancel_button.configure(state="disabled")

    library_tree.bind("<<TreeviewSelect>>", show_library_selection)
    library_import_button.configure(command=library_import_action)
    library_folder_import_button.configure(command=library_folder_import_action)
    library_package_import_button.configure(command=library_package_import_action)
    library_move_up_button.configure(command=lambda: library_move_action("up"))
    library_move_down_button.configure(command=lambda: library_move_action("down"))
    library_rename_button.configure(command=library_rename_destination_action)
    library_remove_button.configure(command=library_remove_action)
    library_prepare_button.configure(command=library_prepare_action)
    library_preview_button.configure(command=library_preview_action)
    library_selected_queue_button.configure(
        command=library_primary_transfer_review_action
    )
    library_all_queue_button.configure(
        command=lambda: library_transfer_review_action(SELECTION_ALL_READY)
    )
    library_live_preflight_button.configure(command=library_live_preflight_action)
    library_transfer_once_button.configure(command=library_transfer_once_action)
    library_cancel_button.configure(command=library_cancel_action)
    library_technical_details_button.configure(command=library_technical_details_action)
    refresh_library_view()

    def load_conversion_preview() -> None:
        nonlocal conversion_document
        source = converter_source_var.get().strip()
        if not source:
            choose_source(converter_source_var, "Choose UTF-8 text for conversion")
            source = converter_source_var.get().strip()
        if not source:
            return
        try:
            conversion_document = load_utf8_text_document(Path(source))
            _set_readonly_text(converter_report, format_offline_conversion_report(conversion_document))
            converter_export_button.configure(state="normal")
            converter_status_var.set(
                f"Loaded {conversion_document.page_count} logical page(s); no device access"
            )
        except (OfflineConversionError, OSError) as exc:
            conversion_document = None
            converter_export_button.configure(state="disabled")
            converter_status_var.set(str(exc))
            messagebox.showerror("Text conversion", str(exc), parent=root)

    def export_conversion_package() -> None:
        if conversion_document is None:
            return
        parent = filedialog.askdirectory(
            title="Choose parent folder for offline conversion package", parent=root
        )
        if not parent:
            return
        destination = _conversion_destination(Path(parent), conversion_document.source_path)
        try:
            export_text_document(conversion_document, destination)
            converter_status_var.set(f"Offline package written to {destination}; no device access")
            messagebox.showinfo("Conversion complete", f"Created:\n{destination}", parent=root)
        except OfflineConversionError as exc:
            messagebox.showerror("Text conversion", str(exc), parent=root)

    def load_renderer_preview() -> None:
        nonlocal renderer_document
        source = renderer_source_var.get().strip()
        if not source:
            choose_source(renderer_source_var, "Choose UTF-8 text for page preview")
            source = renderer_source_var.get().strip()
        if not source:
            return
        try:
            renderer_document = load_utf8_text_document(Path(source))
            renderer_page_spin.configure(to=max(1, renderer_document.page_count))
            renderer_page_var.set("1")
            _set_readonly_text(renderer_preview, format_offline_page_preview(renderer_document, 1))
            renderer_status_var.set(
                f"{renderer_document.page_count} logical page(s); 240 × 320 BMP rasterization remains gated"
            )
        except (OfflineConversionError, OSError) as exc:
            renderer_document = None
            renderer_status_var.set(str(exc))
            messagebox.showerror("Ebook renderer", str(exc), parent=root)

    def show_renderer_page(_event: Any = None) -> None:
        if renderer_document is None:
            return
        try:
            number = int(renderer_page_var.get())
            _set_readonly_text(renderer_preview, format_offline_page_preview(renderer_document, number))
        except (OfflineConversionError, ValueError) as exc:
            renderer_status_var.set(str(exc))

    converter_browse_button.configure(
        command=lambda: choose_source(converter_source_var, "Choose UTF-8 text for conversion")
    )
    converter_preview_button.configure(command=load_conversion_preview)
    converter_export_button.configure(command=export_conversion_package)
    renderer_browse_button.configure(
        command=lambda: choose_source(renderer_source_var, "Choose UTF-8 text for page preview")
    )
    renderer_load_button.configure(command=load_renderer_preview)
    renderer_page_spin.bind("<Return>", show_renderer_page)
    renderer_page_spin.bind("<<Increment>>", show_renderer_page)
    renderer_page_spin.bind("<<Decrement>>", show_renderer_page)

    def set_busy(busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in (check_button, backup_button, open_button):
            button.configure(state=state)
        if busy:
            for button in (
                library_move_up_button,
                library_move_down_button,
                library_rename_button,
                library_remove_button,
                library_prepare_button,
                library_preview_button,
                library_selected_queue_button,
                library_all_queue_button,
                library_live_preflight_button,
                library_transfer_once_button,
            ):
                button.configure(state="disabled")
        else:
            show_library_selection()
        export_button.configure(state="disabled" if busy or not tree.selection() else "normal")
        if busy:
            replacement_button.configure(state="disabled")
            write_button.configure(state="disabled")
        if busy:
            progress.configure(value=0)

    def selected_device_destination_path() -> Tuple[str, ...]:
        rows_by_offset = {row.record_offset: row for row in model.rows()}
        selected_offsets = [
            tree_items[item_id]
            for item_id in tree.selection()
            if item_id in tree_items
        ]
        if not selected_offsets:
            return ("root",)
        if len(selected_offsets) != 1:
            return ()
        row = rows_by_offset.get(selected_offsets[0])
        if row is None:
            return ()
        path = tuple(part for part in row.path.split("\\") if part)
        if row.kind == "directory":
            return path or ("root",)
        return path[:-1] or ("root",)

    def update_transfer_footer() -> None:
        destination_path = selected_device_destination_path()
        library_destination_summary_var.set(
            "Destination: "
            + (_device_path_label(destination_path) if destination_path else "select one folder")
        )

    def refresh_tree() -> None:
        selected_offsets = {
            tree_items[item_id]
            for item_id in tree.selection()
            if item_id in tree_items
        }
        tree.delete(*tree.get_children())
        tree_items.clear()
        # ``model.rows()`` follows each directory's stored child table order,
        # which is the order shown by the original device manager.  Do not
        # sort by display name here.
        rows = model.rows()
        rows_by_path = {tuple(row.path.split("\\")): row for row in rows}
        search_text = device_search_var.get().strip().casefold()
        visible_paths: set[Tuple[str, ...]] = set()
        if search_text:
            for row in rows:
                if search_text in row.display_name.casefold() or search_text in row.path.casefold():
                    parts = tuple(row.path.split("\\"))
                    visible_paths.update(parts[:depth] for depth in range(1, len(parts) + 1))
        else:
            visible_paths = set(rows_by_path)
        path_items: Dict[Tuple[str, ...], str] = {}
        offset_items: Dict[int, str] = {}
        for row in rows:
            parts = tuple(row.path.split("\\"))
            if parts not in visible_paths:
                continue
            parent_item = ""
            for depth in range(1, len(parts) + 1):
                prefix = parts[:depth]
                if prefix in path_items:
                    parent_item = path_items[prefix]
                    continue
                current = rows_by_path.get(prefix)
                if current is None or prefix not in visible_paths:
                    continue
                size = "" if current.payload_bytes is None else f"{current.payload_bytes:,} B"
                item = tree.insert(
                    parent_item,
                    "end",
                    text=(current.display_name if current.kind == "file" else prefix[-1]),
                    values=(current.kind, size, current.read_state or ""),
                    open=(
                        current.kind == "directory"
                        and (depth <= 1 or bool(search_text))
                    ),
                )
                path_items[prefix] = item
                tree_items[item] = current.record_offset
                offset_items[current.record_offset] = item
                parent_item = item
        visible_selection = [
            offset_items[offset]
            for offset in selected_offsets
            if offset in offset_items
        ]
        if visible_selection:
            tree.selection_set(visible_selection)
            tree.focus(visible_selection[0])
        export_button.configure(state="disabled")
        replacement_button.configure(state="disabled")
        write_button.configure(state="disabled")
        update_transfer_footer()
        show_selection()

    def show_selection(_event: Any = None) -> None:
        nonlocal preview_image
        update_transfer_footer()
        invalidate_library_transfer_review_if_stale()
        selected = [tree_items[item] for item in tree.selection() if item in tree_items]
        export_button.configure(state="normal" if selected and worker is None else "disabled")
        device_delete_status_var.set(
            "Delete is not enabled for this selection."
            if selected
            else "Select device files or folders; Delete is currently unavailable."
        )
        if not selected:
            replacement_button.configure(state="disabled")
            write_button.configure(state="disabled")
            details_var.set("Select a file or folder")
            image_preview.pack_forget()
            preview.pack(fill="both", expand=True)
            _set_readonly_text(preview, "")
            return
        rows_by_offset = {row.record_offset: row for row in model.rows()}
        if len(selected) > 1:
            replacement_button.configure(state="disabled")
            write_button.configure(state="disabled")
            details_var.set(f"{len(selected)} items selected\nDelete is not enabled for this selection")
            image_preview.pack_forget()
            preview.pack(fill="both", expand=True)
            _set_readonly_text(preview, "Multiple items selected. Choose Download selected… to export them.")
            return
        row = rows_by_offset[selected[0]]
        replacement_button.configure(
            state=(
                "normal"
                if worker is None
                and row.kind == "file"
                and row.extension.lower() == "txt"
                else "disabled"
            )
        )
        size = "directory" if row.payload_bytes is None else f"{row.payload_bytes:,} bytes"
        device_path_parts = tuple(row.path.split("\\"))
        details_var.set(
            f"{row.display_name}\n\nType: {row.kind}\nSize: {size}\n"
            f"Path: {_device_path_label(device_path_parts)}\n"
            "Delete is not enabled for this selection."
        )
        if row.kind == "file" and row.extension.lower() == "txt":
            image_preview.pack_forget()
            preview.pack(fill="both", expand=True)
            try:
                _set_readonly_text(preview, model.read_selected_text(row.record_offset))
            except DesktopWorkflowError as exc:
                _set_readonly_text(preview, friendly_error_message(exc))
        elif row.kind == "file" and row.extension.lower() == "bmp":
            preview.pack_forget()
            try:
                bitmap = model.read_selected_bitmap(row.record_offset)
                preview_image = tk.PhotoImage(width=bitmap.width, height=bitmap.height)
                for output_y, row_data in enumerate(bitmap.photo_rows):
                    preview_image.put(row_data, to=(0, output_y))
                image_preview.configure(image=preview_image, text="")
                image_preview.pack(fill="both", expand=True)
            except (DesktopWorkflowError, tk.TclError) as exc:
                image_preview.pack_forget()
                preview.pack(fill="both", expand=True)
                _set_readonly_text(preview, friendly_error_message(exc))
        else:
            image_preview.pack_forget()
            preview.pack(fill="both", expand=True)
            _set_readonly_text(preview, "Select a TXT file to view its decoded read-only preview.")
        status_var.set(model.state.status)

    def check_device_action() -> None:
        if library_operation_controller.busy or (worker is not None and worker.is_alive()):
            device_home_message_var.set("Another operation is in progress. Refresh when it finishes.")
            return

        device_home_message_var.set("Checking the connected Sony device with a read-only query…")

        def work(cancelled: threading.Event, progress_callback: Any) -> DeviceHomeSnapshot:
            if cancelled.is_set():
                return DeviceHomeSnapshot(
                    state="cancelled",
                    heading="Device check cancelled",
                    message="No query was sent. Refresh Device Home when ready.",
                )
            progress_callback("Reading Device Home status")
            if cancelled.is_set():
                return DeviceHomeSnapshot(
                    state="cancelled",
                    heading="Device check cancelled",
                    message="No query was sent. Refresh Device Home when ready.",
                )
            return device_home_service.inspect()

        def success(snapshot: DeviceHomeSnapshot) -> None:
            update_device_home_display(snapshot)
            status_var.set(snapshot.message)

        start_library_operation(
            "Refresh Device Home",
            (),
            work,
            success,
            validate_revision=False,
        )

    def load_backup_action() -> None:
        nonlocal loaded_backup_summary, latest_backup_summary, latest_backup_error
        if library_operation_controller.busy or (worker is not None and worker.is_alive()):
            status_var.set(
                "Another manager operation is in progress; Device Manager remains disabled"
            )
            return
        selected = filedialog.askdirectory(title="Choose complete InfoCarry backup", parent=root)
        if not selected:
            return
        if library_operation_controller.busy or (worker is not None and worker.is_alive()):
            status_var.set(
                "Another manager operation started while the chooser was open; Device Manager remains disabled"
            )
            return
        try:
            selected_directory = Path(selected).expanduser().resolve()
            summary = summarize_complete_backup(selected_directory)
            model.load_backup(selected_directory)
            loaded_backup_summary = summary
            try:
                selected_directory.relative_to(application_data_paths.backup_root.resolve())
            except ValueError:
                pass
            else:
                latest_backup_summary = remember_complete_backup(
                    application_data_paths, selected_directory
                )
                latest_backup_error = None
            refresh_tree()
            update_device_home_display()
            status_var.set(model.state.status)
        except (DesktopWorkflowError, BackupHistoryError, OSError, ValueError) as exc:
            messagebox.showerror("Open backup", friendly_error_message(exc), parent=root)

    def export_action() -> None:
        if library_operation_controller.busy or (worker is not None and worker.is_alive()):
            status_var.set(
                "Another manager operation is in progress; Device Manager remains disabled"
            )
            return
        offsets = [tree_items[item] for item in tree.selection() if item in tree_items]
        if not offsets:
            messagebox.showinfo("Download selected", "Select one or more files or folders first.", parent=root)
            return
        parent = filedialog.askdirectory(title="Choose destination folder", parent=root)
        if not parent:
            return
        if library_operation_controller.busy or (worker is not None and worker.is_alive()):
            status_var.set(
                "Another manager operation started while the chooser was open; Device Manager remains disabled"
            )
            return
        destination = _export_destination(Path(parent))
        try:
            manifest = model.export_selection(destination, offsets)
            summary = manifest["summary"]
            status_var.set(
                f"Downloaded {summary['files']} file(s) to {destination}; device writes disabled"
            )
            messagebox.showinfo(
                "Download complete",
                f"Exported {summary['files']} file(s) to:\n{destination}",
                parent=root,
            )
        except DesktopWorkflowError as exc:
            messagebox.showerror("Download selected", friendly_error_message(exc), parent=root)

    def replacement_preview_action() -> None:
        if library_operation_controller.busy or (worker is not None and worker.is_alive()):
            status_var.set(
                "Another manager operation is in progress; Device Manager remains disabled"
            )
            return
        selected = [tree_items[item] for item in tree.selection() if item in tree_items]
        if len(selected) != 1:
            messagebox.showinfo(
                "Preview replacement",
                "Select exactly one existing TXT record first.",
                parent=root,
            )
            return
        source = filedialog.askopenfilename(
            title="Choose UTF-8 replacement text",
            filetypes=(
                ("UTF-8 text files", "*.txt"),
                ("All files", "*"),
            ),
            parent=root,
        )
        if not source:
            return
        if library_operation_controller.busy or (worker is not None and worker.is_alive()):
            status_var.set(
                "Another manager operation started while the chooser was open; Device Manager remains disabled"
            )
            return
        try:
            model.select_record(selected[0])
            report = model.preview_selected_text_replacement(Path(source))
            image_preview.pack_forget()
            preview.pack(fill="both", expand=True)
            _set_readonly_text(preview, format_text_replacement_preview(report))
            write_button.configure(
                state=(
                    "normal"
                    if worker is None and replacement_write_safety_available()
                    else "disabled"
                )
            )
            status_var.set(model.state.status)
        except DesktopWorkflowError as exc:
            messagebox.showerror(
                "Preview replacement", friendly_error_message(exc), parent=root
            )

    def replacement_write_action() -> None:
        nonlocal worker
        if library_operation_controller.busy or (worker is not None and worker.is_alive()):
            status_var.set(
                "Another manager operation is in progress; Device Manager writes remain disabled"
            )
            return
        if replacement_safety_owner is None:
            write_button.configure(state="disabled")
            status_var.set(
                "Existing-text replacement is disabled fail-closed: the shared "
                "persistent write-safety boundary is unavailable"
            )
            messagebox.showerror(
                "Replace selected text",
                (
                    "Existing-text replacement is disabled fail-closed because its "
                    "application-wide persistent claim/marker/lock boundary is unavailable.\n\n"
                    f"Details: {replacement_safety_configuration_error or 'unknown safety configuration error'}"
                ),
                parent=root,
            )
            return
        if not replacement_write_safety_available():
            write_button.configure(state="disabled")
            status_var.set(
                "Existing-text replacement is blocked: application-wide write safety "
                "requires read-only diagnosis"
            )
            return
        selected = [tree_items[item] for item in tree.selection() if item in tree_items]
        if len(selected) != 1 or model.state.preview_report is None:
            messagebox.showinfo(
                "Replace selected text",
                "Create an offline replacement preview for exactly one existing TXT record first.",
                parent=root,
            )
            return
        report = model.state.preview_report
        workflow_report = report.get("workflow", {})
        preview_offset = workflow_report.get("target_record_offset")
        try:
            preview_offset_value = int(str(preview_offset), 0)
        except (TypeError, ValueError):
            preview_offset_value = None
        if preview_offset_value is None or selected[0] != preview_offset_value:
            messagebox.showinfo(
                "Replace selected text",
                "The selection changed after the preview. Create a new preview for the selected record.",
                parent=root,
            )
            write_button.configure(state="disabled")
            return
        source_text = workflow_report.get("input_path")
        target_path = workflow_report.get("target_path", "the selected TXT record")
        if not isinstance(source_text, str) or not source_text:
            messagebox.showerror(
                "Replace selected text",
                "The preview does not identify its UTF-8 source file; create a new preview.",
                parent=root,
            )
            return
        parent = filedialog.askdirectory(
            title="Choose parent folder for before/after backups", parent=root
        )
        if not parent:
            return
        answer = simpledialog.askstring(
            "Confirm existing-text replacement",
            (
                f"This changes only {target_path}.\n\n"
                "A fresh backup is required before the write, and a complete read-back "
                "will follow it. Do not disconnect the InfoCarry.\n\n"
                "Type exactly: REPLACE INFOCARRY TEXT"
            ),
            parent=root,
        )
        if answer != "REPLACE INFOCARRY TEXT":
            status_var.set("Replacement cancelled; no device write attempted")
            return
        if library_operation_controller.busy:
            status_var.set(
                "A Library operation is in progress; Device Manager writes remain disabled"
            )
            return
        if worker is not None and worker.is_alive():
            return
        backup_parent = Path(parent).expanduser().resolve()
        before_destination = _replacement_backup_destination(backup_parent, "before")
        after_destination = _replacement_backup_destination(backup_parent, "after")
        cancel_event.clear()
        set_busy(True)
        status_var.set(
            f"Starting guarded replacement; backup will be saved at {before_destination}"
        )

        def progress_callback(label: str, completed: int, total: int) -> None:
            events.put(("progress", (label, completed, total)))

        def run_replacement() -> None:
            try:
                from .transport import InfoCarrySession, PyUsbWriteBackend
                from .write_protocol import AuthorizedWriteSender

                with InfoCarrySession.open() as session:

                    def capture(destination: Path, *, cancelled, progress) -> None:
                        archive = RawBackupArchive.create(destination)
                        BackupClient(session).backup(
                            archive, cancelled=cancelled, progress=progress
                        )

                    def send(transaction, authorization, *, cancelled, progress) -> int:
                        sender = AuthorizedWriteSender(
                            PyUsbWriteBackend(session.device), session.endpoints.bulk_out
                        )
                        return sender.send(
                            transaction,
                            authorization,
                            cancelled=cancelled,
                            progress=progress,
                        )

                    result = ExistingTextReplacementWorkflow(
                        capture,
                        send,
                        safety_owner=replacement_safety_owner,
                    ).run(
                        backup_destination=before_destination,
                        post_write_destination=after_destination,
                        preview_report=report,
                        text_path=Path(source_text),
                        cli_write_flag=True,
                        confirmation=answer,
                        cancelled=cancel_event.is_set,
                        progress=progress_callback,
                    )
                events.put(("write_done", result))
            except BaseException as exc:
                events.put(("write_error", exc))

        worker = threading.Thread(
            target=run_replacement,
            name="infocarry-guarded-text-replacement",
            daemon=True,
        )
        worker.start()

    def process_backup_events() -> None:
        nonlocal worker, latest_backup_summary, loaded_backup_summary, latest_backup_error
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == "progress":
                    label, completed, total = value
                    progress.configure(maximum=total, value=completed)
                    status_var.set(label)
                elif kind == "done":
                    worker = None
                    set_busy(False)
                    progress.configure(value=8)
                    destination, summary, history_error = value
                    model.load_backup(destination)
                    latest_backup_summary = summary
                    loaded_backup_summary = summary
                    latest_backup_error = history_error
                    refresh_tree()
                    update_device_home_display()
                    status_var.set(
                        f"Complete read-only backup saved at {destination}; device writes disabled"
                    )
                    messagebox.showinfo(
                        "Backup complete",
                        f"Completed: {summary.created_at_utc}\n\nLocation:\n{destination}\n\n"
                        + (
                            f"The backup is verified and can be opened, but its latest-backup reference could not be saved:\n{history_error}"
                            if history_error
                            else "The backup is verified and ready to browse."
                        ),
                        parent=root,
                    )
                elif kind == "error":
                    worker = None
                    set_busy(False)
                    progress.configure(value=0)
                    status_var.set("Backup failed; device writes disabled")
                    messagebox.showerror("Backup", friendly_error_message(value), parent=root)
                elif kind == "write_done":
                    worker = None
                    set_busy(False)
                    result: ExistingTextReplacementResult = value
                    try:
                        model.load_backup(result.after_backup.directory)
                        model.record_post_write_verification(result.verification)
                        refresh_tree()
                        backup_var.set(f"Backup: {result.after_backup.directory.name}")
                        _set_readonly_text(
                            preview,
                            format_post_write_verification(result.verification.to_dict()),
                        )
                        details_var.set(
                            "Existing text replacement completed\n"
                            f"Completion: 0x{result.completion:04x}\n"
                            "Independent read-back verification passed"
                        )
                        status_var.set(
                            "Replacement completed and read-back verified; no automatic retry"
                        )
                    except DesktopWorkflowError as exc:
                        status_var.set(friendly_error_message(exc))
                        messagebox.showerror(
                            "Read-back verification", friendly_error_message(exc), parent=root
                        )
                elif kind == "write_error":
                    worker = None
                    set_busy(False)
                    progress.configure(value=0)
                    status_var.set(friendly_error_message(value))
                    messagebox.showerror(
                        "Replace selected text", friendly_error_message(value), parent=root
                    )
        except queue.Empty:
            pass
        if root.winfo_exists():
            root.after(100, process_backup_events)

    def process_library_callbacks() -> None:
        """Drain worker results on Tk's main thread only."""

        if not root.winfo_exists():
            return
        try:
            while True:
                callback = library_callbacks.get_nowait()
                callback()
        except queue.Empty:
            pass
        if root.winfo_exists():
            root.after(50, process_library_callbacks)

    def backup_action() -> None:
        nonlocal worker
        if library_operation_controller.busy:
            status_var.set(
                "A Library operation is in progress; Device Manager backup remains disabled"
            )
            return
        if worker is not None and worker.is_alive():
            return
        if library_operation_controller.busy:
            status_var.set(
                "A Library operation is in progress; Device Manager backup remains disabled"
            )
            return
        try:
            application_data_paths.backup_root.mkdir(parents=True, exist_ok=True)
            destination = _backup_destination(application_data_paths.backup_root)
        except OSError as exc:
            messagebox.showerror(
                "Back Up Now",
                f"InfoCarry could not prepare its backup folder:\n{application_data_paths.backup_root}\n\n{exc}",
                parent=root,
            )
            return
        cancel_event.clear()
        set_busy(True)
        status_var.set(f"Starting read-only backup at {destination}")

        def progress_callback(label: str, completed: int, total: int) -> None:
            events.put(("progress", (label, completed, total)))

        def run_backup() -> None:
            archive = None
            backup_completed = False
            try:
                archive = RawBackupArchive.create(destination)
                from .transport import InfoCarrySession

                with InfoCarrySession.open() as session:
                    BackupClient(session).backup(
                        archive,
                        cancelled=cancel_event.is_set,
                        progress=progress_callback,
                    )
                backup_completed = True
                summary = summarize_complete_backup(destination)
                history_error = None
                try:
                    remember_complete_backup(application_data_paths, destination)
                except BackupHistoryError as exc:
                    history_error = str(exc)
                events.put(("done", (destination, summary, history_error)))
            except BaseException as exc:
                if archive is not None and not backup_completed:
                    try:
                        archive.mark_incomplete(exc)
                    except Exception:
                        pass
                events.put(("error", exc))

        worker = threading.Thread(target=run_backup, name="infocarry-read-only-backup", daemon=True)
        worker.start()

    def close_action() -> None:
        library_busy = library_operation_controller.busy
        if library_device_change_in_progress:
            messagebox.showinfo(
                "Transfer in progress",
                "The transfer is still running. Keep the InfoCarry connected and leave "
                "this window open until the Manager reports a terminal result.",
                parent=root,
            )
            return
        if (worker is not None and worker.is_alive()) or library_busy:
            if not messagebox.askyesno(
                "Operation in progress",
                "Stop the operation and close the window? Any incomplete archive will be preserved; a started write will not be retried.",
                parent=root,
            ):
                return
            cancel_event.set()
            if library_busy:
                library_operation_controller.close()
        else:
            library_operation_controller.close()
        root.destroy()

    tree.bind("<<TreeviewSelect>>", show_selection)
    device_search_entry.bind("<KeyRelease>", lambda _event: refresh_tree())
    check_button.configure(command=check_device_action)
    backup_button.configure(command=backup_action)
    open_button.configure(command=load_backup_action)
    export_button.configure(command=export_action)
    technical_details_button.configure(command=show_technical_details_action)
    show_backup_button.configure(command=show_backup_location_action)
    replacement_button.configure(command=replacement_preview_action)
    write_button.configure(command=replacement_write_action)
    library_search_entry.bind("<KeyRelease>", lambda _event: refresh_library_view())
    library_tree.bind("<ButtonPress-1>", library_drag_press, add="+")
    library_tree.bind("<B1-Motion>", library_drag_motion, add="+")
    library_tree.bind("<ButtonRelease-1>", library_drag_release, add="+")
    library_remove_selection_button.configure(command=library_remove_action)
    library_reorder_up_button.configure(command=lambda: library_move_action("up"))
    library_reorder_down_button.configure(command=lambda: library_move_action("down"))
    library_details_toggle_button.configure(command=show_library_inspector)
    library_technical_details_action_button.configure(
        command=library_technical_details_action
    )
    device_details_button.configure(command=toggle_device_inspector)
    library_transfer_button.configure(command=library_transfer_action)

    def show_help_action() -> None:
        messagebox.showinfo(
            "InfoCarry Manager Help",
            "Local Library references your existing files; Remove only removes a Library entry.\n\n"
            "Select local files or folders, choose a destination folder in Device Library, "
            "then choose Transfer. Existing items are never overwritten. A transfer may be "
            "planned offline even when that selection is not enabled for device transfer.\n\n"
            "Back Up saves a read-only snapshot. Backup is not Restore, and Restore is unavailable. "
            "Delete is not enabled for general selections yet.",
            parent=root,
        )

    def show_settings_action() -> None:
        messagebox.showinfo(
            "Settings",
            f"Runtime: {runtime.description}\n\n"
            "The Local Library catalog is stored in the Manager's per-user application data.\n"
            "Device-changing actions remain behind the existing VNW-V15 safety checks.\n"
            "Restore and general-purpose deletion are unavailable.",
            parent=root,
        )

    menu_bar = tk.Menu(root)
    file_menu = tk.Menu(menu_bar, tearoff=False)
    local_import_state = (
        "normal" if library_catalog is not None and library_workflow is not None else "disabled"
    )
    file_menu.add_command(
        label="Add Files…", command=library_import_action, state=local_import_state
    )
    file_menu.add_command(
        label="Add Folder…",
        command=library_folder_import_action,
        state=local_import_state,
    )
    file_menu.add_separator()
    file_menu.add_command(label="Settings…", command=show_settings_action)
    file_menu.add_separator()
    file_menu.add_command(label="Quit", command=close_action)
    menu_bar.add_cascade(label="File", menu=file_menu)

    device_menu = tk.Menu(menu_bar, tearoff=False)
    device_menu.add_command(label="Refresh", command=check_device_action)
    device_menu.add_command(label="Back Up…", command=backup_action)
    device_menu.add_command(label="Open Backup…", command=load_backup_action)
    device_menu.add_command(
        label="View Backup Location…", command=show_backup_location_action
    )
    device_menu.add_command(label="Export Selected…", command=export_action)
    device_menu.add_separator()
    device_menu.add_command(label="Delete…", state="disabled")
    menu_bar.add_cascade(label="Device", menu=device_menu)

    view_menu = tk.Menu(menu_bar, tearoff=False)
    view_menu.add_command(
        label="Local Library Details", command=show_library_inspector
    )
    view_menu.add_command(label="Device Library Details", command=toggle_device_inspector)
    view_menu.add_command(
        label="Technical Details…", command=show_technical_details_action
    )
    menu_bar.add_cascade(label="View", menu=view_menu)

    help_menu = tk.Menu(menu_bar, tearoff=False)
    help_menu.add_command(label="InfoCarry Manager Help…", command=show_help_action)
    help_menu.add_command(
        label="About InfoCarry Manager…",
        command=lambda: messagebox.showinfo(
            "About InfoCarry Manager",
            "Sony InfoCarry Manager\nA read-first local and device library manager.",
            parent=root,
        ),
    )
    menu_bar.add_cascade(label="Help", menu=help_menu)
    root.configure(menu=menu_bar)

    if loaded_backup_summary is not None:
        refresh_tree()
    update_device_home_display()
    root.protocol("WM_DELETE_WINDOW", close_action)
    root.after(100, process_backup_events)
    root.after(50, process_library_callbacks)
    root.after(1000, process_library_review_freshness)
    root.mainloop()


__all__ = [
    "format_library_device_tree_preview",
    "format_library_host_only_terminal_state",
    "format_library_operation_failure",
    "format_library_preparation_audit",
    "format_library_preparation_summary",
    "format_library_preview_summary",
    "format_library_readiness_summary",
    "format_library_selection_summary",
    "format_library_technical_details",
    "format_library_transfer_review_summary",
    "format_library_transfer_readiness",
    "format_library_transfer_execution_result",
    "format_prepared_package_readiness_preview",
    "format_text_replacement_preview",
    "format_post_write_verification",
    "friendly_error_message",
    "launch_ttk_desktop",
]
