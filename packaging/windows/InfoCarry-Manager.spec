# PyInstaller onedir build for the normal ttk manager.  The application uses
# the existing source package; this spec adds no alternate Windows UI or USB
# protocol path.

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


ROOT = Path(SPECPATH).parents[1]
ENTRY_POINT = ROOT / "scripts" / "windows_manager_entry.py"
NOTICES = ROOT / "packaging" / "windows" / "THIRD_PARTY_NOTICES.txt"

usb_datas, usb_binaries, usb_hiddenimports = collect_all("libusb_package")
usb_datas += copy_metadata("libusb-package")
usb_datas += copy_metadata("PyUSB")
usb_datas += copy_metadata("PyInstaller")
application_datas = [
    (str(ROOT / "LICENSE"), "."),
    (str(NOTICES), "."),
]

a = Analysis(
    [str(ENTRY_POINT)],
    pathex=[str(ROOT / "src")],
    binaries=usb_binaries,
    datas=[*usb_datas, *application_datas],
    hiddenimports=usb_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="InfoCarry Manager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="InfoCarry Manager",
)
