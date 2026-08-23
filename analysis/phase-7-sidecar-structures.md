# Phase 7 — Legacy Sidecar and Mutable View-State Structures

Date: 2026-08-21

This note records static findings from preserved `VicTwo.dll`, correlations
with the live raw responses, and the controlled read-state experiment. No
device command was sent for this analysis.

## Fixed device responses

The DLL helper at `0x10005760` parses commands `0x001b` through `0x001e` into
four consecutive 64-byte host structures. Each response contains:

- big-endian 32-bit entry count at `0x00`;
- two big-endian 16-bit values at `0x04` and `0x06`;
- up to 13 big-endian 32-bit metadata-relative record offsets at `0x08`;
- unused/preserved tail bytes.

The helper rejects counts of 14 or more. A later routine processes the four
lists in command order with category masks `1`, `2`, `4`, and `8`. This gives
the static category-index mapping `0x01 -> 0x001b` (display history),
`0x02 -> 0x001c` (mark 1), `0x04 -> 0x001d` (mark 2), and `0x08 -> 0x001e`
(mark 3). The command meanings are verified by controlled captures; the
static index correlation is documented in
`analysis/phase-7-vicmem-category-mapping.md`.

Command `0x001b` is **verified as display history** by the controlled file-open
experiment: it prepended both displayed-file offsets and discarded the oldest
two entries. Response offsets are relative to metadata start `0x40`; thus
`0x01c0` and `0x0200` map to absolute file records `0x0200` and `0x0240`.
The device manual documents exactly three mark types.

A controlled device-UI sequence selected mark choices 1, 2, 3, then 1 again on
the same file. In the stable final state, `0x001c` had count 1 and record offset
`0x01c0` (absolute file record `0x0200`); `0x001d` and `0x001e` had count 0.
This **verifies `0x001c` as the first mark list**. An isolated second-choice
experiment then produced count 1
at the same offset in `0x001d`, with counts zero in `0x001c` and `0x001e`.
This **verifies `0x001d` as the second mark list** and verifies that selecting
mark 2 replaced mark 1 on this file. A subsequent isolated third-choice state
produced count 1 at the same offset in `0x001e`, with counts zero in `0x001c`
and `0x001d`. This **verifies `0x001e` as the third mark list**. The complete
mark-list ordering is therefore verified, as is replacement of one mark by
another for the tested file.

The zero-count `0x001d` and `0x001e` responses retained `0x01c0` in the first
unused slot. The repeated capture was byte-identical, proving this is stable
unused/shared-buffer residue in this state. Consumers must honor `count` and
must not treat tail slots as entries. See
`analysis/phase-7-mark-state-experiment.md`.

## Command `0x001f`

The helper at `0x10005870` parses command `0x001f` as exactly two consecutive
groups of five big-endian 32-bit values. The consumer at `0x10005a20` iterates
exactly twice, treats the first value as a metadata-record index, and carries
two of the remaining values into a special category-`0x10` entry associated
with that record's path.

The embedded manual documents exactly two global bookmarks, “Bookmark 1” and
“Bookmark 2”, each selecting a file and a line/page position. A controlled
Bookmark 1 action changed only the first group, from all zero to
`(0x01c0, 0x0140, 0, 0, 0)`; the second group remained all zero. A later
isolated Bookmark 2 action one page lower changed only the second group to
`(0x01c0, 0x0140, 0, 20, 0xfff101be)`, while Bookmark 1 remained unchanged.
Each state was confirmed by two byte-identical complete backups. This
**verifies the first and second groups as Bookmark 1 and Bookmark 2** and shows
that the slots are independent. The fourth and fifth values are verified
position-state components. Moving Bookmark 2 from one page to two pages changes
the fourth value from 20 to 40 and the fifth from `0xfff101be` to
`0xfff10448`. The low 16 bits, source offsets 446 and 1096, are valid CP932
boundaries at the corresponding first visible wrapped lines. Thus the fourth
value is strongly identified as the rendered-line index and the low 16 bits of
the fifth as its source-byte offset. The `0xfff1` tag and value 2 remain
unresolved. See
`analysis/phase-7-bookmark-state-experiment.md`.

A cross-file Bookmark 2 capture at the beginning of the adjacent absolute file
record `0x0240` changed the bookmark's first dword from `0x01c0` to `0x0200`,
while the other four dwords returned to the same top-of-file state
`(0x0140, 0, 0, 0)`. Adding metadata start `0x40` maps both values exactly to
their selected file records. This **verifies bookmark dword 1 as the
metadata-relative selected-file record offset**. The simultaneous display
history change obeyed the same coordinate rule.

The static consumer at `0x10005a20` matches dword 1 to the current file and
copies dwords 3 and 4 into two coordinate outputs. Together with the controlled
vertical-text captures, dword 3 is strongly identified as horizontal position
(always zero here) and dword 4 is verified as vertical rendered-line index.
Dwords 2 and 5 are not used by this legacy reconstruction path; dword 5 still
correlates independently with the tagged source-byte position on the device.

## `VICLV.bin`

The complete layout is now reconstructed. The 16-byte header is the ten-byte
signature `VICVLBIN  `, two reserved bytes, and little-endian version 1. Each
261-byte (`0x105`) entry is one neutral category byte followed by a 260-byte
NUL-terminated relative CP932 Windows path field. The legacy creator emits
category 1 or 2 according to odd parity in two adjacent internal 16-bit record
fields. It appends entries in traversal order without sorting or deduplication.

A lossless parser/builder preserves reserved bytes, unknown categories,
post-NUL padding, and entry order exactly. The preserved legacy package itself
contains no sample, but the user-provided fixture now confirms two category-2
entries (an empty path and `日本語書籍`); no broader ordering or category
semantics are inferred from that single image. See
`analysis/phase-7-viclv-format.md` and
`analysis/phase-7-fixture-inventory.md`.

## `VICMEM.bin`

The DLL contains path suffix `\\VICMEM.bin`, signature `VICMEMOBIN`, and the
memo path `\\Sony\\infoCarry\\Memo`. The complete binary layout is now
recovered offline: a 20-byte header (`VICMEMOBIN`, two reserved bytes,
little-endian version 1, and a little-endian section mask), four optional
category sections with 0x104-byte records, and one optional tail section with
0x10c-byte records. The low five mask bits select those sections;
the writer emits category counts and four-byte auxiliary values before each
category's records, and a count before the tail records. The legacy allocations
hold at most 20 category records and two tail records, which are enforced as
modern parser safety limits. The auxiliary value's semantic role remains
unknown because the loader reads it into a temporary slot that non-empty record
loads overwrite. The preserved legacy package itself contains no sample; the
user-provided fixture confirms section mask `0x19`, category-0/category-3
counts and auxiliary bytes, and two zero-valued tail records. Synthetic exact
round-trip fixtures continue to verify the layout. Static constructors and
consumers now prove that every record begins with 0x104 bytes of
NUL-terminated relative-path storage. Tail offsets 0x104 and 0x108 copy
bookmark-group dwords 3 and 4;
controlled observations identify the latter as rendered-line position. All
post-NUL and unresolved bytes remain preserved. See
`analysis/phase-7-vicmem-format.md`.

## `order.vnw`

The DLL stores a registry path `Software\\Sony Corporation\\infoCarry`, value
name `OrderControlFile`, and default filename `order.vnw`. The transfer writer
creates the selected file in text mode, writes the literal `;v1.0\n` preamble,
and appends basename records as newline-terminated ANSI strings. Its generated
physical names use `%s-%d.%s` with a one-based counter. Static tracing now
identifies the base source as the parent path plus the current record's raw
name field (`+0x18`). The extension is the record's three-byte raw field
(`+0x01`) when object byte `+0x1a` has no low `0x07` bits; otherwise the
manager substitutes the constant `ecd`. The reader skips first-byte `;` lines
and truncates other lines at the first `:`, CR, or LF, without validating the
version preamble. A lossless offline parser mirrors those rules. Static loop
tracing now verifies metadata-record ordering and first-failed-read-probe
numeric collision handling; full repacking remains separate and unresolved.
See `analysis/phase-7-order-control.md`.

## Mutable 32-byte text wrapper

Every unread text file in the captured device state uses the same wrapper:

`01fffffffdffffffffffffffffffffffffffffffffffffffffffffffffffffff`

BMP and extensionless 16-byte wrappers are all `ff`. During the controlled
viewing experiment, both displayed text files changed wrapper bytes while their
native payloads remained identical. Each wrapper's eight big-endian dwords
retained modulo-`2^32` sum `0xfffffff8`, keeping the full backup checksum
unchanged.

This is **observed checksum-balanced mutable per-file view state**. A static
serializer at `VicTwo.dll` `0x100042f0` now gives stable raw field locations:
prefix `0x04` copies an internal flag byte at `+0x50`; prefix `0x05`, `0x06`
through `0x07`, `0x08` through `0x0b`, and `0x0c` through `0x0f` copy internal
fields at `+0x44`, `+0x46`, `+0x48`, and `+0x4c` respectively. Prefix `0x00`
through `0x03` is the calculated checksum word and bytes `0x10` onward remain
`ff` in the 32-byte manager serializer. The individual fields still have no
verified user-facing names. The manager-side bit gate is not applied while
parsing captured firmware prefixes because the live device can retain
non-`ff` optional fields with copied flag byte `0xfd`. See
`analysis/phase-7-view-wrapper.md` and `src/infocarry/view_wrapper.py`.
