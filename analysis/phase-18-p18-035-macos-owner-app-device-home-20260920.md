# P18-035 — macOS first-class owner app and read-only Device Home

Date: 2026-09-20  
Branch: `task/P18-035-macos-owner-app-device-home`  
Canonical base: `3b6697eac01b6c35d588d163325bedb99ddf76ff`  
Risk: R2 product/runtime work; R3-quality review required for persistent
write-safety path changes.  
State: local implementation and validation complete; publication, CI,
independent exact-head review, and PM acceptance remain pending.

## Packaging method and runtime

The build uses PyInstaller 6.22.3 to create an Apple Silicon arm64 onedir
bundle at `dist/InfoCarry Manager.app`. The main executable is
`Contents/MacOS/InfoCarryManager`; the visible app name remains
`InfoCarry Manager`. PyInstaller places Python, Tcl/Tk, and collected
dependencies in the bundle's framework/resource layout. The spec bundles
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
available. The actual legacy location was checked read-only; no state was
moved or changed. Tests cover fresh/restarted profiles, clear and active
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

- Focused macOS packaging, Windows backend, runtime, paths/safety, Device Home,
  backup history, and desktop tests: 60 passed.
- Full portable Python 3.12 suite: 922 passed, 3 existing intentional skips.
- `compileall` and `git diff --check`: passed.
- Local arm64 onedir package build and strict ad-hoc signature verification:
  passed.
- Host-side Device Home tests use fake/read-only transport; no physical USB
  enumeration or device operation was performed.

The local LaunchServices smoke could not launch the bundle from the isolated
`/private/tmp` worktree: `open` returned `kLSNoExecutableErr`, and local
LaunchServices had no indexed entry for this temporary bundle path. The bundle
itself has a valid plist, matching `CFBundleExecutable` and executable names,
arm64 Mach-O, and a valid code signature. The automated macOS workflow retains
a LaunchServices open from a Japanese working directory and verifies the
frozen-runtime report; that result is pending CI and is required before PM
acceptance. No runtime smoke report was produced by the failed local open.

Windows backend and packaging sources remain in place. The full suite passed
the Windows backend tests locally; Windows Actions status is pending on the
published PR. Human visual checks remain for Finder launch on the owner's
Mac, Retina and normal scaling, resizing, keyboard/focus behavior, native
open/save dialogs, long Japanese paths, and useful error dialogs. No
read-only physical VNW-V15 inspection was performed.

The next gate is publication against the exact canonical base, passing macOS
and Windows CI, a fresh independent exact-head review of the safety path and
package, and PM acceptance. Do not merge before that acceptance.
