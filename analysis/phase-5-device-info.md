# Phase 5 Device Information Progress

Status: verified offline and on the connected Sony InfoCarry VNW-V15 on
2026-08-21.

## Implemented safety boundary

- Only the statically verified read-only commands `0x18` (configuration) and
  `0x19` (hardware) are exposed by `DeviceInfoClient`.
- Both commands declare and require exactly 64 response bytes.
- The lower transport rejects every command outside its explicit allowlist
  before USB access.
- `infocarry info` requires `--save-raw NEW_DIRECTORY`.
- The destination must not already exist.
- Each raw response is opened exclusively, written, flushed, and synchronized
  before any parsing can occur.
- A manifest records the command, byte length, filename, and SHA-256 hash.
- Parsing occurs only after raw preservation. Verified display dimensions are
  decoded; unknown bytes remain raw evidence with neutral offset-based names.

## Offline verification

Twenty-nine tests pass. In addition to the Phase 4 suite, Phase 5 tests verify:

- exact command `0x18` header `18 00 40 00 00 00`;
- exact command `0x19` header `19 00 40 00 00 00`;
- request-3, 64-byte bulk-IN, request-4 ordering;
- command-specific result metadata;
- raw-file content and SHA-256 integrity;
- in-progress and complete manifest states; and
- refusal to overwrite an existing capture directory or file.

The saved response fixtures are hash-checked by the parser tests. The parser
decodes only big-endian values established by the legacy code. Semantic names
are limited to the 240 x 320 display dimensions, which are independently
corroborated by the VNW-V15 display. Other values retain offset-based names.

## Live verification

The earlier execution-quota condition cleared before these tests. Each command
was then run in three separate open/query/close sessions, followed by one
combined `--query all` session.

### Configuration command `0x18`

All four 64-byte responses were byte-for-byte identical:

```text
SHA-256 ac1f502c5f5b7c9cd57c9f34ae1a787ed998b7c3761da5ce4894e15f59039639

00000000: 0b 00 01 04 03 02 00 00 00 00 00 01 00 00 00 00
00000010: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00000020: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00000030: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
```

`VicTwo.dll` consumes bytes 1 through 11 as model-specific configuration
settings. The live leading byte is `0x0b`, and the parser preserves it separately
without claiming a semantic name. The 11 settings bytes are preserved as
`00 01 04 03 02 00 00 00 00 00 01`; bytes 12 through 63 are zero on this unit.

### Hardware command `0x19`

All four 64-byte responses were byte-for-byte identical:

```text
SHA-256 c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a

00000000: 00 f0 01 40 00 0c 00 0c 00 30 00 00 00 00 00 00
00000010: 00 00 40 00 00 40 00 00 00 00 00 00 00 00 00 00
00000020: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00000030: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
```

The verified big-endian parser yields:

| Offset | Width | Value | Current interpretation |
| --- | --- | --- | --- |
| `0x00` | 16-bit | 240 | Display width in pixels |
| `0x02` | 16-bit | 320 | Display height in pixels |
| `0x04` | 16-bit | 12 | Meaning unknown; retained as `field_04_be16` |
| `0x06` | 16-bit | 12 | Meaning unknown; retained as `field_06_be16` |
| `0x08` | 32-bit | 3,145,728 | Meaning unknown; retained as `field_08_be32` |
| `0x0c` | 16-bit | 0 | Meaning unknown; retained as `field_0c_be16` |
| `0x0e` | 16-bit | 0 | Meaning unknown; retained as `field_0e_be16` |
| `0x10` | 32-bit | 16,384 | Meaning unknown; retained as `field_10_be32` |
| `0x14` | 32-bit | 4,194,304 | Meaning unknown; retained as `field_14_be32` |

Bytes `0x18` through `0x3f` are zero on this unit.

## Preserved captures

The non-overwriting raw directories are:

- `tests/output/phase-5-config-first`
- `tests/output/phase-5-config-second`
- `tests/output/phase-5-config-third`
- `tests/output/phase-5-hardware-first`
- `tests/output/phase-5-hardware-second`
- `tests/output/phase-5-hardware-third`
- `tests/output/phase-5-info-all`

Every directory contains an independently hashed raw file and completed
manifest. `cmp` confirmed equality across the three standalone captures; the
combined capture has the same hashes.

The final public CLI verification was:

```sh
.venv/bin/infocarry info --query all --save-raw tests/output/phase-5-info-all
```

Both queries reported successful transfer/completion status. The InfoCarry was
still detectable as `054c:001e` after all queries. No content-write command,
bulk-OUT transfer, reset, or unknown request was sent.
