# PyInstaller onedir bundle for the normal ttk manager on Apple Silicon.
# The build interpreter supplies the bundled CPython and Tcl/Tk runtime; this
# spec adds no alternate UI, USB, or device-operation path.

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


ROOT = Path(SPECPATH).parents[1]
ENTRY_POINT = ROOT / "scripts" / "macos_manager_entry.py"
NOTICES = ROOT / "packaging" / "macos" / "THIRD_PARTY_NOTICES.txt"

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
    # LaunchServices resolves CFBundleExecutable more reliably when it is a
    # single path component without spaces. The visible .app name stays human
    # friendly below.
    name="InfoCarryManager",
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
app = BUNDLE(
    coll,
    name="InfoCarry Manager.app",
    icon=None,
    bundle_identifier="com.sourvegie.infocarry-manager",
    info_plist={
        "CFBundleDisplayName": "InfoCarry Manager",
        "CFBundleName": "InfoCarry Manager",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "LSApplicationCategoryType": "public.app-category.utilities",
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
        "NSRequiresAquaSystemAppearance": False,
        "NSHumanReadableCopyright": "Copyright © InfoCarry Toolkit contributors",
    },
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)
