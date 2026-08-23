# Phase 6 — Legacy Receive/Backup Protocol

Date: 2026-08-21

This note records static analysis of the VNW-V15 receive path in the preserved
legacy `VicTwo.dll`. No command described here was sent to the InfoCarry while
preparing this note.

## Evidence identity

- File: `VicTwo.dll` from the preserved InfoCarry Manager installation
- SHA-256: `a02e5927d2e5ded988556e0be0e79a38313ce91f6491ad0ac8835971d3db0dae`
- Image base: `0x10000000`
- Exported entry point: `ReceiveVICData` at `0x10007f50`
- Receive worker: `0x10006320`
- Generic receive helper: `0x10003220`

## Recovered sequence

The following order and requested lengths are **verified by static analysis**
of the function reached by exported `ReceiveVICData`:

| Sequence | Command | Requested bytes | Static source |
| ---: | ---: | ---: | --- |
| 1 | `0x0024` | 64 | helper `0x10004c30` |
| 2 | `0x001b` | 64 | helper `0x10005760`, table at `0x10015250` |
| 3 | `0x001c` | 64 | same table |
| 4 | `0x001d` | 64 | same table |
| 5 | `0x001e` | 64 | same table |
| 6 | `0x001f` | 64 | helper `0x10005870` |
| 7 | `0x8004` | 64 | probe helper `0x10001d90` |
| 8 | `0x8004` | dynamic | allocation/receive helper `0x10001e10` |

The worker calls helpers `0x10004c30`, `0x10005760`, `0x10005870`, and
`0x10001e10` in that order. After they return, the remainder of this worker is
local parsing and host-file generation. Other receive commands found elsewhere
in the DLL are not called by this exported receive worker and are therefore not
included.

Each command uses the previously documented read-only transaction: the
six-byte command/length header, readiness polling, bulk-IN data, then completion
status. No bulk-OUT payload operation is involved in this sequence.

## Dynamic `0x8004` length

The calculation below is **verified by static analysis** of `0x10001d90` and
the field parser at `0x100017e0`:

1. Read an unsigned big-endian direct length at raw offset `0x38`.
2. If it is not `0xffffffff`, use it as the dynamic length.
3. If it is `0xffffffff`, read unsigned big-endian 32-bit values at raw
   offsets `0x30` and `0x34`, then calculate
   `((first + second) // 4) * 4 + 4` bytes.

The first live probe showed why the direct-length branch matters: raw offset
`0x38` contained `0x001f4834`, or 2,050,100 bytes. The initial offline parser
incorrectly expected a marker at raw offset zero and stopped before requesting
the dynamic object. The incomplete attempt was preserved, the stack-offset
analysis was corrected, and the device continued to enumerate normally.

The modern implementation also rejects a calculated blob larger than 16 MiB.
This is an **implementation safety policy**, not a verified protocol limit. It
is deliberately above the largest values observed in command `0x0019` while
preventing a damaged probe from causing an unbounded allocation or transfer.

## Conservatively decoded structures

- Responses `0x001b` through `0x001e` appear to begin with a big-endian count,
  two big-endian 16-bit values, and up to thirteen big-endian 32-bit entries.
- Response `0x001f` appears to contain two records with five big-endian 32-bit
  values each.
- Strings near the relevant legacy code include `VICDATA.bin`,
  `VICMEM.bin`, `VICLV.bin`, and `order.vnw`.

These structural and filename associations are **inferred**. Phase 6 stores
neutral object names and does not use these inferences to alter or discard raw
bytes.

## Implemented safety behavior

The offline implementation:

- allowlists only the seven command identifiers above;
- requests the six fixed objects and probe at exactly 64 bytes;
- preserves every completed object before parsing or requesting the next one;
- stores the two `0x8004` responses under distinct sequence-numbered names;
- records timestamps, requested/received sizes, SHA-256 hashes, protocol
  metadata, and state in `manifest.json`;
- creates the destination exclusively and refuses any existing path;
- leaves an `incomplete` manifest and all durable objects after cancellation,
  disconnect, timeout, or malformed probe;
- uses the existing 128 KiB maximum bulk-IN chunking and finite timeouts;
- exposes no bulk-write operation.

Forty offline tests pass, including synthetic full backup, chunking,
short/empty transfer, finite timeout, cable-disconnect equivalent, cancellation,
low-space write failure, unsafe probe length, malformed probe, hashing, and
non-overwrite behavior.

## Still unresolved

- The semantic names and relationships of the six fixed responses remain
  unknown.
- The final dynamic blob's relationship to the named manager files remains an
  inference until raw device data can be correlated with legacy output.

## Live verification

The connected VNW-V15 was tested read-only on 2026-08-21. The first attempt
preserved the six fixed responses and probe, then stopped before the dynamic
read because of the marker-offset error described above. The device continued
to enumerate as `054c:001e`.

After correcting and offline-testing the direct-length branch, three complete
backups were made without changing device contents. Every archive contains
eight objects and has manifest state `complete`. Independent file reads
verified each recorded size and SHA-256 hash, and every corresponding object
was byte-identical across all three archives:

- Incomplete safety-stop archive: `tests/output/phase-6-backup-first`
- Complete archives: `tests/output/phase-6-backup-complete-1`,
  `tests/output/phase-6-backup-complete-2`, and
  `tests/output/phase-6-backup-complete-3`

| Sequence | Command | Bytes | SHA-256 |
| ---: | ---: | ---: | --- |
| 1 | `0x0024` | 64 | `c55df6bb8a91619200ce14477b83e270424ee58525b5ee3de78bbc2bfcb82f9e` |
| 2 | `0x001b` | 64 | `173f5c4320c3a6a9ba939ee09beb3a8d62d03463972e5893d3986383b2bf9198` |
| 3 | `0x001c` | 64 | `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` |
| 4 | `0x001d` | 64 | `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` |
| 5 | `0x001e` | 64 | `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` |
| 6 | `0x001f` | 64 | `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` |
| 7 | `0x8004` probe | 64 | `c0e330b0f8179f87dfd4d017b795dd337ed04383d5f33b7821572d0edf892ff5` |
| 8 | `0x8004` blob | 2,050,100 | `1ff7521cc2b96df8c64f322c41501e45d5efdf21189a9abb39176d99d6cfc14a` |

The SHA-256 of all eight raw objects concatenated in sequence is
`74b0704621c78bf9908e12e7103d192984a120a7c3109eb599cac2e86e23dce6`
for all three backups. The InfoCarry still enumerated normally after the third
backup. No device-to-host backup operation used a bulk-OUT payload.

Phase 6's reproducibility gate is therefore satisfied for this device state.
Semantic decoding of the losslessly preserved objects remains Phase 7 work.
