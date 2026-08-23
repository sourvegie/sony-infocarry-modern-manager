"""Minimal no-write desktop workflow for InfoCarry backups.

The model is framework-independent and is therefore easy to test.  The
optional ttk front end only browses a complete backup and previews text or
validated monochrome BMP records; it deliberately has no device-write control.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from .backup_format import (
    BackupExporter,
    decode_cp932_with_escapes,
    load_complete_backup,
    load_complete_backup_bytes,
)
from .bitmap import BitmapPreview, decode_monochrome_bmp
from .text_authoring import preview_decoded_text_replacement
from .workflow import build_backup_inventory, save_json_report
from .write_gate import PostWriteVerification


class DesktopWorkflowError(RuntimeError):
    """Raised when the desktop workflow cannot complete a safe offline action."""


@dataclass(frozen=True)
class InventoryRow:
    record_offset: int
    path: str
    kind: str
    extension: str
    payload_bytes: Optional[int]
    read_state: Optional[str]
    payload_sha256: Optional[str] = None

    @property
    def display_name(self) -> str:
        if self.extension and self.kind == "file":
            return f"{self.path}.{self.extension}"
        return self.path


@dataclass
class DesktopWorkflowState:
    """State displayed by a future desktop shell."""

    backup_directory: Optional[Path] = None
    source_blob_sha256: Optional[str] = None
    inventory: Optional[Dict[str, Any]] = None
    selected_record_offset: Optional[int] = None
    preview_report: Optional[Dict[str, Any]] = None
    post_write_verification: Optional[Dict[str, Any]] = None
    status: str = "No backup loaded"
    error: Optional[str] = None
    device_write_enabled: bool = False


class DesktopWorkflowModel:
    """Offline state model for backup browsing and text preview."""

    def __init__(self) -> None:
        self.state = DesktopWorkflowState()

    def load_backup(self, directory: Path) -> Sequence[InventoryRow]:
        try:
            parsed, digest = load_complete_backup(directory)
            inventory = build_backup_inventory(parsed, digest)
        except Exception as exc:
            self.state.error = str(exc)
            self.state.status = "Backup could not be loaded"
            raise DesktopWorkflowError(str(exc)) from exc
        self.state.backup_directory = directory.expanduser().resolve()
        self.state.source_blob_sha256 = digest
        self.state.inventory = inventory
        self.state.selected_record_offset = None
        self.state.preview_report = None
        self.state.post_write_verification = None
        self.state.error = None
        self.state.status = "Backup loaded; device writes disabled"
        return self.rows()

    def rows(self) -> Sequence[InventoryRow]:
        if self.state.inventory is None:
            return ()
        rows = []
        for record in self.state.inventory["records"]:
            raw_offset = record["record_offset"]
            rows.append(
                InventoryRow(
                    record_offset=int(raw_offset, 16),
                    path=record["path"],
                    kind=record["kind"],
                    extension=record["extension"],
                    payload_bytes=record.get("payload_bytes"),
                    read_state=record.get("read_state"),
                    payload_sha256=record.get("payload_sha256"),
                )
            )
        return tuple(rows)

    def select_record(self, record_offset: int) -> InventoryRow:
        for row in self.rows():
            if row.record_offset == record_offset:
                self.state.selected_record_offset = record_offset
                self.state.preview_report = None
                self.state.post_write_verification = None
                self.state.error = None
                return row
        raise DesktopWorkflowError(f"record 0x{record_offset:x} is not in the loaded backup")

    def read_selected_text(self, record_offset: int) -> str:
        """Decode a selected TXT payload for a read-only preview."""

        if self.state.backup_directory is None:
            raise DesktopWorkflowError("load a complete backup before previewing text")
        row = self.select_record(record_offset)
        if row.kind != "file" or row.extension.lower() != "txt":
            raise DesktopWorkflowError("selected record is not a reachable txt file")
        try:
            parsed, _digest = load_complete_backup(self.state.backup_directory)
            _prefix, payload = parsed.payload_parts(parsed.record_at(record_offset))
            decoded, _invalid = decode_cp932_with_escapes(payload)
        except Exception as exc:
            self.state.error = str(exc)
            self.state.status = "Text preview failed"
            raise DesktopWorkflowError(str(exc)) from exc
        self.state.error = None
        self.state.status = "Text preview loaded; device writes disabled"
        return decoded

    def read_selected_bitmap(self, record_offset: int) -> BitmapPreview:
        """Decode a selected BMP payload for a read-only preview."""

        if self.state.backup_directory is None:
            raise DesktopWorkflowError("load a complete backup before previewing images")
        row = self.select_record(record_offset)
        if row.kind != "file" or row.extension.lower() != "bmp":
            raise DesktopWorkflowError("selected record is not a reachable bmp file")
        try:
            parsed, _digest = load_complete_backup(self.state.backup_directory)
            _prefix, payload = parsed.payload_parts(parsed.record_at(record_offset))
            preview = decode_monochrome_bmp(payload)
        except Exception as exc:
            self.state.error = str(exc)
            self.state.status = "Image preview failed"
            raise DesktopWorkflowError(str(exc)) from exc
        self.state.error = None
        self.state.status = "Image preview loaded; device writes disabled"
        return preview

    def export_selection(self, destination: Path, offsets: Sequence[int]) -> Dict[str, Any]:
        """Export selected files/folders without accessing USB."""

        if self.state.backup_directory is None:
            raise DesktopWorkflowError("load a complete backup before exporting")
        try:
            parsed, digest = load_complete_backup(self.state.backup_directory)
            manifest = BackupExporter(parsed, digest).export(
                destination, selected_offsets=tuple(offsets)
            )
        except Exception as exc:
            self.state.error = str(exc)
            self.state.status = "Selected export failed"
            raise DesktopWorkflowError(str(exc)) from exc
        self.state.error = None
        summary = manifest["summary"]
        self.state.status = (
            f"Exported {summary['files']} file(s); device writes disabled"
        )
        return manifest

    def preview_selected_text_replacement(
        self, text_path: Path, *, max_payload_bytes: Optional[int] = None
    ) -> Dict[str, Any]:
        """Preview replacing the selected existing TXT record.

        This is deliberately an audit-only operation.  It reads the selected
        record and a local UTF-8 source file, builds the existing in-memory
        replacement audit, and stores only JSON-safe metadata and hashes in
        the model.  No candidate blob is written and no device API is called.
        """

        if self.state.backup_directory is None:
            raise DesktopWorkflowError("load a complete backup before previewing text")
        if self.state.selected_record_offset is None:
            raise DesktopWorkflowError("select a text record before previewing")
        row = self.select_record(self.state.selected_record_offset)
        if row.kind != "file" or row.extension.lower() != "txt":
            raise DesktopWorkflowError("selected record is not a reachable txt file")
        source_path = Path(text_path).expanduser().resolve()
        try:
            raw, digest = load_complete_backup_bytes(self.state.backup_directory)
            text = source_path.read_text(encoding="utf-8")
            report = preview_decoded_text_replacement(
                raw,
                row.record_offset,
                text,
                max_payload_bytes=max_payload_bytes,
            )
        except Exception as exc:
            self.state.error = str(exc)
            self.state.status = "Text preview failed"
            raise DesktopWorkflowError(str(exc)) from exc
        report["workflow"] = {
            "source_backup_blob_sha256": digest,
            "input_path": str(source_path),
            "target_record_offset": report["target"]["record_offset_hex"],
            # The inventory display path includes the extension, while the
            # lower-level authoring report keeps its historical extensionless
            # directory/name path for compatibility.
            "target_path": row.display_name,
            "device_accessed": False,
            "candidate_bytes_included": False,
        }
        self.state.preview_report = report
        self.state.post_write_verification = None
        self.state.error = None
        self.state.status = "Preview ready; device writes disabled"
        return report

    def record_post_write_verification(
        self, verification: PostWriteVerification
    ) -> Dict[str, Any]:
        """Record an independently verified read-back for later display.

        This method accepts only the result produced by the USB-neutral
        :func:`verify_post_write_backup` helper.  It does not send, retry, or
        initiate any device operation.  A failed comparison is rejected so a
        caller cannot present an incomplete read-back as success.
        """

        if not isinstance(verification, PostWriteVerification):
            raise DesktopWorkflowError(
                "post-write result must come from the complete read-back verifier"
            )
        if not (
            verification.fixed_state_matches
            and verification.dynamic_blob_matches
            and verification.unrelated_objects_unchanged
        ):
            self.state.error = "post-write read-back verification did not pass"
            self.state.status = "Read-back verification failed; do not retry automatically"
            raise DesktopWorkflowError(self.state.error)
        result = verification.to_dict()
        self.state.post_write_verification = result
        self.state.error = None
        self.state.status = "Post-write read-back verified; no automatic retry"
        return result

    def preview_text(
        self, text_path: Path, *, max_payload_bytes: Optional[int] = None
    ) -> Dict[str, Any]:
        """Backward-compatible alias for the selected-record preview."""

        return self.preview_selected_text_replacement(
            text_path, max_payload_bytes=max_payload_bytes
        )

    def save_inventory_report(self, destination: Path) -> Path:
        if self.state.inventory is None:
            raise DesktopWorkflowError("load a complete backup before saving inventory")
        try:
            return save_json_report(destination, self.state.inventory)
        except Exception as exc:
            raise DesktopWorkflowError(str(exc)) from exc

    def save_preview_report(self, destination: Path) -> Path:
        if self.state.preview_report is None:
            raise DesktopWorkflowError("create a text preview before saving its report")
        try:
            return save_json_report(destination, self.state.preview_report)
        except Exception as exc:
            raise DesktopWorkflowError(str(exc)) from exc


def launch_desktop() -> None:
    """Launch the optional Tk workflow shell.

    Importing Tk is delayed so headless installations can still use every CLI
    and model API.  The shell exposes only load/select/preview/save actions.
    """

    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError as exc:
        raise DesktopWorkflowError("Tk is not available in this Python installation") from exc

    model = DesktopWorkflowModel()
    try:
        root = tk.Tk()
    except Exception as exc:
        raise DesktopWorkflowError(f"Tk could not start a desktop window: {exc}") from exc
    root.title("Sony InfoCarry — Offline Workflow")
    root.geometry("920x560")
    root.minsize(760, 460)

    # Use classic Tk widgets rather than ttk here.  The system Tk shipped with
    # older macOS releases can render the native themed widget layer as an
    # entirely blank window when the desktop is in dark mode.  Classic Tk
    # widgets with explicit colours are stable on those installations.
    palette = {
        "background": "#24292b",
        "foreground": "#f2f2f2",
        "fieldbackground": "#303438",
        "selectbackground": "#3f78b5",
        "selectforeground": "#ffffff",
        "header": "#3a3f43",
        "button": "#343a3f",
        "button_active": "#4a5258",
        "border": "#70777c",
    }
    root.configure(background=palette["background"])

    top = tk.Frame(root, background=palette["background"], padx=8, pady=8)
    top.pack(fill="x")
    backup_var = tk.StringVar()
    backup_display_var = tk.StringVar(value="No backup loaded")
    tk.Button(
        top,
        textvariable=backup_display_var,
        anchor="w",
        command=lambda: load_action(),
        background=palette["button"],
        foreground=palette["foreground"],
        activebackground=palette["button_active"],
        relief="groove",
        padx=8,
        pady=3,
    ).pack(side="left", fill="x", expand=True, padx=(0, 6))
    status_var = tk.StringVar(value=model.state.status)
    tk.Button(
        root,
        textvariable=status_var,
        anchor="w",
        background=palette["button"],
        foreground=palette["foreground"],
        activebackground=palette["button_active"],
        relief="flat",
        padx=8,
    ).pack(fill="x")

    list_frame = tk.Frame(root, background=palette["background"], padx=8, pady=6)
    list_frame.pack(fill="both", expand=True)
    records_canvas = tk.Canvas(
        list_frame,
        background=palette["background"],
        highlightthickness=0,
        borderwidth=0,
    )
    records_canvas.pack(side="left", fill="both", expand=True)
    list_scroll = tk.Scrollbar(list_frame, command=records_canvas.yview)
    list_scroll.pack(side="right", fill="y")
    records_canvas.configure(yscrollcommand=list_scroll.set)
    records_inner = tk.Frame(records_canvas, background=palette["background"])
    records_window = records_canvas.create_window((0, 0), window=records_inner, anchor="nw")

    def resize_records(_event: Any = None) -> None:
        records_canvas.configure(scrollregion=records_canvas.bbox("all"))
        records_canvas.itemconfigure(records_window, width=records_canvas.winfo_width())

    records_inner.bind("<Configure>", resize_records)
    records_canvas.bind("<Configure>", resize_records)

    bottom = tk.Frame(root, background=palette["background"], padx=8, pady=8)
    bottom.pack(fill="x")
    text_var = tk.StringVar()
    text_display_var = tk.StringVar(value="No UTF-8 text file selected")
    tk.Button(
        bottom,
        textvariable=text_display_var,
        anchor="w",
        command=lambda: choose_text(),
        background=palette["button"],
        foreground=palette["foreground"],
        activebackground=palette["button_active"],
        relief="groove",
        padx=8,
        pady=3,
    ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=(0, 6))
    bottom.columnconfigure(0, weight=1)
    result_var = tk.StringVar(value="No preview created")
    tk.Button(
        bottom,
        textvariable=result_var,
        anchor="w",
        background=palette["button"],
        foreground=palette["foreground"],
        activebackground=palette["button_active"],
        relief="flat",
    ).grid(row=1, column=0, columnspan=5, sticky="ew", pady=(6, 0))

    rows_by_index = []
    record_buttons = []
    selected_index: Optional[int] = None

    def button(parent: Any, text: str, command: Any, **grid_options: Any) -> None:
        tk.Button(
            parent,
            text=text,
            command=command,
            background=palette["button"],
            foreground=palette["foreground"],
            activebackground=palette["button_active"],
            activeforeground=palette["foreground"],
            relief="raised",
            padx=8,
            pady=3,
        ).grid(**grid_options)

    def refresh_rows() -> None:
        rows_by_index[:] = list(model.rows())
        record_buttons.clear()
        for child in records_inner.winfo_children():
            child.destroy()
        if not rows_by_index:
            tk.Button(
                records_inner,
                text="No records loaded",
                anchor="w",
                background=palette["button"],
                foreground=palette["foreground"],
                relief="flat",
            ).pack(fill="x", pady=1)
            resize_records()
            return
        for index, row in enumerate(rows_by_index):
            payload = "" if row.payload_bytes is None else f"{row.payload_bytes} bytes"
            text = f"0x{row.record_offset:08x}   {row.path}   [{row.kind}; {payload}; {row.read_state or ''}]"
            record_button = tk.Button(
                records_inner,
                text=text,
                anchor="w",
                background=palette["button"],
                foreground=palette["foreground"],
                activebackground=palette["selectbackground"],
                activeforeground=palette["selectforeground"],
                relief="flat",
                padx=8,
                pady=2,
                command=lambda row_index=index: select_row(row_index),
            )
            record_button.pack(fill="x", pady=1)
            record_buttons.append(record_button)
        resize_records()

    def select_row(index: int) -> None:
        nonlocal selected_index
        if index < 0 or index >= len(rows_by_index):
            return
        selected_index = index
        model.select_record(rows_by_index[index].record_offset)
        for row_index, record_button in enumerate(record_buttons):
            record_button.configure(
                relief="sunken" if row_index == index else "flat",
                background=palette["selectbackground"] if row_index == index else palette["button"],
                foreground=palette["selectforeground"] if row_index == index else palette["foreground"],
            )
        status_var.set(
            f"Selected 0x{rows_by_index[index].record_offset:x}; device writes disabled"
        )

    def load_action() -> None:
        directory = filedialog.askdirectory(title="Choose complete InfoCarry backup")
        if not directory:
            return
        try:
            backup_var.set(directory)
            backup_display_var.set(f"Backup: {directory}")
            model.load_backup(Path(directory))
            refresh_rows()
            status_var.set(model.state.status)
        except DesktopWorkflowError as exc:
            messagebox.showerror("Backup", str(exc))

    def check_device_action() -> None:
        """Perform a strictly read-only VID/PID enumeration for the status view."""

        try:
            from .usb_access import DeviceAccessError, describe_device, find_devices

            devices = find_devices()
        except DeviceAccessError as exc:
            status_var.set(f"Device check failed; no write attempted: {exc}")
            return
        if not devices:
            status_var.set("No Sony InfoCarry detected; device writes disabled")
            return
        if len(devices) > 1:
            status_var.set(
                f"{len(devices)} Sony InfoCarry devices detected; connect only one"
            )
            return
        device = describe_device(devices[0])
        location = ""
        if device.bus is not None and device.address is not None:
            location = f" on bus {device.bus}, address {device.address}"
        status_var.set(
            f"Sony InfoCarry {device.vendor_id:04x}:{device.product_id:04x} detected{location}; "
            "writes disabled"
        )

    def choose_text() -> None:
        filename = filedialog.askopenfilename(title="Choose UTF-8 text file")
        if filename:
            text_var.set(filename)
            text_display_var.set(f"UTF-8 text: {filename}")

    def preview_action() -> None:
        if selected_index is None or not text_var.get():
            messagebox.showinfo("Preview", "Select a txt record and choose a UTF-8 text file.")
            return
        try:
            model.select_record(rows_by_index[selected_index].record_offset)
            report = model.preview_text(Path(text_var.get()))
            result_var.set(
                f"{report['authoring']['encoded_payload_bytes']} encoded bytes; "
                "candidate bytes omitted; device writes disabled"
            )
            status_var.set(model.state.status)
        except DesktopWorkflowError as exc:
            messagebox.showerror("Preview", str(exc))

    def save_preview_action() -> None:
        if model.state.preview_report is None:
            messagebox.showinfo("Report", "Create a preview first.")
            return
        directory = filedialog.asksaveasfilename(
            title="Choose report directory name", initialfile="text-preview"
        )
        if not directory:
            return
        try:
            model.save_preview_report(Path(directory))
            status_var.set("Preview report saved; device writes disabled")
        except DesktopWorkflowError as exc:
            messagebox.showerror("Report", str(exc))

    tk.Button(
        top,
        text="Open backup",
        command=load_action,
        background=palette["button"],
        foreground=palette["foreground"],
        activebackground=palette["button_active"],
        relief="raised",
        padx=8,
        pady=3,
    ).pack(side="left")
    tk.Button(
        top,
        text="Check device",
        command=check_device_action,
        background=palette["button"],
        foreground=palette["foreground"],
        activebackground=palette["button_active"],
        relief="raised",
        padx=8,
        pady=3,
    ).pack(side="left", padx=(6, 0))
    button(bottom, "Choose…", choose_text, row=0, column=2)
    button(bottom, "Preview", preview_action, row=0, column=3, padx=(6, 0))
    button(bottom, "Save report…", save_preview_action, row=0, column=4, padx=(6, 0))
    root.update_idletasks()
    root.mainloop()


__all__ = [
    "DesktopWorkflowError",
    "DesktopWorkflowModel",
    "DesktopWorkflowState",
    "InventoryRow",
    "launch_desktop",
]


# Keep the original prototype implementation above as historical reference,
# but make the public entry point use the supported ttk Device Manager.
def launch_desktop() -> None:
    from .desktop_ttk import launch_ttk_desktop

    launch_ttk_desktop()
