# P17-002 — Explicit prepared-package import and Library grouping contract

Date: 2026-08-31
Risk: R2
Status: COMPLETE for the offline Library/package-planning scope

## Boundary

P17-002 adds a non-destructive, framework-independent import and review
boundary for one exported flat typed package. It does not detect a device,
query a backup, construct a candidate, authorize a transaction, access USB, or
enable a write. A package that passes this contract is prepared and reviewable;
it is not thereby hardware-compatible or transfer-eligible.

The supported package shape is the existing
`infocarry-prepared-typed-media-package-v1` contract: one root-level folder,
at least two ordered children made only of supported `.txt` and/or validated
1-bit `.bmp` kinds. The historical mixed-media builder keeps its both-kinds
default; the explicitly named content-builder mode permits a single kind.
Nested paths, unsupported kinds, duplicate names, and package paths outside
the selected package root are rejected.

## Contract and validation

`prepared_media_package.py` now records deterministic `package_path` and
`prepared_path` entries for each child. `load_prepared_media_package()` treats
the manifest as authoritative and verifies its canonical SHA-256 before
checking:

- contiguous explicit order, unique flat names, kind/extension agreement, and
  exact `root\\<folder>\\<child>` target paths;
- source archive containment, source size/hash, strict UTF-8-to-CP932 TXT
  authoring metadata, and exact prepared TXT payload;
- supported BMP dimensions, palette/profile metadata, payload size/hash, and
  exact prepared BMP bytes;
- offline state declarations (`device_change: none`, `usb_accessed: false`)
  and no escaping or symlinked package paths.

The returned import view is non-owning. It does not copy, move, rewrite, or
delete any package or original source file. The exporter remains create-new
only and refuses to overwrite a destination.

## Library integration

`LibraryCatalog.import_prepared_package()` stores one logical catalog item for
the whole package. The persistent catalog format remains `infocarry-library-v1`
with an additive optional `item_kind: prepared_package` record, so legacy
source-file records retain their existing fields and meaning. The package
record stores the non-owning package root/manifest paths, manifest hash, and
the exact ordered child table. Loading an old catalog does not migrate or
rewrite it; a later ordinary catalog save preserves the old items and adds
package data only for package records.

Re-importing an unchanged manifest is idempotent. A changed package is kept
under its original catalog identity and becomes stale; it is never silently
replaced. Invalid package contents are rejected before a new catalog entry is
created. Library removal deletes only the catalog entry and leaves package and
source files untouched. Package refresh and queue planning revalidate the
external package before presenting it.

## Queue and review surface

The P17-001 queue planner now treats an imported package as one selected/all-
ready queue item. Its report includes the package contract/hash, destination
folder plus ordered `kind:name` children, child source/payload sizes and
hashes, backup path conflicts, lower-bound growth, and current compatibility
state. Selecting several unrelated Library items still never merges them;
overlapping destinations remain a conflict. The queue remains an offline
review concept, and package `execution_eligible` is always false because this
task adds no candidate, authorization, transaction, or sender path.

The ttk Library adds an `Import prepared package…` directory picker. The
existing one-TXT import/Prepare buttons remain intact; the one-TXT Prepare
control is not shown for grouped package records. Package and queue results
remain explicitly labeled as offline and the normal GUI/CLI transfer controls
remain disabled.

## Evidence classification and limits

- **Verified:** deterministic manifest hashing, explicit order/type/path
  validation, source/prepared payload hash validation, BMP profile validation,
  path containment, source non-destruction, idempotent import, stale/conflict
  handling, catalog round-trip, grouped queue reporting, and offline-only UI
  wiring by host tests.
- **Observed:** existing P15/P16 native reports establish exact constrained
  TXT and TXT/BMP/TXT operations; those reports are not generalized to this
  Library contract.
- **Inferred:** an exported package directory is a suitable non-owning source
  boundary for Library review because the manifest and all copied artifacts
  are revalidated before use.
- **Unresolved:** generalized package hardware compatibility, candidate
  construction, native capacity semantics for arbitrary packages, batching,
  nesting, synchronization, and normal GUI/CLI transfer.

No raw hardware evidence or external evidence directory was changed by
P17-002.

## Validation record

Focused coverage is in `tests/test_library_prepared_package.py` and the
existing media, Library, queue, and ttk test modules. The final portable suite
passes with 569 tests and 3 intentional skips; `git diff --check`, the
excluded-content/history audit, and independent R2 review also pass at this
task checkpoint.
