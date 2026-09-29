"""Packaged Windows entry point for the normal ttk InfoCarry Manager."""

from __future__ import annotations

import json
import os
from importlib.metadata import version
from pathlib import Path
import platform
import sqlite3
import shutil
import sys
import tempfile
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile


def _write_report(path: Path, value: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _make_profile_bmp() -> bytes:
    width, height = 237, 320
    row_stride = ((width + 31) // 32) * 4
    pixels = bytes(row_stride * height)
    payload = bytearray(62 + len(pixels))
    payload[:2] = b"BM"
    payload[2:6] = len(payload).to_bytes(4, "little")
    payload[10:14] = (62).to_bytes(4, "little")
    payload[14:18] = (40).to_bytes(4, "little")
    payload[18:22] = width.to_bytes(4, "little", signed=True)
    payload[22:26] = height.to_bytes(4, "little", signed=True)
    payload[26:28] = (1).to_bytes(2, "little")
    payload[28:30] = (1).to_bytes(2, "little")
    payload[34:38] = len(pixels).to_bytes(4, "little")
    payload[46:50] = (2).to_bytes(4, "little")
    payload[58:62] = b"\xff\xff\xff\x00"
    payload[62:] = pixels
    return bytes(payload)


def _write_epub(path: Path) -> None:
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles>'
            "</container>",
        )
        archive.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            "<dc:title>Windows Smoke Book</dc:title></metadata>"
            '<manifest><item id="chapter" href="chapter.xhtml" '
            'media-type="application/xhtml+xml"/></manifest>'
            '<spine><itemref idref="chapter"/></spine></package>',
        )
        archive.writestr(
            "OEBPS/chapter.xhtml",
            "<html><body><h1>Smoke</h1><p>Offline EPUB preparation.</p></body></html>",
        )


def _review_package(
    *,
    root: Path,
    catalog: Any,
    workflow: Any,
    name: str,
    ordered_sources: list[tuple[Path, str]],
) -> dict[str, Any]:
    from infocarry.library_transfer_plan import build_library_transfer_queue_plan
    from infocarry.library_transfer_readiness import build_library_transfer_readiness
    from infocarry.prepared_media_package import (
        build_prepared_media_package,
        export_prepared_media_package,
    )

    package = build_prepared_media_package(ordered_sources, name)
    package_path = root / f"{name}-prepared-package"
    export_prepared_media_package(package, package_path)
    item = catalog.import_prepared_package(package_path)
    preview = workflow.prepare_preview(item.item_id)
    plan = build_library_transfer_queue_plan(
        catalog,
        selected_item_ids=[item.item_id],
        canonical_artifacts={item.item_id: preview.artifact},
    )
    readiness = build_library_transfer_readiness(plan.to_dict())
    return {
        "eligible": readiness.host_profile_eligible,
        "blocked": readiness.blocked,
        "transfer_enabled": readiness.transfer_enabled,
        "profile": readiness.to_dict()["profile"]["id"],
        "shape": [child.kind for child in preview.artifact.children],
    }


def _run_host_workflow_checks() -> dict[str, Any]:
    from infocarry.desktop_ttk import (
        format_library_preview_summary,
        format_library_readiness_summary,
    )
    from infocarry.device_model_profile import VNW_V10_PROFILE
    from infocarry.library import LibraryCatalog
    from infocarry.library_transfer_plan import build_library_transfer_queue_plan
    from infocarry.library_transfer_readiness import build_library_transfer_readiness
    from infocarry.library_workflow import LibraryWorkflowService
    from infocarry.prepared_media_package import build_prepared_media_package

    with tempfile.TemporaryDirectory(prefix="infocarry-windows-smoke-") as temporary:
        root = Path(temporary)
        story = root / "story.txt"
        story.write_bytes("A packaged TXT smoke test.\n".encode("utf-8"))
        ending = root / "ending.txt"
        ending.write_bytes("An ending.\n".encode("utf-8"))
        extra = root / "extra.txt"
        extra.write_bytes("An additional leaf.\n".encode("utf-8"))
        page = root / "page.bmp"
        page.write_bytes(_make_profile_bmp())
        epub = root / "book.epub"
        _write_epub(epub)

        catalog = LibraryCatalog(root / "library.json")
        workflow = LibraryWorkflowService(catalog)
        imported = workflow.import_files((story, page, epub))
        file_previews: dict[str, str] = {}
        readiness_reviews: dict[str, bool] = {}
        for item in imported:
            preview = workflow.prepare_preview(item.item_id)
            rendered = format_library_preview_summary(preview)
            if "PREVIEW" not in rendered:
                raise RuntimeError(f"preview rendering failed for {item.source_filename}")
            file_previews[Path(item.source_filename).suffix.lower()] = ",".join(
                child.kind for child in preview.artifact.children
            )
            plan = build_library_transfer_queue_plan(
                catalog,
                selected_item_ids=[item.item_id],
                canonical_artifacts={item.item_id: preview.artifact},
            )
            readiness = build_library_transfer_readiness(plan.to_dict())
            rendered_review = format_library_readiness_summary(readiness)
            if "no device change occurred" not in rendered_review:
                raise RuntimeError("transfer-readiness review lost its host-only boundary")
            if readiness.transfer_enabled:
                raise RuntimeError("a host-only content review enabled transfer")
            readiness_reviews[Path(item.source_filename).suffix.lower()] = True

        # Run the package builder used by Add Prepared Package, the normal
        # content preparation service, and the same typed readiness review.
        supported_three = _review_package(
            root=root,
            catalog=catalog,
            workflow=workflow,
            name="Supported-Three",
            ordered_sources=[
                (story, "01-introduction.txt"),
                (page, "02-page.bmp"),
                (ending, "03-ending.txt"),
            ],
        )
        supported_four = _review_package(
            root=root,
            catalog=catalog,
            workflow=workflow,
            name="Supported-Four",
            ordered_sources=[
                (story, "01-introduction.txt"),
                (page, "02-page.bmp"),
                (ending, "03-ending.txt"),
                (extra, "04-extra.txt"),
            ],
        )
        generalized = _review_package(
            root=root,
            catalog=catalog,
            workflow=workflow,
            name="Generalized-Reordered",
            ordered_sources=[
                (story, "01-introduction.txt"),
                (ending, "02-ending.txt"),
                (page, "03-page.bmp"),
                (extra, "04-extra.txt"),
            ],
        )
        if not supported_three["eligible"] or supported_three["blocked"]:
            raise RuntimeError("the exact reviewed VNW-V15 three-leaf shape was not recognized")
        if not supported_four["eligible"] or supported_four["blocked"]:
            raise RuntimeError("the exact reviewed VNW-V15 four-leaf shape was not recognized")
        if not generalized["eligible"] or generalized["blocked"]:
            raise RuntimeError("the generalized reordered flat shape was not host-admissible")
        if any(
            row["transfer_enabled"]
            for row in (supported_three, supported_four, generalized)
        ):
            raise RuntimeError("offline readiness review exposed a transfer action")
        if VNW_V10_PROFILE.transfer_capable:
            raise RuntimeError("Windows runtime inherited a V15 profile for VNW-V10")

        return {
            "add_content": len(imported) == 3,
            "preparation": file_previews,
            "readiness_review": readiness_reviews,
            "verified_shapes": {
                "txt-bmp-txt": supported_three,
                "txt-bmp-txt-txt": supported_four,
            },
            "generalized_shape_host_admissible": generalized,
            "vnw_v10_transfer_capable": VNW_V10_PROFILE.transfer_capable,
        }


def _inspect_widgets(widget: Any) -> list[Any]:
    children = list(widget.winfo_children())
    for child in tuple(children):
        children.extend(_inspect_widgets(child))
    return children


def _read_safety_counters(state_root: Path) -> dict[str, int]:
    """Read the isolated smoke profile's persistent write-safety state."""

    claim_store = state_root / "execution-claims.sqlite3"
    claims_consumed = 0
    sender_markers = 0
    if claim_store.exists():
        database_uri = claim_store.as_uri() + "?mode=ro"
        connection = sqlite3.connect(database_uri, uri=True)
        try:
            claims_consumed = int(
                connection.execute("SELECT COUNT(*) FROM execution_claims").fetchone()[0]
            )
            sender_markers = int(
                connection.execute("SELECT COUNT(*) FROM sender_in_flight").fetchone()[0]
            )
        finally:
            connection.close()
    return {
        "claims_consumed": claims_consumed,
        "sender_marker_rows": sender_markers,
        "installation_lock_mutations": int(
            (state_root / "indeterminate-write-lock.json").exists()
        ),
    }


def _run_packaged_runtime_smoke(report_path: Path) -> int:
    report: dict[str, Any] = {
        "status": "failed",
        "frozen": bool(getattr(sys, "frozen", False)),
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "checks": {},
    }
    try:
        if not getattr(sys, "frozen", False):
            raise RuntimeError("runtime smoke must execute inside the frozen application")
        if sys.platform != "win32":
            raise RuntimeError(f"expected a Windows runtime, found {sys.platform}")
        if platform.machine().casefold() not in {"amd64", "x86_64"}:
            raise RuntimeError(f"expected Windows x64 runtime, found {platform.machine()}")
        python_on_path = {
            command: shutil.which(command)
            for command in ("python", "python3")
        }
        if any(python_on_path.values()):
            raise RuntimeError(
                "runtime smoke expected Python executables to be absent from PATH: "
                f"{python_on_path}"
            )
        report["python_on_path"] = python_on_path

        from infocarry.runtime import check_desktop_runtime

        runtime = check_desktop_runtime()
        if runtime.tk_version < (9, 0):
            raise RuntimeError(f"Tk 9 or newer is required, found {runtime.tk_version}")
        import tkinter

        frozen_resource_root = getattr(sys, "_MEIPASS", None)
        if not isinstance(frozen_resource_root, str) or not frozen_resource_root:
            raise RuntimeError("PyInstaller frozen resource root is missing")
        resource_root = Path(frozen_resource_root).resolve()
        if not resource_root.is_dir():
            raise RuntimeError("PyInstaller frozen resource directory is missing")
        resource_window = tkinter.Tk()
        try:
            resource_window.withdraw()
            resource_window.update_idletasks()
            tcl_version = str(resource_window.tk.call("info", "patchlevel"))
            tk_version = str(resource_window.tk.call("package", "require", "Tk"))
            tcl_library = str(resource_window.tk.call("info", "library"))
            tcl_init_found = bool(
                int(
                    resource_window.tk.call(
                        "file",
                        "exists",
                        resource_window.tk.call("file", "join", tcl_library, "init.tcl"),
                    )
                )
            )
        finally:
            resource_window.destroy()
        if not tcl_init_found:
            raise RuntimeError(f"Tcl init.tcl was not found through Tcl's resource path: {tcl_library}")
        if tkinter.TkVersion < 9.0:
            raise RuntimeError(f"the packaged Tk binding is older than 9: {tkinter.TkVersion}")
        report["tcl_tk"] = {
            "python_runtime_check": runtime.description,
            "tcl_runtime_patchlevel": tcl_version,
            "tk_runtime_package": tk_version,
            "tkinter_compiled_version": tkinter.TkVersion,
            "tcl_library": tcl_library,
            "tcl_init_resource_found": tcl_init_found,
        }
        report["checks"]["frozen_resources"] = str(resource_root)

        import infocarry.desktop_ttk  # noqa: F401 - validate the production UI import graph
        import usb.core  # noqa: F401 - validate PyUSB inclusion
        import libusb_package
        from infocarry.usb_access import _windows_libusb_backend

        dll_path = libusb_package.get_library_path()
        if dll_path is None or not Path(dll_path).is_file():
            raise RuntimeError("the bundled libusb 1.0 DLL was not located")
        backend = _windows_libusb_backend()
        if backend is None or not hasattr(backend, "lib"):
            raise RuntimeError("the packaged PyUSB/libusb backend did not load")
        report["checks"]["application_imports"] = "passed"
        report["checks"]["usb_backend"] = {
            "pyusb_version": version("PyUSB"),
            "libusb_package_version": version("libusb-package"),
            "bundled_library": str(dll_path),
            "native_backend_loaded": True,
        }

        from infocarry.app_paths import application_paths

        state_root = application_paths().safety_root
        profile_root = Path(os.environ["APPDATA"]).expanduser().resolve()
        if not state_root.is_relative_to(profile_root):
            raise RuntimeError("packaged smoke safety state is outside its temporary APPDATA profile")
        if state_root.exists():
            raise RuntimeError("packaged smoke requires a fresh temporary application-data profile")
        smoke_root = report_path.parent
        add_file_source = smoke_root / "Add Files Smoke.txt"
        add_file_source.write_text("Host-only Add Files smoke.\n", encoding="utf-8")
        add_folder_source = smoke_root / "Add Folder Smoke"
        nested_source = add_folder_source / "nested"
        nested_source.mkdir(parents=True)
        nested_file_source = nested_source / "nested.txt"
        nested_file_source.write_text("Host-only nested folder smoke.\n", encoding="utf-8")
        picker_calls: list[str] = []
        import tkinter.filedialog as filedialog_module

        original_askopenfilenames = filedialog_module.askopenfilenames
        original_askdirectory = filedialog_module.askdirectory

        def choose_add_files(**_kwargs: Any) -> tuple[str, ...]:
            picker_calls.append("files")
            return (str(add_file_source),)

        def choose_add_folder(**_kwargs: Any) -> str:
            picker_calls.append("folder")
            return str(add_folder_source)

        filedialog_module.askopenfilenames = choose_add_files
        filedialog_module.askdirectory = choose_add_folder
        isolation_counters = {"device_enumeration_calls": 0, "sender_calls": 0}
        import usb.core
        from infocarry.write_protocol import AuthorizedWriteSender

        original_usb_find = usb.core.find
        original_sender = AuthorizedWriteSender.send
        original_tk = tkinter.Tk

        def forbid_device_enumeration(*_args: Any, **_kwargs: Any) -> Any:
            isolation_counters["device_enumeration_calls"] += 1
            raise RuntimeError("device enumeration is forbidden in the packaged host-only smoke")

        def forbid_sender(*_args: Any, **_kwargs: Any) -> Any:
            isolation_counters["sender_calls"] += 1
            raise RuntimeError("the sender is forbidden in the packaged host-only smoke")

        usb.core.find = forbid_device_enumeration
        AuthorizedWriteSender.send = forbid_sender

        window_state: dict[str, Any] = {}

        def managed_smoke_window(*args: Any, **kwargs: Any) -> Any:
            root = original_tk(*args, **kwargs)
            window_state["root"] = root

            def inspect_and_close() -> None:
                try:
                    root.update_idletasks()
                    window_state["title"] = root.title()
                    if window_state["title"] != "InfoCarry Manager":
                        raise RuntimeError("normal manager window title was not initialized")
                    controls = _inspect_widgets(root)
                    panes = [
                        control
                        for control in controls
                        if str(control.winfo_class()) == "TPanedwindow"
                        and len(control.panes()) == 2
                    ]
                    headings = {
                        str(control.cget("text"))
                        for control in controls
                        if str(control.winfo_class()).endswith("Label")
                    }
                    transfer_buttons = [
                        control
                        for control in controls
                        if str(control.winfo_class()).endswith("Button")
                        and control.cget("text") == "Transfer →"
                    ]
                    guarded_send_buttons = [
                        control
                        for control in controls
                        if str(control.winfo_class()).endswith("Button")
                        and control.cget("text") == "Send to InfoCarry"
                    ]
                    if not panes or not {"LOCAL LIBRARY", "DEVICE LIBRARY"}.issubset(headings):
                        raise RuntimeError("normal manager side-by-side library workspace was not created")
                    if not transfer_buttons:
                        raise RuntimeError("host-only library transfer action was not created")
                    add_buttons = [
                        control
                        for control in controls
                        if str(control.winfo_class()).endswith("Menubutton")
                        and control.cget("text") == "+ Add"
                    ]
                    if len(add_buttons) != 1 or add_buttons[0].instate(["disabled"]):
                        raise RuntimeError("packaged + Add control is not enabled")
                    add_menu = root.nametowidget(str(add_buttons[0].cget("menu")))
                    add_labels = [
                        str(add_menu.entrycget(index, "label"))
                        for index in range(int(add_menu.index("end")) + 1)
                    ]
                    if add_labels != ["Add Files…", "Add Folder…"] or any(
                        str(add_menu.entrycget(index, "state")) != "normal"
                        for index in range(2)
                    ):
                        raise RuntimeError("packaged + Add menu entries are not enabled")
                    menu_bar = root.nametowidget(str(root.cget("menu")))
                    file_entry = next(
                        index
                        for index in range(int(menu_bar.index("end")) + 1)
                        if menu_bar.entrycget(index, "label") == "File"
                    )
                    file_menu = root.nametowidget(
                        str(menu_bar.entrycget(file_entry, "menu"))
                    )
                    if any(
                        str(file_menu.entrycget(index, "state")) != "normal"
                        for index in range(2)
                    ):
                        raise RuntimeError("packaged File-menu Add entries are not enabled")
                    add_menu.invoke(0)
                    add_menu.invoke(1)
                    from infocarry.app_paths import application_paths
                    from infocarry.library import LibraryCatalog, NODE_FILE, NODE_FOLDER

                    catalog = LibraryCatalog(application_paths().library_catalog)
                    imported_file = next(
                        (
                            item
                            for item in catalog.items
                            if item.node_kind == NODE_FILE
                            and Path(item.source_path) == add_file_source.resolve()
                        ),
                        None,
                    )
                    imported_folder = next(
                        (
                            item
                            for item in catalog.roots
                            if item.node_kind == NODE_FOLDER
                            and Path(item.source_path) == add_folder_source.resolve()
                        ),
                        None,
                    )
                    nested_folder = (
                        next(
                            (
                                item
                                for item in catalog.children(imported_folder.item_id)
                                if item.node_kind == NODE_FOLDER
                                and item.source_filename == "nested"
                            ),
                            None,
                        )
                        if imported_folder is not None
                        else None
                    )
                    nested_file = (
                        next(
                            (
                                item
                                for item in catalog.children(nested_folder.item_id)
                                if item.node_kind == NODE_FILE
                                and item.source_filename == "nested.txt"
                            ),
                            None,
                        )
                        if nested_folder is not None
                        else None
                    )
                    if (
                        picker_calls != ["files", "folder"]
                        or imported_file is None
                        or imported_folder is None
                        or nested_folder is None
                        or nested_file is None
                        or add_file_source.read_text(encoding="utf-8")
                        != "Host-only Add Files smoke.\n"
                        or nested_file_source.read_text(encoding="utf-8")
                        != "Host-only nested folder smoke.\n"
                    ):
                        raise RuntimeError("packaged Add pickers did not import the host fixtures safely")
                    window_state["local_library_add"] = {
                        "button": "enabled",
                        "menu_entries": add_labels,
                        "file_menu_entries": "enabled",
                        "pickers_opened": picker_calls,
                        "files_imported": 1,
                        "nested_folder_imported": True,
                        "source_files_unchanged": True,
                    }
                    if not guarded_send_buttons or any(
                        str(button.cget("state")) != "disabled"
                        for button in guarded_send_buttons
                    ):
                        raise RuntimeError("legacy live-send control was not kept disabled")
                    window_state["workspace"] = "local_and_device_library"
                    window_state["host_only_transfer"] = "created"
                    window_state["guarded_send_control"] = "disabled"
                except BaseException as exc:
                    window_state["error"] = f"{type(exc).__name__}: {exc}"
                finally:
                    root.after(50, close_through_window_protocol)

            def close_through_window_protocol() -> None:
                try:
                    command = root.protocol("WM_DELETE_WINDOW")
                    if command:
                        root.tk.call(command)
                    else:
                        root.destroy()
                except BaseException as exc:
                    window_state["error"] = f"clean shutdown failed: {type(exc).__name__}: {exc}"
                    try:
                        root.destroy()
                    except Exception:
                        pass

            root.after(600, inspect_and_close)
            return root

        try:
            report["checks"]["host_content"] = _run_host_workflow_checks()
            tkinter.Tk = managed_smoke_window
            from infocarry.library_transfer_runtime_provider import launch_production_manager

            launch_production_manager()
        finally:
            tkinter.Tk = original_tk
            AuthorizedWriteSender.send = original_sender
            usb.core.find = original_usb_find
            filedialog_module.askopenfilenames = original_askopenfilenames
            filedialog_module.askdirectory = original_askdirectory
        if window_state.get("error"):
            raise RuntimeError(window_state["error"])
        if window_state.get("title") != "InfoCarry Manager":
            raise RuntimeError("main manager window was not observed")
        if window_state.get("guarded_send_control") != "disabled":
            raise RuntimeError("guarded transfer control was not confirmed disabled")
        report["checks"]["main_manager_window"] = {
            "title": window_state["title"],
            "opened": True,
            "workspace": window_state["workspace"],
            "host_only_transfer": window_state["host_only_transfer"],
            "guarded_send_control": "disabled",
            "local_library_add": window_state["local_library_add"],
            "closed_cleanly": True,
        }
        if not (state_root / "execution-claims.sqlite3").is_file():
            raise RuntimeError("normal manager safety state did not initialize in the isolated profile")
        measured_safety_counters = _read_safety_counters(state_root)
        if any(isolation_counters.values()):
            raise RuntimeError(f"forbidden device/sender path was reached: {isolation_counters}")
        if any(measured_safety_counters.values()):
            raise RuntimeError(f"persistent write-safety counters were nonzero: {measured_safety_counters}")

        locked_appdata = smoke_root / "write-locked-appdata" / "Roaming"
        os.environ["APPDATA"] = str(locked_appdata)
        from infocarry.app_paths import application_paths as current_application_paths
        from infocarry.device_model_profile import VNW_V15_PROFILE
        from infocarry.indeterminate_write_lock import PersistentIndeterminateWriteLock
        from infocarry.library_transfer_execution import LibraryTransferExecutionFacade
        import infocarry.library_transfer_runtime_provider as runtime_provider_module

        locked_paths = current_application_paths()
        if not locked_paths.safety_root.is_relative_to(locked_appdata.resolve()):
            raise RuntimeError("locked-state smoke safety files escaped the isolated profile")
        locked_store = PersistentIndeterminateWriteLock(
            locked_paths.indeterminate_write_lock
        )
        locked_store.record_indeterminate(
            reason="host-only packaged Add-control regression fixture",
            evidence_root=str(smoke_root / "locked-state-evidence"),
            model_key=VNW_V15_PROFILE.model_key,
            incident_id="host-only-add-state-smoke",
            attempt_id="host-only-add-state-smoke-01",
        )
        locked_bytes_before = locked_paths.indeterminate_write_lock.read_bytes()
        unavailable_facades: list[LibraryTransferExecutionFacade] = []

        def create_unavailable_facade() -> LibraryTransferExecutionFacade:
            facade = LibraryTransferExecutionFacade()
            unavailable_facades.append(facade)
            return facade

        original_facade_factory = (
            runtime_provider_module.create_production_library_transfer_facade
        )
        runtime_provider_module.create_production_library_transfer_facade = (
            create_unavailable_facade
        )
        locked_window_state: dict[str, Any] = {}
        usb.core.find = forbid_device_enumeration
        AuthorizedWriteSender.send = forbid_sender

        def managed_locked_smoke_window(*args: Any, **kwargs: Any) -> Any:
            root = original_tk(*args, **kwargs)

            def inspect_and_close() -> None:
                try:
                    root.update_idletasks()
                    controls = _inspect_widgets(root)
                    add_buttons = [
                        control
                        for control in controls
                        if str(control.winfo_class()).endswith("Menubutton")
                        and control.cget("text") == "+ Add"
                    ]
                    if len(add_buttons) != 1 or add_buttons[0].instate(["disabled"]):
                        raise RuntimeError(
                            "+ Add was disabled by the installation-wide write lock"
                        )
                    add_menu = root.nametowidget(str(add_buttons[0].cget("menu")))
                    if any(
                        str(add_menu.entrycget(index, "state")) != "normal"
                        for index in range(2)
                    ):
                        raise RuntimeError(
                            "+ Add menu entries were disabled by the installation-wide write lock"
                        )
                    locked_window_state["add_control"] = "enabled"
                    locked_window_state["menu_entries"] = "enabled"
                except BaseException as exc:
                    locked_window_state["error"] = f"{type(exc).__name__}: {exc}"
                finally:
                    root.after(50, close_locked_window)

            def close_locked_window() -> None:
                try:
                    command = root.protocol("WM_DELETE_WINDOW")
                    if command:
                        root.tk.call(command)
                    else:
                        root.destroy()
                    locked_window_state["closed_cleanly"] = True
                except BaseException as exc:
                    locked_window_state["error"] = (
                        f"clean shutdown failed: {type(exc).__name__}: {exc}"
                    )
                    try:
                        root.destroy()
                    except Exception:
                        pass

            root.after(500, inspect_and_close)
            return root

        try:
            tkinter.Tk = managed_locked_smoke_window
            from infocarry.library_transfer_runtime_provider import launch_production_manager

            launch_production_manager()
        finally:
            tkinter.Tk = original_tk
            runtime_provider_module.create_production_library_transfer_facade = (
                original_facade_factory
            )
            AuthorizedWriteSender.send = original_sender
            usb.core.find = original_usb_find
            os.environ["APPDATA"] = str(profile_root)

        if locked_window_state.get("error") or not locked_window_state.get(
            "closed_cleanly"
        ):
            raise RuntimeError(
                locked_window_state.get("error", "locked-state window did not close")
            )
        if (
            len(unavailable_facades) != 1
            or unavailable_facades[0].can_prepare_live
            or unavailable_facades[0].operation_binding is not None
        ):
            raise RuntimeError("unavailable-runtime fixture unexpectedly enabled live transfer")
        if locked_paths.indeterminate_write_lock.read_bytes() != locked_bytes_before:
            raise RuntimeError("packaged startup mutated the pre-existing write lock")
        locked_counters = _read_safety_counters(locked_paths.safety_root)
        if locked_counters["claims_consumed"] or locked_counters["sender_marker_rows"]:
            raise RuntimeError("locked-state Add smoke created a claim or sender marker")
        if any(isolation_counters.values()):
            raise RuntimeError(f"locked-state host-only smoke reached a device path: {isolation_counters}")
        report["checks"]["add_under_lock_and_unavailable_runtime"] = {
            **locked_window_state,
            "runtime_provider_available": False,
            "operation_binding_present": False,
            "write_lock_unchanged": True,
            "claims_created": 0,
            "sender_markers_created": 0,
        }
        report["checks"]["usb_backend"]["device_enumeration_calls"] = isolation_counters[
            "device_enumeration_calls"
        ]
        report["physical_operation_counters"] = {
            "device_enumeration_calls": isolation_counters["device_enumeration_calls"],
            "sender_calls": isolation_counters["sender_calls"],
            "real_0x101b": isolation_counters["sender_calls"],
            "claims_consumed": measured_safety_counters["claims_consumed"],
            "sender_marker_mutations": measured_safety_counters["sender_marker_rows"],
            "installation_lock_mutations": measured_safety_counters[
                "installation_lock_mutations"
            ],
        }
        report["status"] = "passed"
        return_code = 0
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        return_code = 1
    _write_report(report_path, report)
    return return_code


def main() -> int:
    arguments = sys.argv[1:]
    if not arguments:
        from infocarry.library_transfer_runtime_provider import launch_production_manager

        launch_production_manager()
        return 0
    if len(arguments) == 2 and arguments[0] == "--runtime-smoke":
        return _run_packaged_runtime_smoke(Path(arguments[1]))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
