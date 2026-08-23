# Phase 7 — `VICMEM.bin` format reconstruction

This note records an offline reconstruction from the preserved
`legacy/extracted/program files/Sony/infoCarry/infoCarry Manager/VicTwo.dll`.
No device command, file write, or modified legacy package was used.

## Evidence and path

The DLL's data section contains these related values:

| Address | Value |
| --- | --- |
| `0x100151a0` | `VICMEMOBIN\0\0` (ten-byte signature plus NUL padding) |
| `0x100151ac` | `\\VICMEM.bin\0` |
| `0x100151b8` | `\\Sony\\infoCarry\\Memo\0` |
| `0x10015170..0x1001517c` | section mask values `1, 2, 4, 8` |

The writer at `0x10002180` creates the memo directory path, opens
`VICMEM.bin`, and writes a 20-byte header. The loader at `0x10002430` reads
the same header, compares its first ten bytes with `VICMEMOBIN`, and accepts
only little-endian version `1`.

## Recovered byte layout

All integer fields are little-endian, matching the `fwrite`/`fread` calls in
the DLL.

| Offset | Size | Meaning |
| ---: | ---: | --- |
| `0x00` | 10 | ASCII `VICMEMOBIN` |
| `0x0a` | 2 | reserved bytes copied from the signature buffer |
| `0x0c` | 4 | version; the loader requires `1` |
| `0x10` | 4 | section mask |

The low five mask bits select serialized sections:

| Bit | Section | On-disk body when selected |
| ---: | --- | --- |
| 0 | category 0 | `u32 count`, 4-byte auxiliary value, then `count * 0x104` bytes |
| 1 | category 1 | same |
| 2 | category 2 | same |
| 3 | category 3 | same |
| 4 | tail | `u32 count`, then `count * 0x10c` bytes |

The writer computes bits 0–3 from nonzero category counts and bit 4 from a
nonzero tail count. The loader iterates four category slots and then reads
the tail slot. A selected section with count zero is structurally valid and is
preserved by the modern parser even though the legacy writer normally omits
it.

## Record and capacity evidence

Each category record is exactly `0x104` (260) bytes. The legacy category
append routine copies 65 dwords into this shape. The manager allocates
`0x1450` bytes for each category, which is room for 20 records. The tail
buffer at `0x100192a0` is zeroed for `0x218` bytes, which is room for two
`0x10c` (268)-byte records. The original loader does not check counts before
reading into these fixed allocations; the modern parser rejects larger counts
as a safety measure.

The category append helper accepts logical category values 1–15 and maps them
to the four mask values in the data table. Logical value 16 appends to the
tail buffer. The category index order is now statically correlated with the
fixed state responses: index 0 is display history (`0x001b`), followed by
mark lists 1–3 (`0x001c`–`0x001e`). Individual category-record fields remain
unknown.

## Auxiliary four-byte value

For each selected category the writer emits a four-byte value immediately
after the count. The loader reads that value into the allocation at offset
`+4`, then bulk-reads records starting at the allocation base. Thus a
non-empty category's first record overwrites that temporary slot. The value is
preserved byte-for-byte by the modern parser, but no semantic name is assigned
until a produced legacy sample or a controlled offline fixture identifies it.

The caller builds the four values from adjacent internal 16-bit fields before
calling the writer, so the legacy routine's final 4-byte read overlaps the
caller scratch area. This is another reason to retain the raw value rather
than infer a modern meaning.

## Recovered record fields

The append helper at `0x10002360` establishes the record sizes. More
importantly, every preserved caller is now traced:

- `0x10005940` and the first half of `0x10005ac0` copy a NUL-terminated path
  into scratch offset zero, then pass that scratch buffer to the category
  append helper;
- `0x10005a20` and the second half of `0x10005ac0` do the same for logical
  category 16, then place two native dwords at scratch offsets `0x104` and
  `0x108` before appending the `0x10c`-byte record;
- the consumer at `0x10002630` compares category record offset zero directly
  with a constructed internal memo path. For tail records it makes the same
  comparison against the first `0x104` bytes and reads the dwords at `0x104`
  and `0x108`.

This proves the following partial record layouts:

| Record | Offset | Size | Meaning |
| --- | ---: | ---: | --- |
| category | `0x000` | `0x104` | NUL-terminated relative path storage |
| tail | `0x000` | `0x104` | NUL-terminated relative path storage |
| tail | `0x104` | 4 | command `0x001f` bookmark-group dword 3; meaning unresolved |
| tail | `0x108` | 4 | command `0x001f` bookmark-group dword 4; rendered-line position |

Function `0x10005870` parses the two five-dword command `0x001f` bookmark
groups. `0x10005a20` receives those exact structures and copies their offsets
`+0x08` and `+0x0c` into the two tail fields. The controlled bookmark
experiment independently showed that group dword 4 changes from 0 to 20 to 40
as Bookmark 2 advances by rendered pages. This identifies tail offset `0x108`
without assigning a meaning to offset `0x104`.

The callers copy only through the terminating NUL and do not clear the rest of
the 260-byte scratch path area. Consequently, bytes after the first NUL may be
indeterminate legacy scratch data. They must be preserved, not normalized.

The manager's in-memory memo object is a separate `0x16c`-byte allocation
initialized by `0x100033a0`. It contains a path-like NUL-terminated buffer at
internal offset `+0x51` (capacity `0x104`), plus link/count fields near
`+0x158` through `+0x168`. Consumers at `0x10003dc0`, `0x10003f30`, and
`0x10004420` use that internal path buffer when traversing memo entries. This
separate object explains where the constructed paths originate, but its
offset `+0x51` is not serialized into `VICMEM.bin`; callers copy the selected
path to record offset zero first.

## Modern implementation

`src/infocarry/vicmem.py` provides:

- strict signature/version and bounds validation;
- lossless `VicMemHeader`, `VicMemSection`, `VicMemTail`, and `VicMemFile`
  models;
- fixed-size record preservation plus read-only views of the recovered path
  field and two tail dwords;
- deterministic `build_vicmem` and exact `parse_vicmem(...).to_bytes()`
  round-trips;
- conservative capacity checks derived from the legacy allocations.

No produced `VICMEM.bin` is part of the preserved package or prior offline
transfer outputs. The first user-provided fixture is now documented in
`analysis/phase-7-fixture-inventory.md`; it confirms section mask `0x19`,
category-0/category-3 counts and auxiliary bytes, and two zero-valued tail
records. Tests still use synthetic fixtures built from the recovered writer
and consumer layouts, and tail field 3 plus auxiliary values remain
semantically unresolved. The category-to-command index correlation is
recorded in `analysis/phase-7-vicmem-category-mapping.md`.
