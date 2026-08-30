# P15-002 — modern multi-TXT hardware readiness

Date: 2026-08-30
Status: **READY_FOR_HARDWARE_TEST**
Risk: **R3 — device/safety critical**

This is the corrected, isolated host-readiness dossier for one exact modern
four-TXT smoke. No hardware was accessed and no modern `0x101b` transaction
was performed. The earlier P15-001 modern dossier remains preserved as
historical `IMPLEMENTATION_READY` material because it reused the stale Capture
01 pre-backup and had no executable live boundary.

## Exact operation

Use the sanitized package at
`samples/generated/P15-002-modern-multi-chapter-txt/`. It contains one new
root-level folder, `IC_P15_MULTI_20260828_02`, with exactly these four ordered
children:

```text
root\IC_P15_MULTI_20260828_02\chapter-01.txt
root\IC_P15_MULTI_20260828_02\chapter-02.txt
root\IC_P15_MULTI_20260828_02\chapter-03.txt
root\IC_P15_MULTI_20260828_02\chapter-04.txt
```

Every source is 121 bytes, CRLF, and an ASCII subset of CP932. The committed
manifest SHA-256 is
`e6143502a393385ecbc9b62bd9a831917f758dfdcd1e83456321a5af3a37a044`; the
prepared logical manifest SHA-256 is
`22041bae59033a228a1d20577fea973c28c4d18f78916884e71610b525d9b8be`. Source
hashes, in order, are:

```text
ef18d78999b9ec2ab276ffc697ba5a866cf21d171c7b39f2f6037bb9fc32c2de
0323580a5e02206cc0b06d85744a8ef78b449e30d184cef3867152ca4792671a
711c1235f8fe04c6e31a6c152b5e983320a5d1c21a1729a595d630685b8a6598
7688a1fed893b3ad3a24d7531bbb4c27ead68709881d31f06c73b7b943f574b7
```

The target is distinct from the preserved Capture 01 folder
`IC_P15_MULTI_20260828_01` and was absent from the latest preserved Capture 01
post-state. The package contains no BMP, nesting, second folder, batch,
delete, synchronization, or retry behavior.

## Rebuilt offline bindings

The offline baseline is the latest preserved Capture 01 post-operation backup,
not the stale Capture 01 pre-backup:

```text
manifest: 03c54dd799933367d34f8b96baab276bc54e2cbb1ba8cfa3ba3c8d8dbf2d0dec
dynamic blob: 08d8eead50a177b2dc143e7f1d3274b45fe2a45f81d43c5d21cf98f33e25ac99
dynamic bytes: 2,052,272
device: 054c:001e
```

The baseline is used for reproducible offline construction only. The isolated
runner must capture a new complete backup during every future preflight.
Parsed native capacity evidence is the `0x0019` response at field `+0x08`,
SHA-256
`c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a`, with a
3,145,728-byte limit. The rebuilt `_02` candidate is 2,053,280 bytes, grows
the model by 1,008 bytes, and leaves 1,093,456 bytes of model capacity.

The candidate binds these record offsets and paths in order:

| Record | Offset | Path |
| --- | --- | --- |
| folder | `0x380` | `root\IC_P15_MULTI_20260828_02` |
| chapter 1 | `0x400` | `root\IC_P15_MULTI_20260828_02\chapter-01.txt` |
| chapter 2 | `0x440` | `root\IC_P15_MULTI_20260828_02\chapter-02.txt` |
| chapter 3 | `0x480` | `root\IC_P15_MULTI_20260828_02\chapter-03.txt` |
| chapter 4 | `0x4c0` | `root\IC_P15_MULTI_20260828_02\chapter-04.txt` |

Candidate blob SHA-256:
`70ea314d015e0a0f5de6e35814df8418c42c2faf188849ee88aea309fb226368`.
Prospective `0x101b` transaction SHA-256:
`8d6dfe86f82d735a1fe725fca6a76e7e4b09f13eef684c6853bd37bcc4eb10b9`, with
range lengths `[256, 64, 65216, 0, 64, 0, 0, 2053216]`. All five fixed-state
bindings are the verified all-zero hash
`f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b`.

The approved modern timestamp policy preserves every existing record
timestamp and assigns `0x6a91a907` to all newly created records. It does not
reproduce the native legacy operation-wide timestamp rewrite. Capture 01's
one-second fourth-child difference remains observed sequential legacy
serialization, not a modern structural invariant.

## Isolated runner contract

`src/infocarry/prepared_multi_package_live_smoke.py` is deliberately not
imported by the normal CLI or GUI. Its first phase,
`prepare_prepared_multi_package_live_smoke`, defaults to read-only and:

1. detects and binds device identity;
2. queries and binds parsed native `0x0019` capacity;
3. creates and verifies a fresh complete backup;
4. rechecks source hashes, exact four-child shape, and absence of `_02`;
5. reconstructs the exact candidate, presents the preview, and seals the
   candidate, backup, capacity, template, timestamp, and destination.

The second phase,
`execute_prepared_multi_package_live_smoke`, requires both the exact separate
owner approval `APPROVE P15-002 MODERN MULTI-TXT SMOKE 01` and the exact
confirmation `ADD ONE INFOCARRY MULTI-CHILD PACKAGE`. It re-detects identity,
re-queries capacity, verifies the sealed backup and candidate, and authorizes
one exact transaction. The sender is one-shot: at most one `0x101b` is sent;
only an explicit integer `0x0000` is accepted; and automatic retry is always
disabled. Cancellation before transmission is safe. Interruption, timeout,
disconnect, missing or malformed completion, and ambiguous completion after
transmission are terminal indeterminate states. A nonzero completion is a
terminal failure. A complete post-operation backup and independent read-back
verification are required after success.

The sender is an isolated adapter over the established guarded write boundary.
It accepts an injected/fake `WriteBackend` for host tests; it is not a normal
product transfer API and no hardware backend was invoked in this task.

## Host validation and derived evidence

The isolated path was exercised through an injected fake hardware boundary.
The run performed one sender call, simulated explicit `0x0000`, captured a
before and after complete archive, and passed independent read-back. Tests
cover seal tampering, cancellation before start, interruption/timeout/
disconnect before and after start, malformed/nonzero completion,
post-readback mismatch, and second-transaction refusal. Derived candidate,
transaction, fake archives, audits, and their preservation manifest are
outside Git at:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-15-p15-002-modern-multi-txt-20260830-02/07-analysis/p15-002-offline-binding-01/`

Those artifacts are not physical-device evidence. Capture 01 remains in its
original external session and was not deleted, overwritten, restored, or
mutated.

## Readiness stop

P15-002 is **READY_FOR_HARDWARE_TEST** after host validation and strong R3
review. This state is a stop point, not authorization to operate the device.
A later execution requires a new operation-specific owner approval with the
exact phrase above, a new fresh complete backup, exact binding revalidation,
and an explicit decision to cross the live execution boundary. No modern
transaction is part of P15-002. After any transaction starts, no retry is
allowed.

This dossier remains the P15-002 host-readiness record. The separately
approved physical execution of this exact `_02` package was performed under
P15-003 and is documented in
`analysis/phase-15-p15-003-exact-modern-four-txt-hardware-smoke-20260830.md`;
the P15-002 preparation task itself did not perform that operation.
