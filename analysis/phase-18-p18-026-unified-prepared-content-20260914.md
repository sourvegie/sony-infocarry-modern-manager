# P18-026 — Unified Prepared Content Workflow

Date: 2026-09-14
Canonical base: `317e123531c302da0e415bb322e0fe47fd306030`
Branch: `task/P18-026-unified-prepared-content`

## Scope and safety boundary

P18-026 is a host-side consolidation through **Review transfer / host
readiness**. It does not perform physical validation and does not create live
authorization. The implementation contains no device operation, sender call,
real `0x101b`, claim consumption, sender-marker mutation, or
installation-wide-lock mutation.

The exact P18-025 guarded VNW-V15 path remains outside the new preparation
contract. Its live boundary is still the separately reviewed one absent root
with exact TXT → BMP → TXT children, fresh native `0x0019` capacity evidence,
dynamic operation identity, durable one-shot claim, persistent sender marker,
indeterminate lock, no retry after possible sender start, and independent
terminal verification.

## Representation audit

Before P18-026, the same logical Library content could appear as:

1. `PreparedLibraryHierarchy.manifest` from `library_prepare.py`, with
   hierarchy nodes, totals, an offline safety envelope, and a legacy manifest
   hash.
2. `PreparedTextPackage` from `prepared_package.py` for one TXT root/child.
3. `PreparedMediaPackage` and `PreparedMediaPackageImport` from
   `prepared_media_package.py` for imported/exported flat TXT/BMP children.
4. `LibraryPackageReference` in the persisted catalog, which is a non-owning
   package/archive reference and child projection.
5. `PreparedItem` in `transfer_foundation.py`, reconstructed from either a
   hierarchy manifest or a queue report.
6. Queue-plan and readiness dictionaries that rebuilt child order, paths,
   sizes, and payload hashes independently.

The canonical owner is now `PreparedContentArtifact` in
`src/infocarry/prepared_content.py`, with typed `PreparedContentChild` values.
It owns the logical root name, ordered children, child kind/path, immutable
payload identity/path, source provenance, aggregate prepared size, optional
preparation/profile identity, and deterministic `artifact_identity`.

The old representations now have narrow roles:

- `PreparedLibraryHierarchy` is a compatibility view over a canonical
  artifact. Its existing hierarchy manifest remains loadable for persisted and
  existing callers; normal preview feeds the artifact into the transfer
  foundation.
- `PreparedTextPackage` and `PreparedMediaPackage` remain source/archive
  adapters because their existing export/import contracts and exact native
  validation are compatibility boundaries. Both expose
  `to_prepared_content_artifact()`.
- `LibraryPackageReference` remains the persisted non-owning catalog adapter;
  no storage migration was introduced.
- `PreparedItem` is now an explicit transfer-plan adapter from the canonical
  artifact and carries its artifact identity. It no longer needs to own a
  separate semantic content identity.
- Queue reports may still include legacy `ordered_children` fields for
  compatibility, but new reports also carry a canonical artifact projection
  and identity. Readiness validates the canonical projection first and only
  adapts old reports when it is absent.

No milestone/task name was added to a production API. No SQLite or plugin
framework was added.

## Preparation versus live eligibility

`PreparedContentArtifact.valid_preparation` is independent of live transfer.
The readiness report now exposes:

- `preparation.valid` and `preparation.artifact_identity` for the content
  contract; and
- `eligibility.prepared_content_valid` plus
  `eligibility.live_transfer_eligible` for the separate narrow reviewed live
  shape gate.

A valid hierarchy or broader flat shape therefore remains valid prepared
content while remaining live-transfer-ineligible. The exact reviewed
TXT/BMP/TXT package remains host-profile eligible and still has
`transfer_enabled = false` until a separately reviewed live boundary.

## Workflow binding

The normal host path is now:

`Add content → Prepare → Preview → Review transfer`

`LibraryWorkflowService.prepare_preview()` uses the canonical artifact to
create both the device-tree preview and its transfer-plan adapter. Queue
planning adapts source/package boundaries into the same canonical artifact;
readiness consumes and verifies that artifact identity rather than rebuilding a
parallel semantic child model. `PreparedLibraryPackageBridge` also records the
canonical identity while retaining its existing exact package/native builder
adapter.

The normal UI keeps technical hashes, profile IDs, operation identity, claims,
seals, and transaction details in technical report surfaces. User-facing
status remains Prepare, Preview, Review transfer, and Transfer once/verified;
this task does not redesign the ttk layout.

## Conversion boundary

P18-026 does not implement EPUB/MOBI conversion. Future conversion remains:

`source ebook → extract/normalize/render → preview → canonical prepared artifact → Library → transfer`

The conversion layer still owns no USB, authorization, candidate, sender,
claim, marker, or lock state. Existing conversion `PageLayout` `240×320` and
transferable prepared-media BMP validation `237×320` remain unchanged: they
represent rendering canvas versus the currently validated transferable payload
viewport, not duplicate constants that should be forced to match.

## Validation record

Focused host validation includes canonical identity/order/mutation/duplicate
tests, hierarchy preparation, library preparation, queue planning, readiness,
P18-024 projection regression, bridge/fake guarded flow, and transfer-foundation
compatibility. The new canonical-content test module covers:

1. deterministic identity;
2. preserved child order;
3. payload and root-name identity changes;
4. duplicate sibling rejection;
5. valid hierarchy versus live-ineligible shape;
6. exact TXT/BMP/TXT host eligibility with live execution disabled;
7. broader-shape rejection; and
8. stale canonical identity/target rejection.

The required final validation remains:

- full Python 3.12 portable suite;
- compilation, `git diff --check`, and static production-identity/sender-path
  scans;
- final-head macOS CI and Windows CI;
- fresh independent strong R3 review of the exact published head with
  `P0=0, P1=0, P2=0 — PASS`.

P18-026 stops for PM acceptance after those gates. `CAPABILITY_MATRIX.md`
remains unchanged because no live capability is expanded.
