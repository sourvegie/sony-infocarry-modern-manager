# P18-037 — Local Library ↔ Device Library Manager foundation

Date: 2026-09-21

Branch: `task/P18-037-library-device-manager`

Base: `dfeeb4604b25b77a61c99ff9e0677ed69aa7c8ca`

## Scope and disposition

This is an R2 host/UI foundation task. It changes the normal desktop surface to
side-by-side Local Library and Device Library panes and adds generic logical
transfer and deletion-planning models. It does not authorize physical
operations or promote any capability. The primary Transfer action currently
stops after displaying an offline destination/conflict plan. It builds no
candidate or transaction, performs no live-eligibility evaluation, and cannot
authorize or reach a sender. The former guarded live action is not exposed in
the redesigned pane; the existing exact three-/four-leaf service routes and
their capability policies are otherwise untouched.

## Implementation

- Local Library catalog entries continue to reference existing files. The
  redesigned pane supports recursive folder import, search, multi-selection,
  non-destructive removal, ordered siblings, persisted move/reorder, and
  compact contextual details. Drag reorder is native Tk binding; ▲/▼ remain a
  keyboard-independent fallback. Settings and Help remain menu actions.
- `LibraryDeviceTransferPlan` models ordered TXT/BMP leaves and arbitrary
  nested logical folders, selected destination, subtree preservation, source
  freshness, CP932 component validation, and deterministic destination
  conflicts without overwrite/merge. The expected semantic path delta is
  separately described and verified by `device_library_semantics.py`.
- The generated host fixture contains 61 directories and 150 mixed TXT/BMP
  leaves. This is a host/UI scale test, not a device capacity or hierarchy
  limit.
- `DeviceLibraryDeletePlan` computes closure and expected removals for leaf,
  multi-leaf, and subtree selections; it rejects root/system, overlapping or
  stale selections and unresolved/unsafe auxiliary state. The UI Delete
  control remains disabled for generalized selections.
- The Device Library inventory adapter preserves depth-first sibling order,
  includes file extensions in logical paths, and marks auxiliary state
  unresolved where the backup cannot establish it.

## Candidate and live-capability boundary

No generalized binary candidate is produced. Existing candidate/sealing
services are bound to reviewed direct-package semantics, templates, capacity
evidence, and auxiliary-state policies; this logical model does not establish
how arbitrary nested directory records, parent references, metadata, and
auxiliary state should be serialized. Accordingly the plan reports candidate
growth and physical capacity as unknown and does not call a candidate builder.
Exact flat 3-/4-leaf live operations remain limited to their existing reviewed
VNW-V15 policies and shared guarded route in the service layer. The new primary
Transfer control does not invoke that route. Generalized 1–N live transfer,
nested live transfer, generalized delete execution, overwrite, VNW-V10
behavior, and Restore remain unavailable. No sender, claim owner, lock, or
parallel live pipeline was added.

## Durable changes

- `src/infocarry/library.py`
- `src/infocarry/desktop_ttk.py`
- `src/infocarry/library_device_transfer.py`
- `src/infocarry/device_library_semantics.py`
- `src/infocarry/device_library_delete_plan.py`
- `tests/test_library_hierarchy.py`
- `tests/test_library_device_transfer.py`
- `tests/test_device_library_snapshot.py`
- `tests/test_device_library_semantics.py`
- `tests/test_device_library_delete_plan.py`
- `tests/test_library_transfer_execution.py`
- `tests/test_desktop_ttk.py`
- `scripts/macos_manager_entry.py`
- `scripts/windows_manager_entry.py`
- `README.md`
- `CAPABILITY_MATRIX.md`
- `CURRENT_STATUS.md`
- this analysis record

## Validation

- Focused library, planning, deletion, UI, and exact-live regression set:
  135 passed.
- Full portable Python 3.12 suite: 963 passed, 3 documented skips.
- Python 3.12 `py_compile` for both package entry points: passed.
- `git diff --check`: passed.
- macOS arm64 `.app` build and ad-hoc signing/validation: passed with CPython
  3.12.14, Tcl/Tk 9.0, PyInstaller 6.22.3.
- Isolated LaunchServices packaged smoke: passed. The main window opened and
  closed; both library panes and the host-only Transfer action were found; the
  legacy live-send control remained disabled. USB enumeration calls, sender
  calls, claims, sender markers, and installation lock were all zero.
- A host visual startup check was performed on the packaged macOS app. Full
  owner interaction checks (resize/sash, scale navigation, keyboard/focus,
  Japanese filenames, and disconnected/connected states) remain for human
  verification. Windows package workflow and exact-head independent review
  are pending until publication.
- No physical device query/write or device-changing operation was performed.

## Review and publication

## 2026-09-22 continuation — accepted P2 UI reachability finding

The independent P2 finding on PR #65 was accepted: the redesigned primary
**Transfer →** action had left the already-enabled exact VNW-V15 three-/four-
leaf guarded routes reachable only through the old engineering controls. The
user authorized repairing that normal UI reachability in the existing PR, with
no separate PR and no capability-envelope expansion. Because the route can
reach final candidate construction and the canonical sender when a separately
authorized operation is configured, this correction is treated as R3 and
stops at `READY_FOR_HARDWARE_TEST` after host validation and strong independent
review.

The logical planner now expands one explicitly imported prepared package only
after revalidating its source, manifest, ordering, and Library observations.
The normal primary action first creates the generic offline plan; a strict
adapter admits only a single root-level package whose ordered TXT/BMP leaves
and canonical child names match the existing verified three- or four-leaf
profile. It then invokes the existing readiness, fresh preflight, typed
confirmation, and one-shot facade callbacks. The default desktop still has no
runtime or operation binding. Unsupported counts/orders, arbitrary leaves,
nested/batched selections, conflicts, VNW-V10, deletion, and Restore do not
enter the guarded path. No second candidate builder, authorization, claim/
marker/lock owner, sender, or parallel pipeline was added.

Host validation on the current working tree: 972 portable tests passed with 3
documented skips; focused package bridge/readiness/UI/safety suites passed;
`py_compile` and `git diff --check` passed. The macOS arm64/Tk 9 app built and
passed the isolated LaunchServices smoke; the report showed zero device
enumeration, sender, claim, marker, or installation-lock activity. No physical
device was accessed. The existing PR #65 remains open; the exact-head review
and PR CI are pending publication of the corrected head. Do not create another
PR or merge automatically. Final disposition after R3 review and platform CI
is `READY_FOR_HARDWARE_TEST`, then stop for a separately approved procedure.
