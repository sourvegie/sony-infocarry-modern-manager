# P18-036 — Everyday content preparation and transfer review UX

Date: 2026-09-20
Branch: `task/P18-036-everyday-content-transfer-review`
Canonical base: `a13bdecc8381b7d8414b0361203445f96536df11`
Risk: R2 host-only UX and preparation work
State: Implementation and local validation are complete. Pull request CI and
fresh independent review of the exact PR head are pending. Do not merge before
PM acceptance.

## Product changes

The Content tab presents the normal sequence as Add Content → Prepare and
Preview → Arrange → Review Transfer. The one-item and multi-item review views
show prepared order, destination, payload size, backup state, current Device
Home status, and capacity evidence. The review says explicitly that it neither
authorizes nor starts a transfer. Technical identities remain behind the
existing Technical Details control.

The only patterns described as transferable remain the exact reviewed VNW-V15
direct-leaf sequences:

- `TXT → BMP → TXT`
- `TXT → BMP → TXT → TXT`

Other valid arrangements can still be prepared and previewed, but their
transfer review identifies them as unsupported. VNW-V10 remains unsupported.
No capability profile, authorization, sender, transfer, packaging, or
workflow behavior was expanded.

TXT preview now shows the actual prepared CP932/CRLF text, identifies each
deterministic safe punctuation substitution by source line and column, and
stops preparation with codepoint/location details for unsupported characters.
BMP preview uses the validated prepared payload. EPUB output continues through
the existing canonical prepared-content path and preserves CP932 failure
diagnostics. Changing a supported direct-file destination rebuilds the
canonical prepared artifact while leaving its source unchanged.

Review freshness includes the selected content and order, Device Home session,
loaded/latest backup identity, and lightweight backup-file state. A changed
review input invalidates the prior review/readiness while leaving offline
preparation and preview available. Existing background operation generation,
facade, and guarded transfer paths remain in use.

## Validation

- Focused preparation, text diagnostics, desktop formatter, exact-shape,
  readiness, operation-generation, and Windows packaged-workflow regressions
  passed.
- Full portable Python 3.12 suite: 930 tests passed, with 3 intentional skips.
- `compileall` and `git diff --check` passed.
- Local Apple Silicon arm64 onedir build passed with CPython 3.12.14, Tk 9.0,
  PyInstaller 6.22.3, PyUSB 1.3.1, and `libusb-package` 1.0.30.0. `plutil`
  validation and `codesign --verify --deep --strict` passed. The local bundle
  has an ad-hoc signature and is not notarized.
- No device access or physical operation was performed. USB/device operations,
  sender calls, real `0x101b` transfers, consumed claims, sender markers, and
  installation-wide lock mutations remain zero.

The local LaunchServices attempt from the isolated `/private/tmp` worktree
returned `kLSNoExecutableErr`. Directly invoking the frozen executable then
aborted during Tk9/AppKit application registration before writing a runtime
smoke report. The bundle executable matches `CFBundleExecutable`, its plist is
valid, and its signature verifies. This local attempt does not establish a
successful LaunchServices or GUI smoke. The PR macOS package workflow must
provide the frozen LaunchServices smoke result; the Windows package workflow
and macOS/Windows offline CI results are also pending.

## Owner visual check (pending)

After PM acceptance, take 2–5 minutes on the owner Mac to:

1. Launch the app from Finder and resize it at normal and Retina scaling.
2. Add sample TXT, BMP, and EPUB content from a Japanese-named folder; confirm
   prepared text, normalized punctuation locations, and the bitmap preview.
3. Arrange content and review both exact supported orders plus one unsupported
   valid arrangement; confirm the latter remains preparable and previewable.
4. Change selection/order or refresh Device Home and confirm the old review is
   cleared; open Technical Details only when diagnostic information is needed.

This checklist has not been performed. The review has not been accepted by PM,
no PR has been merged, and no physical device operation is authorized by this
task.
