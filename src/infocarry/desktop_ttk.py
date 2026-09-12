"""ttk-based read-only Device Manager view."""

from __future__ import annotations

from datetime import datetime
import errno
import json
import queue
from pathlib import Path
import threading
from typing import Any, Dict, Optional, Sequence, Tuple

from .backup import BackupClient, RawBackupArchive
from .backup_format import BackupFormatError
from .capture import CaptureError
from .desktop import DesktopWorkflowError, DesktopWorkflowModel
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
    NODE_FOLDER,
    NODE_PREPARED_PACKAGE,
    LibraryCatalog,
    LibraryCatalogError,
    LibraryError,
)
from .library_prepare import LibraryPreparationError
from .library_workflow import LibraryWorkflowService
from .library_transfer_plan import (
    LibraryTransferPlanError,
    SELECTION_ALL_READY,
    SELECTION_SELECTED,
    build_library_transfer_queue_plan,
)
from .library_transfer_readiness import (
    LibraryTransferReadinessError,
    build_library_transfer_readiness,
)
from .library_transfer_execution import (
    LibraryTransferExecutionError,
    LibraryTransferExecutionFacade,
    PreparedLibraryTransferOperation,
)
from .runtime import DesktopRuntimeError, check_desktop_runtime
from .write_gate import verify_fresh_backup


# The Library review is designed for an ordinary non-maximized macOS window.
# Keep this geometry explicit so visual checks and future layout changes share
# one documented boundary.
LIBRARY_MINIMUM_GEOMETRY = (980, 680)
LIBRARY_DEFAULT_GEOMETRY = (1120, 760)
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
    """Render the Library Prepare result without implying device access."""

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
    """Render one exact ordered host/offline device-tree preview."""

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
    """Render the Library queue review without implying transfer capability."""

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
    """Render the narrow Experimental review without exposing a send action."""

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
    """Render the terminal result without treating submission as success."""

    if not isinstance(report, dict):
        raise ValueError("Library transfer execution result must be a mapping")
    verification = report.get("verification", {})
    accounting = report.get("accounting", {})
    lines = [
        "GUARDED LIBRARY TRANSFER RESULT",
        "",
        f"  State: {report.get('state', 'unknown')}",
        f"  Completion: {report.get('completion', 'unknown')}",
        f"  Post-write backup verified: {'yes' if report.get('post_backup_verified') else 'no'}",
        f"  Independent read-back verified: {'yes' if report.get('independent_readback_verified') else 'no'}",
        f"  Sender calls: {accounting.get('logical_sender_calls', 'unknown')}",
        f"  Automatic retry: {'yes' if report.get('automatic_retry_allowed') else 'no'}",
        f"  Verification details: {verification.get('shared_path_count', 'unknown')} shared paths checked",
        "",
        "Terminal product status: Transfer verified only after the complete post-backup and independent read-back checks.",
    ]
    return "\n".join(lines)


def format_library_transfer_readiness(report: Dict[str, Any]) -> str:
    """Render the normal-product Experimental readiness review.

    The readiness model is reusable host/profile eligibility, so this surface
    intentionally omits historical operation phrases, candidate identity, and
    any action that could authorize a device change.
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
            "Experimental profile eligible — live transfer not enabled in this build"
            if host_eligible
            else "Blocked — selected package is outside the Experimental profile"
        )
    conflicts = destination.get("conflicts", [])
    if not isinstance(conflicts, list):
        raise ValueError("Library transfer readiness conflicts are malformed")
    children = package.get("ordered_children", [])
    if not isinstance(children, list):
        raise ValueError("Library transfer readiness children are malformed")

    lines = [
        "EXPERIMENTAL TRANSFER READINESS — host review only; no device change occurred",
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

    from .usb_access import DeviceAccessError, describe_device, find_devices

    root = tk.Tk()
    root.title("Sony InfoCarry Manager")
    root.geometry(f"{LIBRARY_DEFAULT_GEOMETRY[0]}x{LIBRARY_DEFAULT_GEOMETRY[1]}")
    root.minsize(*LIBRARY_MINIMUM_GEOMETRY)
    model = DesktopWorkflowModel()
    library_execution_facade = execution_facade or LibraryTransferExecutionFacade()
    events: "queue.Queue[Tuple[str, Any]]" = queue.Queue()
    cancel_event = threading.Event()
    worker: Optional[threading.Thread] = None
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
    details_var = tk.StringVar(value="Select a file or folder")
    tree_items: Dict[str, int] = {}

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=8, pady=(8, 0))
    library_tab = ttk.Frame(notebook, padding=10)
    device_tab = ttk.Frame(notebook)
    text_converter_tab = ttk.Frame(notebook, padding=12)
    ebook_renderer_tab = ttk.Frame(notebook, padding=12)
    settings_tab = ttk.Frame(notebook, padding=12)
    notebook.add(library_tab, text="Library")
    notebook.add(device_tab, text="Device Manager")
    notebook.add(text_converter_tab, text="Text Converter")
    notebook.add(ebook_renderer_tab, text="Ebook Renderer")
    notebook.add(settings_tab, text="Settings & Help")

    library_status_var = tk.StringVar(
        value=(
            f"Library unavailable: {library_catalog_error}"
            if library_catalog_error
            else (
                "Import TXT/BMP files or a folder hierarchy. External drag-and-drop "
                "is unavailable without the optional TkDND adapter; no device operation occurs."
            )
        )
    )
    library_detail_var = tk.StringVar(value="Select a Library item")
    library_tree_items: Dict[str, str] = {}
    library_current_plan_report: Optional[Dict[str, Any]] = None
    library_current_readiness: Any = None
    library_prepared_operation: Optional[PreparedLibraryTransferOperation] = None
    ttk.Label(
        library_tab,
        text="Local Library",
        font=("TkDefaultFont", 14, "bold"),
    ).pack(anchor="w", pady=(0, 4))
    library_toolbar = ttk.Frame(library_tab)
    library_toolbar.pack(fill="x", pady=(0, 8))
    library_toolbar.columnconfigure(1, weight=1)
    library_import_group = ttk.LabelFrame(library_toolbar, text="Select / arrange")
    library_import_group.grid(row=0, column=0, sticky="w")
    library_review_group = ttk.LabelFrame(library_toolbar, text="Prepare / preview")
    library_review_group.grid(row=1, column=0, sticky="w", pady=(4, 0))
    library_experimental_group = ttk.LabelFrame(
        library_toolbar, text="Experimental transfer readiness"
    )
    library_experimental_group.grid(
        row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0)
    )
    library_experimental_group.columnconfigure(4, weight=1)
    library_import_button = ttk.Button(library_import_group, text="Import files…")
    library_folder_import_button = ttk.Button(
        library_import_group, text="Import folder…"
    )
    library_move_up_button = ttk.Button(
        library_import_group, text="Move up", state="disabled"
    )
    library_move_down_button = ttk.Button(
        library_import_group, text="Move down", state="disabled"
    )
    library_package_import_button = ttk.Button(
        library_experimental_group, text="Import prepared package…"
    )
    library_remove_button = ttk.Button(
        library_import_group, text="Remove from Library", state="disabled"
    )
    library_prepare_button = ttk.Button(
        library_review_group, text="Prepare", state="disabled"
    )
    library_preview_button = ttk.Button(
        library_review_group, text="Preview device tree", state="disabled"
    )
    library_selected_queue_button = ttk.Button(
        library_review_group, text="Review selected (offline)…", state="disabled"
    )
    library_all_queue_button = ttk.Button(
        library_review_group, text="Review all ready (offline)…", state="disabled"
    )
    library_experimental_button = ttk.Button(
        library_experimental_group,
        text="Review transfer…",
        state="disabled",
    )
    library_live_preflight_button = ttk.Button(
        library_experimental_group,
        text="Refresh live preflight…",
        state="disabled",
        takefocus=False,
    )
    library_transfer_once_button = ttk.Button(
        library_experimental_group,
        text="Transfer once",
        state="disabled",
        takefocus=False,
    )
    for button in (
        library_import_button,
        library_folder_import_button,
        library_move_up_button,
        library_move_down_button,
        library_remove_button,
    ):
        button.pack(side="left", padx=3, pady=3)
    for button in (
        library_prepare_button,
        library_preview_button,
        library_selected_queue_button,
        library_all_queue_button,
    ):
        button.pack(side="left", padx=3, pady=3)
    library_package_import_button.grid(row=0, column=0, sticky="w", padx=3, pady=3)
    library_experimental_button.grid(row=0, column=1, sticky="w", padx=3, pady=3)
    library_live_preflight_button.grid(row=0, column=2, sticky="w", padx=3, pady=3)
    library_transfer_once_button.grid(row=0, column=3, sticky="w", padx=3, pady=3)
    ttk.Label(
        library_experimental_group,
        text="Live preflight and Transfer once require a fresh separately authorized VNW-V15 operation.",
        foreground="#6b4f00",
        anchor="w",
    ).grid(row=0, column=4, sticky="ew", padx=(8, 8), pady=3)
    library_safety_notice = ttk.Label(
        library_toolbar,
        text=(
            "External file/folder drag-and-drop: unavailable without TkDND; use the "
            "chooser buttons. All preparation and nested previews are host/offline "
            "only. Review transfer explains the Experimental VNW-V15 profile; the "
            "live path requires a fresh separately authorized operation; VNW-V10 "
            "remains unsupported."
        ),
        foreground="#6b4f00",
        anchor="w",
        justify="left",
        wraplength=900,
    )
    library_safety_notice.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(5, 0))

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
    )
    library_tree.grid(row=0, column=0, sticky="nsew")
    library_tree_scroll.grid(row=0, column=1, sticky="ns")
    library_tree_horizontal_scroll.grid(row=1, column=0, sticky="ew")
    library_detail_frame.columnconfigure(0, weight=1)
    library_detail_frame.rowconfigure(2, weight=1)
    library_detail_heading = ttk.Label(library_detail_frame, text="Library selection")
    library_detail_heading.grid(row=0, column=0, sticky="w")
    library_detail_label = ttk.Label(
        library_detail_frame,
        textvariable=library_detail_var,
        wraplength=420,
        justify="left",
    )
    library_detail_label.grid(row=1, column=0, sticky="ew", pady=(2, 10))
    library_report_frame = ttk.Frame(library_detail_frame)
    library_report_frame.grid(row=2, column=0, sticky="nsew")
    library_report_frame.columnconfigure(0, weight=1)
    library_report_frame.rowconfigure(0, weight=1)
    library_report = tk.Text(
        library_report_frame, height=20, width=48, wrap="none", undo=False
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
    library_report.grid(row=0, column=0, sticky="nsew")
    library_report_vertical_scroll.grid(row=0, column=1, sticky="ns")
    library_report_horizontal_scroll.grid(row=1, column=0, sticky="ew")
    library_report.configure(state="disabled")

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

    toolbar = ttk.Frame(device_tab, padding=(10, 10, 10, 6))
    toolbar.pack(fill="x")
    ttk.Label(toolbar, text="Sony InfoCarry", font=("TkDefaultFont", 14, "bold")).pack(
        side="left", padx=(0, 16)
    )
    check_button = ttk.Button(toolbar, text="Check device")
    backup_button = ttk.Button(toolbar, text="New backup…")
    open_button = ttk.Button(toolbar, text="Open backup…")
    export_button = ttk.Button(toolbar, text="Download selected…", state="disabled")
    replacement_button = ttk.Button(
        toolbar, text="Preview replacement…", state="disabled"
    )
    write_button = ttk.Button(
        toolbar, text="Replace selected text…", state="disabled"
    )
    for button in (
        check_button,
        backup_button,
        open_button,
        export_button,
        replacement_button,
        write_button,
    ):
        button.pack(side="left", padx=3)
    ttk.Label(toolbar, textvariable=backup_var, anchor="e").pack(
        side="right", fill="x", expand=True, padx=(12, 0)
    )

    content = ttk.Panedwindow(device_tab, orient="horizontal")
    content.pack(fill="both", expand=True, padx=10, pady=(0, 8))
    browser_frame = ttk.Frame(content, padding=6)
    detail_frame = ttk.Frame(content, padding=10)
    content.add(browser_frame, weight=3)
    content.add(detail_frame, weight=2)

    ttk.Label(browser_frame, text="InfoCarry contents").pack(anchor="w", pady=(0, 5))
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
    tree.configure(yscrollcommand=tree_scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    tree_scroll.pack(side="right", fill="y")

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
        "The exact proven Library TXT/BMP/TXT package is Experimental: the normal UI can reach a guarded one-shot review only after a fresh separately authorized VNW-V15 preflight; this build has no physical ttk validation.\n"
        "Unsupported package shapes remain unavailable; recovery is unresolved and automatic write retry is never used.\n"
        "Text Converter and Ebook Renderer are offline-only in this milestone.\n\n"
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
        open_ids = {
            item_id
            for tree_item, item_id in library_tree_items.items()
            if library_tree.item(tree_item, "open")
        }
        library_tree.delete(*library_tree.get_children())
        library_tree_items.clear()
        if library_catalog is None or library_workflow is None:
            library_import_button.configure(state="disabled")
            library_folder_import_button.configure(state="disabled")
            library_package_import_button.configure(state="disabled")
            library_move_up_button.configure(state="disabled")
            library_move_down_button.configure(state="disabled")
            library_remove_button.configure(state="disabled")
            library_prepare_button.configure(state="disabled")
            library_preview_button.configure(state="disabled")
            library_selected_queue_button.configure(state="disabled")
            library_all_queue_button.configure(state="disabled")
            library_experimental_button.configure(state="disabled")
            library_live_preflight_button.configure(state="disabled")
            library_transfer_once_button.configure(state="disabled")
            return
        library_import_button.configure(state="normal")
        library_folder_import_button.configure(state="normal")
        library_package_import_button.configure(state="normal")
        library_experimental_button.configure(state="disabled")
        library_live_preflight_button.configure(state="disabled")
        library_transfer_once_button.configure(state="disabled")

        node_tree_items: dict[str, str] = {}

        def insert_nodes(parent_id: Optional[str], parent_tree_item: str) -> None:
            for item in library_catalog.children(parent_id):
                node_type = item.node_kind
                if item.package is not None and item.target_folder_name:
                    node_type = _library_package_shape(item.package)
                size = "" if item.node_kind == NODE_FOLDER else f"{item.source_size_bytes:,} B"
                tree_item = library_tree.insert(
                    parent_tree_item,
                    "end",
                    text=item.source_filename,
                    values=(node_type, item.state, size, item.source_path),
                    open=(
                        item.item_id in open_ids
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

    def show_library_selection(_event: Any = None) -> None:
        nonlocal library_current_plan_report, library_current_readiness, library_prepared_operation
        item = selected_library_item()
        enabled = item is not None and library_catalog is not None
        has_selection = bool(library_tree.selection()) and library_catalog is not None
        hierarchy_enabled = enabled and item.node_kind != NODE_PREPARED_PACKAGE
        selected_items = selected_library_items()
        legacy_selection = bool(selected_items) and all(
            selected.package is not None for selected in selected_items
        )
        legacy_items_available = bool(
            library_catalog is not None
            and any(value.package is not None for value in library_catalog.items)
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
        library_prepare_button.configure(state="normal" if hierarchy_enabled else "disabled")
        library_preview_button.configure(state="normal" if hierarchy_enabled else "disabled")
        library_selected_queue_button.configure(
            state="normal" if has_selection and legacy_selection else "disabled"
        )
        library_all_queue_button.configure(
            state="normal" if legacy_items_available else "disabled"
        )
        library_experimental_button.configure(
            state="normal" if enabled and item.package is not None else "disabled"
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
        if item is None:
            library_detail_var.set("Select a Library item")
            _set_readonly_text(library_report, "")
            return
        target = "not prepared"
        if item.package is not None and item.target_folder_name:
            target = (
                f"root\\{item.target_folder_name}"
                f" ({len(item.package.children)} ordered children)"
            )
        elif item.target_folder_name and item.target_child_name:
            target = f"root\\{item.target_folder_name}\\{item.target_child_name}"
        library_detail_var.set(
            f"{item.source_filename}\n\n"
            f"State: {item.state}\n"
            f"Type: {item.node_kind}\n"
            f"Sibling order: {item.sibling_order}\n"
            f"Source: {item.source_path}\n"
            f"SHA-256: {item.source_sha256}\n"
            f"Target: {target}"
        )
        _set_readonly_text(
            library_report,
            json.dumps(item.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        )

    def library_import_action() -> None:
        if library_workflow is None:
            messagebox.showerror("Library", library_catalog_error or "Library is unavailable", parent=root)
            return
        selected = filedialog.askopenfilenames(
            title="Import TXT/BMP files into Library",
            filetypes=(
                ("Supported TXT/BMP files", ("*.txt", "*.bmp")),
                ("UTF-8 text files", "*.txt"),
                ("237x320 1-bit bitmap files", "*.bmp"),
                ("All files", "*"),
            ),
            parent=root,
        )
        if not selected:
            return
        try:
            items = library_workflow.import_files(Path(value) for value in selected)
            refresh_library_view(selected_item_id=items[0].item_id)
            library_status_var.set(
                f"Imported {len(items)} file(s) in chooser order; originals unchanged; "
                "external drag-and-drop unavailable without TkDND; no device access"
            )
            _set_readonly_text(
                library_report,
                json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=2, sort_keys=True),
            )
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
        try:
            item = library_workflow.import_folder(Path(selected))
            refresh_library_view(selected_item_id=item.item_id)
            library_status_var.set(
                f"Imported folder hierarchy {item.source_filename} in deterministic recorded order; "
                "originals unchanged; no device access"
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
        try:
            item = library_catalog.import_prepared_package(Path(selected))
            refresh_library_view(selected_item_id=item.item_id)
            library_status_var.set(
                f"Imported grouped package {item.source_filename}; original files unchanged; no device access"
            )
            _set_readonly_text(
                library_report,
                json.dumps(item.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
            )
        except (LibraryError, OSError) as exc:
            library_status_var.set(f"Prepared package import blocked: {exc}")
            messagebox.showerror("Prepared package import", str(exc), parent=root)

    def library_remove_action() -> None:
        if library_catalog is None or library_workflow is None:
            return
        item = selected_library_item()
        if item is None:
            return
        def subtree_size(item_id: str) -> int:
            return 1 + sum(
                subtree_size(child.item_id) for child in library_catalog.children(item_id)
            )

        removed_count = subtree_size(item.item_id)
        if not messagebox.askyesno(
            "Remove from Library",
            (
                f"Remove {item.source_filename} and {removed_count - 1} descendant(s) "
                "from the local Library?\n\nThe original source files will not be "
                "moved or deleted. The device will not be touched."
            ),
            parent=root,
        ):
            return
        library_workflow.remove(item.item_id)
        refresh_library_view()
        library_status_var.set(
            f"Removed {removed_count} local Library node(s) only; originals and device unchanged"
        )

    def library_move_action(direction: str) -> None:
        if library_workflow is None:
            return
        item = selected_library_item()
        if item is None:
            return
        try:
            if direction == "up":
                library_workflow.move_up(item.item_id)
            elif direction == "down":
                library_workflow.move_down(item.item_id)
            else:
                raise ValueError("Library move direction is invalid")
            refresh_library_view(selected_item_id=item.item_id)
            library_status_var.set(
                f"Moved {item.source_filename} {direction} within its siblings; no device access"
            )
        except (LibraryError, ValueError) as exc:
            library_status_var.set(f"Move blocked: {exc}")

    def library_prepare_action() -> None:
        if library_workflow is None:
            return
        item = selected_library_item()
        if item is None:
            messagebox.showinfo("Prepare", "Select exactly one Library file or folder.", parent=root)
            return
        try:
            result = library_workflow.prepare_preview(item.item_id)
            _set_readonly_text(
                library_report,
                format_library_preparation_audit(result.prepared.to_dict()),
            )
            library_status_var.set(
                f"Prepared {item.source_filename} hierarchy offline; choose Preview device tree "
                "to inspect exact destinations; no device access"
            )
        except (LibraryPreparationError, LibraryError, ValueError, OSError) as exc:
            library_status_var.set(f"Prepare blocked; no device access: {exc}")
            _set_readonly_text(
                library_report,
                "OFFLINE LIBRARY PREPARE — blocked; no device change occurred\n\n" + str(exc),
            )
            messagebox.showerror("Offline Prepare", str(exc), parent=root)

    def library_preview_action() -> None:
        if library_workflow is None:
            return
        item = selected_library_item()
        if item is None:
            messagebox.showinfo("Preview", "Select exactly one Library file or folder.", parent=root)
            return
        try:
            result = library_workflow.prepare_preview(item.item_id)
            _set_readonly_text(
                library_report,
                format_library_device_tree_preview(
                    result.to_dict()["device_tree_preview"]
                ),
            )
            library_status_var.set(
                "Exact ordered device-tree preview displayed; nested capability is host/offline "
                "only and not live-enabled"
            )
        except (LibraryPreparationError, LibraryError, ValueError, OSError) as exc:
            library_status_var.set(f"Preview blocked; no device access: {exc}")
            _set_readonly_text(
                library_report,
                "PREPARED DEVICE-TREE PREVIEW — blocked; no device change occurred\n\n" + str(exc),
            )
            messagebox.showerror("Offline Preview", str(exc), parent=root)

    def library_transfer_review_action(selection_mode: str) -> None:
        """Render an offline queue review; this handler has no USB path."""

        if library_catalog is None:
            return
        selected_item_ids = None
        if selection_mode == SELECTION_SELECTED:
            selected_items = selected_library_items()
            if not selected_items:
                library_status_var.set("Select one or more Library items; no device access")
                return
            selected_item_ids = [item.item_id for item in selected_items]
        backup = None
        backup_directory = model.state.backup_directory
        if backup_directory is not None:
            try:
                backup = verify_fresh_backup(
                    backup_directory,
                    now=None,
                    max_age_seconds=None,
                )
            except Exception as exc:
                library_status_var.set(
                    f"Offline queue review has no verified backup: {exc}"
                )
        try:
            plan = build_library_transfer_queue_plan(
                library_catalog,
                selected_item_ids=selected_item_ids,
                selection_mode=selection_mode,
                backup=backup,
            )
        except LibraryTransferPlanError as exc:
            _set_readonly_text(
                library_report,
                "OFFLINE LIBRARY TRANSFER REVIEW — blocked; no device change occurred\n\n"
                + str(exc),
            )
            library_status_var.set(f"Queue review blocked; no device access: {exc}")
            return
        _set_readonly_text(library_report, format_library_transfer_plan(plan.to_dict()))
        library_status_var.set(
            "Offline queue review displayed; candidate construction and device transfer are disabled"
        )

    def library_experimental_review_action() -> None:
        """Show reusable Experimental readiness without a live action."""

        nonlocal library_current_plan_report, library_current_readiness, library_prepared_operation

        if library_catalog is None:
            return
        selected_items = selected_library_items()
        if len(selected_items) != 1:
            library_status_var.set(
                "Experimental review requires exactly one Library item; no device access"
            )
            return
        backup = None
        backup_directory = model.state.backup_directory
        if backup_directory is not None:
            try:
                backup = verify_fresh_backup(
                    backup_directory,
                    now=None,
                    max_age_seconds=None,
                )
            except Exception as exc:
                library_status_var.set(
                    f"Experimental review has no verified backup: {exc}"
                )
        try:
            plan = build_library_transfer_queue_plan(
                library_catalog,
                selected_item_ids=[selected_items[0].item_id],
                selection_mode=SELECTION_SELECTED,
                backup=backup,
            )
            library_current_plan_report = plan.to_dict()
            review = library_execution_facade.review_readiness(library_current_plan_report)
            library_current_readiness = review
            library_prepared_operation = None
        except (LibraryTransferPlanError, LibraryTransferReadinessError) as exc:
            _set_readonly_text(
                library_report,
                "EXPERIMENTAL TRANSFER READINESS — blocked; no device change occurred\n\n"
                + str(exc),
            )
            library_status_var.set(f"Experimental review blocked; no device access: {exc}")
            return
        _set_readonly_text(
            library_report,
            format_library_transfer_readiness(review.to_dict()),
        )
        library_status_var.set(
            "Transfer readiness displayed; fresh evidence and any live execution remain separately guarded"
        )

        library_live_preflight_button.configure(
            state=(
                "normal"
                if review.host_profile_eligible
                and library_execution_facade.can_prepare_live
                else "disabled"
            )
        )

    def library_live_preflight_action() -> None:
        """Refresh read-only evidence through the product facade only."""

        nonlocal library_current_plan_report, library_current_readiness, library_prepared_operation
        if (
            library_catalog is None
            or library_current_plan_report is None
            or not library_execution_facade.can_prepare_live
        ):
            library_status_var.set(
                "Live preflight is blocked until a fresh authorized VNW-V15 operation is configured"
            )
            return
        runtime = library_execution_facade.runtime
        if runtime is None:
            return
        operation_root = (
            Path(runtime.evidence_namespace).expanduser().resolve()
            / f"ui-preflight-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
        )
        try:
            prepared = library_execution_facade.refresh_live_preflight(
                library_current_plan_report,
                catalog=library_catalog,
                preflight_report_path=operation_root / "sealed-preflight.json",
                bundle_path=operation_root / "operation-bundle.json",
                audit_location=str(runtime.evidence_namespace),
                cancelled=cancel_event.is_set,
            )
        except (LibraryTransferExecutionError, LibraryTransferReadinessError, OSError, ValueError) as exc:
            library_prepared_operation = None
            library_transfer_once_button.configure(state="disabled")
            library_status_var.set(f"Live preflight blocked; no device change: {exc}")
            _set_readonly_text(
                library_report,
                "GUARDED TRANSFER REVIEW — blocked; no device change occurred\n\n" + str(exc),
            )
            return
        library_prepared_operation = prepared
        library_current_plan_report = dict(prepared.plan_report)
        library_current_readiness = prepared.readiness
        _set_readonly_text(
            library_report,
            format_experimental_library_transfer_review(prepared.review.to_dict()),
        )
        library_transfer_once_button.configure(
            state="normal" if library_execution_facade.transfer_actionable else "disabled"
        )
        library_status_var.set(
            "Fresh read-only preflight reviewed; Transfer once is enabled only for this exact one-shot operation"
        )

    def library_transfer_once_action() -> None:
        """Confirm and run one prepared operation through the facade."""

        nonlocal library_prepared_operation

        if (
            library_prepared_operation is None
            or not library_execution_facade.transfer_actionable
            or library_execution_facade.operation_binding is None
        ):
            library_status_var.set(
                "Transfer once is blocked until the exact reviewed operation is ready"
            )
            library_transfer_once_button.configure(state="disabled")
            return
        confirmation_phrase = (
            library_execution_facade.operation_binding.confirmation_phrase
        )
        answer = simpledialog.askstring(
            "Confirm one transfer",
            (
                "This is one guarded VNW-V15 transaction.\n\n"
                "A fresh preflight, complete post-write backup, and independent read-back are required. "
                "An indeterminate result will be locked for read-only diagnosis; it will not be retried.\n\n"
                f"Type exactly: {confirmation_phrase}"
            ),
            parent=root,
        )
        if answer is None:
            library_status_var.set("Transfer cancelled; no device transaction attempted")
            return
        try:
            result = library_execution_facade.execute_once(
                library_current_plan_report or {},
                confirmation_interaction=lambda _review: answer,
            )
        except BaseException as exc:
            library_prepared_operation = None
            library_transfer_once_button.configure(state="disabled")
            library_status_var.set(friendly_error_message(exc))
            messagebox.showerror("Transfer once", friendly_error_message(exc), parent=root)
            return
        _set_readonly_text(
            library_report,
            format_library_transfer_execution_result(result.to_dict()),
        )
        library_transfer_once_button.configure(state="disabled")
        library_status_var.set(
            "Transfer verified; the canonical post-backup and independent read-back checks passed"
        )

    library_tree.bind("<<TreeviewSelect>>", show_library_selection)
    library_import_button.configure(command=library_import_action)
    library_folder_import_button.configure(command=library_folder_import_action)
    library_package_import_button.configure(command=library_package_import_action)
    library_move_up_button.configure(command=lambda: library_move_action("up"))
    library_move_down_button.configure(command=lambda: library_move_action("down"))
    library_remove_button.configure(command=library_remove_action)
    library_prepare_button.configure(command=library_prepare_action)
    library_preview_button.configure(command=library_preview_action)
    library_selected_queue_button.configure(
        command=lambda: library_transfer_review_action(SELECTION_SELECTED)
    )
    library_all_queue_button.configure(
        command=lambda: library_transfer_review_action(SELECTION_ALL_READY)
    )
    library_experimental_button.configure(command=library_experimental_review_action)
    library_live_preflight_button.configure(command=library_live_preflight_action)
    library_transfer_once_button.configure(command=library_transfer_once_action)
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
                library_import_button,
                library_folder_import_button,
                library_package_import_button,
                library_move_up_button,
                library_move_down_button,
                library_remove_button,
                library_prepare_button,
                library_preview_button,
                library_selected_queue_button,
                library_all_queue_button,
                library_experimental_button,
                library_live_preflight_button,
                library_transfer_once_button,
            ):
                button.configure(state="disabled")
        else:
            show_library_selection()
            if library_catalog is None:
                library_import_button.configure(state="disabled")
                library_folder_import_button.configure(state="disabled")
                library_package_import_button.configure(state="disabled")
            else:
                library_import_button.configure(state="normal")
                library_folder_import_button.configure(state="normal")
                library_package_import_button.configure(state="normal")
        export_button.configure(state="disabled" if busy or not tree.selection() else "normal")
        if busy:
            replacement_button.configure(state="disabled")
            write_button.configure(state="disabled")
        if busy:
            progress.configure(value=0)

    def refresh_tree() -> None:
        tree.delete(*tree.get_children())
        tree_items.clear()
        # ``model.rows()`` follows each directory's stored child table order,
        # which is the order shown by the original device manager.  Do not
        # sort by display name here.
        rows = model.rows()
        rows_by_path = {tuple(row.path.split("\\")): row for row in rows}
        path_items: Dict[Tuple[str, ...], str] = {}
        for row in rows:
            parts = tuple(row.path.split("\\"))
            parent_item = ""
            for depth in range(1, len(parts) + 1):
                prefix = parts[:depth]
                if prefix in path_items:
                    parent_item = path_items[prefix]
                    continue
                current = rows_by_path.get(prefix)
                if current is None:
                    continue
                size = "" if current.payload_bytes is None else f"{current.payload_bytes:,} B"
                item = tree.insert(
                    parent_item,
                    "end",
                    text=prefix[-1],
                    values=(current.kind, size, current.read_state or ""),
                    open=(current.kind == "directory" and depth <= 1),
                )
                path_items[prefix] = item
                tree_items[item] = current.record_offset
                parent_item = item
        export_button.configure(state="disabled")
        replacement_button.configure(state="disabled")
        write_button.configure(state="disabled")

    def show_selection(_event: Any = None) -> None:
        nonlocal preview_image
        selected = [tree_items[item] for item in tree.selection() if item in tree_items]
        export_button.configure(state="normal" if selected and worker is None else "disabled")
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
            details_var.set(f"{len(selected)} items selected\nDevice writes disabled")
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
        details_var.set(
            f"{row.display_name}\n\nType: {row.kind}\nSize: {size}\n"
            f"Record: 0x{row.record_offset:08x}\nState: {row.read_state or 'n/a'}\n"
            f"SHA-256: {row.payload_sha256 or 'n/a'}"
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
        try:
            devices = find_devices()
        except DeviceAccessError as exc:
            status_var.set(friendly_error_message(exc))
            return
        if not devices:
            status_var.set("No Sony InfoCarry detected; device writes disabled")
            return
        if len(devices) > 1:
            status_var.set(f"{len(devices)} matching devices detected; connect only one")
            return
        device = describe_device(devices[0])
        location = ""
        if device.bus is not None and device.address is not None:
            location = f" on bus {device.bus}, address {device.address}"
        status_var.set(
            f"Sony InfoCarry {device.vendor_id:04x}:{device.product_id:04x} detected{location}; "
            "device writes disabled"
        )

    def load_backup_action() -> None:
        selected = filedialog.askdirectory(title="Choose complete InfoCarry backup", parent=root)
        if not selected:
            return
        try:
            model.load_backup(Path(selected))
            refresh_tree()
            backup_var.set(f"Backup: {Path(selected).name}")
            status_var.set(model.state.status)
        except DesktopWorkflowError as exc:
            messagebox.showerror("Open backup", friendly_error_message(exc), parent=root)

    def export_action() -> None:
        offsets = [tree_items[item] for item in tree.selection() if item in tree_items]
        if not offsets:
            messagebox.showinfo("Download selected", "Select one or more files or folders first.", parent=root)
            return
        parent = filedialog.askdirectory(title="Choose destination folder", parent=root)
        if not parent:
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
        try:
            model.select_record(selected[0])
            report = model.preview_selected_text_replacement(Path(source))
            image_preview.pack_forget()
            preview.pack(fill="both", expand=True)
            _set_readonly_text(preview, format_text_replacement_preview(report))
            write_button.configure(state="normal" if worker is None else "disabled")
            status_var.set(model.state.status)
        except DesktopWorkflowError as exc:
            messagebox.showerror(
                "Preview replacement", friendly_error_message(exc), parent=root
            )

    def replacement_write_action() -> None:
        nonlocal worker
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

                    result = ExistingTextReplacementWorkflow(capture, send).run(
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
        nonlocal worker
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
                    model.load_backup(value)
                    refresh_tree()
                    backup_var.set(f"Backup: {Path(value).name}")
                    status_var.set(f"Verified backup created at {value}; device writes disabled")
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

    def backup_action() -> None:
        nonlocal worker
        if worker is not None and worker.is_alive():
            return
        parent = filedialog.askdirectory(title="Choose parent folder for new backup", parent=root)
        if not parent:
            return
        destination = _backup_destination(Path(parent))
        cancel_event.clear()
        set_busy(True)
        status_var.set(f"Starting read-only backup at {destination}")

        def progress_callback(label: str, completed: int, total: int) -> None:
            events.put(("progress", (label, completed, total)))

        def run_backup() -> None:
            archive = None
            try:
                archive = RawBackupArchive.create(destination)
                from .transport import InfoCarrySession

                with InfoCarrySession.open() as session:
                    BackupClient(session).backup(
                        archive,
                        cancelled=cancel_event.is_set,
                        progress=progress_callback,
                    )
                events.put(("done", destination))
            except BaseException as exc:
                if archive is not None:
                    try:
                        archive.mark_incomplete(exc)
                    except Exception:
                        pass
                events.put(("error", exc))

        worker = threading.Thread(target=run_backup, name="infocarry-read-only-backup", daemon=True)
        worker.start()

    def close_action() -> None:
        if worker is not None and worker.is_alive():
            if not messagebox.askyesno(
                "Operation in progress",
                "Stop the operation and close the window? Any incomplete archive will be preserved; a started write will not be retried.",
                parent=root,
            ):
                return
            cancel_event.set()
        root.destroy()

    tree.bind("<<TreeviewSelect>>", show_selection)
    check_button.configure(command=check_device_action)
    backup_button.configure(command=backup_action)
    open_button.configure(command=load_backup_action)
    export_button.configure(command=export_action)
    replacement_button.configure(command=replacement_preview_action)
    write_button.configure(command=replacement_write_action)
    root.protocol("WM_DELETE_WINDOW", close_action)
    root.after(100, process_backup_events)
    root.mainloop()


__all__ = [
    "format_library_device_tree_preview",
    "format_library_preparation_audit",
    "format_library_transfer_readiness",
    "format_library_transfer_execution_result",
    "format_prepared_package_readiness_preview",
    "format_text_replacement_preview",
    "format_post_write_verification",
    "friendly_error_message",
    "launch_ttk_desktop",
]
