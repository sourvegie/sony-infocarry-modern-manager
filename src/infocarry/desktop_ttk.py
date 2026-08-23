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
from .library import LibraryCatalog, LibraryCatalogError, LibraryError
from .library_prepare import LibraryPreparationError, prepare_library_item
from .runtime import DesktopRuntimeError, check_desktop_runtime


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


def launch_ttk_desktop() -> None:
    """Launch the supported no-write ttk desktop workflow."""

    runtime = check_desktop_runtime()
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, simpledialog, ttk
    except ImportError as exc:  # pragma: no cover - guarded by runtime check
        raise DesktopRuntimeError("Tkinter is not available in this Python installation") from exc

    from .usb_access import DeviceAccessError, describe_device, find_devices

    root = tk.Tk()
    root.title("Sony InfoCarry Manager")
    root.geometry("1080x680")
    root.minsize(860, 520)
    model = DesktopWorkflowModel()
    events: "queue.Queue[Tuple[str, Any]]" = queue.Queue()
    cancel_event = threading.Event()
    worker: Optional[threading.Thread] = None
    try:
        library_catalog: Optional[LibraryCatalog] = LibraryCatalog()
        library_catalog_error: Optional[str] = None
    except LibraryCatalogError as exc:
        library_catalog = None
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
            else "Import a UTF-8 TXT source; no device operation occurs."
        )
    )
    library_detail_var = tk.StringVar(value="Select a Library item")
    library_tree_items: Dict[str, str] = {}
    library_toolbar = ttk.Frame(library_tab)
    library_toolbar.pack(fill="x", pady=(0, 8))
    ttk.Label(
        library_toolbar,
        text="Local Library",
        font=("TkDefaultFont", 14, "bold"),
    ).pack(side="left", padx=(0, 16))
    library_import_button = ttk.Button(library_toolbar, text="Import TXT…")
    library_remove_button = ttk.Button(
        library_toolbar, text="Remove from Library", state="disabled"
    )
    library_prepare_button = ttk.Button(
        library_toolbar, text="Prepare…", state="disabled"
    )
    library_import_button.pack(side="left", padx=3)
    library_remove_button.pack(side="left", padx=3)
    library_prepare_button.pack(side="left", padx=3)
    ttk.Label(
        library_toolbar,
        text="offline only — no transfer action",
        foreground="#6b4f00",
    ).pack(side="right", padx=(12, 0))

    library_content = ttk.Panedwindow(library_tab, orient="horizontal")
    library_content.pack(fill="both", expand=True)
    library_list_frame = ttk.Frame(library_content, padding=(0, 0, 8, 0))
    library_detail_frame = ttk.Frame(library_content, padding=(8, 0, 0, 0))
    library_content.add(library_list_frame, weight=3)
    library_content.add(library_detail_frame, weight=2)
    library_tree = ttk.Treeview(
        library_list_frame,
        columns=("state", "source", "target"),
        show="tree headings",
        selectmode="browse",
    )
    library_tree.heading("#0", text="Item")
    library_tree.heading("state", text="State")
    library_tree.heading("source", text="Source")
    library_tree.heading("target", text="Target")
    library_tree.column("#0", minwidth=160, width=220, stretch=True)
    library_tree.column("state", minwidth=90, width=100, stretch=False)
    library_tree.column("source", minwidth=180, width=260, stretch=True)
    library_tree.column("target", minwidth=180, width=260, stretch=True)
    library_tree_scroll = ttk.Scrollbar(
        library_list_frame, orient="vertical", command=library_tree.yview
    )
    library_tree.configure(yscrollcommand=library_tree_scroll.set)
    library_tree.pack(side="left", fill="both", expand=True)
    library_tree_scroll.pack(side="right", fill="y")
    ttk.Label(library_detail_frame, text="Library selection").pack(anchor="w")
    ttk.Label(
        library_detail_frame,
        textvariable=library_detail_var,
        wraplength=380,
    ).pack(anchor="w", fill="x", pady=(2, 10))
    library_report = tk.Text(library_detail_frame, height=20, width=48, wrap="word")
    library_report.pack(fill="both", expand=True)
    library_report.configure(state="disabled")
    ttk.Label(
        library_detail_frame,
        textvariable=library_status_var,
        wraplength=520,
    ).pack(anchor="w", fill="x", pady=(8, 0))

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

    def refresh_library_view() -> None:
        library_tree.delete(*library_tree.get_children())
        library_tree_items.clear()
        if library_catalog is None:
            library_import_button.configure(state="disabled")
            library_remove_button.configure(state="disabled")
            library_prepare_button.configure(state="disabled")
            return
        library_import_button.configure(state="normal")
        for item in library_catalog.items:
            target = ""
            if item.target_folder_name and item.target_child_name:
                target = f"root\\{item.target_folder_name}\\{item.target_child_name}"
            tree_item = library_tree.insert(
                "",
                "end",
                text=item.source_filename,
                values=(item.state, item.source_path, target),
            )
            library_tree_items[tree_item] = item.item_id
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

    def show_library_selection(_event: Any = None) -> None:
        item = selected_library_item()
        enabled = item is not None and library_catalog is not None
        library_remove_button.configure(state="normal" if enabled else "disabled")
        library_prepare_button.configure(
            state=(
                "normal"
                if enabled
                and item.supported
                and item.state in {"imported", "ready", "blocked"}
                else "disabled"
            )
        )
        if item is None:
            library_detail_var.set("Select a Library item")
            _set_readonly_text(library_report, "")
            return
        target = "not prepared"
        if item.target_folder_name and item.target_child_name:
            target = f"root\\{item.target_folder_name}\\{item.target_child_name}"
        library_detail_var.set(
            f"{item.source_filename}\n\n"
            f"State: {item.state}\n"
            f"Source: {item.source_path}\n"
            f"SHA-256: {item.source_sha256}\n"
            f"Target: {target}"
        )
        _set_readonly_text(
            library_report,
            json.dumps(item.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        )

    def library_import_action() -> None:
        if library_catalog is None:
            messagebox.showerror("Library", library_catalog_error or "Library is unavailable", parent=root)
            return
        selected = filedialog.askopenfilename(
            title="Import local source into Library",
            filetypes=(
                ("UTF-8 text files", "*.txt"),
                ("All files", "*"),
            ),
            parent=root,
        )
        if not selected:
            return
        try:
            item = library_catalog.import_file(Path(selected))
            refresh_library_view()
            library_status_var.set(
                f"Imported {item.source_filename}; original source unchanged; no device access"
            )
            _set_readonly_text(
                library_report,
                json.dumps(item.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
            )
        except (LibraryError, OSError) as exc:
            library_status_var.set(f"Library import blocked: {exc}")
            messagebox.showerror("Library import", str(exc), parent=root)

    def library_remove_action() -> None:
        if library_catalog is None:
            return
        item = selected_library_item()
        if item is None:
            return
        if not messagebox.askyesno(
            "Remove from Library",
            (
                f"Remove {item.source_filename} from the local catalog?\n\n"
                "The original source file will not be moved or deleted."
            ),
            parent=root,
        ):
            return
        library_catalog.remove(item.item_id)
        refresh_library_view()
        library_status_var.set("Removed catalog entry only; original source unchanged")

    def library_prepare_action() -> None:
        if library_catalog is None:
            return
        item = selected_library_item()
        if item is None:
            messagebox.showinfo("Prepare", "Select exactly one supported TXT Library item.", parent=root)
            return
        folder_name = simpledialog.askstring(
            "Prepare offline package",
            "Root-level folder name:",
            initialvalue=item.target_folder_name or Path(item.source_filename).stem,
            parent=root,
        )
        if folder_name is None:
            return
        child_name = simpledialog.askstring(
            "Prepare offline package",
            "TXT child filename:",
            initialvalue=item.target_child_name or item.source_filename,
            parent=root,
        )
        if child_name is None:
            return
        try:
            result = prepare_library_item(
                library_catalog,
                item.item_id,
                folder_name,
                child_name,
            )
            refresh_library_view()
            _set_readonly_text(library_report, format_library_preparation_audit(dict(result.audit)))
            library_status_var.set(
                f"Prepared {result.package.target_item_path} offline; no device access"
            )
        except LibraryPreparationError as exc:
            refresh_library_view()
            library_status_var.set(f"Prepare blocked; no device access: {exc}")
            _set_readonly_text(
                library_report,
                "OFFLINE LIBRARY PREPARE — blocked; no device change occurred\n\n" + str(exc),
            )
            messagebox.showerror("Offline Prepare", str(exc), parent=root)

    library_tree.bind("<<TreeviewSelect>>", show_library_selection)
    library_import_button.configure(command=library_import_action)
    library_remove_button.configure(command=library_remove_action)
    library_prepare_button.configure(command=library_prepare_action)
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
                library_remove_button,
                library_prepare_button,
            ):
                button.configure(state="disabled")
        else:
            show_library_selection()
            if library_catalog is None:
                library_import_button.configure(state="disabled")
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
    "format_library_preparation_audit",
    "format_text_replacement_preview",
    "format_post_write_verification",
    "friendly_error_message",
    "launch_ttk_desktop",
]
