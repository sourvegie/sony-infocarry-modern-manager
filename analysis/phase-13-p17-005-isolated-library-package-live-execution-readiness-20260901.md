# P17-005 — isolated single Library-package live-execution readiness adapter

Date: 2026-09-01
Baseline: merged canonical `main` at `b15877d` (PR #11)
Status: **READY_FOR_HARDWARE_TEST — host-only; stop before hardware**
Risk: **R3 — device/safety critical**

## Boundary

P17-005 adds the isolated host boundary required for a later, separately
briefed physical operation of one explicitly selected P17-002 Library package.
It does not access USB, detect a device, query capacity, capture a real backup,
request or consume owner approval, or transmit `0x101b` in this task. All
validation here uses injected fake callbacks and a fake write backend.

The adapter is deliberately not imported by the normal CLI or ttk GUI. It is
not a product transfer control and does not broaden Library selection,
grouping, package shape, timestamp policy, or hardware compatibility claims.

## Exact supported operation

The only accepted package is the P17-004 profile:

```text
root\IC_P17_LIBRARY_20260831_03
├── 01-introduction.txt
├── 02-page-01.bmp
└── 03-ending.txt
```

The selected row must be one explicitly imported and fully revalidated
P17-002 prepared-package Library item. The authoritative manifest supplies the
single logical package and child order. The existing reviewed P16-001 native
template, P17-003 bridge, and P17-004 semantics remain the only construction
basis: strict TXT payloads, the validated 237 x 320 1-bit BMP payload, native
prefixes, existing-record preservation, supported fixed/display state,
one-explicit-timestamp policy for new records, additive create-new destination,
and parsed native `0x0019` capacity evidence.

## Implementation

`src/infocarry/prepared_library_package_live_adapter.py` provides:

- `prepare_prepared_library_package_live_preflight()`, which fixes the
  read-only order to expected Sony `0x054c:0x001e` detection, parsed native
  `0x0019` capacity, complete non-overwriting backup capture/verification,
  Library/package candidate reconstruction, hash-only preview, and seal;
- `PreparedLibraryPackageLivePreflight`, an outer immutable report that binds
  the P17-003 core preflight seal, exact profile/destination, device identity,
  candidate, authorization, capacity, backup, approval phrases, no-retry
  policy, and normal GUI/CLI isolation;
- `execute_prepared_library_package_live()`, which requires the exact future
  owner approval and confirmation values, captures and verifies a new complete
  pre-write backup, re-detects/revalidates identity and capacity, revalidates
  the catalog and package, reconstructs the candidate from that fresh backup,
  and requires exact candidate equality before constructing the existing
  `AuthorizedWriteSender` only after every approval, freshness, identity,
  capacity, backup, Library, candidate, and cancellation gate has passed. Its
  execution-local authorization and one-shot call are not exported or
  returned, so this adapter exposes no sender object or second-transaction
  entry point. `0x0000` is the only accepted completion. The external
  evidence-manifest helper refuses overwrite, requires distinct verified
  before/after backups plus a hash-only result audit, and records their
  identities and operation hashes without embedding raw candidate or
  transaction bytes. A nominal execution cannot return success before this
  manifest is persisted, and the success audit accepts only its exact
  canonical operation sequence.

The implementation reuses `build_prepared_library_package_candidate()`,
`authorize_prepared_library_package()`,
`verify_prepared_multi_package_readback()`, and
`AuthorizedWriteSender`; it does not duplicate native record construction.
The future live caller must still supply the reviewed transport and perform a
new fresh preflight. No real backend is constructed by normal application
imports.

## Binding and failure policy

The sealed hash-only report binds the device identity, fresh verified backup
manifest/blob/object hashes, parsed capacity response and field, exact
Library/catalog/item/package/manifest/ordered-child source and prepared
hashes, reviewed native template paths and digest, fixed-state/display-history
policy, destination and record offsets, candidate and transaction hashes,
timestamp policy, no-retry policy, exact approval phrases, and expected
additive post-state. Candidate bytes remain outside the report.

The boundary is fail-closed:

- wrong identity, malformed or insufficient capacity, target conflict,
  package/profile/order/source/manifest/catalog drift, stale or modified
  backup, fixed-state drift, template drift, seal tampering, and any candidate
  mismatch stop before the sender;
- cancellation is allowed before transmission only;
- the sender is called at most once, never retries, and accepts only explicit
  integer completion `0x0000`;
- timeout, disconnect, cancellation, missing/malformed/nonzero completion, or
  any other failure after transaction start is terminal/indeterminate; and
- a nominal completion requires a new complete post-operation backup and
  independent ordered TXT/BMP/TXT read-back. Post-backup or read-back failure
  is terminal/indeterminate, with no corrective write.

The future physical task must preserve complete before/after evidence outside
Git at a new non-overwriting external root and call the versioned evidence
manifest writer. P17-005 created or modified no external evidence, source-pool
files, prior P16/P17 session artifacts, or `InfoCarry-Toolkit` files.

## Host validation and classifications

### Verified offline

- the exact P17-004 package/profile and Sony identity are enforced;
- the ordered fresh preflight and revalidation bindings are sealed;
- P17-003 candidate/authorization construction and the independent verifier
  are reused;
- the sender is one-shot, approval-gated, strict on completion, and
  non-retrying;
- fake-host tests cover stale/tampered seal, source, backup, capacity,
  fixed-state, target, and package bindings; insufficient capacity; wrong
  identity; pre-start cancellation; post-start cancellation, timeout,
  disconnect, missing/malformed/nonzero completion; post-backup/read-back
  failure; at-most-one sender-call enforcement; and non-overwriting evidence
  manifest output;
- no normal CLI/GUI import reaches the adapter; and
- no hardware or external evidence was accessed.

### Observed

None in P17-005. P17-004's owner-supplied detection/capacity/backup facts are
historical context only and are not reused as a live baseline.

### Inferred

The adapter is a suitable host boundary for a later live task because it
reuses the reviewed construction and verification components and requires a
new injected preflight before a sender call. This is not physical compatibility
evidence for the P17-004 content.

### Unresolved / disabled

Physical compatibility of this Library package, native numeric completion
semantics beyond accepted integer `0x0000`, operation-specific capacity
semantics beyond parsed `0x0019`, interrupted-write atomicity/recovery,
broader package shapes, batching, nesting, synchronization, and normal
GUI/CLI transfer remain unresolved or disabled. A later task must perform a
new fresh read-only preflight and obtain separate exact operation-specific
owner approval; P17-005 requests or consumes none.

## Validation checkpoint

- Focused P17-005 adapter tests: **9 passed**.
- Relevant P17 bridge, independent read-back verifier, and P16 mixed-runner
  regression tests: **28 passed** (12 + 6 + 10).
- The adapter, bridge, and P16 mixed-runner set is **31 passed** (9 + 12 + 10);
  **37 passed** when the independent verifier set is included.
- Complete portable suite: **591 passed, 3 intentional evidence-dependent
  skips**.
- `git diff --check`: passed after the correction review checkpoint.
- Excluded-evidence/history audit: passed; raw backups,
  captures, candidate bytes, private source material, and original Sony
  material remain outside Git.
- Independent R3 review: **PASS**, recorded in
  `analysis/phase-13-p17-005-r3-review-20260901.md`.

## Final boundary

P17-005 is **READY_FOR_HARDWARE_TEST** for host-only readiness. Stop here. No
hardware access, approval request, or transaction occurred in this task. A
later separately briefed task must perform a new fresh read-only preflight and
obtain separate operation-specific approval before any device-changing
operation.
Do not access hardware, request or consume live approval, or transmit `0x101b`
under this task. A later separately briefed live task must capture a new
complete backup, obtain fresh parsed capacity evidence, revalidate every
binding, obtain new operation-specific owner approval, preserve complete
external evidence, and independently verify the post-operation state.
