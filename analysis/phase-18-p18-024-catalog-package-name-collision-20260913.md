# P18-024 — Catalog Package-Name Collision Correction

Date: 2026-09-13
Repository: `sourvegie/sony-infocarry-modern-manager`
Canonical base: `818a9da5e9dd3fb6273d778a009dc8168c114c8c`
Branch: `task/P18-024-catalog-package-name-collision`
Boundary: **HOST-ONLY**

## P18-023 disposition preserved

P18-023 is concluded as:

> **BLOCKED before sender entry**

The normal facade/catalog path failed closed with:

```text
duplicate sibling name in Library: 00-package
```

This is not a success and not an ambiguous post-send escalation. The preserved
facts are:

- sender calls = 0;
- real `0x101b` = 0;
- retries = 0;
- claim created/consumed = 0;
- sender marker remained `none`;
- installation-wide lock remained `cleared`;
- device mutation = 0;
- fresh live V15/session evidence was not reached;
- capacity, live target-absence, backup, candidate, transaction, verifier,
  and post-backup were not reached;
- P18-023 authorization and confirmation are concluded and are not reusable.

No physical validation is performed by P18-024.

## Reproduction and exact root cause

The two colliding canonical Library nodes are both root-level
`LibraryItem`s:

1. A folder node created by `LibraryCatalog.import_folder()` in its nested
   `add_directory()` helper. Its `source_filename` is assigned from
   `path.name`.
2. A prepared-package node created by
   `LibraryCatalog.import_prepared_package()`. Its `source_filename` was also
   assigned from `path.name`.

For the P18 fixture, each physical package archive is rooted at a directory
whose basename is `00-package`. The basename is an offline evidence/package
envelope name, not the package's owner-visible device root. When two such
archives or a folder projection and a package projection entered the same
Library root, both canonical nodes therefore normalized to the same folded
sibling name `00-package` and the existing duplicate validator correctly
stopped the operation.

The defect is in the **catalog projection representation seam**. It is not a
package-import validation failure, catalog duplicate-validation failure,
root-wrapper policy, or name-normalization weakness. The package validator
already knows the authoritative logical root in
`manifest.target.folder_name`; the catalog projection discarded that identity
and substituted the physical archive basename.

The focused regression test reproduces the old projection by binding both
package nodes to the physical basename and observes the exact historical
failure. The reproduction uses the P18 package shape and `00-package` archive
envelope without touching the external evidence tree.

## Correction

`LibraryCatalog.import_prepared_package()` now uses the manifest's validated
logical target folder as the package node's Library sibling name. The physical
package root remains hash-bound in `source_path`, package reference, manifest
path, and manifest hash; no files are renamed or moved. The helper
`_prepared_package_library_name()` revalidates the logical component before it
enters the catalog.

This gives the required deterministic and structurally safe behavior:

- independently located package envelopes named `00-package` do not collide
  merely because of their internal archive name;
- two package nodes with the same owner-visible target still fail closed;
- a package target cannot silently coexist with an owner-visible folder of the
  same sibling name;
- duplicate payload child names remain rejected by the prepared-package
  composition validator;
- child order, TXT/BMP/TXT typing, package hashes, target paths, and all
  transfer/readiness identity bindings remain unchanged.

The bridge's catalog binding check was updated to compare against the same
logical target name. No sender, candidate, authorization, transaction, claim,
marker, lock, or GUI/direct-facade path was added.

## Capability and safety boundary

Unchanged: VNW-V15 only (`0x054c:0x001e`), one absent destination root,
exactly three direct payload children in TXT → BMP → TXT order, no overwrite,
deletion, nesting, merge, second package, VNW-V10, broader shapes, automatic
grouping, automatic retry, restore, synchronization, or recovery expansion.

The P18-019/P18-020 invariants remain in force: fresh typed native `0x0019`
capacity provenance, dynamic operation identity, persistent installation-wide
indeterminate lock, persistent sender-start marker, durable one-shot claim, no
retry after possible sender start, and independent terminal semantic
verification.

Host readiness and the catalog/package gate consume no real claim and mutate no
real marker or lock. P18-024 has zero USB/device operations, sender calls,
real `0x101b`, real claim consumption, real marker mutation, and real
installation-wide lock mutation.

## Focused acceptance coverage

`tests/test_p18_024_catalog_package_name_collision.py` proves:

1. the P18-023 `00-package` projection reproduces the old duplicate-sibling
   failure;
2. the corrected exact TXT → BMP → TXT package passes the normal catalog/queue
   gate;
3. true duplicate owner-visible package roots fail closed;
4. distinct logical packages remain safe when their physical envelopes share
   `00-package`;
5. an internal package envelope cannot mask an owner-visible root collision;
6. duplicate payload names remain rejected by package composition.

The existing P18-017 through P18-023 regression suites cover arbitrary valid
fresh targets, target/package/readiness invalidation, stale operation identity
and seal rejection, typed fresh capacity provenance, durable claim/marker/lock
behavior, host readiness with zero write-boundary activity, no GUI/direct
facade bypass, zero sender calls and real `0x101b`, and the single canonical
execution pipeline.

## Local validation at the current local head

The committed local head passed:

- focused P18-024/package-bridge coverage: **28 passing**;
- full portable Python 3.12 suite: **805 passing, 3 intentional skips**;
- Python compilation: **pass**;
- `git diff --check`: **pass**;
- modified-production historical target/approval scan: **clean**;
- modified-production USB/sender/claim/marker/lock import scan: **clean**.

No USB/device operation, sender call, real `0x101b`, real claim consumption,
real marker mutation, or real installation-wide lock mutation occurred.

## Required final-head validation and disposition

Final-head macOS CI, final-head Windows CI, and a fresh independent strong R3
review are required. The required final R3 disposition is:

```text
P0=0, P1=0, P2=0 — PASS
```

P18-024 is **COMPLETE** only after those final-head checks are green and the

Those final-head checks are pending publication. The configured GitHub
credential is invalid, so the branch was not published and no remote CI or
independent R3 result was obtained. P18-024 therefore remains
**HOST-VALIDATED / PENDING FINAL-HEAD CI AND R3**, not `COMPLETE`.
