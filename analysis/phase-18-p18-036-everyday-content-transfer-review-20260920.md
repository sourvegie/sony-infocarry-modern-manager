# P18-036 — Everyday content preparation and transfer review UX

Date: 2026-09-20
Branch: `task/P18-036-everyday-content-transfer-review`
Canonical base: `a13bdecc8381b7d8414b0361203445f96536df11`
Risk: R2 host-only UX and preparation work
State: PR #63 is open against `main`. Runtime/code correction head
`8854421981f02294d0bc88b4b7265e75bb0dd611` passed local validation and fresh
offline/package CI. This analysis/status update is documentation-only and
records artifacts produced from that runtime/code head. The final published PR
head requires a fresh independent review; do not merge before PM acceptance.

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
EPUB and prepared-package previews also identify substitutions, source child,
and text location; EPUB coordinates are explicitly positions in extracted
chapter text. BMP preview uses the validated prepared payload. EPUB output
continues through the existing canonical prepared-content path and preserves
CP932 failure diagnostics. Changing a supported direct-file destination
rebuilds the canonical prepared artifact while leaving its source unchanged.

Review freshness includes the selected content and order, Device Home session,
loaded/latest backup identity, backup-file state, and filesystem metadata for
source files (including child files in prepared packages). A one-second UI
freshness check invalidates the prior review/readiness after a source change,
while the existing planner continues to verify source content before review.
Offline preparation and preview remain available. Existing background
operation generation, facade, and guarded transfer paths remain in use.

## Validation

- Focused preparation, text diagnostics, desktop formatter, exact-shape,
  readiness, operation-generation, and Windows packaged-workflow regressions:
  63 passed.
- Full portable Python 3.12 suite: 933 tests passed, with 3 intentional skips.
- `compileall` and `git diff --check` passed.
- Local Apple Silicon arm64 onedir build from the runtime/code correction head
  passed with CPython 3.12.14, Tk 9.0,
  PyInstaller 6.22.3, PyUSB 1.3.1, and `libusb-package` 1.0.30.0. `plutil`
  validation and `codesign --verify --deep --strict` passed. The local bundle
  has an ad-hoc signature and is not notarized.
- No device access or physical operation was performed. Device enumeration,
  sender calls, real `0x101b` transfers, consumed claims, sender-marker changes,
  and installation-wide lock mutations are all zero.

The local LaunchServices attempt from the isolated `/private/tmp` worktree
returned `kLSNoExecutableErr`. Directly invoking the frozen executable then
aborted during Tk9/AppKit application registration before writing a runtime
smoke report. The bundle executable matches `CFBundleExecutable`, its plist is
valid, and its signature verifies. This local attempt does not establish a
successful local LaunchServices or GUI smoke; this local launch was not repeated
after the correction. Fresh GitHub PR CI on runtime/code head
`8854421981f02294d0bc88b4b7265e75bb0dd611` passed:

| Workflow | Run | GitHub run ID | Result |
| --- | ---: | ---: | --- |
| Offline tests | 196 | `35511672180` | macOS and Windows jobs passed |
| macOS package | 15 | `35511672178` | Passed, including LaunchServices smoke from a Japanese working directory |
| Windows package | 19 | `35511672160` | Passed, including packaged smoke without Python on `PATH` |

The macOS artifact is `InfoCarry-Manager-macos-arm64-py3.14.7-tk9` (artifact
ID `10605163028`, 16,929,951 bytes), SHA-256
`68016fd62a13bfa7603ee9cc57d3d43fcb36ec5e88b81b58adf77aa7c644afe4`. The
Windows artifact is `InfoCarry-Manager-windows-x64-py3.15.0rc2-tk9` (artifact
ID `10605031942`, 19,352,288 bytes), SHA-256
`6b18cd11b1c3e7a2a9cc383451f26765cb8230886445023ef7600f937bbe9ff0`. Both
package artifacts belong to runtime/code head `8854421981f02294d0bc88b4b7265e75bb0dd611`.
The following evidence-record commit is documentation-only; package hashes
remain tied to the runtime/code head and are not regenerated for that commit.

## Owner visual check (pending)

After PM acceptance, take 2–5 minutes on the owner Mac to:

1. Launch the app from Finder and resize it at normal and Retina scaling.
2. Add sample TXT, BMP, and EPUB content from a Japanese-named folder; confirm
   prepared text, normalized punctuation locations in EPUB/prepared-package
   children, and the bitmap preview.
3. Arrange content and review both exact supported orders plus one unsupported
   valid arrangement; confirm the latter remains preparable and previewable.
4. Change selection/order, edit a source file externally, or refresh Device
   Home and confirm the old review is cleared; open Technical Details only when
   diagnostic information is needed.

This checklist has not been performed. The review has not been accepted by PM,
no PR has been merged, and no physical device operation is authorized by this
task.
