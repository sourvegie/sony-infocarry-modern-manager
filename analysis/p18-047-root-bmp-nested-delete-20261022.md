# P18-047 — root-BMP host admission and individual nested-file deletion

## Scope and preserved starting evidence

The branch starts at sanitized checkpoint
`dd715081292a4320bf2f3badd98500a69724644e`, descended from published sanitized
`d344f1e59664f38ebb8c3a3219c72b6eea8f79cd`. P18-046's independently reviewed
implementation and exact disposable BMP placement/Delete evidence remain
preserved. Its complete before/post backups were rehashed read-only; all eight
final objects match the original pre-placement state. The physical proof is
limited to the exact unread BMP at serialized `0x680`, native completion zero,
one sender, no retry, and independent readback. See the
[P18-046 physical record](p18-046-root-bmp-delete-physical-validation-20261021.md).
This task performs no USB command or physical write and touches no production
claim, marker, or lock.

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
The P18-046 exact fixture gate remains the only physically demonstrated BMP
operation. Ordinary TXT behavior and candidate bytes/audits are retained.

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
retry. Before final CLI/anchor boundary additions, the full portable suite ran
1,244 tests: 1,239 passed, five established skips. The final new suites pass
25 tests. Independent exact-head R3 and final full-suite disposition are pending.

The macOS package builds; plist and deep/strict code-signature checks pass.
The frozen runtime attempt aborts with status 134 and emits no smoke report;
LaunchServices fallback returns `-10827` (`kLSNoExecutableErr`) despite a present
executable. This repeats the recorded temporary-checkout limitation and is not
counted as a runtime-smoke pass or a demonstrated application regression.

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

## Sanitized-history integrity limitation

Current snapshots and ancestry are preserved and all new files are sanitized
source/tests/disposable-fixture metadata. No private backups, candidates,
payloads, credentials, original source history or P18-034 changes are imported.
However `git fsck` found five missing ancestor root tree objects in the starting
temporary repository: `74aa2e0e`, `c5646242`, `06d15fc2`, `06708212`, `205aaeea`.
The current snapshot, reviewed heads and published base are readable; a bounded
search found no retained trusted copies of these trees. No object/branch
reconstruction or history rewrite was attempted. Full outgoing-history audit
and publication/integration readiness cannot be claimed until the exact trees
are restored from trusted preservation. This does not prevent host code review
against intact starting snapshot `dd715081`.
