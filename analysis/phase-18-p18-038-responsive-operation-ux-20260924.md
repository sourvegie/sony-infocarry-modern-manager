# P18-038 — Responsive operation UX + simple confirmation

Date: 2026-09-24

## Scope

P18-038 changes the normal Manager transfer interaction only. It does not
expand the VNW-V15 capability envelope. The currently enabled exact three- and
four-leaf guarded profiles remain the only live transfer shapes.

The owner-facing goals are:

- keep Tk responsive during the final guarded transfer;
- show plain-language progress while the existing guarded lifecycle runs;
- replace the long typed confirmation phrase with an ordinary OK/Cancel
  confirmation; and
- prevent a responsive window from introducing unsafe mid-write cancellation
  or close behavior.

## Root cause

Planning and fresh live preflight already run through the shared
`OperationController` on a worker thread. The final
`LibraryTransferExecutionFacade.execute_once()` call was still invoked
synchronously by the Tk callback. During the blocking USB/backup/read-back
lifecycle, Tk could not process events, so the window appeared hung or
"Not Responding".

## Design

The final execute-once call now runs through the same existing
`OperationController`. The canonical facade, coordinator, sender, durable
claim, sender marker, installation-wide indeterminate lock, no-retry policy,
post-write backup, and independent read-back verifier are unchanged.

The worker forwards the existing adapter/sender progress callback through the
controller's main-thread handoff. The ordinary UI presents three coarse states:

1. `Final safety checks — keep the InfoCarry connected`
2. `Transferring to InfoCarry — do not disconnect`
3. `Verifying transfer — do not disconnect`

The progress bar remains indeterminate because the physical operation contains
backup, protocol, and verification work that does not share one meaningful
byte-total.

## Confirmation

The normal transfer surface now uses an OK/Cancel dialog summarizing the exact
target and item count. Clicking OK supplies the already-derived exact
confirmation phrase to the existing operation-specific authorization path.
The internal phrase contract remains unchanged; the user no longer needs to
type it manually.

This is a UX simplification, not an authorization bypass. The executable
binding still exists only for the already sealed exact operation and is still
checked independently by the guarded coordinator immediately before execution.

## Cancellation and close boundary

The confirmation dialog is the user cancellation boundary for a
device-changing transfer.

After OK:

- the visible Cancel action is disabled;
- no cancellation callback is forwarded into the sender lifecycle;
- closing the Manager window is blocked until the guarded operation reaches a
  terminal result; and
- the UI event loop remains responsive for repainting and progress.

Read-only/host-only background operations retain their existing cooperative
cancellation behavior.

A review of the now-responsive interaction found one additional live-UI hazard:
the Library tree can still receive mouse selection and drag events while
buttons are disabled. The pre-P18-038 selection handler could invalidate the
shared OperationController when its selection revision changed. That behavior
is useful for stale host-only work, but it is unsafe once a confirmed
device-changing worker owns the controller because the worker intentionally
ignores cooperative cancellation after the confirmation boundary. P18-038
therefore treats the active live operation specially:

- selection events cannot invalidate or detach the active controller token;
- the tree selection is restored to the exact selection that entered the
  confirmed live operation, preserving terminal diagnostic context;
- mutable Library controls remain disabled while the live operation is active;
- drag reorder is refused while any Library operation owns the controller; and
- after the terminal result is delivered, the selection lock is released and
  the normal selection view is reconciled.

This prevents a harmless click from discarding the terminal write result while
preserving the existing stale-result behavior for cancellable host-only work.

## Safety invariants unchanged

P18-038 does not introduce or alter:

- capability profiles;
- candidate construction;
- device model admission;
- destination/conflict rules;
- durable execution claims;
- sender-start marker semantics;
- installation-wide indeterminate-write lock semantics;
- sender call count;
- retry policy;
- native completion handling;
- post-write backup/read-back verification;
- overwrite/merge behavior;
- deletion;
- Restore; or
- VNW-V10 support.

No physical device operation is authorized by this implementation task.

## Validation

Required before merge:

- focused desktop/operation-controller tests;
- complete portable suite;
- `compileall`;
- `git diff --check`;
- macOS/Windows offline CI;
- macOS package/LaunchServices smoke;
- Windows package smoke; and
- independent exact-head review with P0=0, P1=0, P2=0.

The review should focus on Tk/main-thread confinement, the close/cancel
boundary, and preservation of the canonical one-shot authorization and
execution lifecycle.
