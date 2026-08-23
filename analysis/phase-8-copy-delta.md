# Phase 8 copy-delta analysis

Date: 2026-08-21

This is an offline comparison between the pre-send transaction captured in
`00-read-baseline.usblog` and the fresh read-only backup taken after the
manager's selected-send test. It does not access USB and does not generate a
device-facing payload.

## Blob-level change

| value | before | after | delta |
| --- | ---: | ---: | ---: |
| decoded blob length | 2,059,048 | 2,063,788 | +4,740 (`0x1284`) |
| metadata records | 363 | 365 | +2 |
| reachable paths | 306 | 308 | +2 |
| range-8 model bytes | 2,058,984 | 2,063,724 | +4,740 |

The new dynamic `0x8004` backup object is byte-for-byte equal to the captured
range-5 plus range-8 payload. This confirms that the new capture represents the
manager's resulting model state, not merely a request that happened to be
accepted by the transport.

## Range-5/range-8 split

The three preserved ordinary captures now establish the same byte boundary:

| decoded `VICDATA` region | wire range | observed length | relationship |
| --- | --- | ---: | --- |
| bytes `0x00..0x3f` | range 5 | `0x40` | exact byte equality |
| bytes `0x40..end` | range 8 | variable | exact byte equality |

Thus the decoded blob is not a separately transformed representation at this
boundary: the ordinary worker sends its first 64-byte VICDATA header as range 5
and the exact remainder as range 8. The fixed range-5 helper remains useful for
recovering the source object used by the worker, but no second transform is
needed to split a validated decoded blob.

`src/infocarry/payload_builder.py` exposes this fact through the offline-only
`build_from_decoded_vicdata()` helper. It validates the backup structure,
recovers the range-5 source, serializes ranges 1--3 from a separately supplied
state snapshot, and checks that ranges 5+8 reassemble the original blob. It
does not infer sidecars, ranges 4/6/7, or a new model tree, and it has no USB
entry point.

## Inserted records

Two 64-byte metadata records were inserted at offsets `0x03c0` and `0x0400`,
before the existing `簡易マニュアル\\その他` subtree:

| metadata offset | path | flag | payload length | payload SHA-256 |
| ---: | --- | --- | ---: | --- |
| `0x03c0` | `簡易マニュアル\\Copy of 各部の名前とはたらき.txt` | `0xe0` | 3,135 | `5a036415ae4c95d225135ea875126ece5e4a6c6900a3ff0dad43f3d7c0ad0dcc` |
| `0x0400` | `簡易マニュアル\\Copy of 画面の名前とはたらき.txt` | `0xe0` | 1,410 | `e8a388b9a11b28bfdd7e845b1d1ddf7ceab5396a9a76532eb82bde96cef5ff21` |

Each new payload hash exactly matches the corresponding original manual file.
The manager therefore duplicated both manual records even though the supplied
screenshot highlighted only `画面の名前とはたらき.txt`.

## Structural implications

1. Existing metadata after `0x03c0` is shifted by `0x80`; pointers and content
   offsets are recomputed rather than left stale.
2. The content increase (`0x1204` bytes) is larger than the raw payload sum
   (`0x11c1` bytes), demonstrating that each copied file also carries its
   native 32-byte view prefix and 4-byte content alignment.
3. The new directory/file records are ordinary `0xe0` text records with the
   same native payload-prefix class (`field_14 = 0x00000200`) as their sources.
4. This is useful evidence for a future arbitrary-add implementation, but it
   is not enough to synthesize a complete range-8 model: parent/sibling links,
   directory model nodes, sidecar state, and manager naming/collision rules
   still need independent verification.

The constrained offline builder in `src/infocarry/backup_duplicate.py` now
reconstructs this exact decoded blob when supplied the two source offsets, new
names, copy timestamps, and the observed per-record timestamp map. The result
is byte-identical to the fresh `0x8004` backup object, including metadata
shifts, content alignment, and checksum. This is an offline format result; it
does not establish that arbitrary additions or a generated range-8 model are
accepted by the device.

## Safety decision

The captured transaction is not a disposable modern-write candidate. Replaying
it would request the same two-copy operation again. It is retained solely as a
legacy example for offline model reconstruction. The modern sender remains
disabled until an independently authored minimal candidate is structurally
validated and receives the final interactive `WRITE INFOCARRY` confirmation.
