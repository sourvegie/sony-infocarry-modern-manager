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

The local Library supports ordered hierarchical folders and TXT/BMP leaves.
Normal multi-file and recursive-folder chooser imports are non-destructive;
Move up/Move down changes explicit sibling order, and Library removal never
touches a device or source file. The approved Tk runtime has no external
file-drop API, so drag-and-drop is unavailable without the optional TkDND
dependency. The versioned per-user catalog is stored at
`${HOME}/Library/Application Support/SonyInfoCarryModernManager/library.json`
on macOS. The catalog is outside this checkout and reverse-engineering
evidence; its previous version is retained as `library.previous.json` after a
successful update.

`Prepare` reuses strict UTF-8 → CP932/CRLF TXT preparation and validated
237×320 uncompressed 1-bit BMP preparation. The separate
`host-offline-hierarchical-library-txt-bmp-v1` draft accepts one prepared root,
1–8 leaves, directory depth at most 2, no empty directories, at most 9
directories/17 logical nodes, 39 CP932 bytes per component, 259 CP932 bytes per
relative path, and the existing 1 MiB leaf / 4 MiB source-total / 1 MiB
prepared-total limits. Its deterministic manifest and device-tree preview are
offline only. Unsupported types, encoding/BMP failures, duplicates, stale
sources, and limit or capability mismatch fail closed. A supplied fresh
verified device-path baseline makes destination conflicts visible in the
preview; conflicts remain preview-only and do not authorize an operation.
Capacity fields remain **Not evaluated** without fresh verified evidence. The unchanged flat
V15 profile remains `defined_not_live_enabled`; no Library send control is
exposed.

The no-write desktop Device Manager uses Tkinter/ttk and provides connection
status, verified read-only backup, a hierarchical folder/file browser,
selected download/export, progress/cancellation, recovery guidance, and TXT
and BMP previews. Sibling order follows the order encoded in the device's
directory child tables rather than an alphabetical sort:

```sh
.venv/bin/infocarry desktop
```

The step-by-step desktop workflow and recovery guidance are in
[`docs/USER_GUIDE.md`](docs/USER_GUIDE.md). The v0.1 manual smoke-test evidence
is recorded in [`analysis/phase-9-usability-check.md`](analysis/phase-9-usability-check.md).

Tk is loaded only for this command; the window has no device-write control.
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
