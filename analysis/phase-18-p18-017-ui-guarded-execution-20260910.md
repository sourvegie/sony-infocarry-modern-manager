# P18-017 — Guarded UI-Driven Transfer Integration

Date: 2026-09-11
Repository: `sourvegie/sony-infocarry-modern-manager`
Canonical base: `2841842b0e7d38136d4cd6368b9a4006dd405e66`
Branch: `task/P18-017-ui-guarded-execution`
Risk: **R3 host-side integration**
Required disposition: **READY_FOR_HARDWARE_TEST**

## Scope and safety boundary

P18-017 connects the P18-016 normal ttk Library workflow to the existing
guarded execution lifecycle. It is host-side integration only. No physical
P18-017 transaction is authorized or performed, and no connected device is
required for acceptance.

The normal workflow is:

`Select → Arrange → Prepare → Preview → Review transfer → Refresh live preflight → Review exact operation → Confirm → Transfer once → post-backup/read-back/verify`

The product-facing `LibraryTransferExecutionFacade` is the only new
orchestration boundary. It owns presentation-facing state and delegates all
candidate construction, transaction construction, claim consumption, sender
marker handling, native transfer, post-operation backup, and independent
verification to the existing canonical Library adapter and
`GuardedLibraryExecutionCoordinator`. It does not implement USB or native
transaction semantics. The ttk module calls the facade and does not import the
live adapter or coordinator directly.

Merely opening the normal manager remains non-live: the facade has no runtime
or operation binding by default, and live coordinator/adapter imports are
lazy and reachable only after an explicitly supplied typed fresh operation
binding and execution runtime pass the product gates.

## Exact live-enabled validation boundary

The host facade is intentionally narrower than P18-016 reusable profile
eligibility. A future live operation must bind all of the following:

- Sony InfoCarry VNW-V15 reviewed profile and session identity `0x054c:0x001e`;
- exact fresh target `IC_P18_LIBRARY_20260910_01`;
- one explicitly selected prepared root-level package;
- exactly three direct children, in `TXT → BMP → TXT` order:
  `01-introduction.txt`, `02-page-01.bmp`, `03-ending.txt`;
- canonical filename, path, CP932, payload, and preparation limits;
- target absence, no overwrite, no delete, no merge, no nesting, no batch,
  no automatic grouping, one logical transaction, and no retry;
- fresh complete verified backup, native `0x0019` capacity evidence, exact
  candidate/transaction hashes and sizes, baseline identity, operation bundle,
  preflight seal, and the exact auxiliary-state policy;
- a fresh owner authorization and transaction-specific confirmation.

The exact auxiliary policy remains
`verified_display_history_0x001b_and_bookmark_0x001f_semantic_rebase_plus_zero_count_0x001c_to_0x001e`.
Established `0x001b` and `0x001f` logical paths remain preserved, opaque
bookmark dwords and unused tail remain byte-exact, and `0x001c`–`0x001e`
remain zero-count. Malformed, dangling, unaligned, inconsistent, or
unsupported state fails closed.

VNW-V10 remains **UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED**. Other
child counts, orderings, media combinations, destinations, overwrite,
deletion, nesting, merge, and automatic retry remain unavailable.

## Fresh identity and replay protection

`LibraryTransferOperationBinding` is a typed immutable fresh binding. Its
operation ID is `vnw-v15-library-ui-validation-20260910-01`, its confirmation
is `ADD IC_P18_LIBRARY_20260910_01 ONCE`, and its fresh target is hash-bound in
the operation bundle. The coordinator validates the typed binding against the
bundle before review and again uses the bundle/review identities for final
pre-send revalidation.

The consumed P18-015 target
`IC_P18_LIBRARY_20260907_01`, its owner approval, confirmation, candidate,
transaction, claim, marker, and result are historical only. They cannot form a
P18-017 binding. Supplying fresh scalar phrases to the canonical adapter
without the typed binding is rejected. A verified baseline collision blocks
the exact fresh target; the facade never chooses a replacement destination.

Profile eligibility therefore remains separate from operation authorization:
P18-016 can say that a package has the supported host shape, while P18-017
requires a fresh evidence-bound operation before `Transfer once` can become
actionable.

## Execution ordering and result semantics

The canonical lifecycle preserves this order:

1. Revalidate the immutable plan, bundle, target, model, package, baseline,
   capacity, fixed-state policy, and review.
2. Obtain exact in-app transaction confirmation immediately before execution.
3. Consume the durable execution claim.
4. Commit the sender-start marker.
5. Enter the existing sender at most once for one `0x101b` transaction.
6. Accept only integer completion `0x0000`.
7. Capture a complete post-operation backup.
8. Independently verify the candidate, exact target/order/payload, auxiliary
   state, unrelated state, and the sealed candidate bytes.
9. Persist the canonical result manifest and close the marker.

A click, USB submission, or sender return alone is not product success. Only
the complete verified terminal result may be rendered as `Transfer verified`.

If a sender may have started and the outcome is not independently established,
the canonical path keeps the marker, persists the installation-wide
indeterminate-write lock, rejects replay, and exposes no retry. The operator is
directed to read-only diagnosis. A determinate pre-start failure consumes no
claim; a determinate nonzero native completion consumes the one claim, closes
the marker, fails, and is never retried.

## Correction-round disposition

The normal two-round material-correction limit was reached during review. The
remaining finding was that an indeterminate reconciliation failure was being
classified as an ordinary failed state at the UI/product boundary even though
the canonical coordinator had persisted the installation-wide lock. The
owner/PM explicitly authorized one exceptional third and final material
correction round for that finding only. The correction preserves the
indeterminate state through the adapter, coordinator, facade, and ttk error
surface, and adds the corresponding fake-lifecycle and UI regression tests.
This is a task-specific exception and does not change `WORKFLOW.md` or the
repository-wide correction limit. The exception authorized no hardware
operation and does not authorize a physical P18-017 transaction.

## Host-only validation

The product facade is exercised with deterministic existing fake transport
conventions. Tests cover the exact eligible package and the negative matrix
for selection count, package shape, child count/order/kind, nesting, target
collision, capacity, backup freshness, model/V10 substitution, auxiliary
state, active lock/marker and canonical claim/replay behavior. They also cover
plan/bundle/confirmation tampering, cancellation, claim ordering, exact one
fake sender invocation, exact one fake `0x101b`, explicit `0x0000`, nonzero
completion, missing post-backup, failed terminal read-back, indeterminate
locking, and no automatic retry.

The fake suite performs no real device-changing operation, sender call,
`0x101b` transmission, claim consumption, sender-marker creation, or lock
mutation. Persistent claim/marker/lock changes observed in tests are isolated
fake installation state used to prove the existing lifecycle's failure
semantics; they are not task-side hardware activity.

## Documentation and disposition

The new path is host-reviewed and code-reachable only inside the exact gated
boundary. It is not physically validated from ttk by P18-017. VNW-V10 and
broader package shapes remain unsupported. A separate PM/owner decision and
fresh evidence are required before one bounded physical UI-driven VNW-V15
validation. P18-017 must stop before that transaction and finish with
`READY_FOR_HARDWARE_TEST`, subject to final CI and independent R3 review of
the exact head.
