# I.7 legacy stateful deletion — attempt 01 synthesis

Date: 2026-08-25
Status: **Persisted legacy deletion effect verified; general deletion remains
fail-closed and unproven.**

This report is a sanitized summary of the separately approved
`I7-LEGACY-DELETE-01` evidence session. Original captures, complete backups,
Manager files, timestamp logs, and transaction ranges remain outside Git under
the local evidence root. The derived machine-readable report is
`EVIDENCE_ROOT/phase-13-i7-legacy-delete-20260825-01/06-analysis/i7-legacy-delete-01-offline-analysis.json`.

## Evidence identity

The target was the legacy-created disposable item:

`root\\IC_I7_CLOCK_01.txt`

The complete pre-delete backup reported 374 records, dynamic-model SHA-256
`5b081faf7cc733e9c63c13250d689d6e7beb52bcf10470503dd68684471ab61b`, and the
authoritative nonzero state. The complete post-delete backup reported 373
records and dynamic-model SHA-256
`fbfe0dc9898a0cd6c406bd26542859282a1a410b059b16812c32522a9ce8e450`.

The saved SnoopyPro file has SHA-256
`b6f5957a94a65fc0dca768f1f5bd97fe8c3c2942d0a3156d9b4191ac3c80873a` and the
offline parser found exactly one ordinary `0x101b` transaction. Its native
range-5 plus range-8 candidate is byte-identical to the complete post-delete
dynamic blob: 2,051,420 bytes with SHA-256
`fbfe0dc9898a0cd6c406bd26542859282a1a410b059b16812c32522a9ce8e450`.

The current parser does not recover a trustworthy request-4 completion value.
Completion wording/value is therefore unresolved. The persisted post-backup
effect is independently verified and must not be conflated with a verified
Manager success message.

## Verified device effect

- Exactly `root\\IC_I7_CLOCK_01.txt` was removed.
- No path was added.
- The target record was at absolute offset `0x380`, with metadata-relative
  reference `0x340` and a 1,863-byte payload.
- The target payload SHA-256 was
  `3aa626dc1e0dbd2fe13b59fbea7eddf43358a522b9f55ed15ac18556b2a69d4b`.
- The metadata region shrank by 64 bytes.
- The content region shrank by 1,896 bytes: the target payload and native
  prefix removal rounded to the observed four-byte alignment.
- Total dynamic-model reduction was 1,960 bytes.
- 302 surviving record offsets moved by `-0x40`; 12 remained unchanged.
- 250 surviving file content pointers moved by `-0x768` and 58 directory
  pointers moved by `-0x40`; the remaining six pointers were unchanged.
- All 255 surviving file payloads were byte-identical.
- Shared flags, `field_10`, and `field_14` values were unchanged.

These are observations of this complete pre/transaction/post sequence, not a
general deletion builder rule.

## Stateful reference transition

The authoritative pre-delete fixed state contained the target reference in
display history, Mark 1, and Bookmark 1:

- `0x001b`: count 1, reference `0x340`;
- `0x001c`: count 1, reference `0x340`;
- `0x001d`: count 0;
- `0x001e`: count 0;
- `0x001f`: first group `(0x340, 0, 0x80000000, 0, 0)`, second group zero.

The post-delete backup contained all-zero objects for `0x001b` through
`0x001f`. Thus the three active references were cleared in this observed
stateful deletion. The before/after SHA-256 transitions were:

| Object | Before | After | Classification |
| --- | --- | --- | --- |
| `0x001b` | `c9873fb6...b6b04` | `f5a5fd42...fb4b` | verified target-reference clearing |
| `0x001c` | `c9873fb6...b6b04` | `f5a5fd42...fb4b` | verified target-reference clearing |
| `0x001d` | `f5a5fd42...fb4b` | `f5a5fd42...fb4b` | verified unchanged zero state |
| `0x001e` | `f5a5fd42...fb4b` | `f5a5fd42...fb4b` | verified unchanged zero state |
| `0x001f` | `4f25288f...7273` | `f5a5fd42...fb4b` | verified Bookmark 1 clearing |

The abbreviated hashes above are expanded in the external derived JSON report.
This does not prove how arbitrary referenced or unresolved state must be
rebased in a future operation.

## Timestamp observation

All 314 shared record timestamps changed. The pre-delete model contained
timestamps corresponding to 2026-08-24 13:48:19–14:00:24 UTC. The post-delete
model contained values corresponding to 2026-08-25 12:36:59–12:37:01 UTC.

The validated Windows timestamp sequence was:

1. `stamp-0001`: immediately before the successful Restart Device action;
2. `stamp-0002`: after Manager initialization and packet-idle state;
3. `stamp-0003`: immediately before deletion.

The post-delete metadata timestamps align with the restart/initialization
interval rather than `stamp-0003`. This is a useful negative characterization,
not a proven causal rule. The source of the operation-wide timestamp rewrite
and its relationship to Manager initialization remain unresolved.

## Manager-local files

The relevant Manager files were byte-identical before and after deletion:

- `VICDATA.bin`: `72142be5...b689b728`;
- `VICMEM.bin`: `50480ccd...4bd809e`;
- `VICLV.bin`: `86f79cd4...d869eb2`;
- the applicable `order.vnw`: `13609c2c...bfd50fcd`.

The AFTER intake also contained two `.DS_Store` artifacts; they are local
filesystem artifacts, not Manager sidecars, and are excluded from the parity
claim.

## Gate result and remaining boundary

The stateful legacy deletion effect is now verified for this one disposable
legacy-created TXT record. This closes the missing evidence observation for
H.2's captured legacy effect, but it does **not** close generalized deletion
eligibility:

- the timestamp-generation rule remains unresolved;
- request-4 completion remains unavailable from the preserved native log;
- physical interrupted-write atomicity and recovery remain unproven;
- no modern delete builder, sender, GUI control, or CLI action is authorized.

The exact post-backup result is authoritative for persisted device state. The
Manager result wording, if unavailable, remains an explicit evidence
limitation. No retry was performed.
