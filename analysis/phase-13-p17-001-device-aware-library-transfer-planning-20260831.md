# P17-001 — device-aware Library transfer planning

Date: 2026-08-31
Status: **COMPLETE — offline planning and review only**
Risk: **R2 — regression-sensitive persistence and cross-module state**

## Scope and boundary

P17-001 adds a framework-independent plan for reviewing prepared Library
items as a possible future transfer queue. It does not detect a device, open
USB, create a candidate, authorize a transaction, call a sender, or change a
device. The normal GUI and CLI have no package-transfer control. The optional
ttk buttons say `Review selected (offline)…` and `Review all ready (offline)…`
and render the same no-device-change report as the framework-independent
planner.

The queue does not infer a new package-grouping or destination rule. Each
prepared Library item remains one independently prepared root-level TXT
package. A duplicate or overlapping folder/child destination is a conflict
and fails closed; it is never silently merged into a multi-child package.
That is the supported P17-001 planning boundary. Enabling a queue for device
execution remains outside this task and requires individually proven
operations plus a separately reviewed task.

## Plan contents

`src/infocarry/library_transfer_plan.py` provides the
`build_library_transfer_queue_plan()` entry point and the
`LibraryTransferQueuePlan` JSON-safe result. It supports:

- explicit caller-ordered `selected` item IDs;
- `all_ready`, which includes only supported, present, current, prepared
  items and records other catalog entries as excluded with a reason;
- source and prepared-manifest reconstruction/hash revalidation;
- exact intended folder and child paths, operation type, compatibility state,
  conflicts, per-item source/prepared sizes, and aggregate totals;
- comparison with a supplied `VerifiedBackup`, including existing display
  path conflicts and a lower-bound capacity result; and
- explicit grouping and safety fields showing that automatic grouping,
  candidate construction, authorization, transaction construction, USB
  access, sender calls, and automatic retry are disabled.

The ttk Library tree supports extended selection for the selected review
action. Its selected item IDs are passed in visible Library order, while
single-item Prepare and catalog removal remain single-selection actions.

The existing prepared-package model remains unchanged: it is still the
conservative one-root-folder/one-TXT shape. The plan is a report/queue
boundary, not a candidate builder and not a persistent catalog mutation.

## Evidence classification

### Verified offline

- the plan preserves explicit selection order and produces stable JSON-safe
  output with a hash-bound `plan_sha256`;
- current source and prepared-manifest changes are blocked during planning;
- unsupported, stale, unprepared, unknown, duplicate, and overlapping queue
  selections are represented as blocked/excluded rather than silently acted
  on;
- verified-backup destination conflicts are reported, including extensionful
  display paths, and lower-bound capacity is reported without claiming exact
  device growth; and
- the planner and formatter expose no candidate bytes, authorization,
  transaction, sender, or USB action.

These claims are established by focused Library queue and ttk formatter tests
and the complete portable suite. The focused queue tests cover source drift,
catalog prepared-manifest tampering, an existing folder/extensionful child
conflict, changed verified-backup bytes, malformed backup data, and
destination overlap. The optional ttk handler uses the read-only
`verify_fresh_backup()` path only when a backup is already loaded.

### Observed or human evidence

None was collected for P17-001. No hardware, legacy Manager, or physical
device operation was performed.

### Inferred

The report is suitable for offline human review of a future additive queue
for the already prepared root-TXT shape. This is an implementation inference,
not evidence that a multi-item queue can be sent or that several prepared
items may be represented as one native package.

### Unresolved and deliberately disabled

- exact grouping semantics for multiple Library items;
- any batch candidate construction or physical queue execution;
- exact device growth for an aggregate queue;
- package operations whose individual native gates are not closed; and
- normal GUI/CLI package-transfer exposure.

## Validation and disposition

Focused tests cover selected/all-ready planning, source drift, backup absence,
destination overlap, invalid selection, catalog non-mutation, backup conflict
and tamper handling, and the explicitly offline ttk summary. The complete
portable suite passes 559 tests with three intentional evidence-dependent
skips; the focused queue/ttk set passes 18 tests. The staged diff check and
excluded-content/history audit are clean. The independent R2 review is
recorded in
`analysis/phase-13-p17-001-r2-review-20260831.md`.

P17-001 is **COMPLETE** for this offline-only plan/review scope. It does not
authorize a live operation or change the product safety boundary.
