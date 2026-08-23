# Milestone H.1 — live-delete generalization and readiness

Date: 2026-08-23
Status: **Active and fail-closed; no live delete is eligible or authorized.**

This note records read-only analysis after the complete captured-fixture
Milestone H gate. It does not modify preserved evidence or legacy binaries, and
it does not prepare a device-changing command.

## Decision

Milestone H is complete only for the exact attempt-02 offline reproduction. The
current implementation is not a general fresh-backup deletion model because it
requires:

- a complete caller-supplied opaque timestamp map for every surviving record;
- `DeleteFixedState.attempt02()`, which contains the captured attempt-02
  transmitted fixed-state shape; and
- no independently justified rule for deriving those values from a new fresh
  backup and a newly selected target.

Milestone H.1 therefore remains active. The framework-independent readiness
model in `src/infocarry/delete_readiness.py` reports these facts as blockers.
It is an eligibility report only; it is not an authorization or sender.

## Metadata `+0x0c` comparison

The machine-readable comparison is
`analysis/phase-12-milestone-h1-timestamp-comparison-2026-08-23.json`.
The attempt-01 and attempt-02 pre-delete backups contain the same four source
values, including three consecutive Unix-like values and two special records.
The surviving records in both native candidates are rewritten to three
consecutive values, but the windows differ:

| Operation | Candidate UTC window | Candidate records | Common pre/post timestamp changes |
| --- | --- | ---: | ---: |
| Attempt 01, failed Manager operation | 03:47:08–03:47:10 | 367 | 0 in the actual post-attempt backup; candidate differs |
| Attempt 02, persisted legacy delete | 05:18:56–05:18:58 | 367 | 310 |
| Clean legacy add 04 | 03:55:34–03:55:36 plus one special value | 367 | 308 |
| Modern add G | no common-record rewrite | 368 | 0 |
| Existing replacement | no common-record rewrite | 366 | 0 |

The pre-to-candidate mappings also cross the source timestamp groups rather
than following a simple record-position partition. The values look time-like,
but the evidence does not identify whether they are generated from operation
time, a device clock, source metadata, or an opaque counter. Using current time,
zero, preserved values, or the attempt-02 map would be an unsupported safety
assumption. The rule is unresolved and live eligibility remains false.

## Static analysis

Read-only disassembly of the preserved `VicTwo.dll` (SHA-256
`a02e5927d2e5ded988556e0be0e79a38313ce91f6491ad0ac8835971d3db0dae`) confirms a
file-time helper:

- `0x10008b80` calls the imported `FileTimeToLocalFileTime` and
  `FileTimeToSystemTime` functions and passes converted components to
  `0x1000a060`;
- `0x10008900` and `0x10008a30` call that helper three times and store its
  results at offsets `+0x04`, `+0x08`, and `+0x0c` in a source-side structure;
- `0x10001930` is the known source-node-to-wire-record serializer; and
- no static path was established from the file-time helper through the write
  worker to raw metadata record offset `+0x0c`.

The `+0x0c` read at `0x10004880` is used in model allocation/length logic and
must not be treated as proof that it writes the raw metadata timestamp. Static
analysis therefore narrows the possibilities but does not recover a safe
write-side rule. No legacy program was executed on macOS.

## Fresh fixed-state derivation

Attempt 02 verifies a narrow result: `0x001b`, `0x001c`, `0x001e`, and `0x001f`
match stable post-backup state; `0x001d` transmits `count=0`, `value_04=1`, and
empty offsets, then stabilizes as `value_04=0`. Attempt 01 contains an
additional unexplained `0x001e` two-byte difference and changed several fixed
objects after a failed operation.

This is enough to preserve the attempt-02 golden comparison and the single
documented read-back normalization. It is not enough to derive every fixed
state block from an arbitrary fresh backup, preserve unknown references, and
reject unresolved state membership safely. A new derivation function is not
implemented. `DeleteFixedState.attempt02()` remains a golden-fixture helper
only, never a default for a different live deletion.

## Eligibility and next evidence boundary

The H.1 readiness result must reject a target when any of the following is
unknown: the timestamp rule, fixed-state derivation, target state references,
exact candidate/transaction binding, preserved unrelated payloads, or storage
for complete before/after evidence. A captured candidate that reproduces
attempt 02 is not a live-eligibility result.

The readiness model adds four focused tests. The complete canonical suite now
passes **283 tests**; the preceding Milestone H closure checkpoint was 279.

The smallest safe evidence that could resolve H.1 is a preserved write-side
static trace or an independently controlled legacy comparison that binds the
metadata `+0x0c` values and every changed fixed-state field to fresh input. No
additional legacy capture is requested automatically. Until that evidence
exists, do not implement a live-capable workflow, prepare a live-smoke
protocol, open a write-capable transport, expose a delete control, or begin
Milestone I.

Classification remains explicit:

- **Verified:** attempt-02 persisted removal, exact candidate/post blob match,
  and the narrow observed `0x001d` normalization.
- **Observed:** time-like three-second candidate windows and file-time helper
  code in `VicTwo.dll`.
- **Inferred:** the structural one-record removal and alignment/rebase behavior
  for the captured root-level shape.
- **Unresolved:** general timestamp generation, complete fresh-state derivation,
  physical atomicity, and recovery after interruption.
