# Milestone H — offline analysis of failed delete attempt 01

Date: 2026-08-22
Status: **Offline evidence only; no delete model or modern delete is
authorized.**

This note compares the preserved failed legacy attempt with the complete
pre/post backups and the existing synthetic leaf-delete helper. It does not
replay the native log, write any candidate, contact USB, or modify the source
capture or backup archives.

## Inputs and integrity

| Input | Location | Verified result |
| --- | --- | --- |
| Native SnoopyPro log | Stable evidence `owner-original/usblog/01-delete.usblog` | 2,288,872 bytes; SHA-256 `3f20d9e0bdc4705bb4dafe97ba8e43960b122006dd216e6723b433bc0c3ee4fc` |
| Parsed native candidate | Stable evidence `derived-analysis/native-delete-artifact/` | `0x101b`, `N=0`, `M=2,050,848`; USB transmission performed: false |
| Pre-delete backup | Stable evidence `derived-analysis/pre-delete-actual/` | Complete, eight objects, device `0x054c:0x001e`; manifest SHA-256 `9be0fe3779f8ff74ba722ea48bf46035477a3b1874f392027d2a0793fc785342` |
| Post-attempt backup | Stable evidence `derived-analysis/post-delete-actual/` | Complete, eight objects, device `0x054c:0x001e`; manifest SHA-256 `c5377d1df55fa9000e8323f0fcb4f3b4d81c74a06847315591aefd02a380e865` |
| Failure screenshot | Stable evidence `derived-analysis/owner-supplied/failure-dialog.png` | SHA-256 `1f3fe7d25a1a54abbafe4dc58bd63d41a64c7658e71291b3cdd04f80790bc195` |

The stable root for all paths above is
`${EVIDENCE_ROOT}/phase-12-milestone-h-delete-attempt-20260822-01/`.

The native log contains one parseable ordinary `0x101b` transaction. Its
payload lengths are `[256, 64, 65216, 0, 64, 0, 0, 2050784]`; the
concatenated range-5 plus range-8 candidate is 2,050,848 bytes and has SHA-256
`5f13702c014aa49e245fb27ad4bb593119b3a63e27ecf1534fb48bd07fca4a08`.
The candidate parses with the existing strict backup parser and passes its
checksum validation. The native log and candidate are evidence, not an
authorization artifact.

## Whole-blob comparison

| State | Blob bytes | Metadata records | Reachable paths | Metadata length | Content start | Content length | Stored checksum |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Fresh pre-delete backup | 2,051,000 | 368 | 311 | 23,552 | `0x5c40` | 2,027,380 | `0x32582396` |
| Complete post-attempt backup | 2,051,000 | 368 | 311 | 23,552 | `0x5c40` | 2,027,380 | `0x32582396` |
| Native deletion-shaped candidate | 2,050,848 | 367 | 310 | 23,488 | `0x5c00` | 2,027,292 | `0x4ea0830d` |
| Refined offline `delete_existing_file()` result | 2,050,848 | 367 | 310 | 23,488 | `0x5c00` | 2,027,292 | `0x4e380510` |

The pre- and post-attempt dynamic blobs are byte-identical with SHA-256
`aec90438c1323400b2f4d4210541c599600f4e9493596edc710bd676dee8adf6`.
The post-attempt backup therefore proves that the selected record was not
deleted from the device. It does not prove that the entire device state was
unchanged: four fixed response objects changed after the failed operation.

## Record and payload result

The native candidate removes exactly one reachable path:

```text
root\IC_G_LIVE_20260822_01.txt
```

There are no added paths. Every other shared reachable path retains its
record kind, extension, name, and file payload. The 310 shared file payloads
are byte-identical between the pre-delete blob and the native candidate. This
is a strong structural deletion-shaped result, but it is not successful
device proof because the candidate was never confirmed by the device and the
Manager displayed failure.

The selected pre-delete record is at metadata offset `0x300`, with content
offset `0x1ac`, a 32-byte native prefix, and a 53-byte payload. Its occupied
content segment is therefore 85 bytes (`0x55`). The first following file
segment begins at `0x204` in the pre-delete blob:

| Segment | Pre-delete content range | Native candidate content range | Synthetic helper range |
| --- | ---: | ---: | ---: |
| Target prefix + payload | `0x1ac..0x201` (85 bytes) | removed | removed |
| `root\簡易マニュアル\各部の名前とはたらき` | `0x204` | `0x1ac` | `0x1af` |

The native candidate shifts the following content by `0x58` (88 bytes), not
by the occupied 85 bytes. This matches rounding the deleted segment up to a
four-byte boundary. The refined offline helper now removes that aligned
segment, produces the same length and layout, and preserves the same shared
paths and payloads. Its remaining blob difference is the native candidate's
global timestamp rewrite: copying the native timestamps into the refined
helper and recomputing the checksum produces byte-identical output. That
normalization is a comparison result, not a recovered timestamp-generation
rule.

## Metadata pointer and child-table differences

The native candidate supplied two concrete corrections to the exploratory
helper for this target shape. Both are now represented by the refined
offline helper, with regression coverage in commit `d203ad0`:

1. A metadata pointer equal to the removed record offset is rebased. The
   `簡易マニュアル` directory at `0x180` points to `0x300` before deletion;
   the native candidate changes it to `0x2c0`. The refined helper now treats
   this exact-boundary pointer like a pointer after the removed record.
2. The root child-table length changes from `0x2c0` to `0x280`. Four `..`
   marker records also change their `field_08` from `0x300` to `0x2c0`:
   native offsets `0x300`, `0x14c0`, `0x37c0`, and `0x5b80` (pre-delete
   offsets `0x340`, `0x1500`, `0x3800`, and `0x5bc0`). Their exact semantic
   role is not assigned here; the byte changes are observed and must be
   preserved by any later model.

After normalizing away the candidate's timestamp field, the refined helper's
metadata, names, flags, extensions, native prefixes, payloads, pointer
rebases, child-table changes, and all file content offsets match the native
candidate exactly. The helper still does not generate the native timestamps,
fixed-state ranges, sidecars, completion, or a device operation.

## Timestamp behavior

All 367 remaining metadata records have a timestamp different from the fresh
pre-delete backup. The native candidate uses three consecutive values:

| Timestamp | UTC rendering | Records |
| --- | --- | ---: |
| `0x6a8a6d3c` | `2026-08-23T03:47:08Z` | 165 |
| `0x6a8a6d3d` | `2026-08-23T03:47:09Z` | 130 |
| `0x6a8a6d3e` | `2026-08-23T03:47:10Z` | 72 |

The refined helper preserves the pre-delete timestamps. The candidate shows
that the legacy rebuild may rewrite record timestamps while constructing the
deletion-shaped blob, but this capture does not establish whether the field
is a deletion timestamp, a source-file timestamp, a Manager clock effect, or
another rebuild-time value. A later delete model must either recover this
policy from successful isolated evidence or keep timestamp equivalence
explicitly normalized and unverified.

## Fixed device state

The native fixed ranges were compared both byte-for-byte and against a
metadata-reference-rebased version of the fresh pre-delete state. The
rebase used here subtracts `0x40` from counted metadata-relative references
at or after removed offset `0x300`; it does not invent membership or alter
unused tails.

| Response | Fresh pre-delete | Native candidate | Native vs rebased pre |
| --- | --- | --- | --- |
| `0x001b` | 9 offsets beginning `0x340, 0x380` | 9 offsets beginning `0x300, 0x340` | Exact |
| `0x001c` | Count 0 | Count 0 | Exact |
| `0x001d` | Count 0 | Count 0 | Exact |
| `0x001e` | One offset `0x340` | One offset `0x300` | Only bytes `+0x06..+0x07` differ: `0x0000` vs `0x6e69` |
| `0x001f` | Bookmark record offsets `0x340, 0x380` | `0x300, 0x340` | Exact |

This corrects the earlier shorthand that called the native fixed ranges
“stale.” They are not byte-identical to the fresh backup, but four blocks
exactly follow the deletion rebase and one block has one unresolved two-byte
field. The native candidate therefore provides useful state-rebase evidence;
it still does not establish delete success, completion semantics, sidecar
policy, or safe replay from an arbitrary fresh state.

The actual post-attempt backup is a different result from the native
candidate. Relative to pre-delete, `0x001b`, `0x001d`, `0x001e`, and `0x001f`
changed, while `0x001c`, `0x0024`, and the dynamic blob did not. The post
state has `0x001b` count zero, a new `0x001d` offset `0x300`, `0x001e` count
zero, and changed grouped values. The cause is unresolved and must not be
assigned to deletion or interpreted as rollback.

## Manager-local files

The before/after Manager snapshots are byte-identical for all supplied files:

| File | SHA-256 |
| --- | --- |
| `Backup/VICDATA.bin` | `72142be59413acdbd4c065fad9d16c2e50bc05d77e316844528de802b689b728` |
| `Memo/VICMEM.bin` | `4a0bcfe3a2bbbb62ab872a16f4e30e1b4f7b0419096a98dd740cf1c2c49d3499` |
| `Memo/VICLV.bin` | `86f79cd4d3edf092149203fb9d35dbe212d5651e24c3123f70d931a74d869eb2` |
| `ICM/転送元フォルダ/order.vnw` | `824ec471ffee0154f982a94a7ec4dd0aef7b1f1d6208f0febd94e2f66fc46894` |

Both fixture reports contain 2,035 records, 1,856 reachable records, 1,677
files, and 179 directories. No Manager-local sidecar mutation is observed.
This is a verified negative result for this failed attempt, not proof that
sidecars are never involved in successful deletion.

The byte-identical before/after `order.vnw` contains the legacy-created
basename `IC_E_ADD_20260822_04.txt` but does not contain the modern-created
basename `IC_G_LIVE_20260822_01.txt`. This is a verified Manager-bookkeeping
difference and a plausible, not proven, contributor to attempt 01's failure.
For that reason the same target must not be retried blindly; the corrected
attempt-02 protocol selects the Manager-known `_04` disposable record.

## Failure and recovery interpretation

The owner supplied a Manager failure dialog reading “Data transmission
failed” and reported that the Manager preview became empty. The complete
post-attempt backup contradicts the preview as a representation of persisted
device content: the target and dynamic blob remain unchanged. Because the
device-changing transaction began, the correct immediate classification was
an indeterminate device outcome, not a guaranteed rollback or unchanged
device. The later complete backup resolves the selected-record question but
also records unexplained fixed-state changes.

No completion value proving success is present in this failed evidence. No
retry, modern delete, or candidate transmission occurred. The capture does
not prove physical atomicity, rollback, or recovery behavior.

## Gate decision and next safe work

This attempt advances offline understanding but does not close Milestone H:

- **Verified:** one native deletion-shaped candidate removes exactly the
  target; all shared payloads are preserved; four fixed-state blocks follow
  deletion rebasing; the target remains in the actual post-attempt backup;
  Manager sidecars are unchanged in the supplied snapshots.
- **Observed:** Manager failure, empty preview report, global candidate
  timestamp rewrite, one unexplained `0x001e` two-byte state field, and four
  `..` marker length changes.
- **Inferred:** for this root-level target shape, the native builder removes
  an aligned 88-byte content segment and rebases metadata pointers at `>=`
  the removed record offset. The refined offline helper reproduces this
  structure and matches the native candidate after timestamp normalization.
- **Unresolved:** successful deletion completion, whether the fixed-state
  `0x001e` field is required, timestamp policy, general parent-marker
  semantics, sidecar policy on success, failure atomicity, and exact
  operation binding for a modern delete.

The refined offline delete helper remains comparison-only and must not feed a
modern sender. It makes the observed alignment and exact-boundary rebasing
rules explicit without exposing device I/O. A successful isolated legacy
delete capture remains required before any modern delete approval.
