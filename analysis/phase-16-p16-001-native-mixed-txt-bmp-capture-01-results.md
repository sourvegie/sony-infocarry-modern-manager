# P16-001 — native mixed TXT/BMP Capture 01 results

Date: 2026-08-30  
Status: **BLOCKED_BY_EXTERNAL_EVIDENCE**  
Risk: **R3 — device/safety critical**

## Outcome

The supplied `capture12` tree is preserved unchanged outside Git, and its
native `0x101b` transaction is structurally parseable. It contains a staged
five-record addition for the exact TXT/BMP/TXT package and exposes a useful
native BMP record prefix. The capture is incomplete for the P16 native gate:
there is no complete post-operation raw device backup, no separate event
mapping, and no verbatim Manager result or owner result observation.

The outcome is therefore **BLOCKED_BY_EXTERNAL_EVIDENCE**. The transaction
evidence is not promoted to proof of device persistence, unrelated-data
preservation, capacity/fixed-state behavior, completion, or Manager success.
No modern mixed-package dossier, authorization, or device operation is
prepared from this capture.

## External preservation

The supplied source was `/Users/stardust/Desktop/capture12`. It is preserved
byte-for-byte at:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-16-p16-001-native-mixed-txt-bmp-20260830-01/08-supplied-capture12-raw/`

The source and preserved trees each contain 20 files and their SHA-256 trees
match. The raw USB log is preserved with SHA-256
`e157d3b1a7b28c002e6e065aa0309c53882123da6aeb689d650cabe82879ed0a` and
2,303,476 bytes. The external preservation manifest contains 57 entries;
its entry-list hash is
`9225af04c8968222b4ec745fd21b4b2cc5fb9dee3b4d1b44c9273b1f9cbffc3a` and
the manifest file hash is
`004c12845fbcf7e8997e3d230ab876ff8d31efe6db38caf96345d63e66b547de`.

The exact sanitized fixture remains separately preserved under the external
`00-package/` copy. Its three source hashes remain:

| Order | Native child | Bytes | SHA-256 |
| ---: | --- | ---: | --- |
| 1 | `01-introduction.txt` | 144 | `d16567039a003110d246cc6a0a4d0b2042efa9f2240485f6a5facbb09c00dcb` |
| 2 | `02-page-01.bmp` | 10,302 | `f795a8e1466c3988b804f344645a6208bdcfa27e9d51d8b314c99d9a5973aadd` |
| 3 | `03-ending.txt` | 139 | `a31b66d8b27676dc0af07d32ba4d17b90c54ffa39f406c37a9475672e9e46eec` |

The complete fresh pre-operation backup is independently preserved at
`01-pre-operation/backup-20260830-01/`. Its device identity is `054c:001e`,
its backup manifest SHA-256 is
`8ebc1b28ea83f72b025c0049c7781bfb3d722225b96420972b8ecca28c685382`, and
its dynamic blob SHA-256 is
`70ea314d015e0a0f5de6e35814df8418c42c2faf188849ee88aea309fb226368`.
The backup contains eight objects, 384 records, and 323 reachable paths; the
target folder was absent.

Derived, hash-only reports are outside Git under `07-analysis/`, including
`capture12-evidence-summary-01.json`, the two raw-tree hash listings,
`native-transaction-01/`, and the before/after Manager fixture reports.

## Supplied evidence and completeness

The supplied tree has `before/` and `after/` Manager-local files, three raw
timestamp logs, and one SnoopyPro USB log. The `after/` tree is not a complete
raw device backup: it has only `Backup/VICDATA.bin`, `Memo/VICMEM.bin`,
`Memo/VICLV.bin`, and the nested `order.vnw` sidecar. It has no backup
manifest, fixed-response objects, or complete post-operation `0x8004` blob.
The role directories `04-manager-result/`, `05-post-operation/`, and
`06-timestamps/` were not populated by the supplied tree; the raw copy is
retained under the non-overwriting `08-supplied-capture12-raw/` role.

The three raw timestamp values are:

| Raw log | UTC timestamp | Local timestamp | Supplied event mapping |
| --- | --- | --- | --- |
| `stamp-0001.txt` | `2026-08-30T12:34:40.250Z` | `2026-08-30T21:34:40.250+09:00` | Unresolved; no mapping file supplied |
| `stamp-0002.txt` | `2026-08-30T12:38:25.781Z` | `2026-08-30T21:38:25.781+09:00` | Unresolved; no mapping file supplied |
| `stamp-0003.txt` | `2026-08-30T12:39:13.437Z` | `2026-08-30T21:39:13.437+09:00` | Unresolved; no mapping file supplied |

The raw sequence values are preserved without assigning meanings. No Manager
success/failure wording, screenshot, or owner observation was supplied.

## Native transaction findings

The existing offline parser finds exactly one ordinary `0x101b` header at
record offset `15446` and command offset `15452`. It validates:

- declared length `2,129,804`;
- 524 native payload records;
- `N=0`, `M=2,064,268`;
- range lengths `[256, 64, 65216, 0, 64, 0, 0, 2064204]`;
- transaction end offset `2,300,500`, followed by 2,976 bytes of native log;
- offline artifact manifest SHA-256
  `f348222be6fedc73b3771a4e36de7dd7c1bb434aa258e30bb60f8b60f363e35c`.

The concatenated native range-5/range-8 model is 2,064,268 bytes, parses as a
valid `infoCarry 2.00` blob with checksum verification, and has SHA-256
`6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b`.
It contains 389 records, five more than the 384-record pre-operation model.
The transaction model grew by 320 metadata bytes and 10,668 content bytes,
for 10,988 total bytes.

The transaction-model addition is:

| Record | Offset | Structural facts | Content facts |
| --- | ---: | --- | --- |
| Folder | `0x3c0` | `IC_P16_MIXED_20260830_01`, directory, child table 256 bytes, timestamp `0x6a942449` | — |
| Leading marker | `0x400` | directory `..`, points to folder `0x3c0`, timestamp `0x6a942449` | — |
| Introduction | `0x440` | direct child, unread TXT, `field_14=0x200`, payload offset `0x6300` | 144 bytes; payload hash equals the prepared introduction hash; 32-byte prefix hash `d0bcc6bc85dc36cdc1ad3882952c5d3d4414869c0bdd75b3b58ba28a32deb92a` |
| BMP page | `0x480` | direct child, unread BMP, `field_14=0x100`, payload offset `0x63a0` | 10,302 bytes; payload hash equals the prepared BMP hash; 16-byte prefix is all `ff`, hash `5ac6a5945f16500911219129984ba8b387a06f24fe383ce4e81a73294065461b` |
| Ending | `0x4c0` | direct child, unread TXT, `field_14=0x200`, payload offset `0x8c00` | 139 bytes; payload hash equals the prepared ending hash; same 32-byte TXT prefix hash |

The folder table therefore has the expected marker plus three children in
the requested order. These are **verified properties of the parsed native
transaction model**, not verified properties of a persisted post-operation
device state. The transaction model contains no extra target child and no
BMP transformation was observed.

The native transaction also records the exact BMP wrapper observation needed
to correct the offline size/template model: a 16-byte all-`ff` BMP prefix,
versus the 32-byte TXT prefix. This is an observed native transaction rule;
post-operation persistence remains unresolved.

## Manager-local and result classifications

The before/after Manager fixture reports both parse successfully with 2,035
records and 1,856 reachable records in their local `VICDATA.bin` snapshots.
`VICDATA.bin` is byte-identical before/after at
`72142be59413acdbd4c065fad9d16c2e50bc05d77e316844528de802b689b728`;
`VICMEM.bin` and `VICLV.bin` are also byte-identical. The Manager-local
`order.vnw` changed from 253 to 279 bytes, and its after-sidecar correlation
contains `IC_P16_MIXED_20260830_01` while the before-sidecar does not.

This is **observed Manager-local bookkeeping**, not proof that the target
exists in device-resident `VICDATA`. No complete post-operation backup was
supplied to compare against the native transaction model. No operation-wide
capacity response, post fixed-state object set, post timestamp set, or
decoded numeric completion is supplied. The trailing native log bytes are
retained and are not normalized into `0x0000`.

## Evidence classifications

### Verified

- Raw `capture12` preservation and hash equality.
- Fresh pre-operation backup completeness, identity, hashes, record counts,
  and target absence.
- One ordinary native `0x101b` transaction with internally consistent
  declaration, range split, `N/M`, and checksum-validated staged model.
- Five-record transaction-model addition with folder, parent marker, child
  order, record offsets, native fields, and exact transaction payload hashes.
- Exact TXT and BMP source-payload equality within the staged transaction.
- The 16-byte native BMP prefix observation and 32-byte TXT prefix observation.

### Observed

- Manager-local `order.vnw` changed and gained the target root name.
- Manager-local `VICDATA.bin`, `VICMEM.bin`, and `VICLV.bin` did not change.
- The three raw timestamp values and their sequence identities.

### Inferred

- The legacy Manager generated the staged five-record transaction for the
  selected mixed package.
- The 16-byte BMP prefix is the native wrapper for this exact observed
  mixed-package transaction.

### Unresolved

- Device persistence of the folder and children, because the complete post
  backup is missing.
- Manager success/failure result and owner observation.
- Timestamp event meanings.
- Operation-specific capacity and post fixed-state behavior.
- Numeric request-4/transfer completion; no explicit `0x0000` is accepted.
- Candidate/post-backup equality and preservation of unrelated records,
  payloads, objects, and timestamps.

## Offline reconciliation and safety gate

The offline typed-media model now uses the observed 16-byte BMP prefix for
BMP size accounting, keeps the established 32-byte TXT prefix for TXT, and
requires type-appropriate templates in the existing offline candidate
builder. The P16 fixture now calculates 10,668 aligned content bytes and a
10,988-byte offline lower-bound growth estimate, matching the native
transaction model for this capture. Focused regression coverage verifies the
BMP wrapper length, mixed size accounting, exact source payloads, and the
16-byte BMP candidate template boundary.

No timestamp, fixed-state, capacity, persistence, completion, unrelated-data,
or public transfer behavior was changed. No modern mixed candidate,
authorization, smoke dossier, or hardware transaction was prepared. The
normal GUI/CLI transfer boundary remains disabled.

The native mixed-package gate remains closed. If the owner has the missing
complete post-operation raw backup, Manager result/observation, timestamp
mapping, or operation-specific capacity evidence, those files may be
supplied for a new non-overwriting intake. A repeat device operation is not
requested or authorized by this report.
