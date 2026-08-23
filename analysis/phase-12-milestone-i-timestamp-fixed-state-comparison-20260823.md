# Historical comparison supporting Milestone I.7

Date: 2026-08-23
Status: **Read-only comparison complete; no safe generalization established.**

This analysis compares the preserved capture-7 folder package, clean legacy
root-TXT add capture 04, approved modern root-TXT add evidence, and the
successful existing-text replacement evidence. It reads only preserved files;
it performs no USB operation and does not modify evidence.

The machine-readable comparison is
`analysis/phase-12-milestone-i-timestamp-fixed-state-comparison-20260823.json`.

## Metadata field `+0x0c`

The field is consistently parseable as a valid big-endian Unix timestamp. Its
generation rule is not established:

| Operation | Shared timestamp result | New-record result |
| --- | --- | --- |
| Legacy capture 04, one root TXT | all 309 shared records changed | new record `0x6a8a24b4` (`2026-08-22T22:37:40Z`) |
| Legacy capture 7, one folder plus TXT | all 310 shared records changed | folder and child share `0x6a8aba6f` (`2026-08-23T09:16:31Z`) |
| Modern root-TXT add | all 310 shared records unchanged | new record also has `0x6a8a24b4` |
| Existing-text replacement | all 309 shared records unchanged | no new record |

The legacy behavior shows operation-wide timestamp rewriting, while the modern
root-TXT add and existing-text replacement preserve shared timestamps. The
folder and child sharing one timestamp is an observation, not a construction
rule. The modern add reusing a timestamp already present in its baseline is
also insufficient to establish whether the value is copied, operation-time
derived, or supplied by another Manager-local source. No current-time,
preserved-time, or copied-time policy is promoted.

## Fixed-state comparison

Capture 7's `0x001b` through `0x001f` responses are byte-identical before and
after, with zero counts and zero groups. This verifies preservation for that
fixture but does not exercise fresh membership derivation.

Clean root-TXT add evidence independently shows the narrow offset behavior:

- `0x001b` rebases counted metadata offsets by the inserted `0x40` record;
- `0x001e` rebases its counted offset by `0x40`; and
- `0x001f` rebases its grouped record offsets by `0x40`.

The modern root-TXT add shows the same offset-rebasing pattern. Existing-text
replacement leaves all five fixed-state objects unchanged. These observations
support preservation and proven offset rebasing where a known reference is
present; they do not derive how a new folder or child should be represented in
nonzero state structures.

## Decision

The comparison does not close the fresh timestamp or folder fixed-state gate.
The capture-7 builder must continue to require an explicit captured timestamp
map and a preserved capture-shaped template. The transfer preview must remain
ineligible for fresh folder/package construction. No live package workflow,
normal GUI/CLI package action, or additional hardware capture is authorized or
required by this result.

This is a verified negative result, not a failed experiment: the available
evidence is sufficient to reject unsafe generalization. Milestone H.1 remains
parked. Milestone I.7 is complete for offline characterization, while I.8 and
later protocol-generalization work remain offline-first. J.0-J.2 are complete;
J.3 remains deferred until the relevant package operations are proven.
