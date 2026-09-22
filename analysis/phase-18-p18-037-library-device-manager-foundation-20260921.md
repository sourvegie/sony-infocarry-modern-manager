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

Host validation: 972 portable tests passed with 3 documented skips; the
focused package bridge/readiness/UI/safety group (73 tests) passed;
`py_compile` and `git diff --check` passed. The macOS arm64/Tk 9 app built and
passed the isolated LaunchServices smoke; its report showed zero device
enumeration, sender, claim, marker, or installation-lock activity. No physical
device was accessed.

Implementation commit `c7647aa2adb7b90c6bf83279e8aa4d81595ff0ad` was pushed to
the existing PR #65. Fresh independent exact-head R3 review passed with
`P0=0, P1=0, P2=0`. PR workflows passed on that implementation commit:
[Offline tests run 203](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35628159298),
[macOS package run 20](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35628159292),
and [Windows package run 24](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35628159501).
The offline suite passed on both macOS and Windows; both package builds and
their frozen-runtime/LaunchServices smokes passed. PR #65 remains open and
unmerged; no separate PR was created. Do not merge automatically. Host-side
disposition is `READY_FOR_HARDWARE_TEST`; a physical operation still requires
separate operation-specific owner approval and an approved procedure.

## 2026-09-22 continuation — ordinary-folder adapter

The approved physical UI validation was stopped safely before live preflight,
authorization, or sender start because the redesigned visible UI could not
map an ordinary Local Library folder to the existing exact prepared-package
contract. No device-changing operation or device change occurred. Attempts
`-01` through `-04` remain historical stopped attempts and are not relabeled
successful. No physical validation is part of this continuation.

The owner explicitly authorized a capability-reachability expansion limited
to the already reviewed exact VNW-V15 TXT → BMP → TXT and TXT → BMP → TXT → TXT
profiles, with no expansion of the physical capability envelope. The normal
`Add Folder → select → Transfer` route now first builds the unchanged generic
host-only logical plan. An application-boundary adapter accepts only one
selected ordinary folder to the existing device root, with direct regular-file
children whose persisted Local Library sibling order, canonical existing
profile filenames, supported content, hashes, sizes, and bytes match one
exact existing profile. It reuses the existing preparation/package builder
and stages a transient package under Manager-owned prepared-content state,
providing an in-memory catalog overlay only to the existing transfer
review/readiness services. It does not persist a synthetic catalog entry or
alter source files. CP932 substitutions that would change text are rejected
with a user-facing explanation. Final admission remains with the canonical
readiness/preflight path; no new profile, candidate, sender, authorization,
coordinator, claim store, marker, lock owner, or bypass of backup/capacity/
conflict/confirmation/no-retry/read-back controls was added. Unsupported
structures remain host-only.

Host regression coverage exercises exact three-/four-leaf mappings, persisted
order and target name, source immutability and drift checks, unsupported
counts/orders/nesting/target conflicts/destinations, CP932 replacement refusal,
the visible Add Folder → Transfer route, and arrival only at the existing
readiness boundary with no execution claim or sender call. The focused group
passed (84 tests), the complete portable suite passed (983 tests, 3 documented
skips), and `compileall` plus `git diff --check` passed. The local arm64/Tk 9
macOS app built and passed strict ad-hoc signature verification. However, the
local LaunchServices smoke did not pass: LaunchServices returned
`kLSNoExecutableErr`, forced registration could not scan the `/private/tmp`
bundle (`-10822` from Spotlight), and direct frozen-runtime invocation
aborted before writing its report. This is recorded as a local environment
failure, not a smoke pass. Windows packaging and final-head hosted CI have not
run because `gh auth status` reports the stored GitHub token invalid.
Independent exact-head review remains pending. No hardware was accessed; no PR
was created or merged.
