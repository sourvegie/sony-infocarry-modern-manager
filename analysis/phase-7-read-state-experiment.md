# Phase 7 — Controlled Read-State Experiment

Date: 2026-08-21

## Safety and procedure

This experiment used a normal on-device action followed only by the already
verified read-only backup workflow. The user disconnected the InfoCarry, opened
`簡易マニュアル/各部の名前とはたらき`, closed it, reconnected the device, and
reported completion. The host then made two complete backups. No host write,
restore, unknown command, or control request was sent.

Evidence directories:

- `tests/output/phase-7-read-state-after-1`
- `tests/output/phase-7-read-state-after-2`

Both post-action backups are complete and byte-identical across all eight raw
objects. Their dynamic blob SHA-256 is
`f30153cf3c3a6dbc7c540b600bb2038f9b8b0344a16dbb3cf17eb1ddf0fa771b`.
The stable repeat proves that the backup read itself caused no further state
change.

Deterministic exports from those backups contain 225 unread and 23 read files
and have matching tree aggregate
`d3fbb6e65be3322a0bc65e944b7650e75ccc92922865e585aa863667f04217bf`:

- `tests/output/phase-7-read-state-export-1`
- `tests/output/phase-7-read-state-export-2`

## Verified record-state transition

Compared with the stable Phase 6 baseline, exactly 18 bytes changed in the
2,050,100-byte blob. Two reachable file records changed only in the high state
bits of byte zero:

| Record | File | Before | After |
| ---: | --- | ---: | ---: |
| `0x0200` | `簡易マニュアル/各部の名前とはたらき.txt` | `0xe0` | `0x20` |
| `0x0240` | `簡易マニュアル/画面の名前とはたらき.txt` | `0xe0` | `0x20` |

The user confirmed that scrolling down through the first file transitioned the
device into the adjacent second file. Both records were therefore actually
displayed during the controlled action. The history response retained the
directory and initially selected file, while the read-state flags correctly
changed for both displayed files.

The embedded manual independently states that the device distinguishes unread
and read file icons and changes the icon after displaying content. Combined
with this controlled `0xe0 -> 0x20` transition, the file flags are now
**verified** as:

- `0xe0`: unread file;
- `0x20`: read file.

## Mutable file wrapper

Each affected file's 32-byte wrapper changed while its exact native text
payload remained byte-identical. In both cases the wrapper's eight big-endian
32-bit words retained the same modulo-`2^32` sum, `0xfffffff8`:

- record `0x0200`: `01fffffffdff...` became
  `018cff0dfdff0000007400f0ffff...`;
- record `0x0240`: `01fffffffdff...` became
  `01cfff0dfdff0000003100f0ffff...`.

The wrapper therefore contains checksum-balanced mutable per-file view state. A
static manager serializer at `VicTwo.dll` `0x100042f0` confirms the fixed raw
locations: prefix `0x04` is an internal flag byte, `0x05` is an internal byte,
`0x06..0x07` an internal big-endian word, `0x08..0x0b` and `0x0c..0x0f`
internal big-endian dwords, and `0x10..0x1f` reserved/fill bytes. The first
word is a complement checksum over the remaining words. The meanings of
those internal fields (for example, cursor versus renderer state) remain
unresolved and are preserved losslessly.

The complete blob checksum remained exactly `0xc12ddb73`, as expected: the
legacy checksum excludes the record's high `0xc0` state bits, and the changed
wrapper words preserve their sum.

## Command `0x001b`

The `0x001b` response changed from SHA-256
`173f5c4320c3a6a9ba939ee09beb3a8d62d03463972e5893d3986383b2bf9198`
to `059eb8c07bf129fa1c630f02dba840f53dcfa072f206edd36dee89cff6775de8`.
Its ten-offset list changed from:

`5840 5800 57c0 5780 3340 3300 32c0 3280 1540 1500`

to:

`01c0 0200 5840 5800 57c0 5780 3340 3300 32c0 3280`

These response offsets are relative to the metadata start at blob offset
`0x40`. They therefore map to absolute record offsets `0x0200` and `0x0240`,
the first and second manual files displayed during the continuous scrolling
action. The two viewed files were prepended and the oldest two entries were
dropped. This conversion was verified later by moving Bookmark 2 between the
same two files. Combined with the device's documented “display history”
feature, this **verifies command `0x001b` as the bounded display-history record
list**.

Commands `0x001c` through `0x001f`, command `0x0024`, the size probe, all file
payloads, all directory structures, all timestamps, and all other records were
unchanged.
