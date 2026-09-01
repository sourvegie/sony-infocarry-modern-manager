# P18-001A — Responsive Library review usability correction

Date: 2026-09-02
Base: canonical `main` at merged PR #25 commit `e1e9f7d`
Risk: R1 presentation with R2 safety/status visibility regression risk

## Scope and disposition

P18-001A corrects the merged P18-001 Tk/ttk Library presentation before the
next product milestone. It does not add a transfer action, approval path,
sender, hardware access, candidate/authorization behavior, package or Library
schema change, or new evidence. The exact P18-001 Experimental review remains
review-only.

The owner-supplied visual check identified clipping/compression at ordinary
non-maximized widths even though unused space remained elsewhere. The affected
areas were the single-row toolbar, Experimental/no-send notice, long table and
detail values, and bottom status. The supplied references were inspected as
the presentation baseline; they are not repository evidence and are not
copied into Git.

The owner’s first launch of the corrected surface then exposed a separate
host-only startup defect in `refresh_library_view`: the canonical persisted
`LibraryPackageReference.children` values are dictionaries, while the new
shape display read them as attribute-bearing objects. No hardware, sender, or
transfer path was reached. The display boundary now reads the persisted
`kind` mapping while retaining compatibility with object-shaped in-memory
fixtures, and a focused regression test covers the exact TXT/BMP/TXT shape.

## Corrected layout contract

The desktop opens at `1120x760` and declares a supported minimum of `980x680`.
The Library toolbar uses explicit grouped action rows:

- **Import / prepare:** import TXT, import prepared package, remove, prepare;
- **Offline review:** review selected and review all ready; and
- **Experimental boundary — review only:** a full-width row with the review
  action plus a no-approval, no-send label.

A separate persistent safety notice repeats that Experimental review has no
send action and that fresh backup/candidate/authorization/device execution
remain guarded. The bottom status is outside the resizable panes and wraps to
the available width. Both labels update their wrapping on Library resize.

The list/detail divider remains a user-adjustable ttk paned-window sash with
a 360-pixel list minimum and 440-pixel detail minimum, enforced on resize and
sash release. The table uses concise logical
item, state, shape, source filename, and target values; it no longer displays
the absolute source path in the table. The selection detail retains the full
source path, target, source hash, package data, and JSON diagnostics. The
ordered review report is a scrollable technical text area with both vertical
and horizontal scrollbars so paths and hashes remain recoverable without
compressing the primary list.

The Experimental formatter now presents distinct sections for status, package
contents/order, destination/conflicts, capacity/backup state, safety rules,
technical details, and why the transfer is unavailable. It retains exact
hashes and paths; the technical section keeps long values out of the primary
status summary.

## Independent review

The first independent R1/R2 review found two implementation issues: an
unsupported ttk `minsize` pane option and possible horizontal competition
between the Offline review and Experimental groups. The implementation
replaced `minsize` with supported child width requests, moved the Experimental
group to a full-width row, and added a bounded `sashpos` clamp. A follow-up
review also found trailing whitespace in this record and a stale `641` count in
the risk register; both were corrected in commit `4669357`.

The pre-correction independent re-review at
`466935734a7487379629c845b99f9b3137f08f7f` is **PASS —
READY_FOR_HUMAN_TEST**. It confirmed Tk 9 compatibility, the `980x680`
minimum, grouped toolbar, sash bounds, scrollbars, persistent safety/status
text, concise table/detail separation, GUI/live-adapter isolation, and no
P18-002 scope leakage. It also confirmed 10 focused tests, 643 full-suite
tests with 3 intentional skips, compilation of 181 Python files, and clean
`git diff --check`. No hardware or external evidence was accessed.

The owner-reported startup regression is corrected in the follow-up change;
post-correction focused/full validation and independent review are recorded
below.

Fresh independent R1/R2 re-review of the follow-up diff is **PASS —
READY_FOR_HUMAN_TEST**. It confirmed that persisted child dictionaries are
read at the display boundary, strict catalog validation is unchanged, the
normal GUI/CLI remains isolated from live transfer, and no hardware path is
reachable. It confirmed 11 focused tests, 644 full-suite tests with 3
intentional skips, read-only compilation of 181 Python files, and clean
`git diff --check`.

## Evidence classifications and boundaries

- **Verified:** the change is limited to `desktop_ttk.py`, its formatter/UI
  tests, and documentation; Python 3.12/Tk 9.0 is the supported runtime;
  the normal GUI/CLI import graph remains isolated from the live adapter; no
  approval or send control exists in the Library surface.
- **Observed:** the owner observed clipping/compression at ordinary window
  sizes in the supplied visual references. Host inspection confirms the
  former single-row toolbar and absolute-path table columns were present.
- **Inferred:** the grouped rows, explicit pane minima, dynamic wrapping, and
  scrollbars address the reported failure at the declared minimum geometry.
  This inference still requires the owner’s visual repetition on macOS.
- **Unresolved:** human acceptance of the corrected rendering at `980x680` and
  `1120x760` or larger, native font/theme variations, and all hardware/device
  behavior. No physical or hardware claim is made here.

## Host validation and manual gate

Focused `tests.test_desktop_ttk` tests pass, including the persisted-child
mapping regression, explicit geometry, sectioned-review, no-send, and existing
offline wording assertions. The module and tests compile under the project
virtual environment. The complete suite passes with 644 tests and 3
intentional evidence-dependent skips. `git diff
--check` and the excluded-evidence/history audit pass; no raw evidence,
candidate bytes, transaction bytes, source-pool material, or
`InfoCarry-Toolkit` files are included.

The task disposition is **READY_FOR_HUMAN_TEST**. The owner should launch with
the supported Python 3.12/Tk 9 runtime, open Library, check the exact minimum
`980x680`, verify every grouped action and the persistent no-send/status
messages are readable, drag the list/detail sash toward each pane, select the
prepared package, inspect the scrollable technical detail, then repeat at
`1120x760` or larger. Selection and keyboard focus must remain intact. No
approval, sender, device detection, backup, or `0x101b` operation is part of
this check.
