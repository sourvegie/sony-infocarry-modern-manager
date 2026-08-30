# P16-001 — native mixed TXT/BMP Capture 01 results

Date: 2026-08-30
Status: **BLOCKED_BY_EXTERNAL_EVIDENCE**  
Risk: **R3 — device/safety critical**

## Outcome

The supplied Capture 01 tree remains preserved byte-for-byte outside Git. A
new read-only post-operation backup was obtained after the initial intake and
is complete under the established external evidence root. Its eight object
hashes validate, its device identity is 054c:001e, and its dynamic blob
exactly equals the native transaction model extracted from the preserved
SnoopyPro log.

This resolves the previously reported missing-post-backup blocker. The
complete post state now verifies persistence of the exact flat TXT/BMP/TXT
package, the folder and marker structure, source payload equality, and
unchanged shared file payloads and fixed-state objects. The native transaction
and post-backup model contain no unexplained structural or payload difference.

The overall native gate remains **BLOCKED_BY_EXTERNAL_EVIDENCE** because the
preserved evidence still has no separate Manager success/failure observation,
no event mapping for the three raw timestamp logs, no validated
operation-specific capacity response, and no independently decoded explicit
0x0000 completion. These are retained as unresolved; they are not inferred
from persistence. No modern mixed-package dossier or device transaction is
prepared.

## External preservation and post-operation backup

The supplied source was /Users/stardust/Desktop/capture12. It is preserved
byte-for-byte at:

/Users/stardust/Projects/InfoCarry-Evidence/phase-16-p16-001-native-mixed-txt-bmp-20260830-01/08-supplied-capture12-raw/

The source and preserved trees each contain 20 files and their SHA-256 trees
match. The raw USB log is preserved with SHA-256
e157d3b1a7b28c002e6e065aa0309c53882123da6aeb689d650cabe82879ed0a and
2,303,476 bytes.

The exact sanitized fixture remains separately preserved under the external
00-package copy. Its three source hashes are:

| Order | Native child | Bytes | SHA-256 |
| ---: | --- | ---: | --- |
| 1 | 01-introduction.txt | 144 | d16567039a003110d246cc6a0a4d0b2042efa9f2240485f6a5facbb09c00dcb |
| 2 | 02-page-01.bmp | 10,302 | f795a8e1466c3988b804f344645a6208bdcfa27e9d51d8b314c99d9a5973aadd |
| 3 | 03-ending.txt | 139 | a31b66d8b27676dc0af07d32ba4d17b90c54ffa39f406c37a9475672e9e46eec |

The fresh pre-operation backup remains preserved at
01-pre-operation/backup-20260830-01/. Its manifest SHA-256 is
8ebc1b28ea83f72b025c0049c7781bfb3d722225b96420972b8ecca28c685382 and its
dynamic blob SHA-256 is
70ea314d015e0a0f5de6e35814df8418c42c2faf188849ee88aea309fb226368. It has
eight objects, 384 records, 323 reachable paths, and no target folder.

The newly obtained complete post-operation backup is preserved at
05-post-operation/backup-20260830-02/. Its manifest SHA-256 is
3772f3b6a6dc639af131f76986159f2621ac9913c876fc8504a5119943253dfd. The
manifest state is complete; all eight listed object hashes match their files.
Its dynamic object is 2,064,268 bytes with SHA-256
6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b. It parses
with a valid InfoCarry checksum as 389 records and 327 reachable paths.

The independent post-backup verification is recorded outside Git at
07-analysis/capture12-post-backup-verification-01.json with SHA-256
b66dd234013f55286a41f1de2233e2327610d9cc0a6d60043ce8375e6af05f52. The
version-02 preservation manifest is
preservation-manifest-02.json with 68 verified entries, entry-list hash
e0c5ebec6004b4f6fba2330f4a6c0fcfada30dfe48f7e0de3a2dd9e6ee95c420, and
manifest SHA-256
56477f6714469eb4f73ae8b5b5d14d4574dbc2489bdbe2ea81e82d2eba264b4b. It
supersedes the historical intake manifest without modifying raw evidence.

## Native transaction and post-backup equality

The existing offline parser finds exactly one ordinary 0x101b header at
record offset 15,446 and command offset 15,452. It validates:

- declared length 2,129,804;
- 524 native payload records;
- N=0 and M=2,064,268;
- range lengths [256, 64, 65216, 0, 64, 0, 0, 2064204];
- transaction end offset 2,300,500 followed by 2,976 bytes of native log.

The concatenated native range-5/range-8 model is 2,064,268 bytes with SHA-256
6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b. The
complete post-backup dynamic object has exactly the same length and hash and
is byte-identical to this model. Both models pass the repository backup
parser and checksum validation.

The fresh pre-operation model had 384 records, metadata length 24,576,
content length 2,028,636, and total length 2,053,280. The post model has 389
records, metadata length 24,896, content length 2,039,304, and total length
2,064,268. The native operation therefore added 320 metadata bytes and
10,668 content bytes, for 10,988 bytes total.

## Exact added structure and payloads

The post-backup target is the expected new root folder:
root\IC_P16_MIXED_20260830_01

| Record | Offset | Native facts | Payload facts |
| --- | ---: | --- | --- |
| Folder | 0x03c0 | directory; child table 0x100 bytes; timestamp 0x6a942449 | — |
| Leading marker | 0x0400 | name ..; field_04 0x40; field_08 0x3c0; timestamp 0x6a942449 | — |
| Introduction | 0x0440 | unread TXT; field_14 0x200; field_04 0x160; field_08 0x90 | 144 bytes at 0x6300; source payload hash equal; 32-byte prefix |
| BMP page | 0x0480 | unread BMP; field_14 0x100; field_04 0x210; field_08 0x283e | 10,302 bytes at 0x63a0; source payload hash equal; 16-byte all-ff prefix |
| Ending | 0x04c0 | unread TXT; field_14 0x200; field_04 0x2a60; field_08 0x8b | 139 bytes at 0x8c00; source payload hash equal; 32-byte prefix |
| Following marker | 0x0500 | name ..; field_04 0x40; field_08 0x3c0; timestamp 0x6a942348 | — |

The target directory child table is exactly 256 bytes and contains the
leading marker followed by the three children in the requested order. The
two observed marker records retain their raw pointer fields; no additional
marker semantics are inferred.

The native TXT payload hashes are
d16567039a003110d246cc6a0a4d0b2042efa9f2240485f6a5facbb09c00dcb and
a31b66d8b27676dc0af07d32ba4d17b90c54ffa39f406c37a9475672e9e46eec. The
native BMP payload hash is
f795a8e1466c3988b804f344645a6208bdcfa27e9d51d8b314c99d9a5973aadd. Each
post-backup payload is byte-identical to its exact prepared source.

The BMP prefix is 16 bytes of ff with hash
5ac6a5945f16500911219129984ba8b387a06f24fe383ce4e81a73294065461b. Both
TXT prefixes are 32 bytes with hash
d0bcc6bc85dc36cdc1ad3882952c5d3d4414869c0bdd75b3b58ba28a32deb92a. This
confirms persistence of the native wrapper observation for this package.

## Unrelated data, timestamps, fixed state, and other responses

There are 323 shared reachable paths between the pre and post models. No
shared file payload or prefix differs. The only shared semantic field
difference is the root child-table length, which grows from 0x340 to 0x380
to include the new folder.

All 323 shared records have changed timestamp fields. The observed pre-to-post
timestamp pairs are retained in the external verification JSON; they include
several legacy values rewritten to 0x6a942348, 0x6a942349, or 0x6a94234a.
The target folder, marker, and all three children use 0x6a942449. This is
observed legacy behavior, not a rule to reproduce in a modern candidate.

The post 0x001b, 0x001c, 0x001d, 0x001e, and 0x001f objects are each
byte-identical to the pre-operation objects, each has SHA-256
f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b, and
each is all zero. This fixed-state comparison is verified for those objects.

The 64-byte 0x8004 probe changed from SHA-256
f629697fb585dbbd4c6f2f70c05acc9d0c6c8a9f44f902669fb2707a44ba554f to
8e932877bace7b786988de827ce1041f5ed15c58854415d485f7667f92277870. The
0x0024 response changed from SHA-256
042222c509c4c24dbfebda091e37fdcf4b33854ba6e09283481a70ce3bff812b to
f3f8b6c7a2aa4ae98d4c6684edee7bba79338185be11fc90ef7c8ee8b05c3f5c. These
differences are not normalized or assigned an unverified capacity meaning.

## Manager, timestamps, and completion

The before/after Manager-local fixture reports remain valid observations:
VICDATA.bin, VICMEM.bin, and VICLV.bin are byte-identical; order.vnw changed
from 253 to 279 bytes and gained the target root name. The complete post
backup independently verifies device persistence, but no separate verbatim
Manager success/failure result or owner result observation is present in the
preserved evidence.

The three raw timestamp logs remain preserved with their sequence identities
and exact values. No event-mapping file was supplied, so their meanings are
unresolved. No native 0x0019 capacity response was captured or decoded for
this operation. The 0x0024 and 0x8004 probe changes are retained without
calling them capacity evidence. The request-4/result portion of the USB log
has not been independently decoded as explicit 0x0000; no completion value
is normalized into success.

## Evidence classifications

### Verified

- Source and preserved Capture 01 trees have identical hash trees.
- Fresh pre-operation backup is complete, has identity 054c:001e, and lacks
  the target.
- Newly obtained post-operation backup is complete; all eight object hashes
  validate.
- Post dynamic blob exactly equals the checksum-valid native transaction
  model.
- The target folder, observed marker records, ordered children, native
  fields, and exact source payloads are present in the post backup.
- Shared file payloads and prefixes are unchanged.
- Objects 0x001b through 0x001f are unchanged all-zero fixed-state objects.
- The 16-byte BMP prefix and 32-byte TXT prefixes persist in the post state.

### Observed

- All 323 shared record timestamps were rewritten.
- The root child-table length increased by 320 bytes.
- The 0x0024 response and 0x8004 probe changed.
- Manager-local order.vnw changed while Manager-local VICDATA/Memo files did
  not.
- The target persisted in the complete post-operation backup.

### Inferred

- The legacy Manager operation generated the post-backup state represented
  by the matching native transaction model.

### Unresolved

- Operation-specific capacity response semantics.
- Separate Manager success/failure owner observation.
- Explicit numeric 0x0000 completion.
- Mapping of raw timestamp sequences to the three procedure events.

## Offline reconciliation and safety gate

The offline typed-media model uses the exact observed 16-byte BMP prefix for
BMP size accounting and keeps the established 32-byte TXT prefix. The P16
fixture calculates 10,668 aligned content bytes and a 10,988-byte total
growth estimate, matching the native model. Focused regression coverage
continues to verify BMP wrapper length, mixed size accounting, exact source
payloads, and the type-specific candidate template boundary.

No timestamp, fixed-state, capacity, completion, or public transfer behavior
was generalized from the newly obtained backup. No modern mixed candidate,
authorization, smoke dossier, or hardware transaction is prepared. The
normal GUI/CLI transfer boundary remains disabled. The native gate stays
closed until the remaining required evidence gaps are resolved through
offline decoding or a separately authorized evidence intake; no repeat write
is requested.
