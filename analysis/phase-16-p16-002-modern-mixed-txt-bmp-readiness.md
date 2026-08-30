# P16-002 — modern mixed TXT/BMP package host readiness

Date: 2026-08-30
Status: **READY_FOR_HARDWARE_TEST — host validation and independent R3 review passed**
Risk: **R3 — device/safety critical**

This dossier prepares one exact modern mixed-package operation and stops before
hardware. No device was detected, no backup was captured from hardware, no
capacity request was issued, and no modern `0x101b` transaction was performed.
The host boundary is `READY_FOR_HARDWARE_TEST` after the independent R3 review
and the host validation recorded below. No live operation is authorized by
this dossier.

## Exact constrained package

The sanitized fixture is committed at
`samples/generated/P16-002-modern-mixed-txt-bmp/`. It is derived byte-for-byte
from the P16-001 fixture, but uses the new destination
`IC_P16_MIXED_20260830_02`:

```text
root\IC_P16_MIXED_20260830_02\01-introduction.txt
root\IC_P16_MIXED_20260830_02\02-page-01.bmp
root\IC_P16_MIXED_20260830_02\03-ending.txt
```

The package has exactly one root folder, exactly three direct children, and
the explicit TXT → BMP → TXT order. There are no nested folders, additional
BMP pages, batch items, deletion, restore, synchronization, or GUI/CLI
transfer exposure.

| Order | Kind | Bytes | SHA-256 | Native template fact |
| ---: | --- | ---: | --- | --- |
| 1 | TXT | 144 | `d16567039a003110d246cc6a0a4d0b2042efa9f2240485f6a5facbb09c00dcb1` | 32-byte TXT prefix |
| 2 | BMP | 10,302 | `f795a8e1466c3988b804f344645a6208bdcfa27e9d51d8b314c99d9a5973aadd` | 16-byte all-`FF` BMP prefix |
| 3 | TXT | 139 | `a31b66d8b27676dc0af07d32ba4d17b90c54ffa39f406c37a9475672e9e46eec` | 32-byte TXT prefix |

The fixture manifest SHA-256 is
`b97a31ae58fff418e69170f6d1ea7c9de6182457c834ba7bd04ae8054996eaae`.
The package source hash listing passes when checked from the fixture
directory:

```sh
cd samples/generated/P16-002-modern-mixed-txt-bmp
shasum -a 256 -c SHA256SUMS.txt
```

## Reconciliation with P16-001 native evidence

P16-001 Capture 01 is the controlling native evidence for this exact package
shape. It verifies a 64-byte folder record, a leading 64-byte `..` marker,
ordered direct children, four-byte content alignment, exact TXT and BMP
payload persistence, 32-byte TXT prefixes, a 16-byte all-`FF` BMP prefix,
unchanged shared file payloads, and unchanged all-zero `0x001b`–`0x001f`
fixed-state objects. Its complete post-operation dynamic blob is preserved
outside Git at the P16-001 evidence root and has SHA-256
`6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b`.

The P16-002 candidate reuses those observed type-specific templates and the
observed root insertion geometry offline only. It preserves every baseline
record byte outside the supported offset/length fields and preserves all
existing timestamps. It assigns one explicit reviewed timestamp,
`0x6a942500`, to the five new structural/content records. The legacy global
timestamp rewrite and the fourth-child one-second serialization are not
reproduced.

The following are **verified host construction facts** for the candidate
derived from the complete P16-001 post-operation baseline:

| Binding | Value |
| --- | --- |
| baseline manifest | `3772f3b6a6dc639af131f76986159f2621ac9913c876fc8504a5119943253dfd` |
| baseline dynamic blob | `6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b` |
| baseline model | 2,064,268 bytes; 389 records; 327 reachable paths |
| candidate model | 2,075,256 bytes; 394 records |
| metadata growth | 320 bytes; five records |
| aligned content growth | 10,668 bytes |
| total candidate growth | 10,988 bytes |
| candidate blob | `4bfe8a54bced7a5cabf1502d4e78d4bfacdc656dd1ab56111b4b013edce6f849` |
| template identity | P16-001 post blob; SHA-256 same as baseline |
| fixed-state hashes | five times `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` |

The candidate records are:

| Record | Offset | Type | Field 04 | Field 08 | Timestamp |
| --- | ---: | --- | ---: | ---: | ---: |
| folder | `0x0400` | directory | `0x0400` | `0x0100` | `0x6a942500` |
| leading marker | `0x0440` | `..` marker | `0x0040` | `0x0400` | `0x6a942500` |
| introduction | `0x0480` | TXT | `0x0160` | `0x0090` | `0x6a942500` |
| BMP page | `0x04c0` | BMP | `0x0210` | `0x283e` | `0x6a942500` |
| ending | `0x0500` | TXT | `0x2a60` | `0x008b` | `0x6a942500` |

The TXT payload offsets are `0x6300` and `0x8c00`; the BMP payload offset is
`0x63a0`. The TXT prefix SHA-256 is
`d0bcc6bc85dc36cdc1ad3882952c5d3d4414869c0bdd75b3b58ba28a32deb92a`; the
BMP prefix is 16 `FF` bytes with SHA-256
`5ac6a5945f16500911219129984ba8b387a06f24fe383ce4e81a73294065461b`.
The rebuilt header is 25,216 metadata bytes plus 2,049,972 content bytes and
passes the InfoCarry checksum parser.

## Capacity and transaction binding

The offline construction uses the established parsed native `0x0019` response
fixture with SHA-256
`c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662` and a
3,145,728-byte limit. This is an **offline reference only**, not a fresh
device observation for this task. The future preflight must query a new
native `0x0019` response, parse it at field `+0x08`, verify the expected
`054c:001e` identity, and bind its raw hash before execution.

The offline capacity arithmetic is:

- baseline model: 2,064,268 bytes;
- candidate model: 2,075,256 bytes;
- candidate growth: 10,988 bytes;
- remaining growth from the offline reference: 1,081,460 bytes;
- result: sufficient for offline construction only.

The prospective ordinary `0x101b` transaction is preserved outside Git under
the P16-002 evidence root. Its binding is:

```text
transaction SHA-256: af9d17348ed54cbea57e32acb2c48f67ea49dbf705151c97e795d0ea0fd9cffb
payload length:      2,140,792 bytes
range lengths:       [256, 64, 65216, 0, 64, 0, 0, 2075192]
variable N:          0
variable M:          2,075,256
completion:          explicit integer 0x0000 only
```

The candidate, source paths, source hashes, target paths, target kinds, order,
record offsets, template hash, fixed-state hashes, capacity reference, model
lengths, timestamp policy, transaction, and expected additive path/payload
delta are bound by `PreparedMultiPackageAuthorization`. The candidate audit
also binds the exact absolute source paths used during offline construction;
the corrected audit supplement is preserved outside Git.

## Isolated future runner

`src/infocarry/prepared_mixed_package_live_smoke.py` is a separate P16-002
module and is not imported by the normal CLI or GUI. Importing it performs no
USB access. Its host-tested boundary is:

1. validate exactly the P16-002 TXT/BMP/TXT package and new `_02` destination;
2. detect and bind the expected device identity;
3. query and bind fresh parsed `0x0019` capacity evidence;
4. capture and verify a fresh complete backup;
5. confirm the `_02` target is absent and rebuild the candidate from that
   fresh backup, exact sources, and validated TXT/BMP templates;
6. present the complete preview and seal the stable bindings; and
7. in a later separately approved task, revalidate the seal, identity,
   capacity, backup, sources, and candidate before permitting one transaction.

The future execution boundary requires the exact operation-specific approval
`APPROVE P16-002 MODERN MIXED TXT BMP SMOKE 01` and the established exact
multi-child confirmation `ADD ONE INFOCARRY MULTI-CHILD PACKAGE`. Neither is
requested, supplied, or reused in P16-002. The sender permits at most one
`0x101b`, accepts only explicit integer `0x0000`, and never retries. Safe
cancellation is available before transmission begins. Cancellation, timeout,
disconnect, missing/malformed/ambiguous completion, nonzero completion,
post-backup failure, or read-back mismatch after transmission is terminal;
the device outcome is indeterminate where appropriate and no corrective write
is attempted.

After an eventual success, the future task must capture a complete post-
operation backup and independently verify the exact folder, marker, ordered
TXT/BMP/TXT children, payloads, prefixes, timestamps/state policy, and
preservation of unrelated records and objects. This task performs none of
those physical actions.

## Host validation and evidence preservation

The generated package, candidate blob, prospective transaction ranges,
candidate audit, preflight bindings, reconciliation audit, and versioned
preservation manifest are preserved outside Git at:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-16-p16-002-modern-mixed-txt-bmp-20260830-01/`

The external artifact manifest v4 records 34 derived package, candidate,
transaction, audit, and reconciliation files; the versioned audit supplements
and corrected package snapshot are non-overwriting, and no P16-001 file is
modified. The candidate blob and
transaction artifact are marked `offline_only` and
`usb_transmission_performed=false`.
Manifest v4 SHA-256 is
`54324ed87e49f8d943e857bdb0a424d301aa7cd313db0052a1605c0b5dd8cd52`, with
entry-list SHA-256
`4a6432299e88e5cb5d4108ef4337c525aec6d938d09458e5d09b1ee1b8c58e13`.

Focused tests exercise the exact package gate and injected fake boundary for:

- read-only preflight and seal creation;
- seal tampering;
- source changes and target conflicts;
- device identity, capacity, and fixed-state drift;
- cancellation before transmission;
- timeout and disconnect after transmission begins;
- malformed, missing, and nonzero completion;
- post-backup failure and read-back mismatch; and
- second-send refusal with zero automatic retry.

The existing generic mixed candidate, authorization, fake workflow, and
independent verifier tests remain in the suite. No normal CLI/GUI import or
transfer path was changed. The independent R3 review and resolved correction
record are in
`analysis/phase-16-p16-002-r3-review-20260830.md`.

## Evidence classification and stop

### Verified

- the sanitized `_02` fixture, hashes, strict CP932/CRLF TXT policy, and BMP
  profile;
- deterministic typed package construction in TXT/BMP/TXT order;
- candidate checksum, exact payloads, prefixes, offsets, allocation, and
  preservation of the offline baseline's unknown/shared bytes;
- explicit source-path and source-hash authorization bindings;
- fixed-state and offline capacity arithmetic bindings;
- one-shot sender and complete failure/cancellation behavior through injected
  fake hardware boundaries; and
- absence of the new module from normal GUI/CLI imports.

### Observed from native P16-001 evidence

- the exact folder/marker/child relationships and type-specific prefixes;
- exact TXT/BMP payload persistence for the `_01` native operation; and
- native global timestamp rewriting and unresolved numeric/capacity semantics.

### Inferred for this host-only preparation

- the reviewed native templates and folder geometry can construct this exact
  new absent `_02` candidate offline while preserving the approved modern
  timestamp policy;
- the prospective transaction is the ordinary bounded `0x101b` shape used by
  the established sender boundary.

### Unresolved

- fresh operation-specific `0x0019` capacity response for a future device
  preflight;
- physical acceptance of this new mixed `_02` modern candidate;
- native numeric completion decoding;
- arbitrary mixed/nested/batch behavior; and
- interrupted-write atomicity, rollback, and recovery.

These unresolved items are not silently normalized or treated as proof of
hardware compatibility. After host validation and independent R3 review, this
task stops at **READY_FOR_HARDWARE_TEST**. A separate later task and new
operation-specific owner approval are required before any device-changing
action.
