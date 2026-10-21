# P18-046 — exact root-BMP placement R3 review

Date: 2026-10-17 JST. Review risk: **R3**. Reviewed implementation head:
`3b525d833ad572ddc3d5dd9cfabb5084bfd2f9ef` on
`task/P18-046-sanitized-root-bmp`.

## Disposition

**PASS — P0/P1/P2 = 0/0/0 after one correction round.** The candidate is
`READY_FOR_HARDWARE_TEST` only for the exact disposable root-level BMP fixture
on VNW-V15, after a fresh live backup/capacity preflight and separate
operation-specific owner authorization. The review does not establish physical
root-BMP behavior. General BMP Add, BMP Delete, other file shapes, VNW-V10,
interrupted-write recovery, and production capability promotion remain
disabled.

## Review and correction

The reviewer independently inspected the exact candidate-builder, facade,
authorization, one-shot execution, and readback changes against the previous
head, the existing guarded placement architecture, tests, and cited native
BMP/root-TXT evidence. Initial review found:

- **P1 — Protected-state references.** An aligned but dangling active
  reference could previously be rebased and sealed. The correction now
  requires every active offset-list and bookmark pointer to resolve to a
  reachable file before insertion and to the same surviving path after
  insertion. Dangling, null, directory, and changed-target references fail
  closed before sealing/sender execution.
- **P2 — File allocation geometry.** A checksum-valid baseline could contain
  overlapping file allocations. The correction now requires reachable file
  segments to be four-byte aligned, within the content region, and mutually
  disjoint in both the baseline and generated candidate.

The reviewer reproduced both initial defects and independently replayed the
corrected dangling/null/non-file reference and overlap cases. Each now rejects
before operation sealing or sender activity. A saved complete archive also
produced a valid host candidate; the fixture source remained unchanged. No
additional material findings remained for authorization binding, claim/marker/
global-lock lifecycle, sender invocation/no-retry behavior, independent
readback, or the UI/CLI boundary. No files were modified by the reviewer.

## Validation

- Correction-focused portable tests: **52 run, 50 passed, 2 established
  evidence skips**. Log: `/private/tmp/p18-046-r3-correction-focused.log`.
- Full portable suite: **1,219 run, 1,214 passed, 5 established evidence
  skips**, exit 0. Log: `/private/tmp/p18-046-r3-correction-full.log`.
- `git diff --check` and Python 3.12 `compileall`: passed.
- Python used: `/opt/homebrew/bin/python3.12`; the isolated repository has no
  local `.venv`, so the canonical checkout's Python 3.12 packages supplied the
  existing test dependencies.
- Physical device operation, USB access, and production safety-state mutation:
  none.

The initial review commit `5c0960640121db7a3acb1cf437874846792a4e6d` was
**CHANGES REQUIRED**, P0/P1/P2=0/1/1. Both findings were fixed in one correction
commit and closed by the exact-head review above. The tested operation remains
only a prepared modern hardware experiment; the actual operation identity will
be frozen from a fresh complete device backup and capacity response at its
separately authorized live preflight.
