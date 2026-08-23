# Milestone H — failed legacy delete attempt 01

Date: 2026-08-22
Status: **Failed Manager operation; target remains on device; delete evidence
gate remains open.**

The detailed offline comparison of the native candidate, complete backups,
fixed-state ranges, and exploratory helper is recorded in
`analysis/phase-12-milestone-h-offline-analysis-2026-08-22.md`.

The owner supplied `${OWNER_DESKTOP}/capture5`. The original folder and
native log were read without modification. Derived offline artifacts,
reports, the complete read-only backups, and a copy of the supplied failure
screenshot are preserved in the ignored workspace:

```text
${PROJECT_ROOT}/tmp/milestone-h-delete-capture-20260822-01/
```

On 2026-08-22 both sources were copied without modifying either original into:

```text
${EVIDENCE_ROOT}/phase-12-milestone-h-delete-attempt-20260822-01/
```

The owner-supplied folder is under `owner-original/`; generated backups and
parsed artifacts are under `derived-analysis/`. `diff -rq` verified both
copies byte-for-byte before the manifest was added. Every preserved file then
passed `SHA256SUMS.txt`; that manifest's SHA-256 is
`adb60785a9c038c3f84f78b66d02a70808772a354f36c3084cabdf922443857e`.

## Manager result

The supplied screenshot shows SnoopyPro attached to the InfoCarry row
`USB\\Vid_054c&Pid_001e` with 1,156 packets. Manager displayed the Japanese
message `データの送信が失敗しました。`, meaning **“Data transmission
failed.”** The owner also reports that the Manager device preview became empty
after the failure. This is Manager-level failure evidence, not success.

No retry or second delete was performed.

## Preserved capture inputs

| Artifact | Source or derived path | SHA-256 / result |
| --- | --- | --- |
| Native SnoopyPro log | `${OWNER_DESKTOP}/capture5/usblog/01-delete.usblog` | `3f20d9e0bdc4705bb4dafe97ba8e43960b122006dd216e6723b433bc0c3ee4fc` |
| Failure screenshot | `tmp/milestone-h-delete-capture-20260822-01/owner-supplied/failure-dialog.png` | SHA-256 `1f3fe7d25a1a54abbafe4dc58bd63d41a64c7658e71291b3cdd04f80790bc195`; copied without changing the supplied attachment |
| Pre-delete device backup | `tmp/milestone-h-delete-capture-20260822-01/pre-delete-actual/` | manifest `9be0fe3779f8ff74ba722ea48bf46035477a3b1874f392027d2a0793fc785342`; blob `aec90438c1323400b2f4d4210541c599600f4e9493596edc710bd676dee8adf6` |
| Post-attempt device backup | `tmp/milestone-h-delete-capture-20260822-01/post-delete-actual/` | manifest `c5377d1df55fa9000e8323f0fcb4f3b4d81c74a06847315591aefd02a380e865`; blob `aec90438c1323400b2f4d4210541c599600f4e9493596edc710bd676dee8adf6` |
| Parsed native artifact | `tmp/milestone-h-delete-capture-20260822-01/native-delete-artifact/` | transaction `0x101b`; transaction SHA `19c9cc304ca9e185299113c0a453e261a3f3ad26dca793f4a03fd65444e66464` |

The pre- and post-attempt backups are complete, identify `0x054c:0x001e`,
and contain eight objects each.

## Device result

Independent post-attempt parsing finds:

- pre-delete: 368 metadata records and 311 reachable paths;
- post-attempt: 368 metadata records and 311 reachable paths;
- target `root\\IC_G_LIVE_20260822_01.txt`: present before and after at
  metadata offset `0x300`;
- removed paths: none;
- added paths: none;
- shared file-payload changes: none;
- dynamic blob: byte-identical before and after.

The post-attempt backup therefore proves that the target was not removed from
the device. The empty Manager preview is inconsistent with the complete
read-only device backup and must not be treated as device state.

The fixed response objects changed between the two read-only backups:
`0x001b`, `0x001d`, `0x001e`, and `0x001f` changed; `0x001c` and `0x0024` did
not. The cause and semantic meaning of those post-failure state changes are
not established. They are preserved as observed state, not classified as a
successful delete effect.

The four supplied Manager files were byte-identical before and after:

| File | Before/after SHA-256 |
| --- | --- |
| `Backup/VICDATA.bin` | `72142be59413acdbd4c065fad9d16c2e50bc05d77e316844528de802b689b728` |
| `Memo/VICMEM.bin` | `4a0bcfe3a2bbbb62ab872a16f4e30e1b4f7b0419096a98dd740cf1c2c49d3499` |
| `Memo/VICLV.bin` | `86f79cd4d3edf092149203fb9d35dbe212d5651e24c3123f70d931a74d869eb2` |
| `ICM/転送元フォルダ/order.vnw` | `824ec471ffee0154f982a94a7ec4dd0aef7b1f1d6208f0febd94e2f66fc46894` |

The generated before/after fixture reports both contain 2,035 records, 1,856
reachable records, and 1,677 files. No Manager-side delete mutation is
observed.

## Native candidate evidence

The original log parses as one ordinary eight-range `0x101b` transaction. The
offline artifact has range lengths:

```text
[256, 64, 65216, 0, 64, 0, 0, 2050784]
```

It declares `N=0`, `M=2050848`, and a total payload of 2,116,384 bytes. The
range-5 plus range-8 bytes form a structurally valid candidate blob of
2,050,848 bytes with SHA-256
`5f13702c014aa49e245fb27ad4bb593119b3a63e27ecf1534fb48bd07fca4a08`.
That candidate removes exactly the target path and has 367 metadata records
and 310 reachable paths. The candidate was never sent by the modern client;
it is preserved solely as parsed legacy evidence.

Before the observed-alignment refinement, the native candidate and the
offline `delete_existing_file()` result removed the same target and retained
the same other paths, but their bytes differed: the native candidate was
4 bytes shorter. The refined helper now produces the native length and
structure; after copying the native timestamp fields and recomputing the
checksum, it is byte-identical to the preserved candidate. The timestamp
copy is comparison normalization only and does not recover a safe timestamp
policy or establish successful deletion.

The captured fixed-state ranges are not byte-identical to the fresh pre-delete
backup, but a normalized comparison is more specific than a stale-state
classification. Four blocks exactly match the fresh state after subtracting
`0x40` from counted metadata-relative references at or after the removed
record. The native `0x001e` block has the same count and rebased offset but
differs at bytes `+0x06..+0x07` (`0x0000` versus `0x6e69`). Their hashes are:

```text
native range-1 chunks: 9f614628..., f5a5fd42..., f5a5fd42..., e95e4e02...
native range-2:         6fffe39f...
fresh pre-delete:       7793b6da..., f5a5fd42..., f5a5fd42..., c9873fb6..., 7ca31398...
```

The complete hashes are in the preserved artifact and fresh-backup manifests.
The unresolved `0x001e` field, global timestamp rewrite, alignment difference,
and Manager failure make this transaction unsafe to replay or promote as a
successful delete model. The fixed-state evidence is useful for offline
rebasing analysis and should not be discarded as merely stale.

## Gate decision

This attempt is valuable failure evidence but does not close Milestone H. It
establishes a native deletion-shaped candidate and an observed 4-byte
alignment discrepancy, while the actual device remains unchanged in its
target record. No modern delete candidate, authorization, GUI/CLI control, or
retry is enabled. R2 remains open and R15's no-retry/indeterminate boundary
applies.

Next safe work is offline comparison of the native candidate, alignment
behavior, fixed-state binding, and failure semantics. A successful isolated
legacy delete capture is still required before any modern delete approval.
