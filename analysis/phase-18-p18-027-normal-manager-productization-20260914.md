# P18-027 — Normal Manager Workflow Productization

Date: 2026-09-14  
Canonical base: `e052ae94919856fc413547fc2e2ce110ce27f39e`  
Branch: `task/P18-027-normal-manager-productization`  
Risk: R3 host-side product/safety integration  
Physical scope: host-only; no hardware operation was performed

## Objective and boundary

P18-027 turns the already proven engineering path into a clearer normal
manager workflow:

`Add content → Preview → Prepare → Review transfer → Send to InfoCarry → Verified`

The task does not add live capability. It preserves the exact P18-025 narrow
VNW-V15 boundary, the P18-024 logical package-name projection, the P18-025
stale-authorization rejection, and the P18-026 `PreparedContentArtifact`
semantic owner. The Send action remains unavailable until the existing guarded
facade has fresh operation-specific evidence and all existing live gates.

## Architecture before

P18-026 had already made `PreparedContentArtifact` and
`PreparedContentChild` the canonical content owner, but the normal ttk Library
surface still exposed several engineering-shaped representations and mostly
synchronous handlers:

- preparation, preview, queue review, and readiness were displayed through
  separate free-form or compatibility dictionaries;
- readiness prose was derived from planner strings without a typed reason and
  recovery action contract;
- the Library Prepare, Preview, review, and read-only preflight handlers could
  perform blocking host/device-inspection work on the Tk callback path;
- stale results relied on individual handler state and could be mistaken for
  current selection state;
- technical IDs, hashes, profile fields, and transfer evidence were available
  in the same family of renderers as owner-facing summaries.

The older report shapes remain useful for persisted compatibility and
diagnostics, but they are no longer the normal UI semantic owner.

## Architecture after

### Typed readiness/result model

`library_transfer_readiness.py` now provides the typed normal-UI contract:

- `ReadinessReasonCode` is a deterministic machine-readable vocabulary for
  missing preparation, source/target drift, device/model state, fresh backup
  and capacity evidence, destination conflicts, safety lock state,
  indeterminate prior operations, unsupported live profiles, and validation
  failures;
- `ReadinessReason` binds each code to stable owner-facing text, a safe next
  action, and optional technical detail;
- `ReadinessState` separates state/message, actionability, next action,
  reasons, artifact identity, and the transfer-enabled boundary;
- `LibraryTransferReadiness.ui_state` promotes that model for normal ttk
  consumption while preserving the signed/integrity-bound report as a
  compatibility view.

Fresh evidence and exact profile eligibility still do not enable Send by
themselves. The readiness model explicitly reports reviewability and keeps
`transfer_enabled` false until the existing guarded execution facade owns the
operation.

### Background controller

`operation_controller.py` introduces one toolkit-neutral
`OperationController` for conflicting foreground host operations. It accepts
a caller-provided main-thread handoff; the ttk Library supplies a queue and
drains it with `root.after`. Preparation, preview, transfer review, typed
readiness review, and read-only live preflight run in daemon worker threads.
The Tk thread performs state changes and widget updates only. Progress is
marshalled through the same handoff and displayed as a busy spinner/activity
state.

Only one conflicting Library operation is active at once. Host-only
operations support cooperative cancellation. Cancellation never changes the
meaning of the guarded sender boundary; the existing Send handler continues
to use the single `library_execution_facade.execute_once` path and was not
invoked for this task.

### Stale-result and teardown protection

Each operation has a monotonic token/generation. Input mutations invalidate
the current token and request cooperative cancellation. Completion and
progress callbacks are delivered only when the token is still current and the
controller is not closed. Selection revisions include source identity,
preparation state, target, and canonical prepared manifest state; multi-item
review revisions include the full selected set. A late result cannot unlock
Review or Send after source/target/selection drift. Closing the window closes
the controller before Tk destruction, so queued callbacks become inert.

### Normal UI and technical-details boundary

The Library surface now uses product language: Add content, Preview, Prepare,
Ready to transfer, Review transfer, Check device readiness, Send to InfoCarry,
and Transferred and verified. Normal summaries show destination, ordered
content, size, capacity/conflict status, and actionable next steps. Candidate
SHA, transaction SHA, claim, seal, operation identity, profile IDs, milestone
IDs, and raw transport exceptions are not included in those summaries.

The explicit Technical Details control retains diagnostic JSON/evidence for a
selected item, typed readiness result, or prepared preview. Compatibility
renderers such as the former preparation audit, device-tree preview, queue
plan, and pre-P18-027 readiness renderer remain available as diagnostic/API
views, but normal ttk handlers use the product-safe summaries.

## Workflow coverage

The normal Library path now consumes the `artifact` carried by
`LibraryWorkflowService.prepare_preview` for both Prepare and Preview. Review
and typed readiness continue through the existing canonical queue plan and
`LibraryTransferExecutionFacade`; no reconstructed prepared-content owner and
no second sender pipeline were introduced. A host-only terminal formatter is
available for fakes/tests and says explicitly that no device operation was
performed.

Operations routed through the controller:

- Library Prepare;
- Library Preview;
- offline transfer review and typed readiness review; and
- read-only device readiness/preflight.

The trivial selection rendering and the existing guarded Send confirmation/
execution boundary remain synchronous. The latter is deliberately not made
cooperatively cancellable after a possible sender-start boundary.

## Validation

Focused P18-027/readiness/controller/UI validation: **42 tests passed**.  
Focused P18-017 through P18-026 regression set: **242 tests passed**.  
Full Python 3.12 portable suite: **830 passed, 3 documented skips**.  
Compileall: passed.  
`git diff --check`: passed.

The controller tests use events, barriers, and a deterministic callback queue
to prove worker-thread execution, main-thread callback marshalling, progress,
busy serialization, cancellation, stale-result disposal, typed exceptions,
and teardown safety without relying on fragile wall-clock success criteria.

Static review confirmed one reachable guarded Library execution call,
`library_execution_facade.execute_once`, no normal GUI import of the live
adapter, and no normal summary exposure of implementation identities. The
existing P18-017 through P18-026 fake/safety regressions remain green.

## Physical boundary

This task performed no USB/device-changing operation and no live validation.
All counters for P18-027 are zero:

- USB/device-changing operations: 0
- sender calls: 0
- real `0x101b`: 0
- claims consumed: 0
- sender-marker mutations: 0
- installation-wide lock mutations: 0

`CAPABILITY_MATRIX.md` is unchanged. No physical authorization exists for
P18-027. Final publication, final-head macOS/Windows CI, and a fresh
independent strong R3 review of the exact published head remain required
before the task can stop at `READY_FOR_HARDWARE_TEST` for PM acceptance.

## Publication and review

To be completed after local validation on the final commit:

- exact HEAD: pending commit
- PR: pending publication
- macOS CI run/job: pending final-head run
- Windows CI run/job: pending final-head run
- independent R3: pending; required disposition `P0=0, P1=0, P2=0 — PASS`

