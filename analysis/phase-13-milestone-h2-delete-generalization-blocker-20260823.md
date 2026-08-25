# Milestone H.2 — selective-delete generalization blocker

Date: 2026-08-23
Status: **Blocked and parked; captured-fixture deletion remains the only closed scope.**

The I.7 evidence matrix was applied to the existing delete implementation and
readiness checks. The result is unchanged:

- `delete_gate.py` requires an opaque per-record timestamp map and the
  attempt-02 transmitted fixed-state form;
- `DeleteFixedState.attempt02()` is a golden capture helper, not a derivation
  from a fresh backup and selected target;
- the available add, package, replacement, and delete captures do not establish
  a deterministic metadata `+0x0c` generation rule;
- nonzero display-history, mark-list, bookmark, and other state-reference
  transformations remain insufficiently characterized;
- the framework-independent delete readiness result fails closed when either
  rule or any target reference is unresolved.

The completed Milestone H gate therefore remains limited to exact offline
attempt-02 fixture reproduction, binding, independent verification, and fake
failure behavior. It does not authorize a generalized builder, modern delete,
normal GUI/CLI delete, or a live-delete protocol. Completion must be exactly
`0x0000`; missing, ambiguous, malformed, or nonzero completion remains terminal
with no automatic retry. Any future interruption after `0x101b` begins remains
indeterminate and permits only later read-only recovery.

The smallest useful next evidence is the paired controlled legacy add/delete
procedure already drafted in
`analysis/phase-13-milestone-i7-timestamp-fixed-state-characterization-20260823.md`.
It is not being executed or requested automatically. Separate explicit owner
approval would be required for any device-changing capture.

## Post-I.7 stateful deletion addendum — 2026-08-25

The separately approved `I7-LEGACY-DELETE-01` session has now supplied the
smallest missing stateful legacy-effect observation. A complete pre-delete
backup, one isolated native `0x101b`, complete Manager BEFORE/AFTER files, and
a complete post-delete backup establish that exactly
`root\\IC_I7_CLOCK_01.txt` was removed, no path was added, every surviving file
payload was unchanged, and the native range-5 plus range-8 candidate exactly
matches the post-delete dynamic blob. The target was referenced by display
history, Mark 1, and Bookmark 1; all three references were cleared in the
post-delete fixed state. The four relevant Manager sidecars were
byte-identical before and after.

This closes the captured stateful deletion-effect evidence gap for the one
disposable target. It does **not** close H.2 generalized eligibility. All 314
shared timestamps were regenerated, but the post-delete values align with the
restart/initialization interval rather than the pre-delete timestamp event;
the causal timestamp rule remains unresolved. The current offline parser does
not recover a trustworthy request-4 completion value, and physical atomicity
or recovery remains unproven. H.2 therefore remains blocked and parked. No
modern delete builder, sender, GUI/CLI control, or new live capture is
authorized. See
`analysis/phase-13-milestone-i7-legacy-delete-20260825.md` and keep the raw
session under `EVIDENCE_ROOT` only.
