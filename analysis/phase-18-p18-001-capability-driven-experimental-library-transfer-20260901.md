# P18-001 — Capability-driven Experimental Library transfer integration

Date: 2026-09-01
Base: canonical `main` at merged PR #24 commit `8ce7a7c`
Risk: R3 device-facing orchestration / R2 Library and GUI review semantics

## Scope and disposition

P18-001 is host/offline-only. It does not detect a device, create a backup,
construct a real sender, request approval, transmit `0x101b`, or modify
external evidence. The first integrated product shape is exactly one
explicitly grouped prepared Library item:

```text
root\IC_P17_LIBRARY_20260831_03
├── 01-introduction.txt
├── 02-page-01.bmp
└── 03-ending.txt
```

This is the exact constrained profile read-back verified by P17-018. Physical
opening of the folder and children remains a human acceptance check. The
implementation does not claim compatibility for arbitrary TXT/BMP packages,
nesting, multiple packages, batch operations, or recovery.

## Capability authority correction

`CAPABILITY_MATRIX.md` is now the authoritative exact-shape operation register;
`CURRENT_STATUS.md` is the current-sprint view and `ROADMAP.md` remains
chronological history. The matrix records constrained root-TXT deletion as
live-proven, ordered four-TXT and flat TXT/BMP/TXT as constrained proven
scopes, and the exact P17-018 Library package as read-back verified. It keeps
arbitrary/generalized forms, recovery, and normal generalized transfer
unavailable. Product status is **Experimental** only for the proven narrow
profile and does not imply an approval or hardware operation.

`PRODUCT_VISION.md`, `AGENTS.md`, and `WORKFLOW.md` now route capability
questions to the matrix and no longer describe all multi-child/mixed-package
live proof as missing. Historical evidence reports were not rewritten.

## Integrated workflow boundary

`experimental_library_transfer_review.py` provides a framework-independent,
hash-only review model. A queue plan by itself remains `preview_only`; an
exactly ordered package becomes `ready_for_hardware_test` in the review model
only when the caller supplies a matching sealed preflight and immutable bundle.
The review reports:

- one logical Library item and explicit grouped package contents/order;
- exact paths, source/prepared manifest identity, sizes, and conflicts;
- fresh complete backup and native capacity requirements;
- candidate, transaction, bundle, and preflight seal hashes without candidate
  bytes;
- the complete candidate library image semantics of the physical protocol;
- one logical transaction maximum, explicit `0x0000`, exact confirmation, and
  no automatic retry; and
- complete post-operation backup, independent P17-019 candidate-core
  reconciliation, and evidence audit provenance.

The ttk Library adds `Review Experimental transfer…`. It is a review-only
surface: no approval or send control is exposed, and `desktop_ttk.py` does not
import the live adapter. Unsupported/stale/conflicting/modified/nested/
multi-package/differently shaped items remain preview-only with reasons.

`experimental_library_transfer.py` is the isolated integration shim for a
future enabled path. It accepts one immutable
`PreparedLibraryPackageOperationBundle` and delegates to the existing
P17-017 runner and P17-019 reconciliation. It does not duplicate candidate,
authorization, sender, post-backup, or no-retry logic. The shared
`experimental_transfer_contract.py` records the complete terminal-failure
vocabulary for review and tests; enforcement remains in the canonical runner.

## Evidence classifications

- **Verified:** the P17-018 exact package shape, candidate/authorization/
  transaction/read-back controls, P17-017 output lifecycle, and P17-019
  terminal reconciliation are reused; the new review and delegation are
  covered by host tests; normal GUI/CLI imports remain free of the live adapter.
- **Observed:** none in this task; no hardware or external evidence was
  accessed.
- **Inferred:** the exact P17-018 package can be represented by the new
  Experimental product review and delegated through the established guarded
  path, subject to a future fresh preflight and operation-specific approval.
- **Unresolved:** physical human opening of the P17-018 children, interrupted-
  write recovery, generalized package compatibility, recovery, and the
  broader Library queue/GUI experience.

## Validation boundary

Focused P18 review/model/GUI tests pass (including queue-readiness, exact child
hash/size/path binding, safety-boundary inventory, and normal GUI/CLI import
isolation). The existing P17 bridge, live-adapter, and read-back suites also
pass. The complete portable suite passes with 641 tests and 3 intentional
evidence-dependent skips; Python compilation and `git diff --check` pass. The
excluded-evidence/history audit found no new raw evidence, candidate bytes,
transaction bytes, source-pool content, or `InfoCarry-Toolkit` files in the
change. Independent R3/R2 review is recorded in
`analysis/phase-18-p18-001-r3-review-20260901.md`.

The host result is **READY_FOR_HARDWARE_TEST** for the exact reviewed shape;
the ttk presentation remains **READY_FOR_HUMAN_TEST** until its crude review
surface is visually checked. This is not a hardware authorization and no
device access, approval phrase, sender construction, or `0x101b` occurred.
