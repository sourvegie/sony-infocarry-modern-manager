# Milestone I.7 — timestamp and fixed-state characterization

Date: 2026-08-23
Status: **Offline characterization and controlled add-01 evidence complete; live generalization blocked.**

The separately approved `I7-LEGACY-ADD-01` add result is synthesized in
`analysis/phase-13-milestone-i7-legacy-add-01-results-20260823.md` and its JSON
companion. That result adds an independent legacy root-TXT case: all 314 shared
timestamps changed, the new payload and path were persisted, and all five
fixed-state objects remained byte-identical zero state. The result strengthens
the negative generalization boundary; it does not establish a fresh timestamp
or nonzero fixed-state rule and does not authorize deletion.

This slice compares the preserved capture-7 folder package, clean legacy
root-TXT add capture 04, approved modern root-TXT add evidence, existing-text
replacement, and legacy delete attempts 01/02. It performs no USB operation
and does not modify evidence. The portable machine-readable matrix is
`analysis/phase-13-milestone-i7-timestamp-fixed-state-evidence-20260823.json`.

## Evidence levels

| Subject | Result | Classification |
| --- | --- | --- |
| Metadata `+0x0c` parses as big-endian Unix seconds | Consistent across the available records | verified representation |
| Legacy add rewrites shared metadata timestamps | Seen in capture 04, capture 07, and I7 add-01 | independently observed |
| Modern root-TXT add preserves shared timestamps | Seen in the approved modern smoke | observed in one modern add |
| Replacement preserves shared timestamps | Seen in the replacement fixture | observed in one replacement |
| Folder and child receive one shared timestamp | Seen in capture 07 | verified observation, not a rule |
| Timestamp generation from operation time, source time, or copied record | No hypothesis passes all cases | unresolved |
| Simple record-position timestamp rule | Not supported by cross-case comparison | negative result |
| Capture-7 fixed state before/after | All five objects byte-identical and zero-filled | verified for capture 07 |
| `0x001b`, `0x001e`, `0x001f` offset rebasing on add | Consistent with independent root-TXT add evidence | observed independently in add cases |
| Fresh general fixed-state derivation | Nonzero referenced-state coverage is insufficient | unresolved |
| Unknown fixed-state bytes | Must be preserved; unresolved references must block | safety policy |

## Timestamp conclusion

The field is a valid Unix-style representation, but the generation rule is
not established. Legacy add captures rewrite all shared record timestamps,
whereas the modern root-TXT add and existing-text replacement preserve shared
timestamps. The folder and child sharing one value is an observation, not proof
that a future builder may use the current time, source file time, a copied
record time, or any other implicit value. No timestamp rule is promoted.

Static inspection of the preserved legacy binary found file-time conversion
helpers and stores into source-node offsets `+0x04`, `+0x08`, and `+0x0c`, but
did not prove a write-side path from those helpers to the transmitted metadata
field. A separate allocation path reads node `+0x0c`; that use must not be
renamed as proof that the field is a raw timestamp.

## Fixed-state conclusion

Capture 7 verifies preservation of five zero-filled state objects. Other add
evidence verifies only narrow counted-offset rebasing when references are
present. It does not establish how a fresh package should transform display
history, mark lists, bookmarks, or metadata-relative references in every
nonzero state. The offline eligibility helper therefore requires an explicitly
independently verified rule across at least two cases, preserves unknown bytes,
and rejects unresolved references.

The existing exact capture-7 all-zero preflight remains valid for its
constrained policy. It is not a generalized state derivation and is not
silently reused for future operations.

## Fail-closed result

`infocarry.i7_readiness.assess_timestamp_fixed_state_eligibility` reports a
non-authorizing result. The current evidence is ineligible because neither a
timestamp generation rule nor a fresh fixed-state derivation is independently
verified. This is a verified negative result: it prevents unsafe promotion of
fixture behavior and does not require another capture by itself.

## Smallest owner procedure if more evidence is approved

No procedure is being executed or requested by this commit. If the owner later
approves a new evidence experiment, use two isolated legacy operations on a
disposable target in separate sessions:

1. Add exactly one newly named root-level TXT item through the legacy Manager.
   Before the operation, record the device clock if visible, the Windows file
   creation and modification times, the Manager source-file time, the complete
   device backup, the complete Manager files, and the exact isolated native
   transaction. Record the operation wall-clock time.
2. After returning to a known stable state, delete exactly that legacy-created
   item in a separate capture. Record the same time sources, complete
   pre/post backups, Manager before/after files, and one native transaction.

Both operations must use one disposable unique name, a documented starting
history/mark/bookmark state, non-overwriting destinations, and explicit
stop-on-error rules. Do not combine add and delete, do not retry, and do not
use a modern sender. The purpose is to correlate candidate `+0x0c` and every
fixed-state field with fresh input across both directions; an operation that
does not preserve a complete transaction and before/after backups is
insufficient. Separate owner approval is required before any device-changing
capture.

## Milestone status

Milestone I.7 is complete for offline characterization, the controlled add-01
evidence gate, and its fail-closed eligibility boundary. General legacy
timestamp/fixed-state reconstruction remains unresolved. I.8 may proceed as a
logical/offline multiple-TXT model; no package write or normal GUI/CLI transfer
action is enabled. The add-01 disposable record remains on the device and no
state-reference or deletion experiment has been performed.
