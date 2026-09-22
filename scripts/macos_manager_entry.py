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
