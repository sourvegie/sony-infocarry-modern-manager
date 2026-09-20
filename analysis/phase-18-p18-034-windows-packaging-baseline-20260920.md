# P18-034 — Windows Packaging & Deployment Baseline

- Date: 2026-09-20
- Risk: R2, host/deployment only
- Canonical base: `dc3f840657a113b107891d4f9b619c5903edf73e`
- Branch: `task/P18-034-windows-packaging-baseline`

## Scope and outcome

This task packages the existing ttk Manager; it adds no parallel UI, USB
protocol, sender, authorization, capability, or device-operation path. The
target is a Windows x64 one-folder application with the obvious launcher
`InfoCarry Manager.exe`. Tk 9 remains mandatory. No physical device is used.

The implementation is published in PR #61, still open and unmerged. Exact
head `fde9e407d6418e5bcd1d90e39418be67d74c553a` passed Windows
package/runtime smoke and the Python 3.12 offline suite on macOS and Windows.
The three P2 findings from review of the preceding code checkpoint were
corrected: smoke counters are measured with active enumeration/sender guards,
the isolated SQLite handle is explicitly closed, and this record's whitespace
was cleaned. A fresh review of `fde9e40` found one P2 stale-status wording in
this record and no P0/P1 findings; this update closes that documentation
finding. The only change after the tested code checkpoint is this
documentation correction; no executable or packaging code changed.

The first PR-triggered Windows package run, [35489216721](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35489216721),
stopped before build because `actions/setup-python` did not have Python
3.15.0rc2 for Windows Server 2025 in its distribution manifest. No build or
smoke step ran. The workflow was changed to download the official Python.org
x64 installer and verify its published SHA-256 before installation. In run
[35489363904](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35489363904),
that exact runtime and Tk 9 check passed and PyInstaller produced the onedir
package. The smoke step did not complete: PowerShell received no
`$LASTEXITCODE` from the GUI-subsystem executable. The workflow now launches
it with `Start-Process -Wait -PassThru` and checks the returned process exit
code. The subsequent Windows package run passed, as recorded below.

## Packaging decision

Use PyInstaller 6.22.3 in `onedir` mode. Python 3.12's official Windows
distribution provides Tcl/Tk 8.6, which does not satisfy the existing Tk >=9
runtime guard. The candidate Windows build therefore pins the official
CPython 3.15.0rc2 x64 distribution, whose Tcl/Tk 9 runtime is checked both at
build time and from the frozen application. Python 3.15.0rc2 is a release
candidate, not a final stable release; this establishes a testable packaging
baseline only. Rebuild and rerun the smoke suite against Python 3.15.0 final
before treating the runtime as a stable release target.

Build from the repository root in PowerShell with the matching Python
distribution active:

```powershell
py -3.15 -m venv .venv-windows
.\.venv-windows\Scripts\Activate.ps1
.\scripts\build_windows_package.ps1
```

The script pins packaging dependencies from
`requirements-windows-packaging.txt`, checks Python/Tk/architecture, runs
`pip check`, and writes the one-folder package to
`dist\InfoCarry Manager\`. Distribute that complete folder, not just the EXE.
The package includes build metadata and third-party notices.

## Tk and native USB runtime

The Windows bundle uses the Tcl/Tk files collected by PyInstaller from the
selected Python distribution. The frozen smoke creates a real Tk root,
reports Tcl's runtime patchlevel and Tk's loaded package version, checks
Tcl's `init.tcl` through the active Tcl resource path, opens the normal ttk
Manager window, and closes it through its normal window protocol. It also
checks that `python` and `python3` are absent from `PATH` while the packaged
application runs.

PyUSB is a wrapper and needs a native libusb library on Windows. The pinned
`libusb-package` DLL is included in the one-folder distribution; the Windows
backend passes that package's explicit `find_library` callback to PyUSB rather
than depending on a machine-wide DLL search path. The smoke loads the DLL and
native backend without enumerating USB devices. This does not install a
device driver, establish legacy Sony driver compatibility, or validate a
physical connection. Driver packaging/installation and hardware checks remain
out of scope.

The runtime smoke exercises Add Content and TXT/BMP/EPUB preparation, preview,
readiness review, both exact reviewed VNW-V15 shapes, unsupported-shape
blocking, VNW-V10 exclusion, the disabled Send control, and clean shutdown.
It forbids USB enumeration and sender entry during the GUI smoke and checks
that its isolated application-data profile has no consumed claims, sender
marker, or indeterminate-write lock. These are host checks, not physical
device evidence.

## ARM64 assessment

Classification: `BLOCKED_BY_RUNTIME_OR_DEPENDENCY` for a native ARM64 package
in this milestone.

- Python 3.15.0rc2 has a Windows ARM64 installer, marked Experimental, and an
  ARM64 embeddable package. A final product runtime still needs architecture-
  specific Tk 9 build/smoke confirmation.
- PyInstaller supports Windows packaging and documents building a Windows
  ARM64 bootloader with an ARM toolchain. This does not establish that the
  complete application dependency set is ready on ARM64.
- PyUSB itself is Python code, but the chosen pinned
  `libusb-package==1.0.30.0` release has Windows x64 and x86 wheels, no Windows
  ARM64 wheel, and no source distribution. Therefore its pinned bundled
  libusb runtime cannot be produced as a native ARM64 package by this build.
- An x64 package running under Windows emulation is not native ARM64 support.
  Do not advertise it as such. Keep ARM64 as a separate follow-up after a
  reviewed native libusb distribution/build source is selected and the full
  Tk/PyInstaller/application smoke passes on ARM64.

## CI, package artifact, and review

Windows package workflow run [35489870486](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35489870486)
passed on `fde9e407d6418e5bcd1d90e39418be67d74c553a`. It published artifact
`InfoCarry-Manager-windows-x64-py3.15.0rc2-tk9` (artifact ID `10598951090`,
19,311,017 bytes, SHA-256
`257b212a71907e833239dda2e47f4ad2762d8aa507ab48da5e3141ecdbd04656`),
retained until 2026-10-20. The report confirms Python 3.15.0rc2 AMD64,
Tkinter 9.0 and Tcl/Tk 9.0.4, `init.tcl` found through Tcl zipfs, no
`python`/`python3` on `PATH`, successful PyUSB/libusb 1.3.1/1.0.30.0 load,
normal Manager window open/close, disabled Send, and passing content/profile
checks. Enumeration, sender, real `0x101b`, claims, marker, and installation
lock counters are all zero.

Offline tests run [35489870404](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35489870404)
passed on both macOS and Windows. Each ran 891 tests: macOS reported 5
documented skips; Windows reported 6 platform/evidence-dependent skips. The
earlier Windows `WinError 32` test-cleanup failure was fixed by explicitly
closing the SQLite connection and did not recur. PR #61 remains open and
unmerged for PM acceptance. These CI results cover code checkpoint `fde9e40`;
the later status/analysis correction is documentation-only.

Manual validation still recommended after PM acceptance: launch the extracted
folder on a clean supported Windows x64 machine, check scaling and file
dialogs, and separately follow an approved procedure for any real device
interaction. CI proves only its runner's build and host-only smoke.

## Source references

- Python 3.15.0rc2 Windows installers, ARM64 Experimental label, and release
  status: [Python.org release page](https://www.python.org/downloads/release/python-3150rc2/).
- Python's documented quiet installer options include `TargetDir`,
  `Include_tcltk`, and `Include_pip`:
  [Python on Windows](https://docs.python.org/3.14/using/windows.html).
- Python 3.15 Tkinter documentation states that official Python binary
  releases bundle Tcl/Tk 9.0:
  [Python 3.15 `tkinter` documentation](https://docs.python.org/3.15/library/tkinter.html).
- The Python 3.12 Windows binary runtime bundles Tcl/Tk 8.6:
  [Python 3.12 `tkinter` documentation](https://docs.python.org/3.12/library/tkinter.html).
- PyInstaller 6.22 changelog documents support for Tcl/Tk 9 embedded data and
  cites the Python.org Windows Python 3.15 builds:
  [PyInstaller changelog](https://pyinstaller.org/en/latest/CHANGES.html).
- Exact `libusb-package` release file list and its backend API:
  [libusb-package 1.0.30.0 on PyPI](https://pypi.org/project/libusb-package/1.0.30.0/).
- PyUSB's Windows backend/native DLL requirements:
  [PyUSB FAQ](https://github.com/pyusb/pyusb/blob/master/docs/faq.rst) and
  [libusb1 backend](https://github.com/pyusb/pyusb/blob/master/usb/backend/libusb1.py).
- PyInstaller documents the Windows ARM64 bootloader build path:
  [PyInstaller bootloader build documentation](https://pyinstaller.org/en/stable/bootloader-building.html).
