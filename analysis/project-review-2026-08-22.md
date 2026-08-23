# Project Review — 2026-08-22

> Priority update: the later owner decision in
> `analysis/core-transfer-priority-reset-2026-08-22.md` supersedes this note's
> Library-first implementation order. New-file creation and selective deletion
> are now the active critical path.

## Management conclusion

The project has moved from protocol discovery and risk retirement into product
development. The read-only v0.1 manager is complete, and the deliberately
constrained v0.2 existing-text replacement passed its approved live GUI smoke
with a fresh before backup, one authorized transaction, a complete after
backup, independent read-back verification, and no automatic retry.

The plan should therefore stop describing v0.2 safety implementation as the
next objective. That path is now frozen as a regression-tested capability.
The active product track is v0.3: a local Library and offline Prepare studio
integrated into the canonical ttk application.

## Verified current stage

- Canonical source and immutable evidence are separated and version controlled.
- The supported runtime is Python 3.12.13 with Tcl/Tk 9.0.
- Read-only detection, verified backup, browse, preview, and selected export are
  usable from the GUI.
- One existing TXT record can be replaced through the complete guarded workflow.
- Strict UTF-8 to CP932/CRLF conversion, deterministic logical pagination, a
  dependency-free 1-bit BMP serializer, and the first offline GUI tabs exist.
- The current offline regression baseline is 226 tests.
- Developer ID signing and notarization remain appropriately deferred for the
  limited hobbyist audience.

## Restructured delivery plan

### Milestone E — Local Library foundation

Define the host-side catalog and its source/prepared relationships, then add
non-destructive picker and drag-and-drop import. The Library must track
preparation and stale states, distinguish host data from device data, and never
delete original sources by default.

### Milestone F — Renderer foundation

Select or approve a narrowly scoped font/image dependency, then produce
deterministic 240 x 320, 1-bit monochrome pages from the canonical logical page
model. Validate dimensions, BMP headers, palette, row stride, determinism, and
representative Japanese/Latin glyph output. Integrate the same renderer into
preview and export. Structural success alone must not be described as verified
device compatibility.

### Milestone G — Document import and Prepare workflow

Define a canonical offline document model and add EPUB import first. Preserve
source metadata where practical, report unsupported layout/content clearly,
and keep conversion cancellable and independent of USB. Evaluate MOBI as a
separate follow-on because its parser and dependency choices may differ. Shape
the normal workflow around Prepare for InfoCarry and retain detailed controls
in an advanced Conversion Lab.

### Phase 12 and Milestone H — Staged transfer and integrated hobby release

Build an offline selected/all-ready transfer plan with conflict and capacity
review, then map execution only to proven operations. Exercise representative
Library, Prepare, queue-preview, and existing-text scenarios, improve guidance,
and build a refreshed wheel. Continue the limited-audience unsigned policy.

### Evidence-gated v1 research

General new-file creation remains blocked on category/order sidecars and native
model construction. Delete, restore, firmware/unlock, and alternate modes
remain separate high-risk research tracks. None should interrupt Milestones E
through H.

## Management rules for the next stage

1. Freeze the proven v0.2 writer and expand no device mutation implicitly.
2. Keep `${INFOCARRY_TOOLKIT_ROOT}` read-only and never place
   both projects' `infocarry` packages on one import path.
3. Ask before adding a substantial production dependency.
4. Keep generated conversion output outside preserved evidence.
5. Require explicit approval for every live hardware operation; offline
   authoring work requires none.
6. Update the roadmap with exact test and evidence counts after each slice.

## Immediate decision boundary

The next implementation task is the non-destructive local Library model and
import boundary. It requires no hardware or new production dependency. The
later font-backed renderer remains a dependency-approval boundary under
`AGENTS.md`; transfer execution beyond existing-TXT replacement remains a
separate protocol/safety approval boundary.
