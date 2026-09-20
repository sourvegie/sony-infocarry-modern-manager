# P18-035 — macOS first-class owner app and read-only Device Home

Date: 2026-09-20
Branch: `task/P18-035-macos-owner-app-device-home`
Canonical base: `3b6697eac01b6c35d588d163325bedb99ddf76ff`
Risk: R2 product/runtime work; R3-quality review required for persistent
write-safety path changes.
State: PR #62 is open against the exact canonical base. The final code commit
is `47b2dde`; record cleanup is `6672f68`. Offline run 190 passed on macOS and
Windows, macOS package run 8 and Windows package run 14 passed, and independent
exact-head review approved `6672f68` with no actionable findings. PM acceptance
remains pending.

## Packaging method and runtime

The build uses PyInstaller 6.22.3 to create an Apple Silicon arm64 onedir
bundle at `dist/InfoCarry Manager.app`. The main executable is
`Contents/MacOS/InfoCarryManager`; the visible app name remains
`InfoCarry Manager`. PyInstaller places native libraries in
`Contents/Frameworks` and bundled data and Tcl/Tk scripts in
`Contents/Resources`. The spec bundles
PyUSB 1.3.1, `libusb-package` 1.0.30.0 and its `libusb-1.0.dylib`, plus the
project license and a third-party notices file. No Homebrew or activated
virtual environment is needed to run the packaged app.

The local artifact was built with CPython 3.12.14, Tcl/Tk bindings 9.0/9.0,
and arm64 PyInstaller 6.22.3. Its `Contents/Resources/BUILD-INFO.json` records
the actual tool and dependency versions, layout, architecture, and signing
status. The GitHub macOS workflow installs the official arm64 CPython 3.14.7
distribution with Tcl/Tk 9 before building its independent CI artifact.

The bundle receives a local ad-hoc signature after metadata is written;
`codesign --verify --deep --strict` reports it valid. It is not Developer ID
signed or notarized. Keep Gatekeeper enabled. Public distribution will require
Developer ID signing, hardened-runtime configuration, notarization, and a
stapled ticket.

## Application data and safety state

The central platform abstraction retains the existing macOS root
`~/Library/Application Support/SonyInfoCarryModernManager/`. Durable execution
claims and sender-start markers remain in the historical
`execution-claims.sqlite3`; the installation-wide lock remains at
`indeterminate-write-lock.json`. There is no automatic safety-state move or
second store. The app-managed library catalog, complete backups, evidence,
prepared content/source metadata, and disposable preview cache use named
subpaths under that root.

Before constructing the one application-wide write-safety owner, the app
checks for safety files in proposed `InfoCarry` alternate roots. Conflicting
alternate state, inaccessible state, corrupt state, or an existing historical
support root with a missing claims database blocks owner creation without
replacing or deleting the historical state. Read-only Device Home remains
available with a visible actionable safety notice initialized at launch. The
device state is labeled unchecked until the owner requests a read-only refresh;
the UI does not claim a disconnected result before discovery. The actual
legacy location was checked read-only; no state was moved or changed. Tests
cover fresh/restarted profiles, clear and active
locks, abandoned sender markers, corrupt/missing databases, inaccessible
paths, alternate-root disagreement, and replacement/update behavior at the
stable path.

## Device Home, capacity, and backups

Device Home is the first tab. Discovery is scoped to Sony VID devices; only a
single exact reviewed VNW-V15 session reaches the existing read-only `0x0019`
capacity query. Unsupported Sony devices, multiple devices, disconnects,
backend/access/busy failures, and malformed responses have separate calm
states and retain technical details behind the explicit control. VID/PID and
bus/address are presented only as session observations; no unique physical
identity is claimed. VNW-V10 remains unsupported and is never queried.

Capacity wording separates model total, a complete-backup baseline when known,
candidate growth, and metadata overhead. It never calls the difference “free
space”; an absent or oversized baseline remains unevaluated. `Back Up Now`
creates a read-only complete snapshot in the app Backups folder, validates it,
and stores an atomic latest-complete pointer. Opening the pointer revalidates
the backup and its digest. The UI reports completion time and location and
offers Show in Finder. Explicit selected-content export remains available.
Backup is not Restore; no Restore action was added, and a cached snapshot does
not become fresh write evidence.

The early transfer summary names only the exact verified three- and four-leaf
VNW-V15 shapes as matching reviewed patterns. Other content remains valid for
offline preparation and preview but is labeled unsupported for transfer.
This is descriptive preparation UX only; no write capability was added.

## Validation and remaining checks

Local host validation:

- Focused paths/safety, desktop, and Windows packaging tests: 40 passed.
- Full portable Python 3.12 suite: 926 passed, 3 existing intentional skips.
- `compileall` and `git diff --check`: passed.
- Local arm64 onedir package build and strict ad-hoc signature verification:
  passed.
- Host-side Device Home tests use fake/read-only transport; no physical USB
  enumeration or device operation was performed.

The first PR CI attempt identified two packaging regressions: the macOS spec
was ignored by Git, and the Windows packaged smoke referenced a removed
private path helper and the old window title. The spec is now explicitly
tracked; the smoke uses the shared path abstraction and current product title.
The macOS build metadata also now reports the actual Resources and Frameworks
locations. The macOS package run 8 and Windows package run 14 passed on commit
`6672f68`. The macOS LaunchServices open from a Japanese working directory and
the Windows packaged runtime smoke both passed. The macOS artifact
`InfoCarry-Manager-macos-arm64-py3.14.7-tk9` has SHA-256
`f474473d100dc42410bc49974f5eff87e87f2472a9075d8822a1b837cea90992`; the
Windows artifact `InfoCarry-Manager-windows-x64-py3.15.0rc2-tk9` has SHA-256
`42acf642789b1fd4d530ab1464ce00441011dc75147ebe6e818ec4e8c2be149b`. A later
review found that the UI initially claimed disconnection before checking and
left an active safety-lock notice blank until a guarded action was attempted.
Commit `47b2dde` corrects both states. Exact-head review then approved
`6672f68` with no actionable findings.

The local LaunchServices smoke could not launch the bundle from the isolated
`/private/tmp` worktree: `open` returned `kLSNoExecutableErr`, and local
LaunchServices had no indexed entry for this temporary bundle path. The bundle
itself has a valid plist, matching `CFBundleExecutable` and executable names,
arm64 Mach-O, and a valid code signature. The published-head macOS workflow
successfully opened the bundle through LaunchServices from a Japanese working
directory and validated the frozen-runtime report. No runtime smoke report
was produced by the failed local open.

Windows backend and packaging sources remain in place. The full suite passed
the Windows backend tests locally, and the published head's Windows Actions
package smoke passed. Human visual checks remain for Finder launch on the owner's
Mac, Retina and normal scaling, resizing, keyboard/focus behavior, native
open/save dialogs, long Japanese paths, and useful error dialogs. No
read-only physical VNW-V15 inspection was performed.

The remaining gate is PM acceptance. Do not merge before that acceptance.
