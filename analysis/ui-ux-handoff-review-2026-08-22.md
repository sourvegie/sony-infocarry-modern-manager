# UI/UX Engineering Handoff Review — 2026-08-22

> Sequencing update: the design direction remains approved, but
> `analysis/core-transfer-priority-reset-2026-08-22.md` moves new-file creation
> and selective deletion ahead of Library and visual implementation. The early
> interface may remain crude until those core operations are proven.

## Source and trust boundary

Reviewed the user-supplied archive:

- source: `${LOCAL_USER_ROOT}/Downloads/InfoCarry_Manager_Engineering_Handoff.zip`
- SHA-256: `0206c44202084914716afd0a2055e580ebd239ff2aef60273e70de28f23ca0fe`
- contents: seven Markdown handoff documents, four generated concept boards,
  two screenshots of the existing conversion application, and a manifest.

The handoff is design input, not a replacement for the canonical product,
risk, protocol, or safety documents. Technical values appearing in concept art
are illustrative and are not promoted to verified device facts.

## Management assessment

The handoff identifies the correct long-term product center: a local Library
that connects preparation tools to a persistent Device Bay and a safe transfer
workflow. This is more coherent for a non-technical user than presenting Text
Converter and Ebook Renderer as unrelated top-level tasks.

The recommended normal-user path is adopted:

`Import → Prepare → Inspect → Queue → Transfer → Verify`

The current converter controls remain valuable, but they move conceptually to
an advanced Conversion Lab. The normal workflow is outcome-oriented and uses
tested preparation profiles.

## Accepted design direction

- Concept A is the structural reference: Library, content/selection workspace,
  persistent Device Bay, collapsible System Console, and status bar.
- The visual direction is Sony Industrial with restrained VAIO influence and
  modern desktop usability: “retro-futuristic utility, not retro-themed
  software.”
- Device connection, identity, readiness, capacity, active work, and result
  remain continuously understandable without relying on color alone.
- Normal mode hides hashes, offsets, packet details, and raw byte fields.
  Optional Geek Mode exposes them without hiding critical warnings.
- The Device Bay becomes the shared preview surface for source preparation and
  content read from the device, with explicit labels distinguishing simulated,
  prepared, and physical-device content.
- Routine success uses state, console, and status feedback; modals are reserved
  for risk, ambiguity, or unrecoverable failure.
- Conversion, Library, application workflow, device/protocol, and structured
  logging remain separate, testable layers.

## Required adaptation to proven engineering scope

The handoff's transfer phase cannot be implemented literally yet. The modern
client has proven replacement of one existing TXT record, but arbitrary new
record creation, category/order sidecars, image insertion, and general batch
execution are unresolved.

Therefore:

- **Transfer selected** may construct and review a mixed queue, but execution
  is enabled only for individually proven operation types.
- “Full transfer” is renamed **Transfer all ready items** and means additive
  queue construction only.
- It never means synchronize, delete unmatched items, replace a device side,
  restore a backup, or reproduce legacy send-all.
- New-record and unsupported items remain visibly blocked with their unmet
  evidence gate stated.
- Any later batch execution requires one fresh verified backup, exact
  plan-bound authorization, stop-on-first-failure behavior, no automatic retry,
  and independent verification of every committed item.

## Local Library contract

The Library is host-side data and must remain distinct from a backup or the
live device tree. Its first version records:

- stable item identifier and schema version;
- original source path, type, size, modification time, and hash;
- display name and user category;
- preparation profile identifier/version;
- prepared outputs, hashes, warnings, and estimated size;
- preparation state: `NOT_PREPARED`, `ANALYZING`, `READY`,
  `READY_WITH_WARNINGS`, `STALE_SOURCE_CHANGED`,
  `STALE_SETTINGS_CHANGED`, or `FAILED`;
- last-prepared time and error/recovery information.

Import is non-destructive. Removing an item from the Library does not delete
the original source by default. Generated output never overwrites originals or
immutable reverse-engineering evidence. Picker and drag-and-drop imports call
the same framework-independent validator and perform no USB operation.

## Revised implementation sequence

### Milestone E — Local Library foundation

Build and test the catalog/data contracts, non-destructive picker import,
drag-and-drop adapter, source/prepared relationship, stale-state detection, and
the first Library tree/content table. Keep device content visibly separate.

### Milestone F — Renderer foundation

Complete the reviewed dependency decision and deterministic 240 x 320, 1-bit
font-backed rendering. Connect the canonical page model to shared preview and
export while retaining conservative compatibility labels.

### Milestone G — Document import and Prepare workflow

Define the canonical document model, add EPUB first, evaluate MOBI separately,
add compatibility preflight and tested profiles, and reshape the normal GUI
around Prepare for InfoCarry. Preserve detailed controls in Conversion Lab.

### Phase 12 — Staged transfer and unified shell

Add the offline transfer plan, capacity/conflict review, selected/all-ready
queue construction, structured events, Device Bay, Console, and Geek Mode.
Map execution only to proven operations.

### Milestone H — Integrated hobby release

Exercise representative Library, Prepare, queue-preview, and existing-text
transfer scenarios; update user guidance; and build a refreshed wheel. Signing
and notarization remain deferred for the limited audience.

## Acceptance boundaries

The first Library milestone passes when a user can import supported sources by
picker and drop, browse them offline, distinguish original from prepared
content, see preparation state, and remove catalog entries without deleting
source files. No USB action occurs.

The first transfer-plan milestone passes when a user can select one or several
ready items, understand destinations/conflicts/size/capacity and exactly which
items are blocked, and leave the review without any device change. Hardware
execution is a separate gate.
