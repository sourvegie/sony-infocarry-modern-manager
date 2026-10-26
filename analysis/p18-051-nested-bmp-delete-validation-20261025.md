# P18-051 exact nested BMP placement/Delete preparation

Started 2026-10-25 JST; host readiness finalized 2026-10-26 JST. Owner-authorized offline R3 engineering; no physical writes,
no push/merge, no modification of P18-034 or historical evidence.

## Scope and implementation

Clean isolated branch `task/p18-051-nested-bmp-delete` starts exactly at published
sanitized `c87a208cbf28e23daa1aa5bfa7ffdfdfed4fb771`. The preserved dirty P18-034
checkout and all private evidence stay outside this repository. The before
snapshot covers 1,550 file/symlink entries, including all 1,107 primary dirty
paths; all 1,337 prior P18-050 preservation entries and primary HEAD/status/refs
match. Private full-byte evidence and logs are under `/private/tmp`.

The exact fixture is
`root\IC_P18_040_NESTED_20260930_01\Section-A\IC_P18_051_DELETE_A.bmp`:
10,302 bytes, SHA-256
`2701eb9214e2f0afec20b36c93ef739ef3bce35e931fd8c5721e15915447b26d`.
It reuses the canonical 237×320 uncompressed monochrome BMP specimen.
The existing Section-A parent is `0x700`; current children are `02-page.bmp`
at `0x800` and `03-notes.txt` at `0x840`, with marker `0x780`. Insertion
is predicted at `0x880`, before the existing final marker, with growth 10,384
bytes. Native profile is unread `0xe0`, extension `bmp`, opaque `0xffffffff`,
selector `0x100`, 16 all-FF prefix bytes. All parent/sibling raw fields,
timestamps, payloads, markers, ordering and supported protected associations
must survive both operations.

The guarded placement facade and offline preparer share a canonical BMP source
selector. Preserved native evidence selects source `0x49c0`, raw-record SHA
`51acce683e03f00581e236048a9de91e7617d4b4ab65f536bafa1bd6b747b472`,
payload SHA `a30c4ac820cdd61d1a75825e10f7d7c802d6656b68de7e5617ca0f58bf6bc6ac`,
prefix SHA `5ac6a5945f16500911219129984ba8b387a06f24fe383ce4e81a73294065461b`.
The private envelope binds exact source path, offset, raw record, payload,
prefix and copied-field hashes against the actual candidate audit, independently
of candidate/transaction equality. No historical P18-049 record is altered.

The implementation extends `root_txt_placement`, `delete_workflow`, the existing
Device Library service, and their existing operation identity/authorization
adapters. It adds no USB transport, sender, lock, claim store or recovery path.
The nested BMP core reconstructs P18-047's checked nested inverse and protected
state, verifies complete allocation geometry and creates the established
transaction. Ordinary nested BMP and generic nested sender binding stay closed.
Exact validation requires original all-eight restoration hashes. Both facade
operations require a frozen two-write task before existing owner acceptance;
Delete also requires the actual canonical verified placement result, same fresh
all-eight state, capacity and exact target native record. Unsupported/ambiguous
profiles, parents, ownership, markers, references and native state refuse.

## Experiment contract

Exactly two senders maximum:

1. Place the sole disposable BMP into the existing parent. Fresh complete backup
   and native capacity, frozen timestamp/provenance/candidate/transaction, existing
   exact owner identity, durable claim/marker/global lock, one sender/native
   integer zero and complete independent readback. Independently inverse-check
   the actual placed image against the original dynamic bytes and protected
   associations before proceeding.
2. Through Select → Delete → Confirm → Verify, remove precisely that placed BMP.
   Capture a separate fresh full backup/capacity and match actual verified
   placement, freeze/bind a fresh operation identity, use its own one-shot claim
   and marker, send once, and require all eight native objects equal the original
   pre-placement baseline inside canonical success verification.

Any mismatch, uncertainty, nonzero/malformed/missing completion, disconnect,
failed backup/readback or safety inconsistency stops the entire experiment.
No automatic retry, resume, recovery, re-placement, setup or extra cleanup.
One owner approval covers this immutable two-operation task and the two internal
existing confirmations. There is no intermediate owner approval request.
Native post-placement probe and `0x0024` are not predicted by host simulation;
they are preserved as actual readback evidence and the final state must restore
both original objects exactly. Physical recovery/atomicity remains unproven.

## Fresh native staging and exact record

Fresh read-only native acquisition completed at **22:27 JST** using the existing
VNW-V15 runtime, with its sender backend replaced by a hard refusal. All eight
objects equal the independently verified P18-049 final/original baseline. Device
model length is 2,210,432 bytes; native capacity is 3,145,728 bytes; placement
is 2,220,816 bytes, leaving 924,912 bytes. Native capacity response SHA is
`c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a`.
The initial sandbox could not enumerate the device; host read-only visibility
succeeded. Failed sandbox staging is retained separately. No owner acceptance,
claim consumption, sender invocation or device-changing request occurred.

The new record is 64 bytes at serialized `0x880`:

| Offset | Native field | Frozen value |
| --- | --- | --- |
| `+0x00` | File flag and three-byte extension | `e0` and `bmp` |
| `+0x04` | Big-endian content-relative allocation pointer | `0x2a18` |
| `+0x08` | Big-endian payload length | `10302` |
| `+0x0c` | Big-endian record timestamp | `1792934825` (`0x6ade03a9`) |
| `+0x10` | Opaque field | `0xffffffff` |
| `+0x14` | Prefix selector | `0x100` |
| `+0x18` | CP932 NUL-terminated native stem | `IC_P18_051_DELETE_A` |

Allocation contains all-FF16 prefix, exact fixture payload and two alignment
padding bytes. Raw-record SHA is
`842a51346650b173e95404ba674cfd3a633c571d237cab9867c535088fee85bd`.
The target is unreferenced by protected lists/groups. The sole selected parent
owns the new child; no directory or subtree is selected for deletion.

Frozen private envelope:
`/private/tmp/p18-051-fresh-readonly-20261025-02/frozen-task/task-envelope.json`.
SHA-256:
`315d64e4546c07b6449570585ef34295bd8ebeebb5f286b7d639bde04a18e7dd`.
It binds reviewed source `8a443179298ac13d31b14c0f4d92f53035ba46ff`, full
source-template identity, timestamp, native record, parent/target, baseline
all-eight hashes, native capacity, both operation identities and stop rules.
The actual sealed placement bundle was compared directly with this envelope;
provenance and task binding pass with owner acceptance still false.

| Operation | Candidate SHA-256 | Transaction SHA-256 |
| --- | --- | --- |
| Placement | `341c98374fffaf6fb6db396dab1273583f611e2f293f849b9e803f8db890f92c` | `97995182012738fe9fd4352bebe935826e0d051f4d36abb8ed137d622e84d09a` |
| Delete | `6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8` | `e5831e0e363cab494c3f4aa859763808fa5a7676b01c6fd4ddb15edd4d58c452` |

Production safety snapshots are equal: 26 historical claims, zero markers and
byte-identical cleared global lock. No owner approval file or physical attempt
exists. Subsequent execution must obtain its own fresh backups/capacity before
each operation and refuse any difference from this immutable task.

## Validation and readiness

The initial complete portable run passed **1,313 tests / 1,308 passed / five
established skips** in 697.008 seconds. Its process loaded the first 17 new
tests. The final complete portable run at the exact reviewed source passes **1,314 run / 1,309 passed / five established skips** in **619.613 seconds**, including all 18 new methods.
Focused new 17-test run passes in 382.262 seconds; the added/updated two tests
pass in 19.490 seconds (one overlapping rerun), verifying all 18 new methods.
No new evidence skip was added. Independent exact-source R3 is **PASS, P0/P1/P2 = 0/0/0**, with no source correction round required. The [independent review](p18-051-independent-r3-review-20261026.md) records direct evidence and acceptance checks.

Host GUI/package checks pass: macOS Apple Silicon package build, plist validation
and strict deep ad-hoc signature verification; isolated frozen Python 3.12.14 /
Tk 9 runtime smoke with zero USB enumeration, senders, claims or markers; actual
native Tk tree selection, one Delete/Cancel dialog, fake one-shot completion and
verified refresh; portable wheel build and isolated import of both new adapter
APIs; all source/script/test compilation and whitespace checks. The initial
sandbox GUI could not access the desktop; the permitted native desktop test
passed with real USB explicitly forbidden. The existing wheel helper lacked the
optional `build` frontend, so the wheel was built with the installed setuptools
backend through `pip wheel --no-deps --no-build-isolation`. No compatibility
claim is made for physical Windows execution or hardware behavior.

Independent staged reconstruction reproduced the actual guarded bundle seal
`4ba227635daf23ef80e98825c827eda6a0235918bc3984f8ce97cca790f51556`,
including exact actual candidate audit and full template provenance, using a
runtime whose hardware callbacks all refuse. It separately matches both frozen
transaction artifacts, direct fresh/historical native bytes and all-eight
inverse replay. Independent 18-test focused run passes in **399.371 seconds**.
All 12 additional provenance drift variants refuse.

Final preservation rehash independently confirms all **1,550** file/symlink
anchors unchanged, plus original P18-034 HEAD, exact status and refs. Outgoing
Git objects contain only intended Python and sanitized Markdown; no raw native
archive, private template path/payload, transaction range, credential or other
private evidence is committed. Git integrity and range whitespace checks pass.


## Final readiness — 2026-10-26 JST

**P18-051 READY_FOR_HARDWARE_TEST.** Reviewed executable source remains
`8a443179298ac13d31b14c0f4d92f53035ba46ff`; delivery closeout changes are
Markdown only. Independent exact-source R3, final full regression, actual
native-envelope/provenance reconstruction, package/GUI checks and the complete
future runner's fake-device main loop pass. No P0/P1/P2 finding remains.

The private two-write runner is `/private/tmp/p18-051-two-write-executor.py`,
SHA-256 `0ae2d8ba1fe476f9ad5f2570c96a95672e0b87346f1879cbb10cd07b6357f3ec`.
Its complete fake-hardware run made exactly two fake sender invocations, consumed
two isolated claims and restored all eight fake objects byte-for-byte, with
zero real USB calls. It is bound to the same frozen task envelope, one permanent
attempt directory, one task approval and all existing canonical guards. It has
not been invoked against hardware.

After the overnight pause, an additional **fresh read-only** guarded revalidation
on October 26 used the frozen timestamp and envelope unchanged. All eight actual
native objects and native capacity still match the frozen task; actual candidate,
transaction, native record and full template provenance match exactly; task
binding passes with owner acceptance false and sender backend hard-refused.
Evidence is external at `/private/tmp/p18-051-readonly-revalidation-20261026-01`.
Both its safety snapshots are identical. This is a freshness check of the same
immutable task, not a replacement envelope or new operation. The original
October 25 baseline, frozen artifacts and independent approval boundary remain
preserved.

Only one new owner approval for envelope
`315d64e4546c07b6449570585ef34295bd8ebeebb5f286b7d639bde04a18e7dd`
is outstanding. It covers placement then deletion of the same exact fixture,
maximum two senders total, each with fresh guards and independent readback,
no intermediate approval request, no retries/recovery/extra writes, and final
actual all-eight byte-for-byte restoration. Any failed guard stops the task.
Zero physical writes have been performed; no push or merge; P18-034 and private
historical evidence remain unchanged. Ordinary nested BMP is not promoted.


## Subsequent owner-authorized physical closeout — 2026-10-26 JST

The owner explicitly approved the complete unchanged frozen two-write task.
Placement and same-fixture deletion have now both completed, each native
`0x0000`, one audited sender, no retry and successful complete readback. The
independent final assessment confirms all eight original native objects restored
byte-for-byte, correct actual full source provenance and preserved unrelated
state, P0/P1/P2=0/0/0. Claims are 26→27→28; markers resolve/are absent; the lock
and all original preservation anchors remain unchanged. The two authorized
sender invocations are exhausted. No executable code changed, ordinary nested
BMP was not promoted, and no further operation, push or merge occurred.

The earlier readiness/approval-pending statements above describe their preserved
pre-execution checkpoint. The authoritative actual result is the
[final independent physical-validation report](p18-051-independent-physical-validation-20261026.md).
