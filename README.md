# Sony InfoCarry Toolkit

This project is a read-first modern replacement for the Sony InfoCarry VNW-V15 Windows 2000 software. The CLI supports USB detection, standard descriptor reads, a safe interface open/close check, and the two verified read-only information queries. A guarded modern segmented writer exists for explicitly authorized experiments; it is not exposed through the normal CLI.

## Development setup on macOS

Install libusb with Homebrew, create the canonical environment with the
approved Python 3.12.13/Tcl-Tk 9.0 runtime, and install the project:

```sh
brew install libusb
/path/to/python3.12.13 -m venv .venv
.venv/bin/python -m pip install -e .
```

The macOS system Python 3.9/Tk 8.5 is unsupported. The desktop command checks
the runtime before opening a window and reports how to recover when an old Tk
installation is selected.

Detect the supported device and read its standard USB descriptors:

```sh
.venv/bin/infocarry detect
.venv/bin/infocarry descriptors
.venv/bin/infocarry descriptors --json
.venv/bin/infocarry open-check --cycles 3
```

`open-check` selects the verified configuration/interface only when necessary,
discovers the bulk endpoints from the descriptors, and releases the interface.
It does not send an InfoCarry vendor command or perform a bulk transfer.

Query device information only into a new raw-capture directory:

```sh
.venv/bin/infocarry info --query configuration --save-raw tests/output/config-1
.venv/bin/infocarry info --query hardware --save-raw tests/output/hardware-1
```

The command refuses an existing destination and saves each exact 64-byte
response plus a SHA-256 manifest before parsing. These queries send the
documented vendor control request and perform a bulk-IN transfer; they do not
write device content. On the verified VNW-V15, `info` reports a 240 x 320 pixel
display while leaving unknown configuration and hardware values lossless and
neutrally named.

Create an offline report from preserved manager files without connecting to the
device:

```sh
.venv/bin/infocarry fixture-report \
  ${RESEARCH_ROOT}/fixtures \
  analysis/fixture-report-1
```

The command verifies the observed `VICDATA.bin` encoding and checksum, parses
the `VICMEM.bin`, `VICLV.bin`, and `order.vnw` sidecars, and writes only a new
JSON manifest. It never writes a decoded backup or overwrites an existing
report directory. See
[`analysis/phase-7-fixture-report.md`](analysis/phase-7-fixture-report.md).

The Codex app may need permission to run the descriptor command outside its filesystem sandbox so libusb can see connected USB devices.

Phase 8 also includes a guarded offline payload composer in
`src/infocarry/payload_builder.py`. It reproduces the verified fixed ranges
and accepts unresolved alternate-model ranges only as explicit opaque bytes.
The `build_ordinary_from_decoded_vicdata()` entry point validates the decoded
blob and maps
its first 64 bytes to range 5 and the exact remainder to range 8; it has no
USB write path. `build_from_replacements()` additionally produces an offline
candidate for changing payloads of existing records while preserving the
record tree and unknown fields. The structural helpers also support a
template-backed file add, a leaf-file delete, and a bounded existing-file
rename. Rename/delete can update exact matching `VICMEM.bin` and `VICLV.bin`
paths while preserving category/order/padding; `order.vnw` remains
byte-preserved because its generated-basename lifecycle is not yet modeled.
Full directory/model synchronization remains gated. See
[`analysis/phase-8-offline-payload-generator.md`](analysis/phase-8-offline-payload-generator.md).

The offline model-range boundary in `src/infocarry/model_range.py` can also
compose caller-supplied legacy nodes using the recovered prefix, recursion,
and alignment rules. The static source/node initializer boundary is available
in `src/infocarry/model_tree.py`; it does not infer nodes from `VICDATA.bin`.
Before any
live sender can be used, `src/infocarry/write_gate.py` requires a fresh
verified backup, an explicit write flag, and the exact interactive phrase
`WRITE INFOCARRY`. The ordinary segmented sender is isolated in
`src/infocarry/write_protocol.py` and is not exposed through the normal CLI.
The write gate binds fixed state responses to the candidate and provides a
post-write read-back verifier; see
[`analysis/phase-8-write-hardening.md`](analysis/phase-8-write-hardening.md).

For offline browsing and authoring checks, list a complete backup without
opening USB:

```sh
.venv/bin/infocarry inventory --save-report analysis/inventory-1 BACKUP_DIRECTORY
.venv/bin/infocarry preview-text --save-report analysis/text-preview-1 \
  BACKUP_DIRECTORY 0xc0 input.txt --max-bytes 4096
```

The inventory reports reachable paths, payload sizes, states, and hashes. The
text preview reads UTF-8 input, normalizes it to CRLF, validates strict CP932
encoding and an optional caller-supplied limit, and writes only a JSON audit;
it never includes candidate payload bytes or transmits anything.

The Local Library supports persistent ordered hierarchical folders and
TXT/BMP/EPUB source references. The normal ttk window shows Local Library and
Device Library side-by-side; Add Files/Add Folder, search, multi-selection,
collapsible Details, drag reorder, and ▲/▼ reorder are available without a
separate Arrange stage. Removing an item removes only its catalog reference;
the original source is never deleted. EPUB preparation is host-only: bounded EPUB 2/3 packages are
inspected without extraction, network access, or script execution, then
text-centric chapters are normalized into deterministic TXT children and only
the existing exact local 237×320 1-bit BMP profile is retained as an image
child.
Normal multi-file and recursive-folder chooser imports are non-destructive;
the order is persisted and changing it never rewrites source files. Finder/
Explorer file-drop import remains unavailable without optional TkDND. The
versioned per-user catalog is stored at
`${HOME}/Library/Application Support/SonyInfoCarryModernManager/library.json`
on macOS. The catalog is outside this checkout and reverse-engineering
evidence; its previous version is retained as `library.previous.json` after a
successful update.

`Prepare` reuses strict UTF-8 → CP932/CRLF TXT preparation and validated
237×320 uncompressed 1-bit BMP preparation. EPUB preparation uses the same
normalization boundary, preserves title/provenance/hash metadata, reports
unsupported features explicitly, and produces one canonical
`PreparedContentArtifact`. ZIP slip, external entities, remote resources,
DRM/encryption, malformed package data, and bounded-resource violations fail
closed; the source ZIP is bounded at 64 MiB, with 512 entries, 8 MiB per
entry, 32 MiB total decompressed data, and a 1000:1 compression-ratio limit.
The separate
`host-offline-hierarchical-library-txt-bmp-v1` preparation draft remains
limited to one prepared root, 1–8 leaves, depth at most 2, at most 9
directories/17 nodes, and its stated size/path constraints. P18-037's
`LibraryDeviceTransferPlan` is a separate generic logical host model: it
preserves selection and sibling order, nested folder structure, and a selected
Device Library destination; validates source freshness and CP932 components;
and rejects conflicts without overwrite or merge. Its generated offline
fixture contains 61 directories and 150 mixed TXT/BMP leaves. Those figures
are host/UI test scale, not device limits. The normal **Transfer** action
first displays this generic logical plan. One explicitly imported and
revalidated root-level folder with 1–8 ordered direct TXT/BMP leaves can now
continue through the bounded host profile and the existing readiness,
fresh-preflight, and authorization seams; exact three-/four-leaf shapes retain
their prior physical proof, while the generalized profile remains
host-reviewed and not live-proven. The plan itself never authorizes a device
operation. Packaged macOS and Windows entry points supply one shared lazy
runtime provider, but launch creates neither a live runtime nor an operation
binding and performs no device checks or transaction. After exact-profile
admission and fresh read-only evidence, the final typed confirmation creates a
one-shot binding tied to that preflight and enters the canonical guarded route.
If the external reviewed template or persistent safety configuration is
unavailable, live transfer fails closed while safe read-only Manager functions
remain available. Nesting, unsupported types, duplicate/conflicting names,
over-bound selections, existing targets, and arbitrary structures fail closed
before authorization/claim/marker/sender activity; no generalized physical
operation is enabled by P18-039.
Expected semantic path deltas are modeled independently of candidate
construction. Capacity growth remains unknown when no candidate is built, and
unresolved device auxiliary state is not treated as verified. P18-037 adds
host-only generalized delete-closure planning; the normal Delete control
remains disabled for arbitrary selections. Current live VNW-V15 shapes and
guarded boundaries remain exactly as listed in
[`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md).

The Tkinter/ttk desktop provides connection status, verified read-only backup,
a hierarchical Device Library browser, selected download/export,
progress/cancellation, recovery guidance, and TXT/BMP previews. Device sibling
order follows the order encoded in the device's directory child tables rather
than an alphabetical sort:

```sh
.venv/bin/infocarry desktop
```

The step-by-step desktop workflow and recovery guidance are in
[`docs/USER_GUIDE.md`](docs/USER_GUIDE.md). The v0.1 manual smoke-test evidence
is recorded in [`analysis/phase-9-usability-check.md`](analysis/phase-9-usability-check.md).

### macOS Apple Silicon packaged desktop app

P18-035 adds an onedir PyInstaller application bundle for Apple Silicon. Build
on an arm64 Mac with CPython 3.12 or newer and Tcl/Tk 9 or newer:

```sh
python3.14 -m venv .venv
PYTHON="$PWD/.venv/bin/python" ./scripts/build_macos_package.sh
```

Use a CPython 3.12+ build interpreter that already supplies Tcl/Tk 9. The
script installs pinned packaging requirements into that interpreter, checks the
runtime and architecture, and builds `dist/InfoCarry Manager.app`. The bundle
contains the selected CPython runtime, Tcl/Tk, PyUSB, the user-mode libusb
library, license files, and build metadata. The finished app does not need an
activated environment, Python on `PATH`, or Homebrew. `--skip-install` can be
passed when the selected environment already has the pinned requirements.
GitHub Actions builds with the official stable Python 3.14.7 macOS installer;
`BUILD-INFO.json` records the actual runtime and package layout for each build.

Local packages receive an ad-hoc code signature so the bundle has an
integrity signature without requiring a paid Apple Developer account. They
are not Developer ID signed or notarized. Gatekeeper may show a warning or
block a downloaded copy; keep Gatekeeper enabled and use only a package whose
source you trust. Public distribution would require Developer ID signing,
hardened runtime configuration, Apple notarization, and a stapled ticket.

macOS data stays at the pre-existing
`~/Library/Application Support/SonyInfoCarryModernManager/` root so a new app
cannot sidestep old safety state. It contains the `execution-claims.sqlite3`
database (including sender-start markers), the
`indeterminate-write-lock.json`, the `library.json` catalog, app-managed
`Backups/`, `Evidence/`, `Prepared Content/Source Metadata/`, and disposable
`Cache/Previews/`. `Backups/latest-complete.json` is only a pointer to a
backup that is revalidated when opened; a saved backup never substitutes for
fresh write evidence. There is no automatic safety-state migration. If the
legacy claims database is missing from an existing support directory, or
safety files appear in a proposed alternate InfoCarry root, device-changing
actions fail closed while read-only functions remain available.

The default Device tab gives a calm disconnected/connected state, queries
capacity only for the reviewed VNW-V15, shows a loaded complete-backup baseline
without calling it free space, and offers `Back Up Now`, `Show in Finder`, and
selected-content export. Backup means a read-only snapshot; Restore is
unavailable. Technical USB details remain behind `Technical Details`.
Automated smoke checks the frozen app from a Finder-like environment, Tk 9,
bundled resources and libusb, Japanese paths, clean shutdown, and zero
enumeration/sender/safety mutations. Retina rendering, normal resizing,
keyboard/focus behavior, and native open/save dialogs still need owner visual
checks. See the [P18-035 analysis record](analysis/phase-18-p18-035-macos-owner-app-device-home-20260920.md).

### Windows x64 packaged desktop build

The Windows deployment baseline is a PyInstaller one-folder distribution of
the same ttk manager. It bundles CPython 3.15.0rc2 x64, its Tcl/Tk 9 runtime,
the application, PyUSB, and the pinned user-mode libusb runtime. The release
candidate is used because the supported Python 3.12 Windows runtime supplies
Tk 8.6, below the product's Tk 9 requirement. This is a preview-runtime
baseline, not a stable end-user release; rebuild and rerun the package smoke
when Python 3.15.0 final is available.

Install the official Python 3.15.0rc2 64-bit Windows distribution, then from
the repository root run:

```powershell
py -3.15 -m venv .venv-windows
.\.venv-windows\Scripts\Activate.ps1
.\scripts\build_windows_package.ps1
```

The script checks the exact Python/Tk/architecture, installs the pinned
packaging dependencies from `requirements-windows-packaging.txt`, runs
`pip check`, and builds `dist\InfoCarry Manager\InfoCarry Manager.exe`.
Distribute the entire `dist\InfoCarry Manager` folder (including `_internal`,
`LICENSE`, and `THIRD_PARTY_NOTICES.txt`), not the executable by itself. The
packaged application does not require a separate Python installation. The
libusb DLL is bundled and loaded through the explicit PyUSB backend; this does
not install a device driver or establish compatibility with a particular
Sony/WinUSB driver. Driver deployment, signing/installer work, and physical
device validation remain separate tasks. See the
[P18-034 packaging record](analysis/phase-18-p18-034-windows-packaging-baseline-20260920.md)
for CI, smoke, and ARM64 status.

Tk is loaded only for this command. Packaging adds no new write path; all
existing device-changing actions retain their existing safety gates.
The conversion project at `${INFOCARRY_TOOLKIT_ROOT}` is
read-only and is not installed alongside this package. The staged integration
architecture for its future Text Converter and Ebook Renderer tabs is in
[`analysis/phase-9-gui-runtime-and-integration.md`](analysis/phase-9-gui-runtime-and-integration.md).

Run the offline tests:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

This portable suite is offline: it uses repository-owned fixtures, temporary
directories, and fake transports, and does not require USB hardware, the
reverse-engineering checkout, the separate conversion toolkit, private
evidence, network access, or a user's application data. The three
evidence-dependent checks remain explicit skips when their excluded evidence
is absent. GitHub Actions runs the same suite on macOS and Windows with Python
3.12.

For interim package validation, install the packaging-only tools in the
canonical environment and build a reproducible wheel (the script refuses to
overwrite an existing output directory):

```sh
.venv/bin/python -m pip install --upgrade "setuptools>=61" wheel build
sh scripts/build_reproducible_wheel.sh /tmp/infocarry-wheel-release
```

This wheel is not a signed/notarized macOS application. That is acceptable for
the approved limited-audience hobby release; Developer ID distribution remains
optional future work. Package evidence and the decision record are in
[`analysis/phase-10-package-check.md`](analysis/phase-10-package-check.md) and
[`analysis/phase-10-hobby-distribution-decision.md`](analysis/phase-10-hobby-distribution-decision.md).

See [ROADMAP.md](ROADMAP.md) for verified progress and the safety gates that apply before data-transfer commands are added.

## Development source and private remote

This sanitized checkout is the future development source of truth for the
project. Its verified `main` commits are pushed normally to the approved
private repository:

`https://github.com/sourvegie/sony-infocarry-modern-manager.git`

The sibling evidence-bearing `modern-client` checkout is a read-only local
research archive. Do not commit new product development there. Historical
commit SHAs in the analysis notes refer to that preserved local research
history unless explicitly identified as commits in this sanitized repository.

This private repository is an additional source/history backup, not a public
distribution channel and not the sole backup of reverse-engineering evidence.

Original Sony software, ISO contents, USB captures, complete device backups,
raw live-operation evidence, private device data, credentials, and generated
output remain outside this repository. Keep their manifests and stable
evidence locations under the project’s existing preservation rules; do not
upload them merely because a remote is private.

The normal local workflow is:

```sh
git clone <approved-private-repository-url>
cd modern-client
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -q
git diff --check
```

After a local commit is complete and verified, inspect the commit and full
history for excluded material before pushing the current branch normally to
the approved private remote. Never force-push, rewrite published history,
change visibility, or upload external evidence without explicit owner
approval.

Reverse-engineering and hardware evidence is recorded in
[`analysis/protocol.md`](analysis/protocol.md) and
[`analysis/phase-4-read-only-transport.md`](analysis/phase-4-read-only-transport.md).
Current device-information progress is in
[`analysis/phase-5-device-info.md`](analysis/phase-5-device-info.md).

## License

This project's own source code is released under the MIT License; see
[`LICENSE`](LICENSE). The license does not grant rights to Sony proprietary
software, firmware, documentation, trademarks, captures, backups, private
evidence, or the separate `InfoCarry-Toolkit` and reference archives.
