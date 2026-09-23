"""Packaged macOS entry point for the normal ttk InfoCarry Manager."""

from __future__ import annotations

import json
import os
from importlib.metadata import version
from pathlib import Path
import platform
import shutil
import sqlite3
import sys
from typing import Any


def _write_report(path: Path, value: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _inspect_widgets(widget: Any) -> list[Any]:
    children = list(widget.winfo_children())
    for child in tuple(children):
        children.extend(_inspect_widgets(child))
    return children


def _read_safety_counters(state_root: Path) -> dict[str, int]:
    """Read only the isolated smoke profile's persistent safety database."""

    claim_store = state_root / "execution-claims.sqlite3"
    claims_consumed = 0
    sender_markers = 0
    if claim_store.exists():
        connection = sqlite3.connect(claim_store.as_uri() + "?mode=ro", uri=True)
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
        "installation_lock_present": int(
            (state_root / "indeterminate-write-lock.json").exists()
        ),
    }


def _run_packaged_runtime_smoke(report_path: Path) -> int:
    report_path = report_path.expanduser().resolve()
    report: dict[str, Any] = {
        "status": "failed",
        "frozen": bool(getattr(sys, "frozen", False)),
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "checks": {},
    }
    return_code = 1
    try:
        if not getattr(sys, "frozen", False):
            raise RuntimeError("runtime smoke must execute inside the frozen application")
        if sys.platform != "darwin":
            raise RuntimeError(f"expected a macOS runtime, found {sys.platform}")
        if platform.machine().casefold() not in {"arm64", "aarch64"}:
            raise RuntimeError(f"expected Apple Silicon arm64, found {platform.machine()}")

        # LaunchServices controls the app process environment, so use a
        # profile beside the report and a Unicode working directory to verify
        # the packaged app never depends on the owner's real profile or CWD.
        smoke_root = report_path.parent
        profile_root = smoke_root / "profile"
        working_directory = smoke_root / "作業 フォルダー"
        profile_root.mkdir(parents=True, exist_ok=True)
        working_directory.mkdir(parents=True, exist_ok=True)
        os.environ["HOME"] = str(profile_root)
        os.chdir(working_directory)

        python_on_path = {
            command: shutil.which(command) for command in ("python", "python3", "python3.15")
        }
        # Finder's standard PATH can contain an Apple/Xcode python3 shim on
        # some machines. Record it for the report, while the frozen app itself
        # is launched as the entry executable and does not invoke Python by
        # name or require the build interpreter to be on PATH.
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

        from infocarry.app_paths import application_paths, resource_path

        bundled_license = resource_path("LICENSE")
        if not bundled_license.is_file():
            raise RuntimeError(f"bundled LICENSE was not found: {bundled_license}")
        bundled_notices = resource_path("packaging", "macos", "THIRD_PARTY_NOTICES.txt")
        if not bundled_notices.is_file():
            # The spec intentionally places the notice at the bundle resource
            # root, independently of its source-tree path.
            bundled_notices = resource_path("THIRD_PARTY_NOTICES.txt")
        if not bundled_notices.is_file():
            raise RuntimeError("third-party notices were not found in the app resources")

        runtime_details: dict[str, Any] = {}
        resource_window = tkinter.Tk()
        try:
            resource_window.withdraw()
            resource_window.update_idletasks()
            runtime_details = {
                "tcl_runtime_patchlevel": str(
                    resource_window.tk.call("info", "patchlevel")
                ),
                "tk_runtime_package": str(
                    resource_window.tk.call("package", "require", "Tk")
                ),
                "tcl_library": str(resource_window.tk.call("info", "library")),
            }
            runtime_details["tcl_init_resource_found"] = bool(
                int(
                    resource_window.tk.call(
                        "file",
                        "exists",
                        resource_window.tk.call(
                            "file", "join", runtime_details["tcl_library"], "init.tcl"
                        ),
                    )
                )
            )
        finally:
            resource_window.destroy()
        if not runtime_details["tcl_init_resource_found"]:
            raise RuntimeError(
                "Tcl init.tcl was not found through Tcl's resource path: "
                f"{runtime_details['tcl_library']}"
            )
        if tkinter.TkVersion < 9.0:
            raise RuntimeError(f"the packaged Tk binding is older than 9: {tkinter.TkVersion}")
        runtime_details["tkinter_compiled_version"] = tkinter.TkVersion
        runtime_details["python_runtime_check"] = runtime.description
        report["checks"]["frozen_resources"] = {
            "root": str(resource_root),
            "license": str(bundled_license),
            "third_party_notices": str(bundled_notices),
        }
        report["checks"]["tcl_tk"] = runtime_details

        import infocarry.desktop_ttk  # noqa: F401 - verify the production UI import graph
        import usb.core  # noqa: F401 - verify PyUSB was bundled
        import libusb_package
        from infocarry.usb_access import _packaged_libusb_backend

        library_path = libusb_package.get_library_path()
        if library_path is None or not Path(library_path).is_file():
            raise RuntimeError("the bundled libusb 1.0 dylib was not located")
        backend = _packaged_libusb_backend(required=True)
        if backend is None or not hasattr(backend, "lib"):
            raise RuntimeError("the packaged PyUSB/libusb backend did not load")
        report["checks"]["usb_backend"] = {
            "pyusb_version": version("PyUSB"),
            "libusb_package_version": version("libusb-package"),
            "bundled_library": str(library_path),
            "native_backend_loaded": True,
        }

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

        profile_root = Path.home().expanduser().resolve()
        paths = application_paths()
        if not paths.safety_root.is_relative_to(profile_root):
            raise RuntimeError("packaged smoke safety state is outside its temporary HOME")
        if paths.safety_root.exists():
            raise RuntimeError("runtime smoke requires a fresh temporary HOME profile")
        if paths.root.exists():
            raise RuntimeError("runtime smoke requires a fresh temporary application data root")

        isolation_counters = {"device_enumeration_calls": 0, "sender_calls": 0}
        original_find = usb.core.find

        def forbid_device_enumeration(*_args: Any, **_kwargs: Any) -> Any:
            isolation_counters["device_enumeration_calls"] += 1
            raise RuntimeError("USB enumeration is forbidden in the packaged host-only smoke")

        usb.core.find = forbid_device_enumeration
        from infocarry.write_protocol import AuthorizedWriteSender

        original_sender = AuthorizedWriteSender.send

        def forbid_sender(*_args: Any, **_kwargs: Any) -> Any:
            isolation_counters["sender_calls"] += 1
            raise RuntimeError("the sender is forbidden in the packaged host-only smoke")

        AuthorizedWriteSender.send = forbid_sender

        original_tk = tkinter.Tk
        window_state: dict[str, Any] = {}

        def managed_smoke_window(*args: Any, **kwargs: Any) -> Any:
            root = original_tk(*args, **kwargs)

            def inspect_and_close() -> None:
                try:
                    root.update_idletasks()
                    window_state["title"] = root.title()
                    if window_state["title"] != "InfoCarry Manager":
                        raise RuntimeError("normal manager window title was not initialized")
                    if int(root.winfo_width()) <= 1 or int(root.winfo_height()) <= 1:
                        raise RuntimeError("normal manager window has no usable dimensions")
                    controls = _inspect_widgets(root)
                    panes = [
                        widget
                        for widget in controls
                        if str(widget.winfo_class()) == "TPanedwindow"
                        and len(widget.panes()) == 2
                    ]
                    headings = {
                        str(widget.cget("text"))
                        for widget in controls
                        if str(widget.winfo_class()).endswith("Label")
                    }
                    transfer_buttons = [
                        widget
                        for widget in controls
                        if str(widget.winfo_class()).endswith("Button")
                        and widget.cget("text") == "Transfer →"
                    ]
                    guarded_send_buttons = [
                        widget
                        for widget in controls
                        if str(widget.winfo_class()).endswith("Button")
                        and widget.cget("text") == "Send to InfoCarry"
                    ]
                    if not panes or not {"LOCAL LIBRARY", "DEVICE LIBRARY"}.issubset(headings):
                        raise RuntimeError("normal manager side-by-side library workspace was not created")
                    if not transfer_buttons:
                        raise RuntimeError("host-only library transfer action was not created")
                    add_buttons = [
                        widget
                        for widget in controls
                        if str(widget.winfo_class()).endswith("Menubutton")
                        and widget.cget("text") == "+ Add"
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
                    window_state["opened"] = True
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
                    window_state["closed_cleanly"] = True
                except BaseException as exc:
                    window_state["error"] = f"clean shutdown failed: {type(exc).__name__}: {exc}"
                    try:
                        root.destroy()
                    except Exception:
                        pass

            root.after(750, inspect_and_close)
            return root

        try:
            tkinter.Tk = managed_smoke_window
            from infocarry.library_transfer_runtime_provider import launch_production_manager

            launch_production_manager()
        finally:
            tkinter.Tk = original_tk
            AuthorizedWriteSender.send = original_sender
            usb.core.find = original_find
            filedialog_module.askopenfilenames = original_askopenfilenames
            filedialog_module.askdirectory = original_askdirectory

        if window_state.get("error"):
            raise RuntimeError(window_state["error"])
        if not window_state.get("opened") or not window_state.get("closed_cleanly"):
            raise RuntimeError("the manager window did not complete its open/close smoke")
        report["checks"]["main_manager_window"] = window_state

        if not paths.execution_claims_database.is_file():
            raise RuntimeError("the isolated application safety database was not initialized")
        safety_counters = _read_safety_counters(paths.safety_root)
        if any(isolation_counters.values()):
            raise RuntimeError(f"a forbidden USB/write path was reached: {isolation_counters}")
        if any(safety_counters.values()):
            raise RuntimeError(f"persistent write-safety counters were nonzero: {safety_counters}")

        locked_home = smoke_root / "write-locked-home"
        os.environ["HOME"] = str(locked_home)
        from infocarry.app_paths import application_paths as current_application_paths
        from infocarry.device_model_profile import VNW_V15_PROFILE
        from infocarry.indeterminate_write_lock import PersistentIndeterminateWriteLock
        from infocarry.library_transfer_execution import LibraryTransferExecutionFacade
        import infocarry.library_transfer_runtime_provider as runtime_provider_module

        locked_paths = current_application_paths()
        if not locked_paths.safety_root.is_relative_to(locked_home.resolve()):
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
                        widget
                        for widget in controls
                        if str(widget.winfo_class()).endswith("Menubutton")
                        and widget.cget("text") == "+ Add"
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
            usb.core.find = original_find
            os.environ["HOME"] = str(profile_root)

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
        report["application_data"] = {
            "application_root": str(paths.root),
            "safety_root": str(paths.safety_root),
            "prepared_content_root": str(paths.prepared_content_root),
            "backup_root": str(paths.backup_root),
        }
        report["physical_operation_counters"] = {
            "device_enumeration_calls": isolation_counters["device_enumeration_calls"],
            "sender_calls": isolation_counters["sender_calls"],
            "real_0x101b": isolation_counters["sender_calls"],
            "claims_consumed": safety_counters["claims_consumed"],
            "sender_marker_rows": safety_counters["sender_marker_rows"],
            "installation_lock_present": safety_counters["installation_lock_present"],
        }
        report["status"] = "passed"
        return_code = 0
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
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
