# P18-051 exact nested BMP placement/Delete preparation

Date: 2026-10-25 JST. Owner-authorized offline R3 engineering; no physical writes,
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

## Validation and readiness

Host and exact-head review results, fresh read-only evidence and frozen task
identity will be recorded here before requesting hardware authorization.
