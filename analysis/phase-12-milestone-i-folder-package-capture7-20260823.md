# Milestone I.3 — capture 7 folder/package evidence

Date: 2026-08-23
Status: **Successful legacy folder/package evidence; offline golden builder
verified. Live modern package transfer remains prohibited.**

The owner supplied `${OWNER_DESKTOP}/capture7` after one ordinary
legacy Manager Send Selected operation. The original Desktop directory was
copied, never moved or normalized, into the ignored intake directory:

`tmp/phase-12-milestone-i-folder-package-capture7-20260823-01/owner-original/capture7`

The derived owner manifest contains 12 files. Its SHA-256 is
`3c467f73339152023b78a05c34602e4d4f293241006b829fc550c47c5046c506`, and
every copied-file hash was verified against the Desktop source. The complete
pre-add, recovery, and post-add backups are preserved in separate new
directories under `tmp/`; no prior evidence or backup was overwritten.

## Verified capture inputs

| Artifact | Size / state | SHA-256 |
| --- | ---: | --- |
| pre-add dynamic blob | 2,050,848 bytes | `88b95f8bc158ab89253faea8c9085799cebba76abf0a3f416afa62df8b55f287` |
| recovery dynamic blob | 2,050,848 bytes | `88b95f8bc158ab89253faea8c9085799cebba76abf0a3f416afa62df8b55f287` |
| post-add dynamic blob | 2,051,132 bytes | `bd73cb33adafacbcb0d5d0313606c94ad2de97e2810953387085234863b509d1` |
| native `01-send.usblog` | 2,289,156 bytes | `a0405d7dc87327c947fc3555dece2e46608d2b6c34d1cbc09fe845f8e0c38138` |
| offline range artifact manifest | — | `8a078d7ad1328fbf45cd8c808579aae453bf320847168fc6e25a7a6e8bf8c755` |

All three raw device archives are complete eight-object backups. The pre-add
archive has 367 metadata records and 310 reachable records. The post-add
archive has 370 metadata records and 312 reachable records. The recovery
archive taken after the earlier failed Manager receive was byte-identical to
the pre-add archive, so that failed setup event produced no observed device
state change.

## Device-resident delta

The post-add inventory contains exactly these two new reachable paths:

- `root\\IC_I_FOLDER_20260823_01`
- `root\\IC_I_FOLDER_20260823_01\\chapter`

No reachable path was removed. Every one of the 253 pre-existing file payloads
has the same length and SHA-256 after the operation. The metadata growth is
three 64-byte records: the folder, one leading `..` marker, and the TXT child.
The extra marker is not a new reachable path. The root child-table width grows
by one record, from `0x280` to `0x2c0`.

The new folder record is at `0x300` and has `field_04=0x300`,
`field_08=0x80`, `field_10=0xffffffff`, and `field_14=0`. The child record is
at `0x380`; it has `field_04=0x1ac`, `field_08=0x3b`, a 32-byte native text
prefix, `field_10=0xffffffff`, and `field_14=0x200`. Its payload begins at
`0x5e8c`, is 59 bytes, has SHA-256
`5f9d50dc738cfb70c1e021d48c7b3aa73540fd97a57a9f1134cb5a82eca98372`, and
has one observed `0xff` alignment byte. The source text was strict CP932 with
CRLF normalization; the verified source hash is
`5f9d50dc738cfb70c1e021d48c7b3aa73540fd97a57a9f1134cb5a82eca98372`.

The dynamic blob grows by 284 bytes: 192 bytes of metadata, plus 92 aligned
content bytes. The native range-5 plus range-8 candidate is exactly the post-
add dynamic blob, including byte-for-byte equality and the post-add SHA-256.

## Native transaction and Manager bookkeeping

The native log contains exactly one parseable ordinary `0x101b` transaction:

`[256, 64, 65216, 0, 64, 0, 0, 2051068]`, with `N=0` and
`M=2051132`. Its range-5 plus range-8 bytes are exactly the post-add dynamic
blob. No second device-changing transaction was found.

The observed Manager sidecars are a verified negative result. Each before/after
file is byte-identical:

| Relative path | SHA-256 |
| --- | --- |
| `Backup/VICDATA.bin` | `72142be59413acdbd4c065fad9d16c2e50bc05d77e316844528de802b689b728` |
| `Memo/VICLV.bin` | `86f79cd4d3edf092149203fb9d35dbe212d5651e24c3123f70d931a74d869eb2` |
| `Memo/VICMEM.bin` | `ceeca1df5933bec05b5022f241ec23a08b6bf27bb47ef76d564579fb0265a470` |
| `ICM/転送元フォルダ/order.vnw` | `d5b38676e00f13b11e609f49ca106b3048d69d73a1b6be153d81d2865a93ef18` |

`order.vnw` already contained `IC_I_FOLDER_20260823_01` before Send Selected;
it did not contain `chapter`. These are Manager-local source bookkeeping
files, not evidence that the device transaction required a sidecar write.

The owner reports that Manager completed normally, and the supplied screenshot
shows the folder and child in the device preview. A trustworthy decoded native
request-4 completion word and an independently preserved screenshot file are
not present in the copied capture directory. Completion wording is therefore
**observed by owner report**, not independently decoded from the native log.

## Offline golden model

`src/infocarry/prepared_folder.py` now reproduces the captured three-record
folder shape from a fresh baseline and a preserved post-capture template. It
uses the existing strict CP932/CRLF authoring boundary and copies the captured
32-byte TXT wrapper. It preserves existing paths, payloads, prefixes, and
opaque fields; it does not construct sidecars, fixed-state responses, or USB
operations.

With the capture-7 pre-add blob, post-add blob as template, the captured
timestamp map, and the exact source text, the candidate is byte-identical to
the post-add blob:

`bd73cb33adafacbcb0d5d0313606c94ad2de97e2810953387085234863b509d1`

This is a **golden fixture reproduction**, not arbitrary fresh-backup live
eligibility. Timestamp generation remains unresolved; the builder requires an
explicit timestamp and never uses current time or silently copies one. The
captured shared `..` table-width update is kept as a narrow, documented rule.

## Gate decision

The folder/multi-record **evidence gate is satisfied for this exact one-folder,
one-TXT legacy fixture**. I.3 can proceed to offline builder hardening and
comparison tests. It does not authorize a modern package sender, a normal
GUI/CLI package action, another live capture, or any delete/rename operation.
Manager sidecar participation, general timestamp generation, general fixed-
state rebasing, capacity semantics, and interrupted-write recovery remain
separate unresolved or blocked concerns.

The machine-readable summary is
`analysis/phase-12-milestone-i-folder-package-capture7-20260823.json`.
