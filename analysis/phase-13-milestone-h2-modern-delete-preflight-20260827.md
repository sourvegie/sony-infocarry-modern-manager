# H.2 modern-delete read-only preflight — target `IC_TEST_01.txt`

Date: 2026-08-27

## Result

The approved read-only preflight completed successfully for exactly one
owner-selected target:

`root\\IC_TEST_01.txt`

No `0x101b` request was issued. No sender callback was called. No device
change occurred. The preflight is sealed for owner review only; it is not
permanent write authorization.

Raw backup and preflight artifacts are preserved outside Git under:

`${EVIDENCE_ROOT}/phase-13-i7-h2-modern-delete-20260827-01/`

The session checksum manifest covers 10 files and verified every entry with no
mismatch. Its SHA-256 is:

`2c591a45d601bafafe248601719a6e2148552bf643a1f2d2606d1678f007849a`

## Device and fresh backup bindings

- device: VID `0x054c`, PID `0x001e`, bus `2`, address `3`;
- complete backup: `${EVIDENCE_ROOT}/phase-13-i7-h2-modern-delete-20260827-01/pre-delete-backup/archive-01`;
- backup manifest SHA-256: `39323d69d27c55d342dd1c3c4129268ddad1a43c614d01be513c7100d67775c8`;
- dynamic blob SHA-256: `fbfe0dc9898a0cd6c406bd26542859282a1a410b059b16812c32522a9ce8e450`;
- baseline model: 2,051,420 bytes, 373 records;
- complete backup object count: 8.

## Target binding

- exact path: `root\\IC_TEST_01.txt`;
- record type: ordinary TXT, unread;
- absolute metadata record offset: `0x000001c0`;
- metadata-relative offset: `0x00000180`;
- parent: root directory at `0x00000040`;
- payload length: 41 bytes;
- payload SHA-256: `85c8e82f3547ace5c72f3f2c1c3817788cd134e4e6bbf4dca9032d4ca11e4c08`;
- native prefix SHA-256: `d0bcc6bc85dc36cdc1ad3882952c5d3d4414869c0bdd75b3b58ba28a32deb92a`.

## Candidate and transaction bindings

- expected path delta: remove exactly the target above; add nothing;
- candidate dynamic blob: 2,051,280 bytes, 372 records;
- candidate dynamic blob SHA-256: `d4e4fa74e4338c18aa366e016ba9cb756d0af4e84b3bd19045993553d3526f20`;
- model change: `-140` bytes;
- metadata change: `-64` bytes;
- aligned content removal: `76` bytes;
- transaction SHA-256: `78636328fc7f386fcaf5a565421cd7feae0525a675a740019e7e1813aa148298`;
- transaction payload length: 2,116,816 bytes;
- variable N: `0`; variable M: `2,051,280`;
- range lengths: `256, 64, 65216, 0, 64, 0, 0, 2051216`.

## Fixed state and policies

The five fixed-state objects `0x001b` through `0x001f` were the exact
supported all-zero state. Every before and prospective-after object has SHA-256:

`f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b`

No fixed-state command changes in the candidate. The policy is to preserve the
verified bytes exactly, preserve surviving timestamps, accept completion
`0x0000` only, and never retry automatically.

The sealed preflight artifact is:

`${EVIDENCE_ROOT}/phase-13-i7-h2-modern-delete-20260827-01/derived/preflight-01.json`

Its SHA-256 is:

`28d52af70d6fec6415f2a3c39cd96871d9c7513e4a1fe69be66633125c1cd832`

The artifact contains hashes, lengths, offsets, classifications, and the
expected path delta; it does not contain candidate bytes, raw state objects, or
payload contents.

## Gate status

This is a successful read-only preflight. It does not authorize deletion.
Normal CLI/GUI deletion remains absent. Physical interrupted-write atomicity
and recovery remain unresolved under R15. A future execution would require a
new explicit owner approval after this final preflight, the exact phrase
`DELETE ONE INFOCARRY ITEM`, one transaction at most, completion `0x0000`, and
complete independent post-operation read-back. Any interruption after
transaction entry is indeterminate and must not be retried.
