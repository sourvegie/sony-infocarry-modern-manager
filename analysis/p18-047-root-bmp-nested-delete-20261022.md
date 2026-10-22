# P18-047 — root-BMP host admission and individual nested-file deletion

## Scope and preserved starting evidence

Implementation began from sanitized checkpoint
`dd715081292a4320bf2f3badd98500a69724644e`, descended from published sanitized
`d344f1e59664f38ebb8c3a3219c72b6eea8f79cd`. The final isolated delivery uses
exact snapshot ports onto that published base, as detailed below. P18-046's independently reviewed
implementation and exact disposable BMP placement/Delete evidence remain
preserved. Its complete before/post backups were rehashed read-only; all eight
final objects match the original pre-placement state. The physical proof is
limited to the exact unread BMP at serialized `0x680`, native completion zero,
one sender, no retry, and independent readback. See the
[P18-046 physical record](p18-046-root-bmp-delete-physical-validation-20261021.md).
The original offline engineering checkpoint performed no USB command or
physical write and touched no production claim, marker, or lock. Subsequent
separately owner-authorized physical execution is recorded below.

## Ordinary root-BMP host admission

`build_root_bmp_delete` adds a conservative wrapper around the existing BMP
candidate, protected-state derivation, transaction and host authorization model:

- VNW-V15 verified complete backup; one unique exact root-level `.bmp` path.
- Safe NUL-terminated CP932 native name, roundtripping within 39 bytes; ambiguous
  native stems, mixed case identity collisions, markers and system/root entries
  fail closed.
- Observed unread `0xe0`, opaque field `0xffffffff`, selector `0x100` and exactly
  16 all-`ff` prefix bytes. Read and 32-prefix BMP profiles stay outside this
  conservative wrapper.
- Existing 237×320, uncompressed one-bit Windows BMP validator; positive or
  negative height follows that existing validator. No new conversion rules.
- Exact target-only removal, aligned nonoverlapping target allocation, checksum,
  pointer/record rebasing, survivor bytes/timestamps and protected-state checks.
  Referenced targets and active Marks refuse. Final live capacity evidence is
  still required by the existing coordinator; offline admission is no claim of
  live capacity or physical support.

Ordinary BMP sender binding and normal UI execution remain blocked. The
existing `prepare_root_bmp_delete.py inspect --backup ... --target ...` command
provides offline candidate inspection with explicit unavailable execution.
The P18-046 exact fixture remains the only normal-UI BMP gate. The additional
P18-047 exact B profile was subsequently physically demonstrated in explicit
validation mode, as recorded below. Ordinary TXT behavior and candidate
bytes/audits are retained.

## Individual nested-file model

The existing one-file repacker now has explicit host-only nested TXT/BMP
admission and an independent verifier. It preserves every parent directory,
sibling, child order, marker record, surviving raw metadata field, prefix,
payload and timestamp, including a parent left logically empty. It rejects
orphan records, duplicate native identities, unsafe/unrepresentable ancestor
names, overlapping child tables or content, missing markers, unsupported
states/prefixes and invalid BMP payloads. Marker rebasing uses the established
relation rule; archived marker fields are not guessed to be directory pointers.

`build_nested_file_delete_candidate` combines this model with the existing
protected-state derivation. Its object deliberately has no transaction or
authorization. `verify_nested_file_delete_readback` checks complete backups and
protected state without calling the repacker or granting live success. The
existing generalized sender binding also rejects nested source paths before
sender entry, including ordinary nested TXT host authorizations. The Device
Library continues to refuse nested selections. No directory/subtree deletion
is introduced.

## Offline evidence and testing

Read-only archive inspection used the preserved complete 455-record BMP-present
backup (`be4c570cbb625592128863518ab2c16d06d8b0aac8b63aee4db0ab48ad6a2de1`).
All 136 old/new TXT candidate bytes and audit dictionaries match; the exact
archived root-BMP candidate/audit matches too.

Nested TXT: 132 inspected, 99 structurally admitted and independently verified,
94 protected-state candidate passes, five referenced-target refusals. Nested
BMP: 163 inspected, 13 structurally admitted/verified, 11 protected-state passes,
two referenced-target refusals. The other 183 records refuse conservatively:
119 first fail the BMP payload profile, 54 path syntax, and ten exact CP932
representation. These counts describe host inspection, not physical deletion.

A separate 163-BMP payload census found 33 supported 237×320 records (22 unique
payloads); 130 other dimensions are outside the profile. All 33 archived
supported payloads pass ordinary host admission in three **synthetic root
positions** (99 candidates). They are not represented as real root records.

New focused tests exercise names, state/prefix/opaque fields, first/middle/last
records, orientations, markers, empty parents, P18-040's reconstructed hierarchy,
protected references, all four TXT alignment remainders, tampered readback,
normal UI refusal, exact B-only validation, source/anchor/slot refusal,
fake one-sender/native-zero/readback/refresh, and ambiguous-send locking with no
retry. The final portable suite ran 1,247 tests: **1,242 passed, five established
skips**, 180.961 seconds. The final new suites pass 25 tests. Independent exact-head
R3 passes **P0/P1/P2=0/0/0**, including 105 independently run focused tests and
independent old/new TXT/BMP comparison, physical evidence and readback rechecks.
See the [independent review record](p18-047-independent-r3-review-20261022.md).

The macOS package builds; plist and deep/strict code-signature checks pass.
Sandboxed frozen startup aborts with status 134 and LaunchServices returns
`-10827`; those attempts are not counted as passed. The same final package's
narrowly approved out-of-sandbox runtime smoke then passes with exit zero:
actual Manager/Tk startup and close, Add/menu behavior, isolated profile,
resources/libusb, and locked/unavailable-runtime checks all pass. Device
enumeration, sender calls, claims, markers and real `0x101b` counters are all
zero. This comparison establishes the observed startup limitation as
sandbox-dependent. It is a native widget/runtime smoke, not a claimed screenshot
visual inspection. The private report is preserved outside Git under
`/private/tmp/p18-047-runtime-smoke-20261022/report-unsandboxed.json`.

## Minimum additional root-BMP experiment

One new disposable BMP Delete is proposed; read/32-prefix states remain excluded
so they do not need experiments for this intended envelope. Canonical BMP
payloads are always 10,302 bytes, so the profile has no additional variable
payload-alignment remainder to test. The additional case changes both bitmap
content/orientation and serialized position with survivors on both sides.

The deterministic [B fixture manifest](p18-047-disposable-root-bmp-fixture-20261022.json)
uses `root\\IC_P18_047_DELETE_B.bmp`, 10,302 bytes, SHA-256
`c172a44bb01de67abb3146b2bad89abe524963cf9ca56fc911bb4430dac70e82`.
It is top-down, with inverted P18-046 specimen pixels, and uses the same native
unread/all-`ff`16 prefix profile. An already-proven 32-byte disposable A TXT
anchor establishes A at `0x680` and B at `0x6c0`; these positions are checked in
serialized metadata, never inferred from GUI order. The B placement and Delete
routes refuse a wrong/missing anchor or wrong target position. Normal Manager
mode does not expose B. Explicit existing Manager validation mode permits only
B, with the same single Delete/Cancel dialog and canonical lifecycle.

The offline replay uses preserved complete source state and existing add/delete
builders. It predicts A's archive hash
`9d2fb2dbb9cd2abcea6cb8a3e1d0fb32678bbab184fffe6cf0dfbd6c32fe644e` and B's
archive hash `1f2334bb13ad4f8d8e9e04dbfaca0ec2a7cd2636a0cfe1770de9b804e3af6700`
with fixed **simulation timestamps**. B has 26 serialized survivor records
before and 429 after it. Deleting B exactly returns the A state; cleaning up A
returns the original dynamic and fixed state. Raw simulated archives remain
outside Git. These artifacts cannot be adopted as a fresh live approval.

Concise operator procedure, after R3 passes:

1. Keep the legacy Manager closed. Obtain fresh complete read-only backup and
   native capacity; check the original baseline, target absence and safety state.
2. Prepare the exact existing A32 placement. Confirm actual predicted `0x680`,
   freeze, then request separate approval **ADD IC_P18_043_DELETE_A.txt ONCE**.
   Send once and independently verify before proceeding.
3. Prepare B through the existing bounded BMP placement facade. Require exact
   manifest payload and A anchor, actual B `0x6c0`, and survivor geometry. Freeze
   and request **ADD IC_P18_047_DELETE_B.bmp ONCE**. Send/verify once.
4. Launch the existing explicit Manager validation target for B. Select B,
   click Delete, review its fresh backup and single readable confirmation, then
   request **DELETE IC_P18_047_DELETE_B.bmp ONCE**. Native zero, one sender,
   no retry and complete independent readback must return the A state.
5. Separately prepare/authorize **DELETE IC_P18_043_DELETE_A.txt ONCE** and verify
   the complete original state is restored. Stop all physical work immediately
   on failure/ambiguity; never retry or automatically restore.

Four separately authorized writes (including anchor cleanup) are the minimum
using the established one-file placement mechanisms to obtain a second root
record position without touching personal files. This task grants none of
those approvals. Success would trigger a bounded evidence/R3 assessment of the
ordinary unread root-BMP envelope; there is no automatic class-enabling switch.
Nested TXT/BMP physical validation remains a later separately scoped operation.

## Physical execution and final cleanup — October 23 JST

The owner separately approved each of the four frozen operations. The reviewed
implementation remained unchanged at `ed76e7990faf77b181726ff56f0debfccc0f3389`.
Every operation returned native **`0x0000`**, with exactly **one audited guarded
sender / single `0x101b` transaction**, **zero automatic retries**, a fresh
complete pre-operation backup and complete independent post-operation readback.
No independent USB bus trace was captured; counts are execution-audit evidence.

| Operation | Actual serialized target | Verified result |
| --- | --- | --- |
| Add `IC_P18_043_DELETE_A.txt` | `0x680`, exact canonical 32-byte A32 | Sole addition; 300 existing payload/prefix pairs and 454 timestamps preserved |
| Add `IC_P18_047_DELETE_B.bmp` | `0x6c0`, exact manifest 10,302-byte B | Sole addition; A32 intact; 301 existing payload/prefix pairs and 455 timestamps preserved |
| Delete B through Device Library | `0x6c0`; 26 survivor records before, 429 after | Sole removal; all eight objects match actual verified A32 placement state; 301 survivor payload/prefix pairs and 455 timestamps preserved |
| Delete A32 through Device Library | `0x680` | Sole removal; all eight objects match original pre-experiment baseline; 300 survivor payload/prefix pairs and 454 timestamps preserved |

Every readback also verified checksum/structure, protected state and supported
auxiliary associations. Actual A32 archive SHA-256 was
`5b37577aa61e2903affef62608e9b954a545e41afc5de908973e2173fdcadb1f`;
actual B archive SHA-256 was
`78cb68973ba97ccebc362240467326c431d199122f2b01be48da7fbc583197b4`.
B deletion returned the A32 archive exactly. Final cleanup archive SHA-256
`6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`
matches the original 2,210,432-byte archive and its frozen deletion candidate.
All eight final raw objects, including fixed state, capacity and blob probe,
match the original complete baseline. Both disposable files are absent.
These are actual operation results, distinct from the fixed-timestamp offline
simulation above; placement timestamp differences explain their different hashes.

Each operation consumed its own exact claim once. All four sender markers were
terminally resolved and are absent. The final read-only safety inspection found
24 historical consumed claims, with the previous 23 unchanged by cleanup, no
in-flight marker, and the clear global lock byte-identical to pre-operation
state. Frozen bundles, owner approvals, raw before/after backups, result audits,
terminal-resolution reports, independent reports and actual GUI screenshots
remain outside Git without alteration.

Sanitized evidence anchors (SHA-256):

| Operation | Complete post-backup manifest | Independent post-operation report |
| --- | --- | --- |
| A32 placement | `46da21e4aa5bce05138406e660ca9cce9661a9bdb60d56ec5ce0b5c7d6fe4952` | `3a3f850f067b7d400f6767b3221d1f238575e442ccd8a9d011a1de9d91c8dc5b` |
| B placement | `a6d86925968545c1ffb80540e969b7877564658d30f9ce30e71d66ea05c8aed7` | `517244f74cc952ce8dafe8270e6f0ad05a15de57c8851e53298c2f6b130c72dd` |
| B Delete | `204bbb10ce606325e44d6ccd3a5f06e6da7d87a56f42d96ba9595c097f1ba9d9` | `5d8a152989381d0b68a74a580abcdf73376117d1996a4c6ad0e3182eec446de0` |
| A32 cleanup | `a468e63b795263612749d740bd732b0f5493633427e6bebc9b1086fcfd4d29d3` | `153cd1a759a31b570b830cff2a4f7cbf5854c19383d2fca8d0eda4c4c3247eda` |

The actual Manager screenshots confirm the refreshed verified post-backup,
empty search for the removed target, disabled Delete and verified-completion
footer. Single Delete/Cancel confirmations were used; no typed fingerprint or
new approval mechanism was introduced.

Together with P18-046, this adds a second exact BMP payload, top-down orientation
and serialized position `0x6c0` with survivors on both sides, using the same
unread `0xe0` / `0x100` selector / 16-byte all-`ff` prefix profile. It supports
a bounded assessment of ordinary unread root-BMP admission; it is not physical
proof of every host-admitted file. No capability gate changes accompany this
closeout: ordinary BMP and all nested Delete remain host-only, B remains an
explicit exact-fixture validation route, and P18-046 retains its existing exact
normal-UI profile. Read/32-prefix BMP states, directories/subtrees, VNW-V10 and
interrupted-write recovery remain unsupported. Any class promotion requires a
separate reviewed decision and owner approval; no further experiment is run
automatically.

## Sanitized snapshot port and preservation

The original temporary repository has five missing ancestor root tree objects
(`74aa2e0e`, `c5646242`, `06d15fc2`, `06708212`, `205aaeea`) and missing primary
checkout Git metadata. Those objects were not guessed or reconstructed; no
original repository/reference was modified. Current approved/reviewed snapshots
and the published base remained intact.

Delivery instead uses a new isolated repository at
`/private/tmp/p18-047-sanitized-delivery`. Only published sanitized commit graph
`d344f1e59664f38ebb8c3a3219c72b6eea8f79cd` and the two exact snapshot trees were
imported. Local port `16235be02e7cafaac9dca069c9a2a5263c786462` has the exact
approved P18-046 `dd715081` tree. Reviewed P18-047 source head
`2ec34073f00fbc3253d957598aa6c1f75f7df81a` has the exact original reviewed
`375fd82` tree. The implementation diff is byte-identical, independently
verified. Original task commits/broken ancestry were not imported.

The new repository passes `git fsck --full`. All 37 outgoing blob versions
across the two source snapshot commits were independently inspected: no binary
raw evidence, blob above 1 MiB, suspected credentials or personal user paths.
The largest is the intentional 251,514-byte desktop source. Known private JSON
blob `ef7e5a2d05ebdaf008a3c04380251e6a26d291ed` is absent. New author/committer
metadata matches the published no-reply identity. Final report updates are
sanitized documentation only. This resolves delivery integrity without
rewriting published history or claiming that the old missing objects were
restored. Any future publication must still fetch and verify the actual remote
tip; no push or merge is authorized here.

P18-034's branch, status and all 1,043 dirty-file hashes were independently
checked unchanged. The sibling evidence archive and all private hardware data
remain outside Git. The original offline checkpoint performed no physical
operation; the later separately authorized experiment and final cleanup are
complete as recorded above. No additional hardware action is pending in this
procedure. Ordinary BMP and all nested Delete stay host-only pending their
separately approved capability/validation work.
