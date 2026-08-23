# Phase 8 — Range-5 Source Recovery

Date: 2026-08-21

This is an offline comparison of the two preserved native SnoopyPro captures.
It does not replay either capture, open USB, or create a write candidate.

## Exact fixed transform

Static disassembly of `VicTwo.dll` helper `0x10001550` establishes the
ordinary 64-byte map:

| Source offset | Output offset | Rule |
| ---: | ---: | --- |
| `0x00`–`0x07` | `0x00`–`0x07` | raw dword copies |
| `0x08` | `0x08` | raw byte copy |
| `0x09`–`0x0d` | `0x09`–`0x0d` | raw byte/dword stores |
| `0x0e` | `0x0e` | 16-bit byte swap |
| `0x10` | `0x10` | 16-bit byte swap |
| `0x12` | `0x12` | raw 16-bit copy |
| `0x14`–`0x38` | same offsets | 32-bit byte swaps |
| `0x3c`–`0x3f` | `0x3c`–`0x3f` | raw dword copy |

The worker supplies a 64-byte length, so every output byte is represented by
the source object. `serialize_range5_model()` implements the map and
`recover_range5_source()` applies its exact reverse, then verifies a forward
byte-for-byte round trip. The recovery result carries an empty
`unknown_offsets` tuple because no source byte is omitted at this length.

## Preserved captures

Capture identities:

- `00-read-baseline.usblog` SHA-256
  `70ebd381ccf8864130230dd91caba644f525437c562ddb323528ef2a23046afa`;
  transaction record offset `0x23641f`.
- `01-selected-send.usblog` SHA-256
  `c8b3812682e1d1974c7d3843e25b7a7fa471dc1de4bcd83a7acec66c447f4a5c`;
  transaction record offsets `0x237647` and `0x467425`.

The baseline transaction and the first selected-send transaction have the
same range-5 wire hash and recover the same source candidate:

```text
696e666f436172727920322e303000014000ffff20000000276b1f00b731d468000000000000000040000000c05a0000005b000024101f00286b1f00ffffffff
```

Source-candidate SHA-256:
`2332a5ca2e4d95594599b973f51f06456fe875343b15066c38020dbdf487d96c`.

The second selected-send transaction recovers:

```text
696e666f436172727920322e303000014000ffff20000000c7771f00be675141000000000000000040000000005b0000405b0000841c1f00c8771f00ffffffff
```

Source-candidate SHA-256:
`61807372d2549369ef8e6085df10e751e928c93e5a7c1918b99f6cd8c9abef62`.

The selected transaction therefore changes the recovered source at the same
fixed offsets that changed on the wire; it is not a packet-framing artifact.
The source fields remain deliberately unnamed. Some values look like counts,
lengths, checksums, or offsets, but these captures alone do not establish
their semantics or the rules that populate them for new content.

## Implementation boundary

The recovery helper is useful for fixture comparison and regression tests. It
does not infer the range-5 source from `VICDATA.bin`, does not reconstruct the
model tree, and is not connected to `ProspectiveWriteTransaction` or any USB
backend. Ranges 4 and 6–8, including the variable part of the model builder,
remain the gating work for a future write-capable implementation.
