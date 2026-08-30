# P15-003 — exact modern four-TXT hardware smoke

Date: 2026-08-30
Status: **COMPLETE — exact constrained smoke verified**
Risk: **R3 — device/safety critical**

This record covers one owner-approved modern operation for the exact P15-002
package. It does not broaden the supported transfer scope. The complete raw
evidence, backups, USB transaction audit, and preservation manifest remain
outside Git at:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-15-p15-003-modern-four-txt-20260830-01/`

Capture 01 and its `_01` package were not modified. The preserved Capture 01
bundle was independently checked against its existing manifest: 119 of 119
listed files matched their recorded sizes and SHA-256 hashes.

## Exact bindings

The operation used the Sony InfoCarry identity `0x054c:0x001e` and the fresh
pre-operation backup captured during the P15-003 preflight:

| Binding | Value |
| --- | --- |
| destination | `root\\IC_P15_MULTI_20260828_02` |
| children | `chapter-01.txt`, `chapter-02.txt`, `chapter-03.txt`, `chapter-04.txt` |
| baseline backup manifest | `a39f6246cfe633c7d4621f2578cc49266dc24cbdac2cbdaec736dd2c3b0f2eed` |
| baseline dynamic blob | `08d8eead50a177b2dc143e7f1d3274b45fe2a45f81d43c5d21cf98f33e25ac99` |
| native capacity response | `0x0019`, SHA-256 `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662` |
| capacity limit | 3,145,728 bytes |
| candidate blob | `70ea314d015e0a0f5de6e35814df8418c42c2faf188849ee88aea309fb226368` |
| candidate transaction | `8d6dfe86f82d735a1fe725fca6a76e7e4b09f13eef684c6853bd37bcc4eb10b9` |
| transaction ranges | `[256, 64, 65216, 0, 64, 0, 0, 2053216]` |
| preflight seal | `130fff4b51588da55396a69655967736c6638bfbba341734c62a50160d8acb49` |
| new-record timestamp | `0x6a91a907` |

The four source files were 121 bytes each. Their source/payload hashes, in
order, were:

| Order | Path | SHA-256 |
| ---: | --- | --- |
| 1 | `chapter-01.txt` | `ef18d78999b9ec2ab276ffc697ba5a866cf21d171c7b39f2f6037bb9fc32c2de` |
| 2 | `chapter-02.txt` | `0323580a5e02206cc0b06d85744a8ef78b449e30d184cef3867152ca4792671a` |
| 3 | `chapter-03.txt` | `711c1235f8fe04c6e31a6c152b5e983320a5d1c21a1729a595d630685b8a6598` |
| 4 | `chapter-04.txt` | `7688a1fed893b3ad3a24d7531bbb4c27ead68709881d31f06c73b7b943f574b7` |

## Operation result

Both exact P15-003 phrases were supplied after the sealed preflight. The
isolated sender recorded one sender invocation, one begin request, bounded
bulk writes, and an explicit completion `0x0000`. It permitted no automatic
retry. The result was followed by a fresh complete backup and an independent
offline read-back verifier.

The post-operation backup has manifest SHA-256
`a37377768e0de175eb6f6ec44addf7b429306f9d19dc0349a4253eb43d7b6165` and
dynamic-blob SHA-256
`70ea314d015e0a0f5de6e35814df8418c42c2faf188849ee88aea309fb226368`.
The post blob is byte-identical to the reviewed candidate. The complete
backup object count remained eight.

Independent parsing verified 378 baseline records / 318 reachable paths and
384 post-operation records / 323 reachable paths. The only reachable path
delta was the requested folder and its four children; no path was removed.
The folder record is at `0x00000380`, has a 320-byte child table, and its
parent-marker relationship is valid. The ordered child records are:

| Order | Record offset | Payload bytes | Wrapper bytes | Timestamp |
| ---: | ---: | ---: | ---: | --- |
| 1 | `0x00000400` | 121 | 32 | `0x6a91a907` |
| 2 | `0x00000440` | 121 | 32 | `0x6a91a907` |
| 3 | `0x00000480` | 121 | 32 | `0x6a91a907` |
| 4 | `0x000004c0` | 121 | 32 | `0x6a91a907` |

All four post-operation payloads exactly matched their source files. The
validated native TXT wrapper was present on every child. All five fixed-state
objects were unchanged. Shared timestamps, shared payloads, and shared
metadata outside the candidate's allowed length/offset adjustments were
unchanged. The expected payload-dependent response, probe, and dynamic blob
objects changed; no unrelated object changed.

The modern policy was therefore applied as approved: preserve existing record
timestamps and assign one explicit timestamp to all newly created records.
The legacy Manager's operation-wide timestamp rewrite and its observed
fourth-child one-second serialization were not reproduced or normalized into
the modern policy.

## Classification and correction

- **Verified:** device identity, fresh complete backups, capacity fit, target
  absence in the baseline, exact source/payload hashes, candidate/post-blob
  equality, folder/parent-marker structure, four-child order, TXT wrappers,
  fixed state, preservation of unrelated content, and no path removal.
- **Observed:** one isolated sender invocation, USB begin/bulk/completion
  sequence, explicit `0x0000`, and successful post-operation device read-back.
- **Inferred within this exact scope:** the constrained modern four-TXT
  candidate is physically accepted by this InfoCarry unit when built from the
  reviewed `_02` baseline and bindings.
- **Unresolved:** arbitrary multi-child behavior, BMP or mixed packages,
  nested folders, batches, deletion/restore/synchronization, interrupted-write
  atomicity or recovery, and the native legacy request-4 numeric semantics.

During offline reload, re-hashing the unchanged baseline produced a new
`verified_at_utc` observation value. The original runner had included that
volatile observation in its seal, so reload initially stopped before any USB
access. Stable baseline identity and all raw hashes matched; the exact sealed
observation was retained for the approved run, without modifying raw files.
The runner is now hardened so future seals exclude only that volatile audit
observation while retaining it in the audit record, and a regression test
covers cross-process re-verification.

## Final boundary

P15-003 is complete for this exact one-folder/four-TXT operation. Normal
multi-TXT package GUI/CLI transfer remains disabled; the existing constrained
replacement path is unchanged. No further device-changing operation is
approved by this record; any broader or different operation requires a new
task, independent R3 review, and a new operation-specific owner approval.
