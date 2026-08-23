# Core Transfer Priority Reset — 2026-08-22

## Owner decision

The project exists to reverse-engineer the legacy Sony InfoCarry Manager's core
functions and reproduce them safely on a modern system. The current modern
writer can replace the payload of one existing TXT record, but a normal user
expects to add new books/content and remove finished content to reclaim space.

General new-file creation and selective removal are therefore the critical
path. Library architecture, drag-and-drop, renderer/EPUB expansion, Concept A
visual refinement, Geek Mode, packaging refresh, and aesthetic work follow the
core transfer primitives. An early engineering interface may be crude.

## Current proven boundary

- Complete read-only backup, browse, preview, and selected export are proven.
- Guarded replacement of one existing TXT record is proven through a live ttk
  smoke with fresh before/after backups and complete read-back verification.
- Offline parsers/builders include template-backed file-add and leaf-delete
  experiments, but complete arbitrary model-node and sidecar synchronization
  remain unresolved.
- Existing native selected-send captures must not be assumed to represent a
  genuinely new record until the evidence audit demonstrates that fact.

## Immediate instructions for the next agent

1. Read `AGENTS.md`, `PRODUCT_VISION.md`, `RISK_REGISTER.md`, and `ROADMAP.md`
   completely before acting.
2. Confirm the canonical working tree and run the complete 226-test offline
   baseline from `.venv`.
3. Do not begin Library, renderer, EPUB/MOBI, visual, signing, or packaging work.
4. Audit existing evidence first. At minimum inspect:
   - `analysis/phase-8-arbitrary-content.md`
   - `analysis/phase-8-structural-mutations.md`
   - `analysis/phase-8-sidecar-sync-boundary.md`
   - `analysis/phase-8-model-tree-static-boundary.md`
   - `analysis/phase-8-range-evidence-matrix.md`
   - `analysis/phase-8-manager-test-3.md`
   - `analysis/phase-8-manager-test-4.md`
   - `analysis/phase-8-usblog-capture-analysis.md`
   - all preserved fixture reports and the external capture/fixture locations
     referenced by those notes.
5. Produce a concise evidence matrix for genuinely new TXT creation: known,
   observed, inferred, and missing. Cover record/model node, directory path,
   category membership, `VICMEM.bin`, `VICLV.bin`, `order.vnw`, identifiers,
   allocation/capacity, naming, transaction ranges, completion, and unrelated
   changes.
6. If existing evidence closes the gate, proceed to the offline model in small
   tested slices. If it does not, write one exact legacy Windows 2000 capture
   protocol and stop for owner participation. Do not ask for redundant data.

## Required legacy capture if the audit finds a gap

Use one small disposable UTF-8/ASCII TXT file with a unique name and contents.
Preserve these as separate stages:

1. complete pre-add device backup;
2. standalone SnoopyPro capture of adding the genuinely new file with the
   legacy Manager;
3. complete post-add device backup;
4. exact source file and manager-produced sidecars;
5. only if separately approved, standalone legacy deletion capture of that same
   disposable item and a complete post-delete backup.

Do not mix Manager startup, unrelated browsing, multiple sends, rename, or
other mutations into either operation capture. Never overwrite earlier logs,
backups, fixtures, or evidence.

## Implementation gates

### Milestone E — Evidence

The new-file delta and all affected metadata/sidecars are documented with
hashes and confidence labels.

### Milestone F — Offline new-record model

Pure builders reproduce the observed post-add state from the pre-add state and
source while preserving unknown and unrelated bytes. Tests cover duplicates,
names, encoding, capacity, malformed inputs, interruption, timeout,
cancellation, ambiguous completion, and zero automatic retries.

### Milestone G — Guarded new TXT

The workflow provides exact path/metadata preview, fresh verified backup,
operation-bound authorization, one-shot bounded transfer, and complete
read-back. The normal GUI/CLI action remains disabled until offline gates pass.
One live smoke requires new explicit approval.

### Milestone H — Selective delete

Deletion is modeled from independent evidence and receives its own preview,
authorization, failure-injection, backup, and verification gates. Successful
creation is not deletion proof. Restore and bulk delete remain excluded.

### Milestone I — Prepared content package

Prove the minimum folder/multi-record behavior for one simple text book before
bitmap-page packages or broad ebook features.

### Milestones J/K — Product integration

Only after the primitives work, connect Library import/drag-and-drop, Prepare,
selected add/remove, capacity/conflict queue, and **Transfer all ready items**.
Batch transfer never means destructive synchronization. Apply the approved
Concept A refinement after the crude core workflow succeeds.

## Stop and approval boundaries

- No live hardware mutation or new Windows capture without explicit approval.
- No modern new-file or delete replay based only on inference.
- No automatic retry after any device-changing request begins.
- No restore, bulk delete, sync/replace-all, firmware, unlock, or alternate
  mode.
- Ask before adding a substantial dependency or changing the application stack.
