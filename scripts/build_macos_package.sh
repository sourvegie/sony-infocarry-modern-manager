#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPOSITORY_ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "The macOS package must be built on macOS." >&2
  exit 1
fi

ARCHITECTURE="$(/usr/bin/uname -m)"
if [[ "$ARCHITECTURE" != "arm64" ]]; then
  echo "The P18-035 package target is Apple Silicon arm64; found $ARCHITECTURE." >&2
  exit 1
fi

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Build interpreter '$PYTHON' was not found. Select a Python 3.12+ arm64 interpreter with Tcl/Tk 9." >&2
  exit 1
fi

PYTHON_VERSION="$("$PYTHON" -c 'import platform; print(platform.python_version())')"
PYTHON_IMPLEMENTATION="$("$PYTHON" -c 'import platform; print(platform.python_implementation())')"
PYTHON_ARCH="$("$PYTHON" -c 'import platform; print(platform.machine())')"
if [[ "$PYTHON_IMPLEMENTATION" != "CPython" ]]; then
  echo "A CPython build interpreter is required; found $PYTHON_IMPLEMENTATION." >&2
  exit 1
fi
"$PYTHON" -c 'import sys; assert sys.version_info >= (3, 12), sys.version'
if [[ "$PYTHON_ARCH" != "arm64" && "$PYTHON_ARCH" != "aarch64" ]]; then
  echo "The build interpreter must run as arm64; found $PYTHON_ARCH." >&2
  exit 1
fi

TK_VERSION="$("$PYTHON" -c 'import tkinter; print(f"{tkinter.TkVersion:.1f}")')"
"$PYTHON" -c 'import tkinter; assert tkinter.TkVersion >= 9.0, f"Tcl/Tk 9.0 or newer is required; found {tkinter.TkVersion}"'

if [[ "${1:-}" != "--skip-install" ]]; then
  "$PYTHON" -m pip install --disable-pip-version-check --requirement requirements-macos-packaging.txt
fi
"$PYTHON" -m pip check

# Keep PyInstaller's cache inside ignored build output. A Finder-oriented app
# build must not depend on or write a shared user-level support directory.
export PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$REPOSITORY_ROOT/build/pyinstaller-config}"
mkdir -p "$PYINSTALLER_CONFIG_DIR"
"$PYTHON" -m PyInstaller --clean --noconfirm packaging/macos/InfoCarry-Manager.spec

APP_PATH="$REPOSITORY_ROOT/dist/InfoCarry Manager.app"
EXECUTABLE="$APP_PATH/Contents/MacOS/InfoCarryManager"
INFO_PLIST="$APP_PATH/Contents/Info.plist"
if [[ ! -d "$APP_PATH" || ! -x "$EXECUTABLE" || ! -f "$INFO_PLIST" ]]; then
  echo "The expected onedir application bundle was not produced at $APP_PATH." >&2
  exit 1
fi
/usr/bin/plutil -lint "$INFO_PLIST"

INFOCARRY_APP_PATH="$APP_PATH" "$PYTHON" - <<'PY'
import json
import os
from importlib.metadata import version
from pathlib import Path
import platform
import tkinter

app = Path(os.environ["INFOCARRY_APP_PATH"])
resource_metadata = app / "Contents" / "Resources" / "BUILD-INFO.json"
resource_metadata.parent.mkdir(parents=True, exist_ok=True)
import libusb_package

library = libusb_package.get_library_path()
if library is None or not Path(library).is_file():
    raise SystemExit("libusb-package did not locate its bundled native library")

info = {
    "artifact": app.name,
    "package_layout": "onedir macOS application bundle (Contents/MacOS + Contents/Frameworks)",
    "architecture": platform.machine(),
    "python_version": platform.python_version(),
    "python_implementation": platform.python_implementation(),
    "tcl_tk_binding_version": f"{tkinter.TclVersion:.1f}/{tkinter.TkVersion:.1f}",
    "pyinstaller_version": version("PyInstaller"),
    "pyusb_version": version("PyUSB"),
    "libusb_package_version": version("libusb-package"),
    "bundled_libusb_library": Path(library).name,
    "source_entry_point": "scripts/macos_manager_entry.py",
    "resource_root": "Contents/Frameworks/_internal",
    "bundle_identifier": "com.sourvegie.infocarry-manager",
    "signing": "PyInstaller local ad-hoc code signature; no Developer ID or notarization",
    "notarized": False,
}
resource_metadata.write_text(
    json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps(info, indent=2, sort_keys=True))
PY

# Build metadata must be in place before signing because bundle resources are
# part of the code signature. Use a local ad-hoc signature for owner builds;
# public distribution still requires Developer ID signing and notarization.
/usr/bin/codesign --force --deep --sign - "$APP_PATH"
/usr/bin/codesign --verify --deep --strict --verbose=2 "$APP_PATH"

echo "macOS application created: $APP_PATH"
echo "Build metadata: $APP_PATH/Contents/Resources/BUILD-INFO.json"
