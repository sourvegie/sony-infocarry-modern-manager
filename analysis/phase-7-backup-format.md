# Phase 7 — Backup Format and Lossless Export

Date: 2026-08-21

This phase uses only local copies of the three stable Phase 6 backups. No USB
device command was sent during the analysis or export work described here.

## Evidence

- Source blob SHA-256:
  `1ff7521cc2b96df8c64f322c41501e45d5efdf21189a9abb39176d99d6cfc14a`
- Source length: 2,050,100 bytes (`0x001f4834`)
- Legacy evidence: preserved `VicTwo.dll`, especially header parser
  `0x100017e0`, record parser `0x10001ab0`, validator `0x10005550`, and receive
  worker `0x10006320`
- Independent live copies: all three complete Phase 6 blobs are byte-identical

## Top-level blob layout

The following offsets are **verified by static parsing code and observed in all
three live blobs**:

| Header offset | Observed value | Meaning |
| ---: | ---: | --- |
| `0x00` | `infoCarry 2.00` | format signature |
| `0x0e` | `1` | major version |
| `0x0f` | `0` | minor version |
| `0x10` | 64 | metadata record size |
| `0x14` | 32 (`0x20`) | checksum's first header offset |
| `0x18` | 2,050,099 | last valid blob byte offset |
| `0x1c` | `c12ddb73` | stored 32-bit checksum |
| `0x20` | 0 | optional checksum-region start |
| `0x24` | 0 | optional checksum-region end |
| `0x28` | 64 (`0x40`) | metadata start |
| `0x2c` | 23,168 (`0x5a80`) | metadata length |
| `0x30` | 23,232 (`0x5ac0`) | content-region start |
| `0x34` | 2,026,864 (`0x1eed70`) | content-region length |
| `0x38` | 2,050,100 (`0x1f4834`) | total blob length |
| `0x3c` | `ffffffff` | unknown marker/check value |

The regions are contiguous and reproduce the received length exactly:

`0x40 + 0x5a80 = 0x5ac0`

`0x5ac0 + 0x1eed70 + 4 = 0x1f4834`

The final four bytes are also `ffffffff`. Their marker semantics remain
**unknown**.

## Checksum

The checksum algorithm is **verified by static analysis** of legacy validator
`0x10005550` and by exact agreement across all three live blobs. It adds
big-endian 32-bit words modulo `2^32` from:

1. the header range beginning at the offset stored at `0x14` and ending at the
   64-byte record-size boundary;
2. an optional range stored at `0x20`/`0x24` when nonempty;
3. the complete metadata region, after subtracting the legacy flag/value
   adjustment from the first word of each 64-byte record;
4. the content region through the four-byte trailer.

The result is compared with header offset `0x1c`. All three live blobs calculate
to the stored value `0xc12ddb73`. The production parser now rejects any content
or metadata change that does not preserve this checksum, in addition to checking
the raw archive's SHA-256.

## Metadata records

`VicTwo.dll` parses each 64-byte record as follows. Numeric fields are
big-endian:

| Record offset | Size | Current interpretation |
| ---: | ---: | --- |
| `0x00` | 1 | record flag/type |
| `0x01` | 3 | ASCII extension or zeroes |
| `0x04` | 4 | directory-table anchor or content-relative offset |
| `0x08` | 4 | directory-table byte length or file payload length |
| `0x0c` | 4 | unsigned Unix timestamp (seconds since 1970-01-01 UTC) |
| `0x10` | 4 | unknown flags/value |
| `0x14` | 4 | payload-prefix/subtype value for files |
| `0x18` | 40 | zero-terminated CP932 name field |

Observed record flags are:

- `0xd0`: directory;
- `0xe0`: unread file;
- `0x20`: read file.

The high `0xc0` bits are deliberately excluded from the checksum adjustment in
the legacy validator, so they are checksum-neutral mutable state bits. A
controlled before/after experiment then observed ordinary on-device viewing
change both files displayed during continuous scrolling from `0xe0` to `0x20`,
with exact payload bytes unchanged. The embedded manual independently states
that displaying unread content changes it to read. The meanings are therefore
**verified**. See `analysis/phase-7-read-state-experiment.md`.

## Timestamps

Record field `0x0c` is **verified as a 32-bit Unix timestamp**. The preserved
values `0x6a86a0ba` through `0x6a86a0d6` decode to 2026-08-20 06:37:46 through
06:38:14 UTC (15:37:46 through 15:38:14 in the host's JST timezone), matching
the content creation/import session. Static code in the legacy DLL uses the
standard 2,208,988,800-second conversion between the 1900 and 1970 epochs and
the Windows time APIs. The export manifest now includes the original integer
plus a UTC ISO-8601 rendering; it never applies the current host timezone.

For a directory, children begin one record after the anchor in field `0x04`.
Field `0x08` is the child-table length and is always a multiple of 64. Walking
these tables from the root at `0x40` accounts for every non-parent record with
no cycles, duplicate links, missing records, or out-of-bounds tables.

## File payloads

For files, field `0x04` is relative to the content-region start and field
`0x08` is the payload length. Field `0x14` selects a preserved prefix:

- `0x00000100`: 16-byte prefix;
- `0x00000200`: 32-byte prefix.

The manager-produced fixture also contains `0x00010200`. Its low 16 bits are
the same `0x00000200` selector and therefore still give a 32-byte prefix; the
high state bit is retained in the raw record and must not cause the parser to
reject the otherwise valid payload. This is an observed compatibility variant
from one fixture, not yet a complete semantic definition of the high bit.

This agrees with the legacy worker multiplying the relevant unit by 16 and is
also verified by all live payload boundaries. The prefixes are retained in the
export manifest. Exact native payloads begin after the prefix. For 32-byte text
prefixes, the stable raw field offsets and checksum rule are documented in
`analysis/phase-7-view-wrapper.md`; the modern exporter reports those offsets
without assigning unresolved cursor or renderer semantics.

The complete tree contains:

- 362 metadata records;
- 57 reachable directories;
- 57 `..` parent records;
- 248 reachable files;
- 150 BMP files;
- 97 text files;
- one extensionless `.DS_Store` file;
- zero orphan or unknown-type records.

All 150 BMP payloads have valid Windows BMP signatures and internal file
lengths. Every BMP is 1-bit monochrome. Of these, 114 are 240 x 320; the other
36 have smaller content-specific dimensions and are preserved unchanged.

## Text encoding

File and directory names decode strictly as CP932. Text payloads use CP932-like
data, but 21 of 97 files contain 194 device-specific two-byte sequence
occurrences that Python's CP932 codec correctly rejects. They comprise 41
distinct values. Every observed value begins with a CP932 lead-range byte and
uses a second byte below the ordinary CP932 trail-byte range; examples include
`81 25`, `82 2c`, `83 20`, and `87 28`. Repetition in the shipped Japanese
manual establishes these as structured private glyph/control codes rather than
random corruption.

The manual text directly establishes semantic roles for 38 of the 41 types.
These include read/unread status, marks, folders, scrolling modes, lock state,
battery and external-power indicators, and memo-editor controls. These meanings
are included in the export manifest. Only three components from the manual's
top-level folder illustration remain unnamed. See
`analysis/phase-7-private-glyphs.md`.

The exporter therefore creates two views:

1. `native/` contains the exact payload bytes, without transcoding.
2. `decoded-text/` contains UTF-8 text. Valid CP932 is decoded; every invalid
   source byte is represented explicitly as `\xNN`, and its original offset is
   listed in the manifest.

This approach is readable while avoiding silent replacement or unexplained
loss. The original full blob, record bytes, payload prefix, native payload, and
hash remain available independently.

The manifest additionally inventories every candidate sequence by source byte
offset and raw two-byte value, plus a deterministic global frequency catalog.
This makes later screen/font correlation possible without changing the native
files or prematurely assigning glyph names.

## Fixed-response correlations

The following are **observed correlations**, not semantic names:

- Command `0x0024` begins with `0x001f4834`, exactly the dynamic blob length.
- Command `0x001b` is the bounded display-history record list. A controlled
  file-open experiment prepended both displayed-file records and dropped the
  oldest two offsets. Response offsets are metadata-relative: add header
  `metadata_start` (`0x40`) to correlate them with absolute exported records.
- In the original stable device state, commands `0x001c`, `0x001d`, `0x001e`,
  and `0x001f` were all zero. After the controlled mark sequence, `0x001c`
  reported one entry at metadata-relative `0x01c0` (absolute file record
  `0x0200`), verifying it as the first mark list.

Static parsing in `VicTwo.dll` establishes the response shapes:

- each of `0x001b` through `0x001e` is parsed as a big-endian 32-bit count, two
  big-endian 16-bit values, then up to 13 big-endian 32-bit record offsets;
- the legacy code rejects a count of 14 or more;
- `0x001f` is parsed as two consecutive groups of five big-endian 32-bit
  values;
- the DLL contains the on-disk signatures `VICVLBIN  ` and `VICMEMOBIN` and
  paths `VICLV.bin`, `VICMEM.bin`, `VICDATA.bin`, and `order.vnw`.

`0x001b` is verified as display history, and the complete mark ordering is
verified as `0x001c` = mark 1, `0x001d` = mark 2, and `0x001e` = mark 3. The
two five-value groups in `0x001f` are verified as Bookmark 1 and Bookmark 2.
The fourth dword advances by 20 per full page and is strongly identified as the
rendered-line index. At one and two pages, the fifth dword is `0xfff101be` and
`0xfff10448`; its low 16 bits point to valid CP932 boundaries at the
corresponding first visible wrapped lines and are strongly identified as source
byte offsets. A cross-file capture changed bookmark dword 1 from `0x01c0` to
`0x0200` when the selected absolute file record changed from `0x0200` to
`0x0240`, verifying dword 1 as the metadata-relative selected-file record
offset. The upper `0xfff1` tag remains unresolved. A zero entry count is
authoritative:
the controlled captures showed that unused offset slots may retain stale
bytes. Selecting a different mark on the same file replaced its previous mark.
Static `VICLV.bin` and `VICMEM.bin` findings are recorded in
`analysis/phase-7-sidecar-structures.md`.

Static consumer `0x10005a20` matches bookmark dword 1 to the current file and
copies dwords 3 and 4 as a coordinate pair. With the vertical text experiments,
dword 3 is strongly identified as horizontal position (zero in all captures)
and dword 4 is verified as vertical rendered-line index. Dwords 2 and 5 are not
used by that legacy reconstruction path.

## Implementation and verification

The offline command is:

`infocarry export BACKUP_DIRECTORY NEW_DIRECTORY`

It requires a complete Phase 6 manifest, verifies the dynamic object's length
and SHA-256, validates all structural bounds, refuses an existing destination,
and writes native files, decoded text views, and a provenance manifest.

Fifty-five offline tests pass. Tests cover header and tree parsing, checksum
verification and mutation detection, exact payload
extraction, malformed magic/length/table rejection, invalid CP932 escaping,
device-sequence inventory, Unix timestamp rendering, hash verification,
deterministic export, and non-overwrite behavior in addition to all earlier
transport and backup tests. Neutral bounded parsers for the verified
`0x001b`--`0x001f` response shapes are also implemented and agree with the
preserved live responses. A separate lossless `VICLV.bin` parser/builder has
exact synthetic round-trip coverage for its statically recovered layout.

Current verified exports from complete backups 1 and 3 contain 346 files each
(248 native files, 97 decoded text files, and one manifest) and are
byte-identical. Their
deterministic tree aggregate is:

`ddc1d89edeaa0f455cc33f3dff43c25642c90fea514ee62fde1bb20b2ca641fd`

Generated evidence directories:

- `tests/output/phase-7-export-verified-5`
- `tests/output/phase-7-export-verified-6`

## Remaining work

- Determine the exact meanings of record flags `0x20` versus `0xe0`.
- Correlate the remaining three private graphic components with exact glyph
  artwork.
- Assign verified names and structures to commands `0x001b` through `0x001f`
  and to `VICMEM.bin`, `VICLV.bin`, and `order.vnw`.
- Add a lossless repacking/round-trip test only after those fields are known;
  write support remains out of scope until Phase 8's separate safety gate.
