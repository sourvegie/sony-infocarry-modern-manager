# P18-028 — Add Content & Conversion Workspace

Date: 2026-09-16
Branch: `task/P18-028-add-content-conversion-workspace`
Requested canonical base: `6724cbc3ab12fc4a1023df9474ebc2fae6e7d7c8`

## Scope and base note

P18-028 is host-only through Review transfer/readiness. It performs no USB,
device-changing, sender, authorization, claim, marker, or installation-lock
operation. The requested base hash was not present in the local repository or
available refs, and the network was unavailable for fetching it. The branch
was therefore created from the checked-out P18-027 successor head
`2943b85` after recording that discrepancy; this must remain visible in the
release/PR review.

## Product result

The normal Library path is now:

`Add content → Convert/prepare → Preview → Prepare → Review transfer`

`ContentWorkspace` is the single host import/conversion seam. Successful
preparation returns `ContentWorkspaceResult` with one exact
`PreparedContentArtifact`; its `ContentWorkspacePreview` is bound to that
same artifact instance. `LibraryItem` persists the canonical artifact and
preparation metadata. Queue review and readiness use the persisted artifact
identity rather than rebuilding a second content representation.

Preparation validity remains independent from live eligibility. A valid
direct TXT/BMP artifact, hierarchy, or broader prepared shape can be stored
and previewed while the existing exact live profile still blocks it.

## Source support

Supported in this task:

- UTF-8 TXT, using the existing strict CP932/CRLF preparation and 240×320
  logical layout utilities.
- Exact 237×320, 1-bit, uncompressed Windows BMP.
- Existing prepared typed-media package directories, adapted through
  `PreparedMediaPackage.to_prepared_content_artifact()`.
- Existing prepared source folders, adapted through the existing
  `LibraryCatalog` and `prepare_library_hierarchy` path.

EPUB is intentionally deferred. The repository contains no sufficiently
complete, tested extraction/rendering path for this product task. The
workspace returns the typed user-facing state: “This format is not ready for
conversion yet.” No new large converter was introduced.

## Architecture before and after

Before P18-028, the normal Library service prepared a hierarchy only. Direct
TXT authoring, typed media packages, offline conversion previews, and folder
preparation each had useful utilities but separate entry/result views:

`desktop_ttk → LibraryWorkflowService → prepare_library_hierarchy`

alongside independent `PreparedTextPackage`, `PreparedMediaPackage`,
`OfflineTextDocument`, and package-import paths.

After P18-028, the production seam is:

`source → ContentWorkspace → PreparedContentArtifact → Library → existing guarded review path`

The new workspace composes existing utilities rather than duplicating their
conversion logic. `PreparedLibraryHierarchy`, `PreparedTextPackage`, and
`PreparedMediaPackage` remain compatibility views/adapters because their
manifests and loaders are already persisted/tested. They no longer define a
second canonical Library-content identity. The older single-item preparation
helper now also persists its canonical artifact when used.

## Artifact invariants

The artifact preserves logical root/title, ordered typed children, destination
paths, payload/source identities, byte sizes, aggregate size, profile metadata,
and deterministic identity. Root, order, payload, and preparation-setting
changes produce different identities. Preview and Review transfer expose the
same identity; the normal UI hides technical hashes until Technical Details.

## Dimension finding

The 240×320 and 237×320 values describe different layers and were not
collapsed:

- `240×320` is the existing logical rendering/layout canvas used by
  `PageLayout` and text pagination.
- `237×320` is the existing transferable/display payload viewport required by
  strict 1-bit BMP validation and prepared-media packages.

The workspace records these separately as `rendering_canvas` and
`transferable_payload_viewport`. It does not crop or silently change either
dimension.

## Character-normalization policy

The existing strict CP932 boundary remains authoritative. A small deterministic
policy, `explicit-punctuation-and-common-latin-v1`, substitutes known safe
typographic punctuation and common Latin variants (for example curly quotes,
em/en dash, ellipsis, non-breaking space, and common accents). CRLF handling
remains deterministic. Other unsupported characters, including emoji, still
fail closed. Substitutions are included in preparation metadata and surfaced
as a normal Preview/Prepare warning.

## UI and background behavior

The normal Add content group accepts TXT/BMP and exposes existing prepared
package import; Add folder covers prepared folders. Prepare and Preview use
the P18-027 `OperationController`, progress callbacks, cooperative
cancellation, and revision/generation stale-result protection. A late
conversion completion cannot replace a newer source or settings selection.
Failures become typed actionable UI states, including the explicit deferred
EPUB message. No Tk work is added to the conversion worker's result path.

## Validation record

The final local validation run passed: 126 focused tests and 841 tests in the
full Python 3.12 portable suite, with 3 intentional skips.

- Focused conversion/import/preparation/UI tests: 126 passed.
- Full Python 3.12 portable suite: 841 passed, 3 intentional skips.
- `compileall`: passed.
- `git diff --check`: passed.
- Static ownership scans: conversion workspace has no USB/sender/authorization
  imports; the existing guarded sender path remains the only sender path.
- `CAPABILITY_MATRIX.md`: unchanged.
- Physical counters: USB/device-changing operations 0; sender calls 0; real
  `0x101b` 0; claims consumed 0; sender-marker mutations 0;
  installation-lock mutations 0.

P0/P1/P2 acceptance target: all zero, PASS. Do not merge; stop for PM
acceptance after final validation and review status are recorded.

Publication, final-head macOS/Windows CI, and the fresh independent R3 review
are external follow-up gates; their identifiers and outcomes must be appended
before PM acceptance.
